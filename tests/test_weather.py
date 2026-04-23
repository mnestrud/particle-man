"""Tests for particle_man weather platform."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.components.weather import WeatherEntityFeature

from custom_components.particle_man.coordinator import ParticleManCoordinator
from custom_components.particle_man.weather import ParticleManWeather
from tests.conftest import ENTRY_ID, TEST_API_KEY, TEST_LAT, TEST_LON, TEST_LOCATION_NAME


WEATHER_DATA = {
    "weather_current": {
        "temperature": 15.0,
        "feels_like": 13.0,
        "dew_point": 8.0,
        "humidity": 60,
        "wind_speed": 10.0,
        "wind_bearing": 270,
        "wind_gust_speed": 15.0,
        "pressure": 1013.0,
        "visibility": 16.0,
        "cloud_coverage": 10,
        "precipitation_probability": 5,
        "precipitation": 0.0,
        "condition": "sunny",
        "thunderstorm_probability": 2,
        "heat_index": 16.0,
        "wind_chill": 12.0,
    },
    "weather_hourly": [
        {
            "datetime": "2026-04-22T13:00:00+00:00",
            "native_temperature": 16.0,
            "condition": "sunny",
            "precipitation_probability": 3,
            "native_wind_speed": 8.0,
            "wind_bearing": 260,
            "humidity": 55,
        }
    ],
    "weather_daily": [
        {
            "datetime": "2026-04-22T12:00:00+00:00",
            "native_temperature": 18.0,
            "native_templow": 10.0,
            "condition": "sunny",
            "precipitation_probability": 5,
            "native_wind_speed": 12.0,
            "wind_bearing": 270,
            "humidity": 50,
        }
    ],
}


@pytest.fixture
def coord(hass: HomeAssistant, mock_config_entry) -> ParticleManCoordinator:
    mock_config_entry.add_to_hass(hass)
    with patch("custom_components.particle_man.coordinator.Store", autospec=True) as ms:
        ms.return_value.async_load = AsyncMock(return_value=None)
        ms.return_value.async_save = AsyncMock()
        c = ParticleManCoordinator(
            hass=hass,
            api_key=TEST_API_KEY,
            latitude=TEST_LAT,
            longitude=TEST_LON,
            location_name=TEST_LOCATION_NAME,
            enable_weather=True,
            entry_id=ENTRY_ID,
            config_entry=mock_config_entry,
        )
    c.data = WEATHER_DATA
    return c


def test_weather_entity_state(coord: ParticleManCoordinator) -> None:
    w = ParticleManWeather(coord)
    assert w.condition == "sunny"
    assert w.native_temperature == 15.0
    assert w.humidity == 60
    assert w.native_wind_speed == 10.0
    assert w.wind_bearing == 270


def test_weather_entity_unique_id(coord: ParticleManCoordinator) -> None:
    w = ParticleManWeather(coord)
    assert "weather" in w.unique_id


def test_weather_entity_has_entity_name(coord: ParticleManCoordinator) -> None:
    w = ParticleManWeather(coord)
    assert w._attr_has_entity_name is True


async def test_weather_hourly_forecast(coord: ParticleManCoordinator) -> None:
    w = ParticleManWeather(coord)
    forecasts = await w.async_forecast_hourly()
    assert forecasts is not None
    assert len(forecasts) == 1
    assert forecasts[0]["native_temperature"] == 16.0


async def test_weather_daily_forecast(coord: ParticleManCoordinator) -> None:
    w = ParticleManWeather(coord)
    forecasts = await w.async_forecast_daily()
    assert forecasts is not None
    assert len(forecasts) == 1
    assert forecasts[0]["native_temperature"] == 18.0


async def test_weather_forecast_none_when_no_data(coord: ParticleManCoordinator) -> None:
    coord.data = {}
    w = ParticleManWeather(coord)
    daily = await w.async_forecast_daily()
    hourly = await w.async_forecast_hourly()
    assert daily is None or daily == []
    assert hourly is None or hourly == []


def test_weather_supported_features(coord: ParticleManCoordinator) -> None:
    w = ParticleManWeather(coord)
    features = w.supported_features
    assert features is not None
    assert features & WeatherEntityFeature.FORECAST_DAILY
    assert features & WeatherEntityFeature.FORECAST_HOURLY


def test_weather_imperial_units(coord: ParticleManCoordinator) -> None:
    """IMPERIAL weather_units returns imperial unit strings (lines 89, 97, 109, 117)."""
    from homeassistant.const import (
        UnitOfLength,
        UnitOfPrecipitationDepth,
        UnitOfSpeed,
        UnitOfTemperature,
    )
    coord.weather_units = "IMPERIAL"
    w = ParticleManWeather(coord)
    assert w.native_temperature_unit == UnitOfTemperature.FAHRENHEIT
    assert w.native_wind_speed_unit == UnitOfSpeed.MILES_PER_HOUR
    assert w.native_visibility_unit == UnitOfLength.MILES
    assert w.native_precipitation_unit == UnitOfPrecipitationDepth.INCHES


def test_weather_pressure_unit_always_hpa(coord: ParticleManCoordinator) -> None:
    """native_pressure_unit always returns HPA (line 105)."""
    from homeassistant.const import UnitOfPressure
    w = ParticleManWeather(coord)
    assert w.native_pressure_unit == UnitOfPressure.HPA


def test_weather_native_precipitation(coord: ParticleManCoordinator) -> None:
    """native_precipitation reads from weather_current precipitation (line 184)."""
    coord.data["weather_current"]["precipitation"] = 2.5
    w = ParticleManWeather(coord)
    assert w.native_precipitation == 2.5


async def test_weather_twice_daily_forecast(coord: ParticleManCoordinator) -> None:
    """async_forecast_twice_daily returns twice_daily data (line 197)."""
    coord.data["weather_twice_daily"] = [
        {"datetime": "2026-04-22T12:00:00+00:00", "is_daytime": True},
        {"datetime": "2026-04-22T21:00:00+00:00", "is_daytime": False},
    ]
    w = ParticleManWeather(coord)
    result = await w.async_forecast_twice_daily()
    assert result is not None
    assert len(result) == 2
