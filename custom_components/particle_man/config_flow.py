"""Config flow for Particle Man integration."""
from __future__ import annotations

import logging
import math
from typing import Any

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
    CONF_ENABLE_AIR_QUALITY,
    CONF_ENABLE_POLLEN,
    CONF_ENABLE_WEATHER,
    CONF_ENABLE_WEATHER_ALERTS,
    CONF_ENFORCE_LIMITS,
    CONF_FORECAST_DAYS,
    CONF_HEALTH_RECS,
    CONF_LANGUAGE,
    CONF_LATITUDE,
    CONF_LOCAL_AQI,
    CONF_LOCAL_AQI_CODE,
    CONF_LONGITUDE,
    CONF_PLANT_DESCRIPTIONS,
    CONF_PLANT_SENSORS,
    CONF_POLLEN_MONTHLY_LIMIT,
    CONF_QUIET_END,
    CONF_QUIET_HOURS_ENABLED,
    CONF_QUIET_START,
    CONF_UPDATE_INTERVAL,
    CONF_WEATHER_MONTHLY_LIMIT,
    CONF_WEATHER_UNITS,
    DEFAULT_AQ_MONTHLY_LIMIT,
    DEFAULT_ENABLE_AIR_QUALITY,
    DEFAULT_ENABLE_POLLEN,
    DEFAULT_ENABLE_WEATHER,
    DEFAULT_ENABLE_WEATHER_ALERTS,
    DEFAULT_ENFORCE_LIMITS,
    DEFAULT_FORECAST_DAYS,
    DEFAULT_HEALTH_RECS,
    DEFAULT_LANGUAGE,
    DEFAULT_LOCAL_AQI,
    DEFAULT_LOCAL_AQI_CODE,
    DEFAULT_PLANT_DESCRIPTIONS,
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
)

_LOGGER = logging.getLogger(__name__)

_MINUTES_PER_MONTH = 30 * 24 * 60  # 43,200

# Calls per poll per enabled API
_AQ_CALLS_PER_POLL = 2
_POLLEN_CALLS_PER_POLL = 1
_WEATHER_CALLS_PER_POLL = 3


def _safe_interval_minutes(
    num_locations: int,
    enabled_apis: dict[str, tuple[int, int]],  # api → (calls_per_poll, monthly_limit)
) -> int:
    """Minimum safe polling interval to stay within free tier."""
    intervals = [
        math.ceil(_MINUTES_PER_MONTH * calls * num_locations / limit)
        for calls, limit in enabled_apis.values()
        if limit > 0
    ]
    return max(15, max(intervals)) if intervals else 15


def _projected_usage(interval: int, num_locations: int, calls_per_poll: int) -> int:
    return round(_MINUTES_PER_MONTH / interval * calls_per_poll * num_locations)


def _usage_summary(
    interval: int,
    num_locations: int,
    enable_aq: bool,
    enable_pollen: bool,
    enable_weather: bool,
    enforce: bool,
    aq_limit: int,
    pollen_limit: int,
    weather_limit: int,
) -> str:
    parts = []
    if enable_aq:
        parts.append(
            f"Air Quality ~{_projected_usage(interval, num_locations, _AQ_CALLS_PER_POLL)}"
            + (f"/{aq_limit}" if enforce else "")
        )
    if enable_pollen:
        parts.append(
            f"Pollen ~{_projected_usage(interval, num_locations, _POLLEN_CALLS_PER_POLL)}"
            + (f"/{pollen_limit}" if enforce else "")
        )
    if enable_weather:
        parts.append(
            f"Weather ~{_projected_usage(interval, num_locations, _WEATHER_CALLS_PER_POLL)}"
            + (f"/{weather_limit}" if enforce else "")
        )
    if not parts:
        return "No APIs enabled."
    loc_str = f"{num_locations} location(s)"
    return f"With {loc_str} at {interval} min — estimated monthly: {' · '.join(parts)} calls."


async def _validate_api_key(hass, api_key: str, lat: float, lon: float) -> None:
    """Raise if API key or location is invalid."""
    session = async_get_clientsession(hass)
    url = f"{BASE_URL}/currentConditions:lookup?key={api_key}"
    body = {
        "location": {"latitude": lat, "longitude": lon},
        "universalAqi": True,
    }
    async with session.post(
        url, json=body, timeout=aiohttp.ClientTimeout(total=10)
    ) as resp:
        if not resp.ok:
            error_body = await resp.text()
            _LOGGER.error(
                "Particle Man API validation failed %s: %s", resp.status, error_body
            )
        resp.raise_for_status()


# ---------------------------------------------------------------------------
# Config Flow (first-add only)
# ---------------------------------------------------------------------------

class ParticleManConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Particle Man."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> ParticleManOptionsFlow:
        return ParticleManOptionsFlow(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                await _validate_api_key(
                    self.hass,
                    user_input[CONF_API_KEY],
                    user_input[CONF_LATITUDE],
                    user_input[CONF_LONGITUDE],
                )
            except aiohttp.ClientResponseError as err:
                errors["base"] = (
                    "invalid_auth" if err.status in (400, 401, 403) else "cannot_connect"
                )
            except aiohttp.ClientError:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected error validating Particle Man key")
                errors["base"] = "unknown"
            else:
                lat = user_input[CONF_LATITUDE]
                lon = user_input[CONF_LONGITUDE]
                await self.async_set_unique_id(f"{lat:.6f},{lon:.6f}")
                self._abort_if_unique_id_configured()
                # Seed all option defaults so the integration works without
                # the user needing to open Options immediately
                seeded_options = {
                    CONF_UPDATE_INTERVAL: DEFAULT_UPDATE_INTERVAL,
                    CONF_FORECAST_DAYS: DEFAULT_FORECAST_DAYS,
                    CONF_LANGUAGE: DEFAULT_LANGUAGE,
                    CONF_LOCAL_AQI: DEFAULT_LOCAL_AQI,
                    CONF_LOCAL_AQI_CODE: DEFAULT_LOCAL_AQI_CODE,
                    CONF_HEALTH_RECS: DEFAULT_HEALTH_RECS,
                    CONF_PLANT_SENSORS: DEFAULT_PLANT_SENSORS,
                    CONF_PLANT_DESCRIPTIONS: DEFAULT_PLANT_DESCRIPTIONS,
                    CONF_ENABLE_AIR_QUALITY: DEFAULT_ENABLE_AIR_QUALITY,
                    CONF_ENABLE_POLLEN: DEFAULT_ENABLE_POLLEN,
                    CONF_ENABLE_WEATHER: DEFAULT_ENABLE_WEATHER,
                    CONF_ENABLE_WEATHER_ALERTS: DEFAULT_ENABLE_WEATHER_ALERTS,
                    CONF_WEATHER_UNITS: DEFAULT_WEATHER_UNITS,
                    CONF_ENFORCE_LIMITS: DEFAULT_ENFORCE_LIMITS,
                    CONF_AQ_MONTHLY_LIMIT: DEFAULT_AQ_MONTHLY_LIMIT,
                    CONF_POLLEN_MONTHLY_LIMIT: DEFAULT_POLLEN_MONTHLY_LIMIT,
                    CONF_WEATHER_MONTHLY_LIMIT: DEFAULT_WEATHER_MONTHLY_LIMIT,
                    CONF_QUIET_HOURS_ENABLED: DEFAULT_QUIET_HOURS_ENABLED,
                    CONF_QUIET_START: DEFAULT_QUIET_START,
                    CONF_QUIET_END: DEFAULT_QUIET_END,
                }
                return self.async_create_entry(
                    title=f"Particle Man ({lat:.4f}, {lon:.4f})",
                    data={
                        CONF_API_KEY: user_input[CONF_API_KEY],
                        CONF_LATITUDE: lat,
                        CONF_LONGITUDE: lon,
                    },
                    options=seeded_options,
                )

        # Inform user if this API key is already used by other entries
        existing = [
            e for e in self.hass.config_entries.async_entries(DOMAIN)
            if e.data.get(CONF_API_KEY) == (user_input or {}).get(CONF_API_KEY)
        ]
        placeholders: dict[str, str] = {}
        if existing:
            placeholders["num_locations"] = str(len(existing))

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_API_KEY): TextSelector(
                        TextSelectorConfig(type=TextSelectorType.PASSWORD)
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
            description_placeholders=placeholders or None,
            errors=errors,
        )


# ---------------------------------------------------------------------------
# Options Flow (up to 6 steps, conditional)
# ---------------------------------------------------------------------------

class ParticleManOptionsFlow(config_entries.OptionsFlow):
    """Multi-step options flow for Particle Man."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self.config_entry = config_entry
        self._options: dict[str, Any] = {}

    def _get(self, key: str, default: Any) -> Any:
        """Read from in-progress options, then saved options, then data, then default."""
        return self._options.get(
            key,
            self.config_entry.options.get(
                key, self.config_entry.data.get(key, default)
            ),
        )

    def _num_locations(self) -> int:
        api_key = self.config_entry.data.get(CONF_API_KEY, "")
        return sum(
            1 for e in self.hass.config_entries.async_entries(DOMAIN)
            if e.data.get(CONF_API_KEY) == api_key
        )

    def _next_step(self, after: str) -> str | None:
        """Return the next step ID after `after`, or None to create entry."""
        order = ["apis", "air_quality", "pollen", "weather", "api_limits"]
        enable_map = {
            "air_quality": self._options.get(CONF_ENABLE_AIR_QUALITY, DEFAULT_ENABLE_AIR_QUALITY),
            "pollen": self._options.get(CONF_ENABLE_POLLEN, DEFAULT_ENABLE_POLLEN),
            "weather": self._options.get(CONF_ENABLE_WEATHER, DEFAULT_ENABLE_WEATHER),
            "api_limits": not self._options.get(CONF_ENFORCE_LIMITS, DEFAULT_ENFORCE_LIMITS),
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

    # -------------------------------------------------------------------------
    # Step 1: Polling & Limits
    # -------------------------------------------------------------------------

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        if user_input is not None:
            self._options.update(user_input)
            return await self.async_step_apis()

        interval = self._get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)
        enforce = self._get(CONF_ENFORCE_LIMITS, DEFAULT_ENFORCE_LIMITS)
        num_loc = self._num_locations()
        enable_aq = self._get(CONF_ENABLE_AIR_QUALITY, DEFAULT_ENABLE_AIR_QUALITY)
        enable_pollen = self._get(CONF_ENABLE_POLLEN, DEFAULT_ENABLE_POLLEN)
        enable_weather = self._get(CONF_ENABLE_WEATHER, DEFAULT_ENABLE_WEATHER)
        aq_limit = self._get(CONF_AQ_MONTHLY_LIMIT, DEFAULT_AQ_MONTHLY_LIMIT)
        pollen_limit = self._get(CONF_POLLEN_MONTHLY_LIMIT, DEFAULT_POLLEN_MONTHLY_LIMIT)
        weather_limit = self._get(CONF_WEATHER_MONTHLY_LIMIT, DEFAULT_WEATHER_MONTHLY_LIMIT)

        # Safe interval suggestion
        enabled_apis: dict[str, tuple[int, int]] = {}
        if enable_aq:
            enabled_apis["aq"] = (_AQ_CALLS_PER_POLL, DEFAULT_AQ_MONTHLY_LIMIT)
        if enable_pollen:
            enabled_apis["pollen"] = (_POLLEN_CALLS_PER_POLL, DEFAULT_POLLEN_MONTHLY_LIMIT)
        if enable_weather:
            enabled_apis["weather"] = (_WEATHER_CALLS_PER_POLL, DEFAULT_WEATHER_MONTHLY_LIMIT)
        safe = _safe_interval_minutes(num_loc, enabled_apis)

        summary = _usage_summary(
            interval, num_loc, enable_aq, enable_pollen, enable_weather,
            enforce, aq_limit, pollen_limit, weather_limit,
        )
        if enforce:
            usage_text = f"{summary} Suggested minimum: {safe} min."
        else:
            usage_text = f"{summary} Set your own limits on the last page."

        schema = vol.Schema(
            {
                vol.Required(CONF_LATITUDE): NumberSelector(
                    NumberSelectorConfig(min=-90, max=90, step="any", mode=NumberSelectorMode.BOX)
                ),
                vol.Required(CONF_LONGITUDE): NumberSelector(
                    NumberSelectorConfig(min=-180, max=180, step="any", mode=NumberSelectorMode.BOX)
                ),
                vol.Required(CONF_UPDATE_INTERVAL): NumberSelector(
                    NumberSelectorConfig(
                        min=15, max=1440, step=5, unit_of_measurement="min",
                        mode=NumberSelectorMode.BOX,
                    )
                ),
                vol.Required(CONF_ENFORCE_LIMITS): BooleanSelector(),
            }
        )

        suggested = {
            CONF_LATITUDE: self._get(CONF_LATITUDE, self.hass.config.latitude),
            CONF_LONGITUDE: self._get(CONF_LONGITUDE, self.hass.config.longitude),
            CONF_UPDATE_INTERVAL: self._get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL),
            CONF_ENFORCE_LIMITS: self._get(CONF_ENFORCE_LIMITS, DEFAULT_ENFORCE_LIMITS),
        }

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(schema, suggested),
            description_placeholders={"usage_summary": usage_text},
        )

    # -------------------------------------------------------------------------
    # Step 2: Data Sources
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

        schema = vol.Schema(
            {
                vol.Required(CONF_ENABLE_AIR_QUALITY): BooleanSelector(),
                vol.Required(CONF_ENABLE_POLLEN): BooleanSelector(),
                vol.Required(CONF_ENABLE_WEATHER): BooleanSelector(),
            }
        )
        suggested = {
            CONF_ENABLE_AIR_QUALITY: self._get(CONF_ENABLE_AIR_QUALITY, DEFAULT_ENABLE_AIR_QUALITY),
            CONF_ENABLE_POLLEN: self._get(CONF_ENABLE_POLLEN, DEFAULT_ENABLE_POLLEN),
            CONF_ENABLE_WEATHER: self._get(CONF_ENABLE_WEATHER, DEFAULT_ENABLE_WEATHER),
        }
        return self.async_show_form(
            step_id="apis",
            data_schema=self.add_suggested_values_to_schema(schema, suggested),
        )

    # -------------------------------------------------------------------------
    # Step 3: Air Quality Options (conditional)
    # -------------------------------------------------------------------------

    async def async_step_air_quality(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        if user_input is not None:
            self._options.update(user_input)
            next_step = self._next_step("air_quality")
            if next_step:
                return await getattr(self, f"async_step_{next_step}")()
            return self._create_entry()

        schema = vol.Schema(
            {
                vol.Required(CONF_FORECAST_DAYS): NumberSelector(
                    NumberSelectorConfig(min=1, max=5, step=1, mode=NumberSelectorMode.SLIDER)
                ),
                vol.Required(CONF_LANGUAGE): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.TEXT)
                ),
                vol.Required(CONF_LOCAL_AQI): BooleanSelector(),
                vol.Required(CONF_LOCAL_AQI_CODE): SelectSelector(
                    SelectSelectorConfig(options=LOCAL_AQI_CODES, mode=SelectSelectorMode.DROPDOWN)
                ),
                vol.Required(CONF_HEALTH_RECS): BooleanSelector(),
            }
        )
        suggested = {
            CONF_FORECAST_DAYS: self._get(CONF_FORECAST_DAYS, DEFAULT_FORECAST_DAYS),
            CONF_LANGUAGE: self._get(CONF_LANGUAGE, DEFAULT_LANGUAGE),
            CONF_LOCAL_AQI: self._get(CONF_LOCAL_AQI, DEFAULT_LOCAL_AQI),
            CONF_LOCAL_AQI_CODE: self._get(CONF_LOCAL_AQI_CODE, DEFAULT_LOCAL_AQI_CODE),
            CONF_HEALTH_RECS: self._get(CONF_HEALTH_RECS, DEFAULT_HEALTH_RECS),
        }
        return self.async_show_form(
            step_id="air_quality",
            data_schema=self.add_suggested_values_to_schema(schema, suggested),
        )

    # -------------------------------------------------------------------------
    # Step 4: Pollen Options (conditional)
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

        schema = vol.Schema(
            {
                vol.Required(CONF_PLANT_SENSORS): BooleanSelector(),
                vol.Required(CONF_PLANT_DESCRIPTIONS): BooleanSelector(),
            }
        )
        suggested = {
            CONF_PLANT_SENSORS: self._get(CONF_PLANT_SENSORS, DEFAULT_PLANT_SENSORS),
            CONF_PLANT_DESCRIPTIONS: self._get(CONF_PLANT_DESCRIPTIONS, DEFAULT_PLANT_DESCRIPTIONS),
        }
        return self.async_show_form(
            step_id="pollen",
            data_schema=self.add_suggested_values_to_schema(schema, suggested),
        )

    # -------------------------------------------------------------------------
    # Step 5: Weather Options (conditional)
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

        schema = vol.Schema(
            {
                vol.Required(CONF_WEATHER_UNITS): SelectSelector(
                    SelectSelectorConfig(
                        options=["METRIC", "IMPERIAL"],
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Required(CONF_ENABLE_WEATHER_ALERTS): BooleanSelector(),
            }
        )
        suggested = {
            CONF_WEATHER_UNITS: self._get(CONF_WEATHER_UNITS, DEFAULT_WEATHER_UNITS),
            CONF_ENABLE_WEATHER_ALERTS: self._get(CONF_ENABLE_WEATHER_ALERTS, DEFAULT_ENABLE_WEATHER_ALERTS),
        }
        return self.async_show_form(
            step_id="weather",
            data_schema=self.add_suggested_values_to_schema(schema, suggested),
        )

    # -------------------------------------------------------------------------
    # Step 6: Custom Limits & Quiet Hours (conditional — enforce_limits=False only)
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

        fields[vol.Required(CONF_QUIET_HOURS_ENABLED)] = BooleanSelector()
        fields[vol.Required(CONF_QUIET_START)] = TimeSelector()
        fields[vol.Required(CONF_QUIET_END)] = TimeSelector()
        suggested[CONF_QUIET_HOURS_ENABLED] = self._get(CONF_QUIET_HOURS_ENABLED, DEFAULT_QUIET_HOURS_ENABLED)
        suggested[CONF_QUIET_START] = self._get(CONF_QUIET_START, DEFAULT_QUIET_START)
        suggested[CONF_QUIET_END] = self._get(CONF_QUIET_END, DEFAULT_QUIET_END)

        return self.async_show_form(
            step_id="api_limits",
            data_schema=self.add_suggested_values_to_schema(vol.Schema(fields), suggested),
            description_placeholders={"usage_summary": summary},
        )

    # -------------------------------------------------------------------------
    # Final step helper
    # -------------------------------------------------------------------------

    def _create_entry(self) -> config_entries.ConfigFlowResult:
        """Merge accumulated options with existing saved options and create entry."""
        merged = dict(self.config_entry.options)
        merged.update(self._options)
        return self.async_create_entry(title="", data=merged)
