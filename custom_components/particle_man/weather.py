"""Particle Man weather entity."""
from __future__ import annotations

from datetime import timedelta
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
from homeassistant.core import (
    HomeAssistant,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.helpers import entity_platform
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import DOMAIN, WEATHER_ATTRIBUTION
from .coordinator import ParticleManCoordinator

PARALLEL_UPDATES = 1

SERVICE_GET_MINUTE_FORECAST = "get_minute_forecast"


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

    # Matches the convention core's OpenWeatherMap integration established and
    # that nowcast-capable frontend cards look for, resolving the service
    # domain from the entity's platform.
    entity_platform.async_get_current_platform().async_register_entity_service(
        SERVICE_GET_MINUTE_FORECAST,
        None,
        "async_get_minute_forecast",
        supports_response=SupportsResponse.ONLY,
    )


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
    def ozone(self) -> float | None:
        return (self.coordinator.data.get("pollutant_o3") or {}).get("value")

    # -------------------------------------------------------------------------
    # Forecast methods
    # -------------------------------------------------------------------------

    async def async_forecast_hourly(self) -> list[Forecast] | None:
        forecasts = self.coordinator.data.get("weather_hourly")
        if not forecasts:
            return None
        now_hour = dt_util.utcnow().replace(minute=0, second=0, microsecond=0)
        result = [
            f for f in forecasts
            if (dt := dt_util.parse_datetime(f.get("datetime", ""))) is not None
            and dt >= now_hour
        ]
        return result or None

    async def async_forecast_daily(self) -> list[Forecast] | None:
        return self.coordinator.data.get("weather_daily") or None

    async def async_forecast_twice_daily(self) -> list[Forecast] | None:
        return self.coordinator.data.get("weather_twice_daily") or None

    async def async_get_minute_forecast(self) -> ServiceResponse:
        """Return the minute-by-minute precipitation nowcast.

        The two canonical keys — `datetime` and `precipitation` in mm/h — match
        what core's OpenWeatherMap integration returns, so cards built against
        that convention work unmodified. Richer fields are added alongside them,
        never instead of them.

        Only the first hour is returned. Consumers of this convention expect a
        roughly 60-minute window, and the full six hours is available on the
        nowcast sensor's attributes for anything that wants it.

        `precipitation` is derived by dividing each segment's forecast quantity
        by its duration. Google does not document whether that quantity is an
        accumulation for the bucket or already a rate; this assumes the former.
        """
        info = self.coordinator.data.get("weather_minute") or {}
        now = dt_util.utcnow()
        cutoff = now + timedelta(hours=1)
        forecast: list[dict[str, Any]] = []

        for seg in info.get("segments") or []:
            start = dt_util.parse_datetime(seg.get("start") or "")
            end = dt_util.parse_datetime(seg.get("end") or "")
            if start is None or end is None or start >= cutoff:
                continue

            hours = (end - start).total_seconds() / 3600
            qpf = seg.get("qpf")
            if isinstance(qpf, (int, float)) and hours > 0:
                rate: float | None = round(qpf / hours, 4)
            else:
                rate = 0.0 if qpf is None else None

            forecast.append({
                "datetime": seg["start"],
                # A dry segment is 0, not absent — omitting it would make
                # consumers draw a gap where there is simply no rain.
                "precipitation": rate if seg.get("precipitation") else 0.0,
                "type": seg.get("type"),
                "probability": seg.get("probability"),
                "intensity": seg.get("intensity"),
                "end": seg.get("end"),
            })

        return {"forecast": cast("list[Any]", forecast)}
