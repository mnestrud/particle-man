"""Tests for particle_man binary_sensor platform."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.core import HomeAssistant

from custom_components.particle_man.coordinator import ParticleManCoordinator
from custom_components.particle_man.binary_sensor import PrecipitationNowSensor
from tests.conftest import ENTRY_ID, TEST_API_KEY, TEST_LAT, TEST_LON, TEST_LOCATION_NAME


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
    c.data = {"weather_current": {"condition": "sunny"}}
    return c


@pytest.mark.parametrize("condition", [
    "rainy",
    "pouring",
    "lightning-rainy",
    "hail",
    "snowy",
    "snowy-rainy",
])
def test_precipitation_now_true_for_precipitation_conditions(
    coord: ParticleManCoordinator, condition: str
) -> None:
    coord.data = {"weather_current": {"condition": condition}}
    sensor = PrecipitationNowSensor(coord)
    assert sensor.is_on is True


@pytest.mark.parametrize("condition", [
    "sunny",
    "partlycloudy",
    "cloudy",
    "windy",
    "fog",
    "clear-night",
])
def test_precipitation_now_false_for_non_precipitation_conditions(
    coord: ParticleManCoordinator, condition: str
) -> None:
    coord.data = {"weather_current": {"condition": condition}}
    sensor = PrecipitationNowSensor(coord)
    assert sensor.is_on is False


def test_precipitation_now_false_when_weather_current_absent(
    coord: ParticleManCoordinator,
) -> None:
    coord.data = {}
    sensor = PrecipitationNowSensor(coord)
    assert sensor.is_on is False


def test_precipitation_now_false_when_condition_key_missing(
    coord: ParticleManCoordinator,
) -> None:
    coord.data = {"weather_current": {"temperature": 20.0}}
    sensor = PrecipitationNowSensor(coord)
    assert sensor.is_on is False


def test_precipitation_now_device_class(coord: ParticleManCoordinator) -> None:
    sensor = PrecipitationNowSensor(coord)
    assert sensor.device_class == BinarySensorDeviceClass.MOISTURE


def test_precipitation_now_unique_id(coord: ParticleManCoordinator) -> None:
    sensor = PrecipitationNowSensor(coord)
    assert "precipitation_now" in sensor.unique_id


def test_precipitation_now_has_entity_name(coord: ParticleManCoordinator) -> None:
    sensor = PrecipitationNowSensor(coord)
    assert sensor._attr_has_entity_name is True


def test_precipitation_now_extra_state_attributes_contains_condition(
    coord: ParticleManCoordinator,
) -> None:
    coord.data = {"weather_current": {"condition": "rainy"}}
    sensor = PrecipitationNowSensor(coord)
    attrs = sensor.extra_state_attributes
    assert attrs["condition"] == "rainy"
    assert "attribution" in attrs
