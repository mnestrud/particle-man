"""Diagnostics for Particle Man integration."""
from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_API_KEY


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    runtime = entry.runtime_data or {}
    coordinators = runtime.get("coordinators", {})

    safe_data = dict(entry.data)
    if CONF_API_KEY in safe_data:
        safe_data[CONF_API_KEY] = "**REDACTED**"

    locations_diag: dict[str, Any] = {}
    for name, coordinator in coordinators.items():
        locations_diag[name] = {
            "last_update_success": coordinator.last_update_success,
            "data_keys": sorted(coordinator.data.keys()) if coordinator.data else [],
            "api_failures": dict(coordinator._api_failures),
            "api_backoff_until": {
                k: v.isoformat() for k, v in coordinator._api_backoff.items()
            },
            "cached_tracking": dict(coordinator._cached_tracking),
            "config": {
                "enable_air_quality": coordinator.enable_air_quality,
                "enable_pollen": coordinator.enable_pollen,
                "enable_weather": coordinator.enable_weather,
                "enable_weather_alerts": coordinator.enable_weather_alerts,
                "automagic_mode": coordinator.automagic_mode,
                "update_interval_minutes": int(
                    coordinator.update_interval.total_seconds() / 60
                ),
                "num_locations": coordinator.num_locations,
            },
        }

    return {
        "entry": {
            "data": safe_data,
            "options": dict(entry.options),
        },
        "locations": locations_diag,
    }
