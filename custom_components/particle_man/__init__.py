"""Particle Man integration."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import (
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
    DOMAIN,
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
    _WEATHER_CALLS_PER_POLL,
    safe_interval_minutes,
)
from .coordinator import ParticleManCoordinator, ParticleManGlobalState

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR, Platform.WEATHER, Platform.SWITCH]


def _remove_stale_devices(
    hass: HomeAssistant,
    entry: ConfigEntry,
    coordinators: dict[str, ParticleManCoordinator],
    enable_aq: bool,
    enable_pollen: bool,
    enable_weather: bool,
) -> None:
    """Remove device registry entries for locations/APIs no longer configured."""
    dev_reg = dr.async_get(hass)
    expected: set[tuple[str, str]] = {(DOMAIN, f"{entry.entry_id}_diagnostics")}
    for coordinator in coordinators.values():
        slug = coordinator.location_slug
        expected.add((DOMAIN, f"{entry.entry_id}_{slug}"))
        if enable_pollen:
            expected.add((DOMAIN, f"{entry.entry_id}_{slug}_pollen"))
        if enable_weather:
            expected.add((DOMAIN, f"{entry.entry_id}_{slug}_weather"))

    for device in dr.async_entries_for_config_entry(dev_reg, entry.entry_id):
        if not any(ident in expected for ident in device.identifiers):
            dev_reg.async_remove_device(device.id)


def _opt(entry: ConfigEntry, key: str, default: Any) -> Any:
    """Read option from options first, then data, then default."""
    return entry.options.get(key, entry.data.get(key, default))


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Particle Man from a config entry."""
    api_key = entry.data[CONF_API_KEY]
    locations = entry.options.get(CONF_LOCATIONS, [])

    if not locations:
        _LOGGER.warning("Particle Man: no locations configured for entry %s", entry.entry_id)
        entry.runtime_data = {"coordinators": {}, "global_state": ParticleManGlobalState()}
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
        entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
        return True

    # Global options (shared across all locations)
    automagic = _opt(entry, CONF_AUTOMAGIC_MODE, DEFAULT_AUTOMAGIC_MODE)
    enable_aq = _opt(entry, CONF_ENABLE_AIR_QUALITY, DEFAULT_ENABLE_AIR_QUALITY)
    enable_pollen = _opt(entry, CONF_ENABLE_POLLEN, DEFAULT_ENABLE_POLLEN)
    enable_weather = _opt(entry, CONF_ENABLE_WEATHER, DEFAULT_ENABLE_WEATHER)
    enable_weather_alerts = _opt(entry, CONF_ENABLE_WEATHER_ALERTS, DEFAULT_ENABLE_WEATHER_ALERTS)
    weather_units = _opt(entry, CONF_WEATHER_UNITS, DEFAULT_WEATHER_UNITS)
    forecast_days = _opt(entry, CONF_FORECAST_DAYS, DEFAULT_FORECAST_DAYS)
    language_code = _opt(entry, CONF_LANGUAGE, DEFAULT_LANGUAGE)
    include_plant_sensors = _opt(entry, CONF_PLANT_SENSORS, DEFAULT_PLANT_SENSORS)
    aq_monthly_limit = _opt(entry, CONF_AQ_MONTHLY_LIMIT, DEFAULT_AQ_MONTHLY_LIMIT)
    pollen_monthly_limit = _opt(entry, CONF_POLLEN_MONTHLY_LIMIT, DEFAULT_POLLEN_MONTHLY_LIMIT)
    weather_monthly_limit = _opt(entry, CONF_WEATHER_MONTHLY_LIMIT, DEFAULT_WEATHER_MONTHLY_LIMIT)
    quiet_hours_enabled = _opt(entry, CONF_QUIET_HOURS_ENABLED, DEFAULT_QUIET_HOURS_ENABLED)
    quiet_start = _opt(entry, CONF_QUIET_START, DEFAULT_QUIET_START)
    quiet_end = _opt(entry, CONF_QUIET_END, DEFAULT_QUIET_END)

    # Compute effective update interval
    num_locations = len(locations)
    if automagic:
        # AQ and pollen are always fetched hourly in the coordinator regardless of this interval.
        # Only weather drives the coordinator polling cadence.
        enabled_apis: dict[str, tuple[int, int]] = {}
        if enable_weather:
            enabled_apis["weather"] = (_WEATHER_CALLS_PER_POLL, weather_monthly_limit)
        effective_interval = safe_interval_minutes(num_locations, enabled_apis)
        _LOGGER.debug(
            "Particle Man Automagic: %d location(s) → weather interval %d min",
            num_locations, effective_interval,
        )
    else:
        effective_interval = _opt(entry, CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)

    # Shared global state (quiet hours runtime override)
    global_state = ParticleManGlobalState()

    # Create one coordinator per location
    coordinators: dict[str, ParticleManCoordinator] = {}
    for loc in locations:
        loc_name = loc.get(CONF_LOCATION_NAME, "Location")
        lat = float(loc.get(CONF_LATITUDE, 0))
        lon = float(loc.get(CONF_LONGITUDE, 0))
        loc_local_aqi = loc.get(CONF_LOCAL_AQI, DEFAULT_LOCAL_AQI)
        loc_local_aqi_code = loc.get(CONF_LOCAL_AQI_CODE, DEFAULT_LOCAL_AQI_CODE)

        coordinator = ParticleManCoordinator(
            hass=hass,
            api_key=api_key,
            latitude=lat,
            longitude=lon,
            location_name=loc_name,
            global_state=global_state,
            automagic_mode=automagic,
            num_locations=num_locations,
            update_interval_minutes=effective_interval,
            forecast_days=forecast_days,
            language_code=language_code,
            enable_local_aqi=loc_local_aqi,
            local_aqi_code=loc_local_aqi_code,
            include_plant_sensors=include_plant_sensors,
            aq_monthly_limit=aq_monthly_limit,
            pollen_monthly_limit=pollen_monthly_limit,
            weather_monthly_limit=weather_monthly_limit,
            enable_air_quality=enable_aq,
            enable_pollen=enable_pollen,
            enable_weather=enable_weather,
            enable_weather_alerts=enable_weather_alerts,
            weather_units=weather_units,
            quiet_hours_enabled=quiet_hours_enabled,
            quiet_start=quiet_start,
            quiet_end=quiet_end,
            entry_id=entry.entry_id,
            config_entry=entry,
        )
        coordinators[loc_name] = coordinator

    await asyncio.gather(
        *(c.async_config_entry_first_refresh() for c in coordinators.values())
    )

    entry.runtime_data = {
        "coordinators": coordinators,
        "global_state": global_state,
    }

    _remove_stale_devices(hass, entry, coordinators, enable_aq, enable_pollen, enable_weather)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
    return True


async def _async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry when options are updated."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok and not hass.config_entries.async_entries(DOMAIN):
        hass.data.pop(DOMAIN, None)
    return unload_ok
