"""Config flow for Particle Man integration."""
from __future__ import annotations

import hashlib
import logging
from typing import Any

import asyncio
import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    BooleanSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
    TimeSelector,
)

from .const import (
    BASE_URL,
    CONF_API_KEY,
    CONF_AQ_MONTHLY_LIMIT,
    CONF_AUTOMAGIC_MODE,
    CONF_ENABLE_AIR_QUALITY,
    CONF_ENABLE_POLLEN,
    CONF_ENABLE_WEATHER,
    CONF_ENABLE_WEATHER_ALERTS,
    CONF_FORECAST_DAYS,
    CONF_LANGUAGE,
    CONF_LATITUDE,
    CONF_LOCAL_AQI,
    CONF_LOCAL_AQI_CODE,
    CONF_LOCATION_NAME,
    CONF_LOCATIONS,
    CONF_LONGITUDE,
    CONF_PLANT_SENSORS,
    CONF_POLLEN_MONTHLY_LIMIT,
    CONF_QUIET_END,
    CONF_QUIET_HOURS_ENABLED,
    CONF_QUIET_START,
    CONF_UPDATE_INTERVAL,
    CONF_WEATHER_MONTHLY_LIMIT,
    CONF_WEATHER_UNITS,
    DEFAULT_AQ_MONTHLY_LIMIT,
    DEFAULT_AUTOMAGIC_MODE,
    DEFAULT_ENABLE_AIR_QUALITY,
    DEFAULT_ENABLE_POLLEN,
    DEFAULT_ENABLE_WEATHER,
    DEFAULT_ENABLE_WEATHER_ALERTS,
    DEFAULT_FORECAST_DAYS,
    DEFAULT_LANGUAGE,
    DEFAULT_LOCAL_AQI,
    DEFAULT_LOCAL_AQI_CODE,
    DEFAULT_PLANT_SENSORS,
    DEFAULT_POLLEN_MONTHLY_LIMIT,
    DEFAULT_QUIET_END,
    DEFAULT_QUIET_HOURS_ENABLED,
    DEFAULT_QUIET_START,
    DEFAULT_UPDATE_INTERVAL,
    DEFAULT_WEATHER_MONTHLY_LIMIT,
    DEFAULT_WEATHER_UNITS,
    DOMAIN,
    LOCAL_AQI_CODES,
    POLLEN_API_URL,
    WEATHER_API_URL,
    _AQ_CALLS_PER_POLL,
    _MINUTES_PER_MONTH,
    _POLLEN_CALLS_PER_POLL,
    _WEATHER_CALLS_PER_POLL,
    safe_interval_minutes,
)

_LOGGER = logging.getLogger(__name__)

# Internal key for the locations step action selector
_ACTION = "action"
_ACTION_ADD = "add"
_ACTION_REMOVE = "remove"
_ACTION_CONTINUE = "continue"


def _projected_usage(interval: int, num_locations: int, calls_per_poll: int) -> int:
    return round(_MINUTES_PER_MONTH / interval * calls_per_poll * num_locations)


def _usage_summary(
    weather_interval: int,
    num_locations: int,
    enable_aq: bool,
    enable_pollen: bool,
    enable_weather: bool,
    enforce: bool,
    aq_limit: int,
    pollen_limit: int,
    weather_limit: int,
) -> str:
    # AQ and pollen are always fetched hourly regardless of the weather interval.
    parts = []
    if enable_aq:
        parts.append(
            f"Air Quality ~{_projected_usage(60, num_locations, _AQ_CALLS_PER_POLL)}"
            + (f"/{aq_limit}" if enforce else "")
        )
    if enable_pollen:
        parts.append(
            f"Pollen ~{_projected_usage(60, num_locations, _POLLEN_CALLS_PER_POLL)}"
            + (f"/{pollen_limit}" if enforce else "")
        )
    if enable_weather:
        parts.append(
            f"Weather ~{_projected_usage(weather_interval, num_locations, _WEATHER_CALLS_PER_POLL)}"
            + (f"/{weather_limit}" if enforce else "")
        )
    if not parts:
        return "No APIs enabled."
    loc_str = f"{num_locations} location(s)"
    return f"With {loc_str} at {weather_interval} min — estimated monthly: {' · '.join(parts)} calls."


def _classify_api_error(status: int, body: dict) -> str:
    if status == 403:
        err = body.get("error", {}) or {}
        msg = (err.get("message") or "").lower()
        reasons = [d.get("reason", "") for d in (err.get("details") or [])]
        if "SERVICE_DISABLED" in reasons or "has not been used" in msg or "is disabled" in msg:
            return "not_enabled"
    if status in (400, 401, 403):
        return "invalid_auth"
    return "cannot_connect"


async def _check_api_coverage(
    hass, api_key: str, lat: float, lon: float
) -> tuple[dict[str, str], list[str]]:
    session = async_get_clientsession(hass)

    async def _check_aq() -> tuple[str, list[str]]:
        url = f"{BASE_URL}/currentConditions:lookup?key={api_key}"
        body = {
            "location": {"latitude": lat, "longitude": lon},
            "universalAqi": True,
            "extraComputations": ["LOCAL_AQI"],
        }
        try:
            async with session.post(
                url, json=body, timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                if resp.ok:
                    data = await resp.json()
                    codes = [
                        i.get("code") for i in data.get("indexes", [])
                        if i.get("code") and i.get("code") != "uaqi"
                    ]
                    return "ok", [c for c in codes if c]
                try:
                    body_data = await resp.json()
                except Exception:
                    body_data = {}
                if resp.status == 404:
                    return "not_covered", []
                return _classify_api_error(resp.status, body_data), []
        except aiohttp.ClientError:
            return "cannot_connect", []

    async def _check_pollen() -> str:
        params = {
            "key": api_key,
            "location.latitude": f"{lat:.6f}",
            "location.longitude": f"{lon:.6f}",
            "days": 1,
        }
        try:
            async with session.get(
                POLLEN_API_URL, params=params, timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                if resp.ok:
                    return "ok"
                try:
                    body_data = await resp.json()
                except Exception:
                    body_data = {}
                if resp.status == 404:
                    return "not_covered"
                return _classify_api_error(resp.status, body_data)
        except aiohttp.ClientError:
            return "cannot_connect"

    async def _check_weather() -> str:
        url = f"{WEATHER_API_URL}/currentConditions:lookup"
        params = {
            "key": api_key,
            "location.latitude": f"{lat:.6f}",
            "location.longitude": f"{lon:.6f}",
            "unitsSystem": "METRIC",
        }
        try:
            async with session.get(
                url, params=params, timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                if resp.ok:
                    return "ok"
                try:
                    body_data = await resp.json()
                except Exception:
                    body_data = {}
                if resp.status == 404:
                    return "not_covered"
                return _classify_api_error(resp.status, body_data)
        except aiohttp.ClientError:
            return "cannot_connect"

    aq_result, pollen_result, weather_result = await asyncio.gather(
        _check_aq(), _check_pollen(), _check_weather()
    )
    aq_status, local_aqi_codes = aq_result
    statuses = {"aq": aq_status, "pollen": pollen_result, "weather": weather_result}
    return statuses, local_aqi_codes


def _build_coverage_notes(statuses: dict[str, str]) -> str:
    coverage_urls = {
        "aq": "https://developers.google.com/maps/documentation/air-quality/coverage",
        "pollen": "https://developers.google.com/maps/documentation/pollen/coverage",
        "weather": "https://developers.google.com/maps/documentation/weather/coverage",
    }
    labels = {"aq": "Air Quality", "pollen": "Pollen", "weather": "Weather"}
    notes = [
        f"⚠ {labels[api]} data may not be available at this location. [Coverage map]({coverage_urls[api]})"
        for api, status in statuses.items()
        if status == "not_covered"
    ]
    return "\n\n".join(notes)


# ---------------------------------------------------------------------------
# Config Flow (first-add only)
# ---------------------------------------------------------------------------

class ParticleManConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Particle Man."""

    VERSION = 3

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> ParticleManOptionsFlow:
        return ParticleManOptionsFlow()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            api_key = user_input[CONF_API_KEY]
            loc_name = (user_input.get(CONF_LOCATION_NAME) or "Home").strip() or "Home"
            lat = user_input[CONF_LATITUDE]
            lon = user_input[CONF_LONGITUDE]

            try:
                statuses, _codes = await _check_api_coverage(self.hass, api_key, lat, lon)
                _not_enabled = {
                    "aq": "aq_not_enabled",
                    "pollen": "pollen_not_enabled",
                    "weather": "weather_not_enabled",
                }
                for api, err_key in _not_enabled.items():
                    if statuses.get(api) == "not_enabled":
                        errors["base"] = err_key
                        break
                if not errors:
                    for api, status in statuses.items():
                        if status in ("invalid_auth", "cannot_connect"):
                            errors["base"] = status
                            break
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected error validating Particle Man key")
                errors["base"] = "unknown"

            if not errors:
                key_hash = hashlib.md5(api_key.encode()).hexdigest()
                await self.async_set_unique_id(key_hash)
                self._abort_if_unique_id_configured()

                locale_units = "METRIC" if self.hass.config.units.name == "metric" else "IMPERIAL"
                seeded_options = {
                    CONF_AUTOMAGIC_MODE: DEFAULT_AUTOMAGIC_MODE,
                    CONF_QUIET_HOURS_ENABLED: DEFAULT_QUIET_HOURS_ENABLED,
                    CONF_QUIET_START: DEFAULT_QUIET_START,
                    CONF_QUIET_END: DEFAULT_QUIET_END,
                    CONF_UPDATE_INTERVAL: DEFAULT_UPDATE_INTERVAL,
                    CONF_FORECAST_DAYS: DEFAULT_FORECAST_DAYS,
                    CONF_LANGUAGE: DEFAULT_LANGUAGE,
                    CONF_PLANT_SENSORS: DEFAULT_PLANT_SENSORS,
                    CONF_ENABLE_AIR_QUALITY: DEFAULT_ENABLE_AIR_QUALITY,
                    CONF_ENABLE_POLLEN: DEFAULT_ENABLE_POLLEN,
                    CONF_ENABLE_WEATHER: DEFAULT_ENABLE_WEATHER,
                    CONF_ENABLE_WEATHER_ALERTS: DEFAULT_ENABLE_WEATHER_ALERTS,
                    CONF_WEATHER_UNITS: locale_units,
                    CONF_AQ_MONTHLY_LIMIT: DEFAULT_AQ_MONTHLY_LIMIT,
                    CONF_POLLEN_MONTHLY_LIMIT: DEFAULT_POLLEN_MONTHLY_LIMIT,
                    CONF_WEATHER_MONTHLY_LIMIT: DEFAULT_WEATHER_MONTHLY_LIMIT,
                    CONF_LOCATIONS: [{
                        CONF_LOCATION_NAME: loc_name,
                        CONF_LATITUDE: lat,
                        CONF_LONGITUDE: lon,
                        CONF_LOCAL_AQI: DEFAULT_LOCAL_AQI,
                        CONF_LOCAL_AQI_CODE: DEFAULT_LOCAL_AQI_CODE,
                    }],
                }
                return self.async_create_entry(
                    title=f"Particle Man",
                    data={CONF_API_KEY: api_key},
                    options=seeded_options,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_API_KEY): TextSelector(
                        TextSelectorConfig(type=TextSelectorType.PASSWORD)
                    ),
                    vol.Required(
                        CONF_LOCATION_NAME, default="Home"
                    ): TextSelector(
                        TextSelectorConfig(type=TextSelectorType.TEXT)
                    ),
                    vol.Required(
                        CONF_LATITUDE, default=self.hass.config.latitude
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=-90, max=90, step="any", mode=NumberSelectorMode.BOX
                        )
                    ),
                    vol.Required(
                        CONF_LONGITUDE, default=self.hass.config.longitude
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=-180, max=180, step="any", mode=NumberSelectorMode.BOX
                        )
                    ),
                }
            ),
            errors=errors,
        )


# ---------------------------------------------------------------------------
# Options Flow (multi-step, conditional on Automagic mode)
# ---------------------------------------------------------------------------

class ParticleManOptionsFlow(config_entries.OptionsFlow):
    """Multi-step options flow for Particle Man."""

    def __init__(self) -> None:
        self._options: dict[str, Any] = {}
        self._locations: list[dict[str, Any]] | None = None  # None = not yet loaded
        self._availability: dict[str, str] = {}
        self._available_local_aqi_codes: list[str] = []
        self._coverage_notes: str = ""

    def _get(self, key: str, default: Any) -> Any:
        """Read from in-progress options, then saved options, then data, then default."""
        return self._options.get(
            key,
            self.config_entry.options.get(
                key, self.config_entry.data.get(key, default)
            ),
        )

    def _ensure_locations_loaded(self) -> None:
        if self._locations is None:
            self._locations = list(self.config_entry.options.get(CONF_LOCATIONS, []))

    def _num_locations(self) -> int:
        self._ensure_locations_loaded()
        return len(self._locations)  # type: ignore[arg-type]

    def _format_location_list(self) -> str:
        self._ensure_locations_loaded()
        if not self._locations:
            return "No locations added yet."
        lines = []
        for loc in self._locations:  # type: ignore[union-attr]
            name = loc.get(CONF_LOCATION_NAME, "?")
            lat = loc.get(CONF_LATITUDE, 0)
            lon = loc.get(CONF_LONGITUDE, 0)
            lines.append(f"• **{name}** ({float(lat):.4f}, {float(lon):.4f})")
        return "\n".join(lines)

    def _automagic(self) -> bool:
        return self._options.get(
            CONF_AUTOMAGIC_MODE,
            self._get(CONF_AUTOMAGIC_MODE, DEFAULT_AUTOMAGIC_MODE),
        )

    def _next_step(self, after: str) -> str | None:
        """Return next step ID after `after`, or None to create entry."""
        automagic = self._automagic()
        order = ["apis", "air_quality", "pollen", "weather", "api_limits"]
        # Detail steps and api_limits only shown in manual mode
        enable_map = {
            "air_quality": (not automagic) and self._options.get(CONF_ENABLE_AIR_QUALITY, DEFAULT_ENABLE_AIR_QUALITY),
            "pollen": (not automagic) and self._options.get(CONF_ENABLE_POLLEN, DEFAULT_ENABLE_POLLEN),
            "weather": (not automagic) and self._options.get(CONF_ENABLE_WEATHER, DEFAULT_ENABLE_WEATHER),
            "api_limits": not automagic,
        }
        found = False
        for step in order:
            if step == after:
                found = True
                continue
            if not found:
                continue
            if step not in enable_map or enable_map[step]:
                return step
        return None

    def _create_entry(self) -> config_entries.ConfigFlowResult:
        """Merge accumulated options with existing saved options and create entry."""
        self._ensure_locations_loaded()
        merged = dict(self.config_entry.options)
        merged.update(self._options)
        merged[CONF_LOCATIONS] = self._locations
        return self.async_create_entry(title="", data=merged)

    # -------------------------------------------------------------------------
    # Step 1: API Mode
    # -------------------------------------------------------------------------

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        self._ensure_locations_loaded()

        if user_input is not None:
            self._options.update(user_input)
            return await self.async_step_locations()

        schema = vol.Schema({
            vol.Required(CONF_AUTOMAGIC_MODE): BooleanSelector(),
        })
        suggested = {
            CONF_AUTOMAGIC_MODE: self._get(CONF_AUTOMAGIC_MODE, DEFAULT_AUTOMAGIC_MODE),
        }
        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(schema, suggested),
        )

    # -------------------------------------------------------------------------
    # Step 2: Location Management
    # -------------------------------------------------------------------------

    async def async_step_locations(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        self._ensure_locations_loaded()

        if user_input is not None:
            action = user_input.get(_ACTION)
            if action == _ACTION_ADD:
                return await self.async_step_add_location()
            if action == _ACTION_REMOVE:
                return await self.async_step_remove_location()
            # _ACTION_CONTINUE
            return await self.async_step_quiet_hours()

        has_locations = bool(self._locations)
        action_options = [{"value": _ACTION_ADD, "label": "Add a location"}]
        if has_locations:
            action_options.append({"value": _ACTION_REMOVE, "label": "Remove a location"})
            action_options.append({"value": _ACTION_CONTINUE, "label": "Continue →"})

        schema = vol.Schema({
            vol.Required(_ACTION, default=_ACTION_ADD if not has_locations else _ACTION_CONTINUE): SelectSelector(
                SelectSelectorConfig(options=action_options, mode=SelectSelectorMode.LIST)
            ),
        })

        location_list = self._format_location_list()
        return self.async_show_form(
            step_id="locations",
            data_schema=schema,
            description_placeholders={"location_list": location_list},
        )

    # -------------------------------------------------------------------------
    # Step 2a: Add Location
    # -------------------------------------------------------------------------

    async def async_step_add_location(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        self._ensure_locations_loaded()
        errors: dict[str, str] = {}

        if user_input is not None:
            loc_name = (user_input.get(CONF_LOCATION_NAME) or "").strip()
            lat = user_input.get(CONF_LATITUDE)
            lon = user_input.get(CONF_LONGITUDE)

            if not loc_name:
                errors[CONF_LOCATION_NAME] = "location_name_required"
            else:
                existing_names = [
                    (loc.get(CONF_LOCATION_NAME) or "").lower()
                    for loc in (self._locations or [])
                ]
                if loc_name.lower() in existing_names:
                    errors[CONF_LOCATION_NAME] = "location_name_duplicate"

            if not errors:
                api_key = self.config_entry.data[CONF_API_KEY]
                try:
                    statuses, codes = await _check_api_coverage(self.hass, api_key, lat, lon)
                    self._availability = statuses
                    self._available_local_aqi_codes = codes
                    self._coverage_notes = _build_coverage_notes(statuses)
                    _not_enabled = {
                        "aq": "aq_not_enabled",
                        "pollen": "pollen_not_enabled",
                        "weather": "weather_not_enabled",
                    }
                    for api, err_key in _not_enabled.items():
                        if statuses.get(api) == "not_enabled":
                            errors["base"] = err_key
                            break
                except Exception:  # noqa: BLE001
                    _LOGGER.debug("Coverage check failed in add_location, continuing")

            if not errors:
                self._locations.append({  # type: ignore[union-attr]
                    CONF_LOCATION_NAME: loc_name,
                    CONF_LATITUDE: lat,
                    CONF_LONGITUDE: lon,
                    CONF_LOCAL_AQI: DEFAULT_LOCAL_AQI,
                    CONF_LOCAL_AQI_CODE: DEFAULT_LOCAL_AQI_CODE,
                })
                self._coverage_notes = ""
                return await self.async_step_locations()

        coverage_str = ("\n\n" + self._coverage_notes) if self._coverage_notes else ""
        schema = vol.Schema({
            vol.Required(CONF_LOCATION_NAME): TextSelector(
                TextSelectorConfig(type=TextSelectorType.TEXT)
            ),
            vol.Required(CONF_LATITUDE, default=self.hass.config.latitude): NumberSelector(
                NumberSelectorConfig(min=-90, max=90, step="any", mode=NumberSelectorMode.BOX)
            ),
            vol.Required(CONF_LONGITUDE, default=self.hass.config.longitude): NumberSelector(
                NumberSelectorConfig(min=-180, max=180, step="any", mode=NumberSelectorMode.BOX)
            ),
        })
        return self.async_show_form(
            step_id="add_location",
            data_schema=schema,
            errors=errors,
            description_placeholders={"coverage_notes": coverage_str},
        )

    # -------------------------------------------------------------------------
    # Step 2b: Remove Location
    # -------------------------------------------------------------------------

    async def async_step_remove_location(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        self._ensure_locations_loaded()

        if user_input is not None:
            name_to_remove = user_input.get(CONF_LOCATION_NAME)
            self._locations = [
                loc for loc in (self._locations or [])
                if loc.get(CONF_LOCATION_NAME) != name_to_remove
            ]
            return await self.async_step_locations()

        location_names = [
            loc.get(CONF_LOCATION_NAME, "?")
            for loc in (self._locations or [])
        ]
        schema = vol.Schema({
            vol.Required(CONF_LOCATION_NAME): SelectSelector(
                SelectSelectorConfig(options=location_names, mode=SelectSelectorMode.DROPDOWN)
            ),
        })
        return self.async_show_form(
            step_id="remove_location",
            data_schema=schema,
        )

    # -------------------------------------------------------------------------
    # Step 3: Quiet Hours (always shown)
    # -------------------------------------------------------------------------

    async def async_step_quiet_hours(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        if user_input is not None:
            self._options.update(user_input)
            return await self.async_step_apis()

        schema = vol.Schema({
            vol.Required(CONF_QUIET_HOURS_ENABLED): BooleanSelector(),
            vol.Required(CONF_QUIET_START): TimeSelector(),
            vol.Required(CONF_QUIET_END): TimeSelector(),
        })
        suggested = {
            CONF_QUIET_HOURS_ENABLED: self._get(CONF_QUIET_HOURS_ENABLED, DEFAULT_QUIET_HOURS_ENABLED),
            CONF_QUIET_START: self._get(CONF_QUIET_START, DEFAULT_QUIET_START),
            CONF_QUIET_END: self._get(CONF_QUIET_END, DEFAULT_QUIET_END),
        }
        return self.async_show_form(
            step_id="quiet_hours",
            data_schema=self.add_suggested_values_to_schema(schema, suggested),
        )

    # -------------------------------------------------------------------------
    # Step 4: Data Sources & Update Interval (manual mode only)
    # -------------------------------------------------------------------------

    async def async_step_apis(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        if user_input is not None:
            self._options.update(user_input)
            next_step = self._next_step("apis")
            if next_step:
                return await getattr(self, f"async_step_{next_step}")()
            return self._create_entry()

        automagic = self._automagic()
        enable_aq = self._get(CONF_ENABLE_AIR_QUALITY, DEFAULT_ENABLE_AIR_QUALITY)
        enable_pollen = self._get(CONF_ENABLE_POLLEN, DEFAULT_ENABLE_POLLEN)
        enable_weather = self._get(CONF_ENABLE_WEATHER, DEFAULT_ENABLE_WEATHER)

        fields: dict = {
            vol.Required(CONF_ENABLE_AIR_QUALITY): BooleanSelector(),
            vol.Required(CONF_ENABLE_POLLEN): BooleanSelector(),
            vol.Required(CONF_ENABLE_WEATHER): BooleanSelector(),
        }
        suggested: dict = {
            CONF_ENABLE_AIR_QUALITY: enable_aq,
            CONF_ENABLE_POLLEN: enable_pollen,
            CONF_ENABLE_WEATHER: enable_weather,
        }

        if automagic:
            usage_text = "Air quality and pollen update hourly. Weather updates automatically based on your location count."
        else:
            interval = self._get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)
            num_loc = self._num_locations()
            aq_limit = self._get(CONF_AQ_MONTHLY_LIMIT, DEFAULT_AQ_MONTHLY_LIMIT)
            pollen_limit = self._get(CONF_POLLEN_MONTHLY_LIMIT, DEFAULT_POLLEN_MONTHLY_LIMIT)
            weather_limit = self._get(CONF_WEATHER_MONTHLY_LIMIT, DEFAULT_WEATHER_MONTHLY_LIMIT)
            enabled_apis: dict[str, tuple[int, int]] = {}
            if enable_weather:
                enabled_apis["weather"] = (_WEATHER_CALLS_PER_POLL, DEFAULT_WEATHER_MONTHLY_LIMIT)
            safe = safe_interval_minutes(num_loc, enabled_apis)
            summary = _usage_summary(
                interval, num_loc, enable_aq, enable_pollen, enable_weather,
                True, aq_limit, pollen_limit, weather_limit,
            )
            usage_text = f"{summary} Suggested weather minimum: {safe} min."
            fields[vol.Required(CONF_UPDATE_INTERVAL)] = NumberSelector(
                NumberSelectorConfig(
                    min=15, max=1440, step=5, unit_of_measurement="min",
                    mode=NumberSelectorMode.BOX,
                )
            )
            suggested[CONF_UPDATE_INTERVAL] = interval

        coverage_notes_str = ("\n\n" + self._coverage_notes) if self._coverage_notes else ""
        return self.async_show_form(
            step_id="apis",
            data_schema=self.add_suggested_values_to_schema(vol.Schema(fields), suggested),
            description_placeholders={"usage_summary": usage_text, "coverage_notes": coverage_notes_str},
        )

    # -------------------------------------------------------------------------
    # Step 5: Air Quality Options (conditional)
    # -------------------------------------------------------------------------

    async def async_step_air_quality(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            local_aqi = user_input.get(CONF_LOCAL_AQI, False)
            code = user_input.get(CONF_LOCAL_AQI_CODE, DEFAULT_LOCAL_AQI_CODE)
            if (
                local_aqi
                and self._available_local_aqi_codes
                and code not in self._available_local_aqi_codes
            ):
                errors[CONF_LOCAL_AQI_CODE] = "local_aqi_unavailable"
            if not errors:
                self._options.update(user_input)
                next_step = self._next_step("air_quality")
                if next_step:
                    return await getattr(self, f"async_step_{next_step}")()
                return self._create_entry()

        available_codes = self._available_local_aqi_codes or LOCAL_AQI_CODES
        local_aqi_detail = (
            "\n\nAvailable regional AQI codes at this location: `"
            + "`, `".join(available_codes) + "`"
            if self._available_local_aqi_codes
            else ""
        )
        schema = vol.Schema({
            vol.Required(CONF_FORECAST_DAYS): NumberSelector(
                NumberSelectorConfig(min=1, max=5, step=1, mode=NumberSelectorMode.SLIDER)
            ),
            vol.Required(CONF_LANGUAGE): TextSelector(
                TextSelectorConfig(type=TextSelectorType.TEXT)
            ),
            vol.Required(CONF_LOCAL_AQI): BooleanSelector(),
            vol.Required(CONF_LOCAL_AQI_CODE): SelectSelector(
                SelectSelectorConfig(options=available_codes, mode=SelectSelectorMode.DROPDOWN)
            ),
        })
        suggested = {
            CONF_FORECAST_DAYS: self._get(CONF_FORECAST_DAYS, DEFAULT_FORECAST_DAYS),
            CONF_LANGUAGE: self._get(CONF_LANGUAGE, DEFAULT_LANGUAGE),
            CONF_LOCAL_AQI: self._get(CONF_LOCAL_AQI, DEFAULT_LOCAL_AQI),
            CONF_LOCAL_AQI_CODE: self._get(CONF_LOCAL_AQI_CODE, DEFAULT_LOCAL_AQI_CODE),
        }
        return self.async_show_form(
            step_id="air_quality",
            data_schema=self.add_suggested_values_to_schema(schema, suggested),
            errors=errors,
            description_placeholders={"local_aqi_detail": local_aqi_detail},
        )

    # -------------------------------------------------------------------------
    # Step 6: Pollen Options (conditional)
    # -------------------------------------------------------------------------

    async def async_step_pollen(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        if user_input is not None:
            self._options.update(user_input)
            next_step = self._next_step("pollen")
            if next_step:
                return await getattr(self, f"async_step_{next_step}")()
            return self._create_entry()

        schema = vol.Schema({
            vol.Required(CONF_PLANT_SENSORS): BooleanSelector(),
        })
        suggested = {
            CONF_PLANT_SENSORS: self._get(CONF_PLANT_SENSORS, DEFAULT_PLANT_SENSORS),
        }
        return self.async_show_form(
            step_id="pollen",
            data_schema=self.add_suggested_values_to_schema(schema, suggested),
        )

    # -------------------------------------------------------------------------
    # Step 7: Weather Options (conditional)
    # -------------------------------------------------------------------------

    async def async_step_weather(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        if user_input is not None:
            self._options.update(user_input)
            next_step = self._next_step("weather")
            if next_step:
                return await getattr(self, f"async_step_{next_step}")()
            return self._create_entry()

        schema = vol.Schema({
            vol.Required(CONF_WEATHER_UNITS): SelectSelector(
                SelectSelectorConfig(
                    options=["METRIC", "IMPERIAL"],
                    mode=SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Required(CONF_ENABLE_WEATHER_ALERTS): BooleanSelector(),
        })
        locale_units = "METRIC" if self.hass.config.units.name == "metric" else "IMPERIAL"
        suggested = {
            CONF_WEATHER_UNITS: self._get(CONF_WEATHER_UNITS, locale_units),
            CONF_ENABLE_WEATHER_ALERTS: self._get(CONF_ENABLE_WEATHER_ALERTS, DEFAULT_ENABLE_WEATHER_ALERTS),
        }
        return self.async_show_form(
            step_id="weather",
            data_schema=self.add_suggested_values_to_schema(schema, suggested),
        )

    # -------------------------------------------------------------------------
    # Step 8: Custom Monthly Limits (manual mode only, no quiet hours)
    # -------------------------------------------------------------------------

    async def async_step_api_limits(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        if user_input is not None:
            self._options.update(user_input)
            return self._create_entry()

        interval = self._options.get(CONF_UPDATE_INTERVAL, self._get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL))
        num_loc = self._num_locations()
        enable_aq = self._options.get(CONF_ENABLE_AIR_QUALITY, self._get(CONF_ENABLE_AIR_QUALITY, DEFAULT_ENABLE_AIR_QUALITY))
        enable_pollen = self._options.get(CONF_ENABLE_POLLEN, self._get(CONF_ENABLE_POLLEN, DEFAULT_ENABLE_POLLEN))
        enable_weather = self._options.get(CONF_ENABLE_WEATHER, self._get(CONF_ENABLE_WEATHER, DEFAULT_ENABLE_WEATHER))

        summary = _usage_summary(
            interval, num_loc, enable_aq, enable_pollen, enable_weather,
            False,
            self._get(CONF_AQ_MONTHLY_LIMIT, DEFAULT_AQ_MONTHLY_LIMIT),
            self._get(CONF_POLLEN_MONTHLY_LIMIT, DEFAULT_POLLEN_MONTHLY_LIMIT),
            self._get(CONF_WEATHER_MONTHLY_LIMIT, DEFAULT_WEATHER_MONTHLY_LIMIT),
        )

        fields: dict = {}
        suggested: dict = {}

        if enable_aq:
            fields[vol.Required(CONF_AQ_MONTHLY_LIMIT)] = NumberSelector(
                NumberSelectorConfig(min=0, max=500000, step=1000, mode=NumberSelectorMode.BOX)
            )
            suggested[CONF_AQ_MONTHLY_LIMIT] = self._get(CONF_AQ_MONTHLY_LIMIT, DEFAULT_AQ_MONTHLY_LIMIT)

        if enable_pollen:
            fields[vol.Required(CONF_POLLEN_MONTHLY_LIMIT)] = NumberSelector(
                NumberSelectorConfig(min=0, max=500000, step=1000, mode=NumberSelectorMode.BOX)
            )
            suggested[CONF_POLLEN_MONTHLY_LIMIT] = self._get(CONF_POLLEN_MONTHLY_LIMIT, DEFAULT_POLLEN_MONTHLY_LIMIT)

        if enable_weather:
            fields[vol.Required(CONF_WEATHER_MONTHLY_LIMIT)] = NumberSelector(
                NumberSelectorConfig(min=0, max=500000, step=1000, mode=NumberSelectorMode.BOX)
            )
            suggested[CONF_WEATHER_MONTHLY_LIMIT] = self._get(CONF_WEATHER_MONTHLY_LIMIT, DEFAULT_WEATHER_MONTHLY_LIMIT)

        return self.async_show_form(
            step_id="api_limits",
            data_schema=self.add_suggested_values_to_schema(vol.Schema(fields), suggested),
            description_placeholders={"usage_summary": summary},
        )
