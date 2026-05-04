"""Particle Man binary sensor platform."""
from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ATTRIBUTION
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, WEATHER_ATTRIBUTION
from .coordinator import ParticleManCoordinator

PARALLEL_UPDATES = 1

_PRECIPITATION_CONDITIONS: frozenset[str] = frozenset({
    "rainy",
    "pouring",
    "lightning-rainy",
    "hail",
    "snowy",
    "snowy-rainy",
})


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up binary sensor entities from a config entry."""
    runtime = entry.runtime_data
    coordinators = runtime.get("coordinators", {})
    entities = [
        PrecipitationNowSensor(coordinator)
        for coordinator in coordinators.values()
        if coordinator.enable_weather
    ]
    async_add_entities(entities, True)


class PrecipitationNowSensor(CoordinatorEntity[ParticleManCoordinator], BinarySensorEntity):
    """Binary sensor: True when precipitation is currently occurring."""

    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.MOISTURE
    _attr_translation_key = "precipitation_now"

    def __init__(self, coordinator: ParticleManCoordinator) -> None:
        super().__init__(coordinator)
        self.coordinator = coordinator
        self._attr_unique_id = (
            f"{coordinator.entry_id}_{coordinator.location_slug}_precipitation_now"
        )

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={
                (DOMAIN, f"{self.coordinator.entry_id}_{self.coordinator.location_slug}_weather")
            },
            name=f"{self.coordinator.location_name} Weather",
            manufacturer="Google",
            model="Weather API",
            via_device=(
                DOMAIN,
                f"{self.coordinator.entry_id}_{self.coordinator.location_slug}",
            ),
        )

    @property
    def is_on(self) -> bool:
        condition = self.coordinator.data.get("weather_current", {}).get("condition")
        return condition in _PRECIPITATION_CONDITIONS

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "condition": self.coordinator.data.get("weather_current", {}).get("condition"),
            ATTR_ATTRIBUTION: WEATHER_ATTRIBUTION,
        }
