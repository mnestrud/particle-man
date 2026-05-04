"""Particle Man data coordinator."""
from __future__ import annotations

import asyncio
import hashlib
import re
from collections import defaultdict
from datetime import datetime, time as _time, timedelta, timezone
from typing import Any, cast

import aiohttp

from homeassistant.helpers.issue_registry import (
    IssueSeverity,
    async_create_issue,
    async_delete_issue,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    BASE_URL,
    CONDITION_MAP,
    CURRENT_EXTRA_COMPUTATIONS_BASE,
    DEFAULT_AQ_MONTHLY_LIMIT,
    DEFAULT_ENABLE_AIR_QUALITY,
    DEFAULT_ENABLE_POLLEN,
    DEFAULT_ENABLE_WEATHER,
    DEFAULT_ENABLE_WEATHER_ALERTS,
    DEFAULT_AUTOMAGIC_MODE,
    DEFAULT_FORECAST_DAYS,
    DEFAULT_LANGUAGE,
    DEFAULT_LOCAL_AQI,
    DEFAULT_LOCAL_AQI_CODE,
    DEFAULT_POLLEN_MONTHLY_LIMIT,
    DEFAULT_QUIET_END,
    DEFAULT_QUIET_HOURS_ENABLED,
    DEFAULT_QUIET_START,
    DEFAULT_UPDATE_INTERVAL,
    DEFAULT_WEATHER_MONTHLY_LIMIT,
    DEFAULT_WEATHER_UNITS,
    DOMAIN,
    EPA_BREAKPOINTS,
    FORECAST_EXTRA_COMPUTATIONS,
    GAS_MW,
    MOLAR_VOL,
    POLLEN_API_URL,
    WEATHER_API_URL,
    _PACIFIC_TZ,
    _WEATHER_CALLS_PER_POLL,
)

import logging
_LOGGER = logging.getLogger(__name__)

_STORAGE_VERSION = 1
_STORAGE_KEY = "particle_man"

# Google AQ data refreshes every hour; pollen models update daily but we match AQ cadence.
_AQ_FETCH_INTERVAL = timedelta(hours=1)
_POLLEN_FETCH_INTERVAL = timedelta(hours=1)


class ParticleManGlobalState:
    """Shared state across all location coordinators for the same config entry."""

    def __init__(self) -> None:
        self._quiet_hours_runtime_override: bool | None = None

    def set_quiet_hours_runtime(self, enabled: bool | None) -> None:
        """Override quiet hours at runtime. Pass None to revert to config default."""
        self._quiet_hours_runtime_override = enabled

    def quiet_hours_active(self, config_enabled: bool) -> bool:
        """Return effective quiet-hours enabled state (runtime override or config default)."""
        if self._quiet_hours_runtime_override is not None:
            return self._quiet_hours_runtime_override
        return config_enabled


_POLLEN_LEVEL_ORDER = ["None", "Very Low", "Low", "Moderate", "High", "Very High"]


def _empty_shared_tracking() -> dict[str, Any]:
    return {"period_month": "", "aq_calls": 0, "pollen_calls": 0, "weather_calls": 0}


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


def _day_to_datetime(date_obj: dict[str, Any]) -> str | None:
    """Convert pollen API date dict {year, month, day} to ISO 8601 noon UTC string."""
    try:
        y = date_obj["year"]
        m = date_obj["month"]
        d = date_obj["day"]
        return f"{y:04d}-{m:02d}-{d:02d}T12:00:00+00:00"
    except (KeyError, TypeError):
        return None


def _w_degrees(obj: Any) -> float | None:
    if isinstance(obj, dict):
        return obj.get("degrees")
    return None


def _w_condition(cond_obj: Any, is_daytime: bool) -> str | None:
    cond_type = (cond_obj or {}).get("type", "") if isinstance(cond_obj, dict) else ""
    if not cond_type:
        return None
    if cond_type == "CLEAR":
        return "sunny" if is_daytime else "clear-night"
    return CONDITION_MAP.get(cond_type, "exceptional")


class ParticleManCoordinator(DataUpdateCoordinator):
    """Coordinator for Particle Man — fetches air quality, pollen, and weather data."""

    def __init__(
        self,
        hass: HomeAssistant,
        api_key: str,
        latitude: float,
        longitude: float,
        location_name: str = "Location",
        global_state: ParticleManGlobalState | None = None,
        automagic_mode: bool = DEFAULT_AUTOMAGIC_MODE,
        num_locations: int = 1,
        update_interval_minutes: int = DEFAULT_UPDATE_INTERVAL,
        forecast_days: int = DEFAULT_FORECAST_DAYS,
        language_code: str = DEFAULT_LANGUAGE,
        enable_local_aqi: bool = DEFAULT_LOCAL_AQI,
        local_aqi_code: str = DEFAULT_LOCAL_AQI_CODE,
        aq_monthly_limit: int = DEFAULT_AQ_MONTHLY_LIMIT,
        pollen_monthly_limit: int = DEFAULT_POLLEN_MONTHLY_LIMIT,
        weather_monthly_limit: int = DEFAULT_WEATHER_MONTHLY_LIMIT,
        enable_air_quality: bool = DEFAULT_ENABLE_AIR_QUALITY,
        enable_pollen: bool = DEFAULT_ENABLE_POLLEN,
        enable_weather: bool = DEFAULT_ENABLE_WEATHER,
        enable_weather_alerts: bool = DEFAULT_ENABLE_WEATHER_ALERTS,
        weather_units: str = DEFAULT_WEATHER_UNITS,
        quiet_hours_enabled: bool = DEFAULT_QUIET_HOURS_ENABLED,
        quiet_start: str = DEFAULT_QUIET_START,
        quiet_end: str = DEFAULT_QUIET_END,
        aq_fetch_interval: timedelta = _AQ_FETCH_INTERVAL,
        pollen_fetch_interval: timedelta = _POLLEN_FETCH_INTERVAL,
        weather_calls_per_poll: int = _WEATHER_CALLS_PER_POLL,
        entry_id: str = "",
        config_entry: Any = None,
    ) -> None:
        self.api_key = api_key
        self.latitude = latitude
        self.longitude = longitude
        self.location_name = location_name
        self.location_slug = re.sub(r"[^a-z0-9]+", "_", location_name.lower()).strip("_") or "location"
        self._global_state = global_state
        self.automagic_mode = automagic_mode
        self.num_locations = num_locations
        self.forecast_days = max(1, min(5, forecast_days))
        self.language_code = language_code.strip() if language_code else DEFAULT_LANGUAGE
        self.enable_local_aqi = enable_local_aqi
        self.local_aqi_code = local_aqi_code
        self.include_health_recs = True
        self.include_plant_descriptions = True
        self.aq_monthly_limit = int(aq_monthly_limit)
        self.pollen_monthly_limit = int(pollen_monthly_limit)
        self.weather_monthly_limit = int(weather_monthly_limit)
        self.enable_air_quality = enable_air_quality
        self.enable_pollen = enable_pollen
        self.enable_weather = enable_weather
        self.enable_weather_alerts = enable_weather_alerts
        self.weather_units = weather_units
        self._quiet_hours_enabled = quiet_hours_enabled
        self._quiet_start = quiet_start
        self._quiet_end = quiet_end
        self._aq_fetch_interval = aq_fetch_interval
        self._pollen_fetch_interval = pollen_fetch_interval
        self.weather_calls_per_poll = weather_calls_per_poll
        self.entry_id = entry_id

        key_hash = hashlib.md5(api_key.encode()).hexdigest()[:12]
        self._key_hash = key_hash
        self._shared_store: Store[dict[str, Any]] = Store(
            hass, _STORAGE_VERSION, f"{_STORAGE_KEY}.shared.{key_hash}"
        )
        shared_state = hass.data.setdefault(DOMAIN, {})
        self._shared_lock: asyncio.Lock = (
            shared_state.setdefault("locks", {}).setdefault(key_hash, asyncio.Lock())
        )
        self._cached_tracking: dict[str, Any] = _empty_shared_tracking()
        self._api_backoff: dict[str, Any] = {}
        self._api_failures: dict[str, int] = {}
        self._api_unavailable_logged: set[str] = set()
        self._last_aq_fetch: datetime | None = None
        self._last_pollen_fetch: datetime | None = None

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{self.location_slug}",
            update_interval=timedelta(minutes=update_interval_minutes),
            config_entry=config_entry,
            always_update=False,
        )

    def _current_billing_month(self) -> str:
        return datetime.now(_PACIFIC_TZ).strftime("%Y-%m")

    def _effective_quiet_hours_enabled(self) -> bool:
        if self._global_state is not None:
            return self._global_state.quiet_hours_active(self._quiet_hours_enabled)
        return self._quiet_hours_enabled

    def _is_quiet_hours(self) -> bool:
        if not self._effective_quiet_hours_enabled():
            return False
        now = datetime.now().time()
        try:
            start = _time.fromisoformat(self._quiet_start)
            end = _time.fromisoformat(self._quiet_end)
        except (ValueError, TypeError):
            return False
        if start > end:  # spans midnight (e.g. 23:00–05:00)
            return now >= start or now < end
        return start <= now < end

    def _is_backed_off(self, api: str) -> bool:
        until = self._api_backoff.get(api)
        if until is None:
            return False
        if datetime.now(timezone.utc) < until:
            return True
        del self._api_backoff[api]
        return False

    def _record_api_error(self, api: str, status: int | None = None) -> None:
        if status in (401, 403):
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="auth_failed",
            )
        failures = self._api_failures.get(api, 0) + 1
        self._api_failures[api] = failures
        now = datetime.now(timezone.utc)
        if status == 429:
            hours = min(8, 2 ** (failures - 1))
            self._api_backoff[api] = now + timedelta(hours=hours)
            if api not in self._api_unavailable_logged:
                self._api_unavailable_logged.add(api)
                _LOGGER.warning(
                    "Particle Man %s API rate-limited (429). Backing off %dh.", api.upper(), hours
                )
        elif status is not None and 500 <= status < 600:
            if failures == 1:
                self._api_unavailable_logged.add(api)
                _LOGGER.warning(
                    "Particle Man %s API server error %s — will retry.", api.upper(), status
                )
            elif failures >= 3:
                hours = min(8, 2 ** (failures - 2))
                self._api_backoff[api] = now + timedelta(hours=hours)
                _LOGGER.debug(
                    "Particle Man %s API persistent errors. Backing off %dh.", api.upper(), hours
                )
        else:
            if failures == 1:
                self._api_unavailable_logged.add(api)
                _LOGGER.warning("Particle Man %s fetch failed — will retry.", api.upper())
            else:
                _LOGGER.debug(
                    "Particle Man %s fetch still failing (failure %d).", api.upper(), failures
                )

    def _clear_api_error(self, api: str) -> None:
        if api in self._api_unavailable_logged:
            self._api_unavailable_logged.discard(api)
            _LOGGER.warning("Particle Man %s API recovered.", api.upper())
        self._api_failures.pop(api, None)
        self._api_backoff.pop(api, None)

    async def _async_setup(self) -> None:
        """Load persistent API call counts from shared storage."""
        async with self._shared_lock:
            stored = await self._shared_store.async_load()
            current_month = self._current_billing_month()
            if stored and stored.get("period_month") == current_month:
                self._cached_tracking = dict(stored)
            else:
                self._cached_tracking = _empty_shared_tracking()
                self._cached_tracking["period_month"] = current_month
                await self._shared_store.async_save(self._cached_tracking)

    async def _save_tracking(
        self, aq_inc: int = 0, pollen_inc: int = 0, weather_inc: int = 0
    ) -> None:
        """Persist API call counts to shared storage."""
        async with self._shared_lock:
            stored = await self._shared_store.async_load() or _empty_shared_tracking()
            current_month = self._current_billing_month()
            if stored.get("period_month") != current_month:
                stored = _empty_shared_tracking()
                stored["period_month"] = current_month
            stored["aq_calls"] = stored.get("aq_calls", 0) + aq_inc
            stored["pollen_calls"] = stored.get("pollen_calls", 0) + pollen_inc
            stored["weather_calls"] = stored.get("weather_calls", 0) + weather_inc
            self._cached_tracking = dict(stored)
            await self._shared_store.async_save(stored)

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from enabled APIs, respecting quiet hours and monthly limits."""
        if self._is_quiet_hours():
            _LOGGER.debug("Particle Man [%s]: quiet hours active, skipping update", self.location_name)
            await self._save_tracking(aq_inc=0, pollen_inc=0, weather_inc=0)
            return self.data or {}

        # Roll over month counter if needed
        current_month = self._current_billing_month()
        if self._cached_tracking.get("period_month") != current_month:
            async with self._shared_lock:
                new_tracking = _empty_shared_tracking()
                new_tracking["period_month"] = current_month
                self._cached_tracking = new_tracking
                await self._shared_store.async_save(new_tracking)
            for api in ("aq", "pollen", "weather"):
                async_delete_issue(self.hass, DOMAIN, f"{api}_quota_{self.entry_id}")

        now = dt_util.utcnow()
        data = dict(self.data) if self.data else {}
        session = async_get_clientsession(self.hass)
        aq_inc = 0
        pollen_inc = 0
        weather_inc = 0

        # --- Air Quality (fetched at most once per hour — Google updates hourly) ---
        if self.enable_air_quality:
            aq_due = self._last_aq_fetch is None or (now - self._last_aq_fetch) >= self._aq_fetch_interval
            if not aq_due:
                _LOGGER.debug(
                    "Particle Man [%s]: AQ not due yet (last: %s), skipping",
                    self.location_name, self._last_aq_fetch,
                )
            else:
                aq_blocked = (
                    self.automagic_mode
                    and self.aq_monthly_limit > 0
                    and self._cached_tracking.get("aq_calls", 0) >= self.aq_monthly_limit
                )
                if aq_blocked:
                    async_create_issue(
                        self.hass, DOMAIN, f"aq_quota_{self.entry_id}",
                        is_fixable=False, severity=IssueSeverity.WARNING,
                        translation_key="api_quota_exhausted",
                        translation_placeholders={"api_name": "Air Quality"},
                    )
                    _LOGGER.debug(
                        "AQ monthly limit reached (%d/%d), skipping",
                        self._cached_tracking.get("aq_calls", 0),
                        self.aq_monthly_limit,
                    )
                elif self._is_backed_off("aq"):
                    _LOGGER.debug("AQ API backed off until %s, skipping", self._api_backoff.get("aq"))
                else:
                    try:
                        current, forecast_hours = await asyncio.gather(
                            self._fetch_current(session),
                            self._fetch_forecast(session),
                        )
                        aq_data = self._build_data(current, forecast_hours)
                        data.update(aq_data)
                        aq_inc += 2
                        self._last_aq_fetch = now
                        self._clear_api_error("aq")
                    except aiohttp.ClientResponseError as err:
                        self._record_api_error("aq", err.status)
                    except Exception as err:  # noqa: BLE001
                        self._record_api_error("aq")
                        _LOGGER.debug("Air Quality fetch exception: %s", err)

        # --- Weather ---
        if self.enable_weather:
            weather_blocked = (
                self.automagic_mode
                and self.weather_monthly_limit > 0
                and self._cached_tracking.get("weather_calls", 0) >= self.weather_monthly_limit
            )
            if weather_blocked:
                async_create_issue(
                    self.hass, DOMAIN, f"weather_quota_{self.entry_id}",
                    is_fixable=False, severity=IssueSeverity.WARNING,
                    translation_key="api_quota_exhausted",
                    translation_placeholders={"api_name": "Weather"},
                )
                _LOGGER.debug(
                    "Weather monthly limit reached (%d/%d), skipping",
                    self._cached_tracking.get("weather_calls", 0),
                    self.weather_monthly_limit,
                )
            elif self._is_backed_off("weather"):
                _LOGGER.debug("Weather API backed off until %s, skipping", self._api_backoff.get("weather"))
            else:
                try:
                    weather_tasks: list[Any] = [
                        self._fetch_weather_current(session),
                        self._fetch_weather_hourly(session),
                        self._fetch_weather_daily(session),
                    ]
                    if self.enable_weather_alerts:
                        weather_tasks.append(self._fetch_weather_alerts(session))

                    results = await asyncio.gather(*weather_tasks, return_exceptions=True)

                    w_current: dict[str, Any] = results[0] if not isinstance(results[0], Exception) else {}  # type: ignore[assignment]
                    w_hourly: dict[str, Any] = results[1] if not isinstance(results[1], Exception) else {}  # type: ignore[assignment]
                    w_daily: dict[str, Any] = results[2] if not isinstance(results[2], Exception) else {}  # type: ignore[assignment]
                    w_alerts: dict[str, Any] | None = None
                    if self.enable_weather_alerts and len(results) > 3:
                        w_alerts = results[3] if not isinstance(results[3], Exception) else {}  # type: ignore[assignment]

                    any_failed = False
                    for i, res in enumerate(results):
                        if isinstance(res, Exception):
                            any_failed = True
                            _LOGGER.debug("Weather fetch task %d failed: %s", i, res)
                        else:
                            weather_inc += 1

                    weather_data = self._build_weather_data(w_current, w_hourly, w_daily, w_alerts)
                    data.update(weather_data)
                    if not any_failed:
                        self._clear_api_error("weather")
                except aiohttp.ClientResponseError as err:
                    self._record_api_error("weather", err.status)
                except Exception as err:  # noqa: BLE001
                    self._record_api_error("weather")
                    _LOGGER.debug("Weather fetch exception: %s", err)

        # --- Pollen (fetched at most once per hour — Google updates pollen models daily,
        #     but we match the AQ cadence to keep sensor freshness consistent) ---
        if self.enable_pollen:
            pollen_due = self._last_pollen_fetch is None or (now - self._last_pollen_fetch) >= self._pollen_fetch_interval
            if not pollen_due:
                _LOGGER.debug(
                    "Particle Man [%s]: Pollen not due yet (last: %s), skipping",
                    self.location_name, self._last_pollen_fetch,
                )
            else:
                pollen_blocked = (
                    self.automagic_mode
                    and self.pollen_monthly_limit > 0
                    and self._cached_tracking.get("pollen_calls", 0) >= self.pollen_monthly_limit
                )
                if pollen_blocked:
                    async_create_issue(
                        self.hass, DOMAIN, f"pollen_quota_{self.entry_id}",
                        is_fixable=False, severity=IssueSeverity.WARNING,
                        translation_key="api_quota_exhausted",
                        translation_placeholders={"api_name": "Pollen"},
                    )
                    _LOGGER.debug(
                        "Pollen monthly limit reached (%d/%d), skipping",
                        self._cached_tracking.get("pollen_calls", 0),
                        self.pollen_monthly_limit,
                    )
                elif self._is_backed_off("pollen"):
                    _LOGGER.debug("Pollen API backed off until %s, skipping", self._api_backoff.get("pollen"))
                else:
                    try:
                        pollen_response = await self._fetch_pollen(session)
                        pollen_data = self._build_pollen_data(pollen_response)
                        data.update(pollen_data)
                        pollen_inc += 1
                        self._last_pollen_fetch = now
                        self._clear_api_error("pollen")
                    except aiohttp.ClientResponseError as err:
                        self._record_api_error("pollen", err.status)
                        if self.data:
                            for key, val in self.data.items():
                                if key.startswith("pollen_"):
                                    data.setdefault(key, val)
                    except Exception as err:  # noqa: BLE001
                        self._record_api_error("pollen")
                        _LOGGER.debug("Pollen fetch exception: %s", err)
                        if self.data:
                            for key, val in self.data.items():
                                if key.startswith("pollen_"):
                                    data.setdefault(key, val)

        await self._save_tracking(
            aq_inc=aq_inc, pollen_inc=pollen_inc, weather_inc=weather_inc
        )

        if not data and not self.data:
            raise UpdateFailed(translation_domain=DOMAIN, translation_key="no_data_available")

        return data

    # -------------------------------------------------------------------------
    # Air Quality fetch
    # -------------------------------------------------------------------------

    async def _fetch_current(self, session: aiohttp.ClientSession) -> dict[str, Any]:
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
            if resp.status >= 400:
                error_body = await resp.text()
                _LOGGER.error(
                    "Google AQI currentConditions error %s: %s", resp.status, error_body
                )
            resp.raise_for_status()
            return cast(dict[str, Any], await resp.json())

    async def _fetch_forecast(self, session: aiohttp.ClientSession) -> list[dict[str, Any]]:
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
            if resp.status >= 400:
                error_body = await resp.text()
                _LOGGER.error(
                    "Google AQI forecast error %s: %s", resp.status, error_body
                )
            resp.raise_for_status()
            result: dict[str, Any] = cast(dict[str, Any], await resp.json())
            return cast(list[dict[str, Any]], result.get("hourlyForecasts", []))

    # -------------------------------------------------------------------------
    # Pollen fetch
    # -------------------------------------------------------------------------

    async def _fetch_pollen(self, session: aiohttp.ClientSession) -> dict[str, Any]:
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
            if resp.status >= 400:
                error_body = await resp.text()
                _LOGGER.warning(
                    "Google Pollen API error %s: %s", resp.status, error_body[:300]
                )
                resp.raise_for_status()
            return cast(dict[str, Any], await resp.json())

    # -------------------------------------------------------------------------
    # Weather fetch
    # -------------------------------------------------------------------------

    async def _fetch_weather_current(self, session: aiohttp.ClientSession) -> dict[str, Any]:
        url = f"{WEATHER_API_URL}/currentConditions:lookup"
        params: dict[str, Any] = {
            "key": self.api_key,
            "location.latitude": f"{self.latitude:.6f}",
            "location.longitude": f"{self.longitude:.6f}",
            "unitsSystem": self.weather_units,
        }
        async with session.get(
            url, params=params, timeout=aiohttp.ClientTimeout(total=15)
        ) as resp:
            if resp.status >= 400:
                error_body = await resp.text()
                _LOGGER.warning(
                    "Google Weather currentConditions error %s: %s", resp.status, error_body[:300]
                )
                resp.raise_for_status()
            return cast(dict[str, Any], await resp.json())

    async def _fetch_weather_hourly(self, session: aiohttp.ClientSession) -> dict[str, Any]:
        url = f"{WEATHER_API_URL}/forecast/hours:lookup"
        params: dict[str, Any] = {
            "key": self.api_key,
            "location.latitude": f"{self.latitude:.6f}",
            "location.longitude": f"{self.longitude:.6f}",
            "hours": 24,
            "pageSize": 24,
            "unitsSystem": self.weather_units,
        }
        async with session.get(
            url, params=params, timeout=aiohttp.ClientTimeout(total=15)
        ) as resp:
            if resp.status >= 400:
                error_body = await resp.text()
                _LOGGER.warning(
                    "Google Weather forecast/hours error %s: %s", resp.status, error_body[:300]
                )
                resp.raise_for_status()
            return cast(dict[str, Any], await resp.json())

    async def _fetch_weather_daily(self, session: aiohttp.ClientSession) -> dict[str, Any]:
        url = f"{WEATHER_API_URL}/forecast/days:lookup"
        params: dict[str, Any] = {
            "key": self.api_key,
            "location.latitude": f"{self.latitude:.6f}",
            "location.longitude": f"{self.longitude:.6f}",
            "days": 10,
            "pageSize": 10,
            "unitsSystem": self.weather_units,
        }
        async with session.get(
            url, params=params, timeout=aiohttp.ClientTimeout(total=15)
        ) as resp:
            if resp.status >= 400:
                error_body = await resp.text()
                _LOGGER.warning(
                    "Google Weather forecast/days error %s: %s", resp.status, error_body[:300]
                )
                resp.raise_for_status()
            return cast(dict[str, Any], await resp.json())

    async def _fetch_weather_alerts(self, session: aiohttp.ClientSession) -> dict[str, Any]:
        url = f"{WEATHER_API_URL}/publicAlerts:lookup"
        params: dict[str, Any] = {
            "key": self.api_key,
            "location.latitude": f"{self.latitude:.6f}",
            "location.longitude": f"{self.longitude:.6f}",
        }
        async with session.get(
            url, params=params, timeout=aiohttp.ClientTimeout(total=15)
        ) as resp:
            if resp.status >= 400:
                error_body = await resp.text()
                _LOGGER.warning(
                    "Google Weather publicAlerts error %s: %s", resp.status, error_body[:300]
                )
                resp.raise_for_status()
            return cast(dict[str, Any], await resp.json())

    # -------------------------------------------------------------------------
    # Air Quality data builders
    # -------------------------------------------------------------------------

    def _build_data(self, current: dict[str, Any], forecast_hours: list[dict[str, Any]]) -> dict[str, Any]:
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
                (i for i in indexes if i.get("code") == self.local_aqi_code), None
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

        # AQ advisory
        category = (new_data.get("aqi") or {}).get("category", "")
        elevated = [
            v.get("display_name", k.replace("pollutant_", ""))
            for k, v in new_data.items()
            if k.startswith("pollutant_") and v.get("epa_category") not in ("Good", None)
        ]
        new_data["aq_advisory"] = {
            "value": category,
            "aqi": (new_data.get("aqi") or {}).get("value"),
            "dominant_pollutant": dominant_code or None,
            "health_recommendations": health_recs,
            "elevated_pollutants": elevated,
            "trend": aqi_trend,
        }

        return new_data

    def _build_aqi_hourly_forecast(
        self, hours: list[dict[str, Any]]
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        uaqi_hourly: list[dict[str, Any]] = []
        local_hourly: list[dict[str, Any]] = []
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
        self, hours: list[dict[str, Any]]
    ) -> dict[str, list[dict[str, Any]]]:
        result: dict[str, list[dict[str, Any]]] = defaultdict(list)
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
        self, hours: list[dict[str, Any]]
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        uaqi_days: dict[str, list[dict[str, Any]]] = defaultdict(list)
        local_days: dict[str, list[dict[str, Any]]] = defaultdict(list)

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

        def _to_daily(days_dict: dict[str, Any]) -> list[dict[str, Any]]:
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
        self, hours: list[dict[str, Any]]
    ) -> dict[str, list[dict[str, Any]]]:
        days: dict[str, dict[str, list[Any]]] = defaultdict(lambda: defaultdict(list))
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

        result: dict[str, list[dict[str, Any]]] = {}
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

    # -------------------------------------------------------------------------
    # Pollen data builder
    # -------------------------------------------------------------------------

    def _build_pollen_data(self, response: dict[str, Any]) -> dict[str, Any]:
        """Parse Google Pollen API response into sensor data."""
        if not isinstance(response, dict):
            return {}

        daily = response.get("dailyInfo")
        if not isinstance(daily, list) or not daily:
            return {}

        result: dict[str, Any] = {}

        type_codes: set[str] = set()
        type_by_day: list[dict[str, Any]] = []
        plant_by_day: list[dict[str, Any]] = []
        plant_codes: list[str] = []

        for i, day in enumerate(daily):
            day_types: dict[str, Any] = {}
            for item in day.get("pollenTypeInfo", []) or []:
                if not isinstance(item, dict):
                    continue
                code = (item.get("code") or "").strip().upper()
                if code:
                    day_types[code] = item
                    type_codes.add(code)
            type_by_day.append(day_types)

            day_plants: dict[str, Any] = {}
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

        # Pollen advisory — worst in-season type
        worst_level = "None"
        dominant_type = None
        dominant_index = None
        in_season: list[str] = []
        all_levels: dict[str, str] = {}
        advisory_health_recs = None

        for key, val in result.items():
            if not key.startswith("pollen_type_"):
                continue
            category = val.get("category") or "None"
            display = val.get("display_name", key)
            if val.get("in_season"):
                in_season.append(display)
                all_levels[display] = category
                try:
                    if _POLLEN_LEVEL_ORDER.index(category) > _POLLEN_LEVEL_ORDER.index(worst_level):
                        worst_level = category
                        dominant_type = display
                        dominant_index = val.get("value")
                        advisory_health_recs = val.get("health_recommendations")
                except ValueError:
                    pass

        result["pollen_advisory"] = {
            "value": worst_level,
            "dominant_type": dominant_type,
            "dominant_index": dominant_index,
            "in_season_types": in_season,
            "all_levels": all_levels,
            "health_recommendations": advisory_health_recs,
        }

        return result

    def _build_pollen_forecast(
        self,
        daily: list[dict[str, Any]],
        by_day: list[dict[str, Any]],
        code: str,
        kind: str,
    ) -> list[dict[str, Any]]:
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

    # -------------------------------------------------------------------------
    # Weather data builders
    # -------------------------------------------------------------------------

    def _build_weather_data(
        self,
        current: dict[str, Any],
        hourly: dict[str, Any],
        daily: dict[str, Any],
        alerts: dict[str, Any] | None,
    ) -> dict[str, Any]:
        result: dict[str, Any] = {}

        is_daytime = current.get("isDaytime", True)
        wind = current.get("wind") or {}
        precip = current.get("precipitation") or {}
        qpf = precip.get("qpf") or {}

        result["weather_current"] = {
            "condition": _w_condition(current.get("weatherCondition"), is_daytime),
            "temperature": _w_degrees(current.get("temperature")),
            "apparent_temperature": _w_degrees(current.get("feelsLikeTemperature")),
            "dew_point": _w_degrees(current.get("dewPoint")),
            "humidity": current.get("relativeHumidity"),
            "wind_speed": ((wind.get("speed") or {}).get("value")),
            "wind_bearing": ((wind.get("direction") or {}).get("degrees")),
            "wind_gust_speed": ((wind.get("gust") or {}).get("value")),
            "pressure": (current.get("airPressure") or {}).get("meanSeaLevelMillibars"),
            "visibility": (current.get("visibility") or {}).get("distance"),
            "uv_index": current.get("uvIndex"),
            "cloud_coverage": current.get("cloudCover"),
            "precipitation": qpf.get("quantity"),
            "thunderstorm_probability": current.get("thunderstormProbability"),
            "heat_index": _w_degrees(current.get("heatIndex")),
            "wind_chill": _w_degrees(current.get("windChill")),
            "is_daytime": is_daytime,
            "datetime": current.get("currentTime"),
        }

        result["weather_hourly"] = self._build_weather_hourly(hourly)
        daily_list, twice_daily_list = self._build_weather_daily(daily)
        result["weather_daily"] = daily_list
        result["weather_twice_daily"] = twice_daily_list

        if alerts is not None:
            result["weather_alerts"] = self._build_weather_alerts(alerts)

        return result

    def _build_weather_hourly(self, hourly: dict[str, Any]) -> list[dict[str, Any]]:
        entries = []
        for h in hourly.get("forecastHours", []):
            is_daytime = h.get("isDaytime", True)
            wind = h.get("wind") or {}
            precip = h.get("precipitation") or {}
            prob = (precip.get("probability") or {}).get("percent")
            cloud = h.get("cloudCover")
            cloud_val = cloud.get("percent") if isinstance(cloud, dict) else cloud

            entry = {
                "datetime": (h.get("interval") or {}).get("startTime") or h.get("displayDateTime"),
                "condition": _w_condition(h.get("weatherCondition"), is_daytime),
                "is_daytime": is_daytime,
                "native_temperature": _w_degrees(h.get("temperature")),
                "native_apparent_temperature": _w_degrees(h.get("feelsLikeTemperature")),
                "native_dew_point": _w_degrees(h.get("dewPoint")),
                "humidity": h.get("relativeHumidity"),
                "native_wind_speed": ((wind.get("speed") or {}).get("value")),
                "wind_bearing": ((wind.get("direction") or {}).get("degrees")),
                "native_wind_gust_speed": ((wind.get("gust") or {}).get("value")),
                "precipitation_probability": prob,
                "native_precipitation": (precip.get("qpf") or {}).get("quantity"),
                "native_pressure": (h.get("airPressure") or {}).get("meanSeaLevelMillibars"),
                "cloud_coverage": cloud_val,
                "uv_index": h.get("uvIndex"),
            }
            if entry.get("datetime"):
                entries.append(entry)
        return entries

    def _build_weather_daily(self, daily: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        daily_list: list[dict[str, Any]] = []
        twice_daily_list: list[dict[str, Any]] = []

        for day in daily.get("forecastDays", []):
            date_obj = day.get("displayDate") or {}
            try:
                y = date_obj["year"]
                m = date_obj["month"]
                d = date_obj["day"]
                date_str = f"{y:04d}-{m:02d}-{d:02d}T12:00:00+00:00"
                date_str_night = f"{y:04d}-{m:02d}-{d:02d}T21:00:00+00:00"
            except (KeyError, TypeError):
                continue

            max_temp = _w_degrees(day.get("maxTemperature"))
            min_temp = _w_degrees(day.get("minTemperature"))
            feels_max = _w_degrees(day.get("feelsLikeMaxTemperature"))
            feels_min = _w_degrees(day.get("feelsLikeMinTemperature"))
            day_fc = day.get("daytimeForecast") or {}
            night_fc = day.get("nighttimeForecast") or {}

            def _parse_fc(
                fc: dict[str, Any],
                dt_str: str,
                is_daytime: bool,
                temp: float | None,
                templow: float | None,
                apparent_temp: float | None = None,
            ) -> dict[str, Any]:
                wind = fc.get("wind") or {}
                precip = fc.get("precipitation") or {}
                prob = (precip.get("probability") or {}).get("percent")
                humidity_val = fc.get("relativeHumidity")
                cloud = fc.get("cloudCover")
                cloud_val = (
                    cloud.get("percent") if isinstance(cloud, dict) else cloud
                )
                return {
                    "datetime": dt_str,
                    "is_daytime": is_daytime,
                    "condition": _w_condition(fc.get("weatherCondition"), is_daytime),
                    "native_temperature": temp,
                    "native_templow": templow,
                    "native_apparent_temperature": apparent_temp,
                    "precipitation_probability": prob,
                    "native_precipitation": (precip.get("qpf") or {}).get("quantity"),
                    "native_wind_speed": ((wind.get("speed") or {}).get("value")),
                    "wind_bearing": ((wind.get("direction") or {}).get("degrees")),
                    "native_wind_gust_speed": ((wind.get("gust") or {}).get("value")),
                    "humidity": humidity_val,
                    "cloud_coverage": cloud_val,
                    "uv_index": fc.get("uvIndex"),
                }

            if day_fc:
                entry = _parse_fc(day_fc, date_str, True, max_temp, min_temp, feels_max)
                daily_entry = {k: v for k, v in entry.items() if k != "is_daytime"}
                # Add nighttime QPF so the daily total covers the full 24 hours.
                if night_fc:
                    night_qpf = ((night_fc.get("precipitation") or {}).get("qpf") or {}).get("quantity")
                    if night_qpf is not None:
                        daily_entry["native_precipitation"] = (daily_entry.get("native_precipitation") or 0.0) + night_qpf
                daily_list.append(daily_entry)
                twice_daily_list.append(_parse_fc(day_fc, date_str, True, max_temp, None, feels_max))
            if night_fc:
                twice_daily_list.append(
                    _parse_fc(night_fc, date_str_night, False, min_temp, None, feels_min)
                )

        return daily_list, twice_daily_list

    def _build_weather_alerts(self, alerts: dict[str, Any]) -> list[dict[str, Any]]:
        result = []
        for alert in alerts.get("publicAlerts", []) or []:
            severity = (alert.get("severity") or "").replace("_SEVERITY", "")
            result.append({
                "title": alert.get("alertHeadline", ""),
                "severity": severity,
                "event_type": (alert.get("event") or {}).get("type", ""),
                "area": alert.get("areaDescription", ""),
                "start_time": alert.get("effectiveTime"),
                "expiration_time": alert.get("expireTime"),
                "description": alert.get("description", ""),
                "instructions": alert.get("instruction", ""),
            })
        return result

    # -------------------------------------------------------------------------
    # Trend / peak helpers
    # -------------------------------------------------------------------------

    @staticmethod
    def _compute_trend(current_val: Any, forecast: list[dict[str, Any]]) -> str | None:
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
    def _compute_peak(forecast: list[dict[str, Any]]) -> dict[str, Any] | None:
        peak = None
        for f in forecast:
            idx = f.get("index")
            if isinstance(idx, (int, float)):
                if peak is None or idx > peak.get("index", -1):
                    peak = f
        return peak
