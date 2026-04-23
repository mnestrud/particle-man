"""Particle Man switch entities."""
from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_QUIET_HOURS_ENABLED,
    DEFAULT_QUIET_HOURS_ENABLED,
    DOMAIN,
)
from .coordinator import ParticleManGlobalState


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    runtime = entry.runtime_data
    global_state: ParticleManGlobalState = runtime["global_state"]
    config_default = entry.options.get(CONF_QUIET_HOURS_ENABLED, DEFAULT_QUIET_HOURS_ENABLED)
    async_add_entities(
        [QuietHoursSwitch(global_state, entry.entry_id, config_default)],
        False,
    )


class QuietHoursSwitch(SwitchEntity):
    """Switch to enable/disable quiet hours at runtime without entering options."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:weather-night"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_should_poll = False

    def __init__(
        self,
        global_state: ParticleManGlobalState,
        entry_id: str,
        config_default: bool,
    ) -> None:
        self._global_state = global_state
        self._entry_id = entry_id
        self._config_default = config_default
        self._attr_unique_id = f"{entry_id}_quiet_hours"

    @property
    def name(self) -> str:
        return "Quiet Hours"

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self._entry_id}_diagnostics")},
            name="Particle Man Diagnostics",
            manufacturer="Google",
            model="Particle Man",
        )

    @property
    def is_on(self) -> bool:
        return self._global_state.quiet_hours_active(self._config_default)

    async def async_turn_on(self, **kwargs: Any) -> None:
        self._global_state.set_quiet_hours_runtime(True)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        self._global_state.set_quiet_hours_runtime(False)
        self.async_write_ha_state()
