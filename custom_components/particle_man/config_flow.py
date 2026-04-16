"""Config flow for Particle Man integration."""
from __future__ import annotations

import logging
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
)

from .const import (
    BASE_URL,
    CONF_API_KEY,
    CONF_FORECAST_DAYS,
    CONF_HEALTH_RECS,
    CONF_LANGUAGE,
    CONF_LATITUDE,
    CONF_LOCAL_AQI,
    CONF_LOCAL_AQI_CODE,
    CONF_LONGITUDE,
    CONF_PLANT_DESCRIPTIONS,
    CONF_PLANT_SENSORS,
    CONF_UPDATE_INTERVAL,
    DEFAULT_FORECAST_DAYS,
    DEFAULT_HEALTH_RECS,
    DEFAULT_LANGUAGE,
    DEFAULT_LOCAL_AQI,
    DEFAULT_LOCAL_AQI_CODE,
    DEFAULT_PLANT_DESCRIPTIONS,
    DEFAULT_PLANT_SENSORS,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    LOCAL_AQI_CODES,
)

_LOGGER = logging.getLogger(__name__)

# Memorial Stadium, Lincoln NE (fallback only — real entries always have lat/lon in data)
_DEFAULT_LAT = 40.8209
_DEFAULT_LON = -96.7058


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
                "Particle Man API validation failed %s: %s",
                resp.status,
                error_body,
            )
        resp.raise_for_status()


class ParticleManConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Particle Man."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> ParticleManOptionsFlow:
        """Return the options flow handler."""
        return ParticleManOptionsFlow()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
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
                _LOGGER.warning("Particle Man validation error: %s", err)
                errors["base"] = (
                    "invalid_auth" if err.status in (400, 401, 403) else "cannot_connect"
                )
            except aiohttp.ClientError as err:
                _LOGGER.warning("Particle Man connection error: %s", err)
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error validating Particle Man key")
                errors["base"] = "unknown"
            else:
                lat = user_input[CONF_LATITUDE]
                lon = user_input[CONF_LONGITUDE]
                await self.async_set_unique_id(f"{lat:.6f},{lon:.6f}")
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"Particle Man ({lat:.4f}, {lon:.4f})",
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_API_KEY): TextSelector(
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
                    vol.Optional(
                        CONF_UPDATE_INTERVAL, default=DEFAULT_UPDATE_INTERVAL
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=15, max=1440, step=5, unit_of_measurement="min", mode=NumberSelectorMode.BOX
                        )
                    ),
                }
            ),
            errors=errors,
        )


class ParticleManOptionsFlow(config_entries.OptionsFlow):
    """Handle options for Particle Man."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Show the options form."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        def _get(key, default):
            return self.config_entry.options.get(
                key, self.config_entry.data.get(key, default)
            )

        schema = vol.Schema(
            {
                vol.Required(CONF_LATITUDE): NumberSelector(
                    NumberSelectorConfig(min=-90, max=90, step="any", mode=NumberSelectorMode.BOX)
                ),
                vol.Required(CONF_LONGITUDE): NumberSelector(
                    NumberSelectorConfig(min=-180, max=180, step="any", mode=NumberSelectorMode.BOX)
                ),
                vol.Required(CONF_UPDATE_INTERVAL): NumberSelector(
                    NumberSelectorConfig(min=15, max=1440, step=5, unit_of_measurement="min", mode=NumberSelectorMode.BOX)
                ),
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
                vol.Required(CONF_PLANT_SENSORS): BooleanSelector(),
                vol.Required(CONF_PLANT_DESCRIPTIONS): BooleanSelector(),
            }
        )

        suggested = {
            CONF_LATITUDE: _get(CONF_LATITUDE, _DEFAULT_LAT),
            CONF_LONGITUDE: _get(CONF_LONGITUDE, _DEFAULT_LON),
            CONF_UPDATE_INTERVAL: _get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL),
            CONF_FORECAST_DAYS: _get(CONF_FORECAST_DAYS, DEFAULT_FORECAST_DAYS),
            CONF_LANGUAGE: _get(CONF_LANGUAGE, DEFAULT_LANGUAGE),
            CONF_LOCAL_AQI: _get(CONF_LOCAL_AQI, DEFAULT_LOCAL_AQI),
            CONF_LOCAL_AQI_CODE: _get(CONF_LOCAL_AQI_CODE, DEFAULT_LOCAL_AQI_CODE),
            CONF_HEALTH_RECS: _get(CONF_HEALTH_RECS, DEFAULT_HEALTH_RECS),
            CONF_PLANT_SENSORS: _get(CONF_PLANT_SENSORS, DEFAULT_PLANT_SENSORS),
            CONF_PLANT_DESCRIPTIONS: _get(CONF_PLANT_DESCRIPTIONS, DEFAULT_PLANT_DESCRIPTIONS),
        }

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(schema, suggested),
        )
