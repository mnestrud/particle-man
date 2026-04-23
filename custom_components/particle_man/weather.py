"""Particle Man weather entity."""
from __future__ import annotations

from typing import Any, cast

from homeassistant.components.weather import (  # type: ignore[attr-defined]
    Forecast,
    WeatherEntity,
    WeatherEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    UnitOfLength,
    UnitOfPrecipitationDepth,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, WEATHER_ATTRIBUTION
from .coordinator import ParticleManCoordinator

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up weather entities from a config entry."""
    runtime = entry.runtime_data
    coordinators = runtime.get("coordinators", {})
    entities = [
        ParticleManWeather(coordinator)
        for coordinator in coordinators.values()
        if coordinator.enable_weather
    ]
    async_add_entities(entities, True)


class ParticleManWeather(CoordinatorEntity[ParticleManCoordinator], WeatherEntity):
    """Weather entity backed by Google Weather API."""

    _attr_has_entity_name = True
    _attr_name = None  # entity name = device name
    _attr_supported_features = (
        WeatherEntityFeature.FORECAST_DAILY
        | WeatherEntityFeature.FORECAST_HOURLY
        | WeatherEntityFeature.FORECAST_TWICE_DAILY
    )

    def __init__(self, coordinator: ParticleManCoordinator) -> None:
        super().__init__(coordinator)
        self.coordinator = coordinator
        self._attr_unique_id = (
            f"{coordinator.entry_id}_{coordinator.location_slug}_weather"
        )
        self._attr_attribution = WEATHER_ATTRIBUTION

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

    @callback
    def _handle_coordinator_update(self) -> None:
        super()._handle_coordinator_update()
        self.hass.async_create_task(self.async_update_listeners(None))

    # -------------------------------------------------------------------------
    # Unit declarations (depend on weather_units setting)
    # -------------------------------------------------------------------------

    @property
    def native_temperature_unit(self) -> str:
        return (
            UnitOfTemperature.CELSIUS
            if self.coordinator.weather_units == "METRIC"
            else UnitOfTemperature.FAHRENHEIT
        )

    @property
    def native_wind_speed_unit(self) -> str:
        return (
            UnitOfSpeed.KILOMETERS_PER_HOUR
            if self.coordinator.weather_units == "METRIC"
            else UnitOfSpeed.MILES_PER_HOUR
        )

    @property
    def native_pressure_unit(self) -> str:
        return UnitOfPressure.HPA  # Google always returns hPa (mean sea level millibars)

    @property
    def native_visibility_unit(self) -> str:
        return (
            UnitOfLength.KILOMETERS
            if self.coordinator.weather_units == "METRIC"
            else UnitOfLength.MILES
        )

    @property
    def native_precipitation_unit(self) -> str:
        return (
            UnitOfPrecipitationDepth.MILLIMETERS
            if self.coordinator.weather_units == "METRIC"
            else UnitOfPrecipitationDepth.INCHES
        )

    # -------------------------------------------------------------------------
    # Current condition properties
    # -------------------------------------------------------------------------

    @property
    def _current(self) -> dict[str, Any]:
        return cast(dict[str, Any], self.coordinator.data.get("weather_current", {}))

    @property
    def condition(self) -> str | None:
        return self._current.get("condition")

    @property
    def native_temperature(self) -> float | None:
        return self._current.get("temperature")

    @property
    def native_apparent_temperature(self) -> float | None:
        return self._current.get("apparent_temperature")

    @property
    def native_dew_point(self) -> float | None:
        return self._current.get("dew_point")

    @property
    def humidity(self) -> int | None:
        val = self._current.get("humidity")
        return int(val) if val is not None else None

    @property
    def native_wind_speed(self) -> float | None:
        return self._current.get("wind_speed")

    @property
    def wind_bearing(self) -> int | None:
        val = self._current.get("wind_bearing")
        return int(val) if val is not None else None

    @property
    def native_wind_gust_speed(self) -> float | None:
        return self._current.get("wind_gust_speed")

    @property
    def native_pressure(self) -> float | None:
        return self._current.get("pressure")

    @property
    def native_visibility(self) -> float | None:
        return self._current.get("visibility")

    @property
    def uv_index(self) -> float | None:
        return self._current.get("uv_index")

    @property
    def cloud_coverage(self) -> int | None:
        val = self._current.get("cloud_coverage")
        return int(val) if val is not None else None

    @property
    def native_precipitation(self) -> float | None:
        return self._current.get("precipitation")

    # -------------------------------------------------------------------------
    # Forecast methods
    # -------------------------------------------------------------------------

    async def async_forecast_hourly(self) -> list[Forecast] | None:
        return self.coordinator.data.get("weather_hourly") or None

    async def async_forecast_daily(self) -> list[Forecast] | None:
        return self.coordinator.data.get("weather_daily") or None

    async def async_forecast_twice_daily(self) -> list[Forecast] | None:
        return self.coordinator.data.get("weather_twice_daily") or None
