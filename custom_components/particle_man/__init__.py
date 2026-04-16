"""Particle Man integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import (
    CONF_AQ_MONTHLY_LIMIT,
    CONF_API_KEY,
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
    CONF_RESET_DAY,
    CONF_UPDATE_INTERVAL,
    DEFAULT_AQ_MONTHLY_LIMIT,
    DEFAULT_ENFORCE_LIMITS,
    DEFAULT_FORECAST_DAYS,
    DEFAULT_HEALTH_RECS,
    DEFAULT_LANGUAGE,
    DEFAULT_LOCAL_AQI,
    DEFAULT_LOCAL_AQI_CODE,
    DEFAULT_PLANT_DESCRIPTIONS,
    DEFAULT_PLANT_SENSORS,
    DEFAULT_POLLEN_MONTHLY_LIMIT,
    DEFAULT_RESET_DAY,
    DEFAULT_UPDATE_INTERVAL,
)
from .coordinator import GoogleAirQualityCoordinator

PLATFORMS = [Platform.SENSOR]


def _opt(entry: ConfigEntry, key: str, default):
    """Read option from options first, then data, then default."""
    return entry.options.get(key, entry.data.get(key, default))


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Particle Man from a config entry."""
    coordinator = GoogleAirQualityCoordinator(
        hass=hass,
        api_key=entry.data[CONF_API_KEY],
        latitude=_opt(entry, CONF_LATITUDE, entry.data[CONF_LATITUDE]),
        longitude=_opt(entry, CONF_LONGITUDE, entry.data[CONF_LONGITUDE]),
        update_interval_minutes=_opt(entry, CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL),
        forecast_days=_opt(entry, CONF_FORECAST_DAYS, DEFAULT_FORECAST_DAYS),
        language_code=_opt(entry, CONF_LANGUAGE, DEFAULT_LANGUAGE),
        enable_local_aqi=_opt(entry, CONF_LOCAL_AQI, DEFAULT_LOCAL_AQI),
        local_aqi_code=_opt(entry, CONF_LOCAL_AQI_CODE, DEFAULT_LOCAL_AQI_CODE),
        include_health_recs=_opt(entry, CONF_HEALTH_RECS, DEFAULT_HEALTH_RECS),
        include_plant_sensors=_opt(entry, CONF_PLANT_SENSORS, DEFAULT_PLANT_SENSORS),
        include_plant_descriptions=_opt(entry, CONF_PLANT_DESCRIPTIONS, DEFAULT_PLANT_DESCRIPTIONS),
        aq_monthly_limit=_opt(entry, CONF_AQ_MONTHLY_LIMIT, DEFAULT_AQ_MONTHLY_LIMIT),
        pollen_monthly_limit=_opt(entry, CONF_POLLEN_MONTHLY_LIMIT, DEFAULT_POLLEN_MONTHLY_LIMIT),
        reset_day=_opt(entry, CONF_RESET_DAY, DEFAULT_RESET_DAY),
        enforce_limits=_opt(entry, CONF_ENFORCE_LIMITS, DEFAULT_ENFORCE_LIMITS),
        entry_id=entry.entry_id,
    )
    await coordinator.async_load_tracking()
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
    return True


async def _async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry when options are updated."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
