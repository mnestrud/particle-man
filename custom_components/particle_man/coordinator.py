"""Google Air Quality + Pollen data coordinator."""
import asyncio
import calendar as _calendar
from collections import defaultdict
from datetime import date as _date
from datetime import datetime, timedelta, timezone
from typing import Any

import aiohttp

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    BASE_URL,
    CURRENT_EXTRA_COMPUTATIONS_BASE,
    DEFAULT_AQ_MONTHLY_LIMIT,
    DEFAULT_FORECAST_DAYS,
    DEFAULT_LANGUAGE,
    DEFAULT_LOCAL_AQI,
    DEFAULT_LOCAL_AQI_CODE,
    DEFAULT_POLLEN_MONTHLY_LIMIT,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    EPA_BREAKPOINTS,
    FORECAST_EXTRA_COMPUTATIONS,
    GAS_MW,
    MOLAR_VOL,
    POLLEN_API_URL,
)

import logging
_LOGGER = logging.getLogger(__name__)

_STORAGE_KEY = "particle_man"
_STORAGE_VERSION = 1


def _parse_units(api_units: str) -> str:
    if api_units == "PARTS_PER_BILLION":
        return "ppb"
    if api_units == "PARTS_PER_MILLION":
        return "ppm"
    return "μg/m³"


def _to_canonical(value: float, from_units: str, target_units: str, code: str) -> float:
    """Convert concentration to EPA canonical units for breakpoint comparison."""
    f = from_units.lower()
    t = target_units.lower()
    if f == t:
        return value
    mw = GAS_MW.get(code)
    if not mw:
        return value
    if f == "μg/m³":
        val_ppb = value * (MOLAR_VOL / mw)
    elif f == "ppb":
        val_ppb = value
    else:
        val_ppb = value * 1000.0
    if t == "ppb":
        return val_ppb
    if t == "ppm":
        return val_ppb / 1000.0
    return val_ppb * (mw / MOLAR_VOL)


def _epa_category(code: str, value: float | None, units: str) -> str | None:
    """Return EPA AQI health category for a pollutant concentration."""
    if value is None:
        return None
    entry = EPA_BREAKPOINTS.get(code)
    if not entry:
        return None
    target_units, breakpoints = entry
    converted = _to_canonical(value, units, target_units, code)
    for upper, category in breakpoints:
        if converted <= upper:
            return category
    return breakpoints[-1][1]


# Pollen color / RGB helpers

def _normalize_channel(val: Any) -> int:
    if isinstance(val, float):
        return round(val * 255)
    if isinstance(val, int):
        return max(0, min(255, val))
    return 0


def _rgb_from_api(color: dict[str, Any] | None) -> tuple[int, int, int] | None:
    if not isinstance(color, dict) or not color:
        return None
    r = _normalize_channel(color.get("red"))
    g = _normalize_channel(color.get("green"))
    b = _normalize_channel(color.get("blue"))
    return (r, g, b)


def _rgb_to_hex(rgb: tuple[int, int, int] | None) -> str | None:
    if rgb is None:
        return None
    return "#{:02x}{:02x}{:02x}".format(*rgb)


def _day_to_datetime(date_obj: dict) -> str | None:
    """Convert pollen API date dict {year, month, day} to ISO 8601 noon UTC string."""
    try:
        y = date_obj["year"]
        m = date_obj["month"]
        d = date_obj["day"]
        return f"{y:04d}-{m:02d}-{d:02d}T12:00:00+00:00"
    except (KeyError, TypeError):
        return None


# Coordinator

class GoogleAirQualityCoordinator(DataUpdateCoordinator):
    """Coordinator for Google Air Quality API + Google Pollen API."""

    def __init__(
        self,
        hass: HomeAssistant,
        api_key: str,
        latitude: float,
        longitude: float,
        update_interval_minutes: int = DEFAULT_UPDATE_INTERVAL,
        forecast_days: int = DEFAULT_FORECAST_DAYS,
        language_code: str = DEFAULT_LANGUAGE,
        enable_local_aqi: bool = DEFAULT_LOCAL_AQI,
        local_aqi_code: str = DEFAULT_LOCAL_AQI_CODE,
        include_health_recs: bool = False,
        include_plant_sensors: bool = True,
        include_plant_descriptions: bool = True,
        aq_monthly_limit: int = DEFAULT_AQ_MONTHLY_LIMIT,
        pollen_monthly_limit: int = DEFAULT_POLLEN_MONTHLY_LIMIT,
        entry_id: str = "",
    ) -> None:
        self.api_key = api_key
        self.latitude = latitude
        self.longitude = longitude
        self.forecast_days = max(1, min(5, forecast_days))
        self.language_code = language_code.strip() if language_code else DEFAULT_LANGUAGE
        self.enable_local_aqi = enable_local_aqi
        self.local_aqi_code = local_aqi_code
        self.include_health_recs = include_health_recs
        self.include_plant_sensors = include_plant_sensors
        self.include_plant_descriptions = include_plant_descriptions
        self.aq_monthly_limit = int(aq_monthly_limit)
        self.pollen_monthly_limit = int(pollen_monthly_limit)
        self.entry_id = entry_id
        self._session_start: datetime = datetime.now(timezone.utc)
        self._aq_current_calls: int = 0
        self._aq_forecast_calls: int = 0
        self._pollen_calls: int = 0
        self._monthly_aq_calls: int = 0
        self._monthly_pollen_calls: int = 0
        self._tracking_month: str = datetime.now(timezone.utc).strftime("%Y-%m")
        self._store: Store = Store(hass, _STORAGE_VERSION, f"{_STORAGE_KEY}.{entry_id}")
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=update_interval_minutes),
        )

    async def async_load_tracking(self) -> None:
        """Load persistent monthly API call counts from storage."""
        stored = await self._store.async_load()
        if stored:
            stored_month = stored.get("month", "")
            current_month = datetime.now(timezone.utc).strftime("%Y-%m")
            if stored_month == current_month:
                self._monthly_aq_calls = stored.get("aq_calls", 0)
                self._monthly_pollen_calls = stored.get("pollen_calls", 0)
                self._tracking_month = stored_month

    async def _save_tracking(self) -> None:
        """Persist monthly call counts to storage."""
        await self._store.async_save({
            "month": self._tracking_month,
            "aq_calls": self._monthly_aq_calls,
            "pollen_calls": self._monthly_pollen_calls,
        })

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch current conditions, forecast, and pollen in parallel."""
        # Reset monthly counters on month rollover
        current_month = datetime.now(timezone.utc).strftime("%Y-%m")
        if current_month != self._tracking_month:
            self._tracking_month = current_month
            self._monthly_aq_calls = 0
            self._monthly_pollen_calls = 0

        session = async_get_clientsession(self.hass)

        try:
            current, forecast_hours = await asyncio.gather(
                self._fetch_current(session),
                self._fetch_forecast(session),
            )
        except aiohttp.ClientResponseError as err:
            raise UpdateFailed(
                f"Google Air Quality API error {err.status}: {err.message}"
            ) from err
        except aiohttp.ClientError as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err

        data = self._build_data(current, forecast_hours)

        try:
            pollen_response = await self._fetch_pollen(session)
            pollen_data = self._build_pollen_data(pollen_response)
            data.update(pollen_data)
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("Pollen API fetch failed, keeping last data: %s", err)
            if self.data:
                for key, val in self.data.items():
                    if key.startswith("pollen_"):
                        data[key] = val

        await self._save_tracking()
        return data

    async def _fetch_current(self, session: aiohttp.ClientSession) -> dict:
        url = f"{BASE_URL}/currentConditions:lookup?key={self.api_key}"
        extra = list(CURRENT_EXTRA_COMPUTATIONS_BASE)
        if self.include_health_recs:
            extra.append("HEALTH_RECOMMENDATIONS")
        if self.enable_local_aqi:
            extra.append("LOCAL_AQI")
        body: dict[str, Any] = {
            "location": {"latitude": self.latitude, "longitude": self.longitude},
            "universalAqi": True,
            "extraComputations": extra,
        }
        if self.language_code:
            body["languageCode"] = self.language_code
        async with session.post(
            url, json=body, timeout=aiohttp.ClientTimeout(total=15)
        ) as resp:
            if not resp.ok:
                error_body = await resp.text()
                _LOGGER.error(
                    "Google AQI currentConditions error %s: %s", resp.status, error_body
                )
            resp.raise_for_status()
            self._aq_current_calls += 1
            self._monthly_aq_calls += 1
            return await resp.json()

    async def _fetch_forecast(self, session: aiohttp.ClientSession) -> list[dict]:
        url = f"{BASE_URL}/forecast:lookup?key={self.api_key}"
        next_hour = (
            datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
            + timedelta(hours=1)
        )
        end = next_hour + timedelta(hours=95)
        body: dict[str, Any] = {
            "location": {"latitude": self.latitude, "longitude": self.longitude},
            "universalAqi": True,
            "extraComputations": list(FORECAST_EXTRA_COMPUTATIONS),
            "period": {
                "startTime": next_hour.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "endTime": end.strftime("%Y-%m-%dT%H:%M:%SZ"),
            },
            "pageSize": 96,
        }
        if self.enable_local_aqi:
            body["extraComputations"] = list(FORECAST_EXTRA_COMPUTATIONS) + ["LOCAL_AQI"]
        if self.language_code:
            body["languageCode"] = self.language_code
        async with session.post(
            url, json=body, timeout=aiohttp.ClientTimeout(total=15)
        ) as resp:
            if not resp.ok:
                error_body = await resp.text()
                _LOGGER.error(
                    "Google AQI forecast error %s: %s", resp.status, error_body
                )
            resp.raise_for_status()
            self._aq_forecast_calls += 1
            self._monthly_aq_calls += 1
            result = await resp.json()
            return result.get("hourlyForecasts", [])

    async def _fetch_pollen(self, session: aiohttp.ClientSession) -> dict:
        params: dict[str, Any] = {
            "key": self.api_key,
            "location.latitude": f"{self.latitude:.6f}",
            "location.longitude": f"{self.longitude:.6f}",
            "days": self.forecast_days,
        }
        if self.language_code:
            params["languageCode"] = self.language_code
        if self.include_plant_descriptions:
            params["plantsDescription"] = "true"
        async with session.get(
            POLLEN_API_URL, params=params, timeout=aiohttp.ClientTimeout(total=15)
        ) as resp:
            if not resp.ok:
                error_body = await resp.text()
                _LOGGER.warning(
                    "Google Pollen API error %s: %s", resp.status, error_body[:300]
                )
                resp.raise_for_status()
            self._pollen_calls += 1
            self._monthly_pollen_calls += 1
            return await resp.json()

    def _build_data(self, current: dict, forecast_hours: list[dict]) -> dict[str, Any]:
        """Structure AQ API responses into sensor data."""
        new_data: dict[str, Any] = {}

        indexes = current.get("indexes", [])
        uaqi = next((i for i in indexes if i.get("code") == "uaqi"), None)
        if uaqi is None and indexes:
            uaqi = indexes[0]

        dominant_code = (uaqi.get("dominantPollutant") if uaqi else None) or ""

        aqi_daily_forecast, local_aqi_daily_forecast = self._build_aqi_daily_forecast(forecast_hours)
        aqi_hourly_forecast, local_aqi_hourly_forecast = self._build_aqi_hourly_forecast(forecast_hours)
        pollutant_daily_forecasts = self._build_pollutant_daily_forecast(forecast_hours)
        pollutant_hourly_forecasts = self._build_pollutant_hourly_forecast(forecast_hours)

        aqi_trend = self._compute_hourly_trend(
            [h["aqi"] for h in aqi_hourly_forecast if h.get("aqi") is not None]
        )

        health_recs = current.get("healthRecommendations") if self.include_health_recs else None

        new_data["aqi"] = {
            "value": uaqi.get("aqi") if uaqi else None,
            "display": uaqi.get("aqiDisplay") if uaqi else None,
            "category": uaqi.get("category") if uaqi else None,
            "dominant_pollutant": dominant_code or None,
            "region_code": current.get("regionCode"),
            "datetime": current.get("dateTime"),
            "health_recommendations": health_recs,
            "daily_forecast": aqi_daily_forecast,
            "hourly_forecast": aqi_hourly_forecast,
            "trend": aqi_trend,
        }

        if self.enable_local_aqi:
            local_idx = next(
                (i for i in indexes if i.get("code") not in ("uaqi", None)), None
            )
            if local_idx:
                local_trend = self._compute_hourly_trend(
                    [h["aqi"] for h in local_aqi_hourly_forecast if h.get("aqi") is not None]
                )
                new_data["local_aqi"] = {
                    "value": local_idx.get("aqi"),
                    "display": local_idx.get("aqiDisplay"),
                    "category": local_idx.get("category"),
                    "code": local_idx.get("code"),
                    "display_name": local_idx.get("displayName"),
                    "dominant_pollutant": local_idx.get("dominantPollutant"),
                    "daily_forecast": local_aqi_daily_forecast,
                    "hourly_forecast": local_aqi_hourly_forecast,
                    "trend": local_trend,
                }

        for p in current.get("pollutants", []):
            code = p.get("code", "")
            conc = p.get("concentration", {})
            units = _parse_units(conc.get("units", ""))
            info = p.get("additionalInfo", {})
            hourly = pollutant_hourly_forecasts.get(code, [])
            trend = self._compute_hourly_trend(
                [h["value"] for h in hourly if h.get("value") is not None]
            )
            new_data[f"pollutant_{code}"] = {
                "code": code,
                "display_name": p.get("displayName", code.upper()),
                "full_name": p.get("fullName", code.upper()),
                "value": conc.get("value"),
                "units": units,
                "epa_category": _epa_category(code, conc.get("value"), units),
                "sources": info.get("sources"),
                "effects": info.get("effects"),
                "is_dominant": code == dominant_code,
                "daily_forecast": pollutant_daily_forecasts.get(code, []),
                "hourly_forecast": hourly,
                "trend": trend,
            }

        return new_data

    def _build_aqi_hourly_forecast(
        self, hours: list[dict]
    ) -> tuple[list[dict], list[dict]]:
        """Build per-hour AQI lists for UAQI and local AQI."""
        uaqi_hourly: list[dict] = []
        local_hourly: list[dict] = []
        for h in hours:
            dt_str = h.get("dateTime", "")
            for idx in h.get("indexes", []):
                if idx.get("code") == "uaqi" and idx.get("aqi") is not None:
                    uaqi_hourly.append({
                        "datetime": dt_str,
                        "aqi": idx["aqi"],
                        "category": idx.get("category"),
                        "dominant_pollutant": idx.get("dominantPollutant"),
                    })
                elif (
                    idx.get("code") not in ("uaqi", None)
                    and idx.get("aqi") is not None
                ):
                    local_hourly.append({
                        "datetime": dt_str,
                        "aqi": idx["aqi"],
                        "category": idx.get("category"),
                    })
        return uaqi_hourly, local_hourly

    def _build_pollutant_hourly_forecast(
        self, hours: list[dict]
    ) -> dict[str, list[dict]]:
        """Build per-hour concentration lists for each pollutant."""
        result: dict[str, list[dict]] = defaultdict(list)
        for h in hours:
            dt_str = h.get("dateTime", "")
            for p in h.get("pollutants", []):
                code = p.get("code", "")
                conc = p.get("concentration", {})
                val = conc.get("value")
                units = _parse_units(conc.get("units", ""))
                if val is not None:
                    result[code].append({
                        "datetime": dt_str,
                        "value": val,
                        "units": units,
                        "epa_category": _epa_category(code, val, units),
                    })
        return dict(result)

    def _build_aqi_daily_forecast(
        self, hours: list[dict]
    ) -> tuple[list[dict], list[dict]]:
        uaqi_days: dict[str, list[dict]] = defaultdict(list)
        local_days: dict[str, list[dict]] = defaultdict(list)

        for h in hours:
            dt_str = h.get("dateTime", "")
            try:
                dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
                local_dt = dt_util.as_local(dt)
                date_key = local_dt.strftime("%Y-%m-%d")
            except (ValueError, TypeError):
                continue

            for idx in h.get("indexes", []):
                if idx.get("code") == "uaqi" and idx.get("aqi") is not None:
                    uaqi_days[date_key].append(
                        {"aqi": idx["aqi"], "category": idx.get("category")}
                    )
                elif idx.get("code") not in ("uaqi", None) and idx.get("aqi") is not None:
                    local_days[date_key].append(
                        {"aqi": idx["aqi"], "category": idx.get("category")}
                    )

        def _to_daily(days_dict: dict) -> list[dict]:
            result = []
            for date_key in sorted(days_dict.keys())[: self.forecast_days]:
                entries = days_dict[date_key]
                peak = max(entries, key=lambda x: x["aqi"])
                result.append(
                    {
                        "datetime": f"{date_key}T12:00:00+00:00",
                        "aqi": peak["aqi"],
                        "category": peak["category"],
                    }
                )
            return result

        return _to_daily(uaqi_days), _to_daily(local_days)

    def _build_pollutant_daily_forecast(
        self, hours: list[dict]
    ) -> dict[str, list[dict]]:
        days: dict[str, dict[str, list]] = defaultdict(lambda: defaultdict(list))
        for h in hours:
            dt_str = h.get("dateTime", "")
            try:
                dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
                local_dt = dt_util.as_local(dt)
                date_key = local_dt.strftime("%Y-%m-%d")
            except (ValueError, TypeError):
                continue
            for p in h.get("pollutants", []):
                code = p.get("code", "")
                conc = p.get("concentration", {})
                val = conc.get("value")
                units = _parse_units(conc.get("units", ""))
                if val is not None:
                    days[code][date_key].append({"value": val, "units": units})

        result: dict[str, list[dict]] = {}
        for code, date_dict in days.items():
            daily = []
            for date_key in sorted(date_dict.keys())[: self.forecast_days]:
                entries = date_dict[date_key]
                max_val = max(e["value"] for e in entries)
                units = entries[0]["units"]
                daily.append(
                    {
                        "datetime": f"{date_key}T12:00:00+00:00",
                        "max": round(max_val, 2),
                        "units": units,
                        "epa_category": _epa_category(code, max_val, units),
                    }
                )
            result[code] = daily
        return result

    def _build_pollen_data(self, response: dict) -> dict[str, Any]:
        """Parse Google Pollen API response into sensor data."""
        if not isinstance(response, dict):
            return {}

        daily = response.get("dailyInfo")
        if not isinstance(daily, list) or not daily:
            return {}

        result: dict[str, Any] = {}

        type_codes: set[str] = set()
        type_by_day: list[dict[str, dict]] = []
        plant_by_day: list[dict[str, dict]] = []
        plant_codes: list[str] = []

        for i, day in enumerate(daily):
            day_types: dict[str, dict] = {}
            for item in day.get("pollenTypeInfo", []) or []:
                if not isinstance(item, dict):
                    continue
                code = (item.get("code") or "").strip().upper()
                if code:
                    day_types[code] = item
                    type_codes.add(code)
            type_by_day.append(day_types)

            day_plants: dict[str, dict] = {}
            for item in day.get("plantInfo", []) or []:
                if not isinstance(item, dict):
                    continue
                code = (item.get("code") or "").strip()
                if code:
                    day_plants[code] = item
                    if i == 0:
                        plant_codes.append(code)
            plant_by_day.append(day_plants)

        for tcode in sorted(type_codes):
            today = type_by_day[0].get(tcode, {})
            idx = today.get("indexInfo") or {}
            rgb = _rgb_from_api(idx.get("color"))

            base: dict[str, Any] = {
                "value": idx.get("value"),
                "category": idx.get("category"),
                "display_name": today.get("displayName", tcode.title()),
                "in_season": today.get("inSeason"),
                "color_hex": _rgb_to_hex(rgb) or None,
                "health_recommendations": (
                    today.get("healthRecommendations") if self.include_health_recs else None
                ),
            }

            forecast = self._build_pollen_forecast(daily, type_by_day, tcode, kind="type")
            base["forecast"] = forecast
            base["trend"] = self._compute_trend(base["value"], forecast)
            base["expected_peak"] = self._compute_peak(forecast)

            result[f"pollen_type_{tcode.lower()}"] = base

        if self.include_plant_sensors:
            for pcode in plant_codes:
                today_p = plant_by_day[0].get(pcode, {})
                pidx = today_p.get("indexInfo") or {}
                prgb = _rgb_from_api(pidx.get("color"))
                desc = (
                    (today_p.get("plantDescription") or {})
                    if self.include_plant_descriptions
                    else {}
                )

                pbase: dict[str, Any] = {
                    "value": pidx.get("value"),
                    "category": pidx.get("category"),
                    "display_name": today_p.get("displayName", pcode),
                    "in_season": today_p.get("inSeason"),
                    "color_hex": _rgb_to_hex(prgb) or None,
                    "family": desc.get("family"),
                    "genus": desc.get("genus"),
                    "season": desc.get("seasonality"),
                    "cross_reaction": desc.get("crossReaction"),
                    "picture": desc.get("imageUrl"),
                }

                forecast = self._build_pollen_forecast(daily, plant_by_day, pcode, kind="plant")
                pbase["forecast"] = forecast
                pbase["trend"] = self._compute_trend(pbase["value"], forecast)
                pbase["expected_peak"] = self._compute_peak(forecast)

                result[f"pollen_plant_{pcode.lower()}"] = pbase

        return result

    def _build_pollen_forecast(
        self,
        daily: list[dict],
        by_day: list[dict[str, dict]],
        code: str,
        kind: str,
    ) -> list[dict]:
        forecast = []
        for i, day in enumerate(daily[1:], start=1):
            date_obj = day.get("date") or {}
            dt_str = _day_to_datetime(date_obj)
            if dt_str is None:
                continue
            item = by_day[i].get(code, {}) if i < len(by_day) else {}
            fidx = (item.get("indexInfo") or {}) if item else {}
            frgb = _rgb_from_api(fidx.get("color")) if fidx else None
            forecast.append(
                {
                    "datetime": dt_str,
                    "index": fidx.get("value"),
                    "category": fidx.get("category"),
                    "color_hex": _rgb_to_hex(frgb),
                }
            )
        return forecast

    @staticmethod
    def _compute_trend(current_val: Any, forecast: list[dict]) -> str | None:
        """Pollen trend: compare today vs tomorrow (up/down/flat)."""
        if not isinstance(current_val, (int, float)) or not forecast:
            return None
        tomorrow = forecast[0].get("index")
        if not isinstance(tomorrow, (int, float)):
            return None
        if tomorrow > current_val:
            return "up"
        if tomorrow < current_val:
            return "down"
        return "flat"

    @staticmethod
    def _compute_hourly_trend(values: list[float]) -> str:
        """AQI/pollutant trend: linear slope across hourly forecast values."""
        clean = [v for v in values if isinstance(v, (int, float))]
        if len(clean) < 3:
            return "stable"
        n = len(clean)
        x_mean = (n - 1) / 2.0
        y_mean = sum(clean) / n
        numerator = sum((i - x_mean) * (v - y_mean) for i, v in enumerate(clean))
        denominator = sum((i - x_mean) ** 2 for i in range(n))
        if denominator == 0:
            return "stable"
        slope = numerator / denominator
        relative_slope = slope / abs(y_mean) if y_mean != 0 else slope
        if relative_slope > 0.02:
            return "rising"
        if relative_slope < -0.02:
            return "falling"
        return "stable"

    @staticmethod
    def _compute_peak(forecast: list[dict]) -> dict | None:
        peak = None
        for f in forecast:
            idx = f.get("index")
            if isinstance(idx, (int, float)):
                if peak is None or idx > peak.get("index", -1):
                    peak = f
        return peak
