"""Google Air Quality + Pollen data coordinator."""
from __future__ import annotations

import asyncio
import logging
import math
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

import aiohttp

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    BASE_URL,
    CURRENT_EXTRA_COMPUTATIONS_BASE,
    DEFAULT_FORECAST_DAYS,
    DEFAULT_HEALTH_RECS,
    DEFAULT_LANGUAGE,
    DEFAULT_LOCAL_AQI,
    DEFAULT_LOCAL_AQI_CODE,
    DEFAULT_PLANT_DESCRIPTIONS,
    DEFAULT_PLANT_SENSORS,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    EPA_BREAKPOINTS,
    FORECAST_EXTRA_COMPUTATIONS,
    GAS_MW,
    MOLAR_VOL,
    POLLEN_API_URL,
)

_LOGGER = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Unit helpers
# ---------------------------------------------------------------------------

def _parse_units(units_raw: str) -> str:
    if "BILLION" in units_raw:
        return "ppb"
    if "CUBIC" in units_raw:
        return "μg/m³"
    return units_raw


def _to_canonical(value: float, from_units: str, target_units: str, code: str) -> float:
    """Convert concentration to EPA canonical units for breakpoint comparison."""
    def _n(s: str) -> str:
        return s.replace("\u00b5", "\u03bc")

    f, t = _n(from_units), _n(target_units)
    if f == t:
        return value
    mw = GAS_MW.get(code)
    if mw is None:
        return value
    ugm3 = "\u03bcg/m\u00b3"
    if f == ugm3:
        val_ppb = value * (MOLAR_VOL / mw)
    elif f == "ppb":
        val_ppb = value
    elif f == "ppm":
        val_ppb = value * 1000.0
    else:
        return value
    if t == "ppb":
        return val_ppb
    if t == "ppm":
        return val_ppb / 1000.0
    if t == ugm3:
        return val_ppb * (mw / MOLAR_VOL)
    return value


def _epa_category(code: str, value: float | None, units: str) -> str | None:
    """Return EPA AQI health category for a pollutant concentration."""
    if value is None:
        return None
    entry = EPA_BREAKPOINTS.get(code)
    if entry is None:
        return None
    target_units, breakpoints = entry
    converted = _to_canonical(value, units, target_units, code)
    for upper, category in breakpoints:
        if converted <= upper:
            return category
    return "Hazardous"


# ---------------------------------------------------------------------------
# Pollen color / RGB helpers
# ---------------------------------------------------------------------------

def _normalize_channel(v: Any) -> int | None:
    try:
        f = float(v)
    except (TypeError, ValueError, OverflowError):
        return None
    if not math.isfinite(f):
        return None
    if 0.0 <= f <= 1.0:
        f *= 255.0
    return max(0, min(255, int(round(f))))


def _rgb_from_api(color: dict[str, Any] | None) -> tuple[int, int, int] | None:
    if not isinstance(color, dict) or not color:
        return None
    r = _normalize_channel(color.get("red"))
    g = _normalize_channel(color.get("green"))
    b = _normalize_channel(color.get("blue"))
    if r is None and g is None and b is None:
        return None
    return (r or 0, g or 0, b or 0)


def _rgb_to_hex(rgb: tuple[int, int, int] | None) -> str | None:
    if rgb is None:
        return None
    return f"#{rgb[0]:02X}{rgb[1]:02X}{rgb[2]:02X}"


def _day_to_datetime(date_obj: dict) -> str | None:
    """Convert pollen API date dict {year, month, day} to ISO 8601 noon UTC string."""
    if not all(k in date_obj for k in ("year", "month", "day")):
        return None
    y, m, d = date_obj["year"], date_obj["month"], date_obj["day"]
    return f"{y:04d}-{m:02d}-{d:02d}T12:00:00+00:00"


# ---------------------------------------------------------------------------
# Coordinator
# ---------------------------------------------------------------------------

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
        include_health_recs: bool = DEFAULT_HEALTH_RECS,
        include_plant_sensors: bool = DEFAULT_PLANT_SENSORS,
        include_plant_descriptions: bool = DEFAULT_PLANT_DESCRIPTIONS,
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
        self.entry_id = entry_id
        self._session_start: datetime = datetime.now(timezone.utc)
        self._aq_current_calls: int = 0
        self._aq_forecast_calls: int = 0
        self._pollen_calls: int = 0
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=update_interval_minutes),
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch current conditions, forecast, and pollen in parallel."""
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
            return await resp.json()

    def _build_data(self, current: dict, forecast_hours: list[dict]) -> dict[str, Any]:
        """Structure AQ API responses into sensor data."""
        new_data: dict[str, Any] = {}

        indexes = current.get("indexes", [])
        uaqi = next((i for i in indexes if i.get("code") == "uaqi"), None)
        if uaqi is None and indexes:
            uaqi = indexes[0]

        dominant_code = (uaqi.get("dominantPollutant") if uaqi else None) or ""
        aqi_forecast, local_aqi_forecast = self._build_aqi_daily_forecast(forecast_hours)

        health_recs = current.get("healthRecommendations") if self.include_health_recs else None

        new_data["aqi"] = {
            "value": uaqi.get("aqi") if uaqi else None,
            "display": uaqi.get("aqiDisplay") if uaqi else None,
            "category": uaqi.get("category") if uaqi else None,
            "dominant_pollutant": dominant_code or None,
            "region_code": current.get("regionCode"),
            "datetime": current.get("dateTime"),
            "health_recommendations": health_recs,
            "forecast": aqi_forecast,
        }

        if self.enable_local_aqi:
            local_idx = next(
                (i for i in indexes if i.get("code") not in ("uaqi", None)), None
            )
            if local_idx:
                new_data["local_aqi"] = {
                    "value": local_idx.get("aqi"),
                    "display": local_idx.get("aqiDisplay"),
                    "category": local_idx.get("category"),
                    "code": local_idx.get("code"),
                    "display_name": local_idx.get("displayName"),
                    "dominant_pollutant": local_idx.get("dominantPollutant"),
                    "forecast": local_aqi_forecast,
                }

        pollutant_forecasts = self._build_pollutant_daily_forecast(forecast_hours)

        for p in current.get("pollutants", []):
            code = p.get("code", "")
            conc = p.get("concentration", {})
            units = _parse_units(conc.get("units", ""))
            info = p.get("additionalInfo", {})
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
                "forecast": pollutant_forecasts.get(code, []),
            }

        return new_data

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
    def _compute_peak(forecast: list[dict]) -> dict | None:
        peak = None
        for f in forecast:
            idx = f.get("index")
            if isinstance(idx, (int, float)):
                if peak is None or idx > peak.get("index", -1):
                    peak = f
        return peak
