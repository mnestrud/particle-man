"""Shared test fixtures for particle_man integration tests."""
from __future__ import annotations

import asyncio
import re
import sys
from collections.abc import Generator

import pytest

from custom_components.particle_man.const import (
    CONF_API_KEY,
    CONF_AQ_MONTHLY_LIMIT,
    CONF_AUTOMAGIC_MODE,
    CONF_ENABLE_AIR_QUALITY,
    CONF_ENABLE_POLLEN,
    CONF_ENABLE_WEATHER,
    CONF_ENABLE_WEATHER_ALERTS,
    CONF_FORECAST_DAYS,
    CONF_LANGUAGE,
    CONF_LOCAL_AQI,
    CONF_LOCAL_AQI_CODE,
    CONF_LOCATION_NAME,
    CONF_LOCATIONS,
    CONF_POLLEN_MONTHLY_LIMIT,
    CONF_QUIET_END,
    CONF_QUIET_HOURS_ENABLED,
    CONF_QUIET_START,
    CONF_UPDATE_INTERVAL,
    CONF_WEATHER_MONTHLY_LIMIT,
    CONF_WEATHER_UNITS,
    DEFAULT_AQ_MONTHLY_LIMIT,
    DEFAULT_FORECAST_DAYS,
    DEFAULT_LANGUAGE,
    DEFAULT_LOCAL_AQI_CODE,
    DEFAULT_POLLEN_MONTHLY_LIMIT,
    DEFAULT_QUIET_END,
    DEFAULT_QUIET_START,
    DEFAULT_UPDATE_INTERVAL,
    DEFAULT_WEATHER_MONTHLY_LIMIT,
    DOMAIN,
)

pytest_plugins = ["pytest_homeassistant_custom_component"]

import hashlib

TEST_API_KEY = "test_api_key_12345"
TEST_LAT = 47.6062
TEST_LON = -122.3321
TEST_LOCATION_NAME = "Seattle"
ENTRY_ID = "test_entry_id"
TEST_UNIQUE_ID = hashlib.md5(TEST_API_KEY.encode()).hexdigest()

MOCK_ENTRY_DATA = {CONF_API_KEY: TEST_API_KEY}

MOCK_ENTRY_OPTIONS = {
    CONF_AUTOMAGIC_MODE: False,
    CONF_UPDATE_INTERVAL: 30,
    CONF_FORECAST_DAYS: DEFAULT_FORECAST_DAYS,
    CONF_LANGUAGE: DEFAULT_LANGUAGE,
    CONF_ENABLE_AIR_QUALITY: True,
    CONF_ENABLE_POLLEN: True,
    CONF_ENABLE_WEATHER: True,
    CONF_ENABLE_WEATHER_ALERTS: True,
    CONF_WEATHER_UNITS: "METRIC",
    CONF_AQ_MONTHLY_LIMIT: DEFAULT_AQ_MONTHLY_LIMIT,
    CONF_POLLEN_MONTHLY_LIMIT: DEFAULT_POLLEN_MONTHLY_LIMIT,
    CONF_WEATHER_MONTHLY_LIMIT: DEFAULT_WEATHER_MONTHLY_LIMIT,
    CONF_QUIET_HOURS_ENABLED: False,
    CONF_QUIET_START: DEFAULT_QUIET_START,
    CONF_QUIET_END: DEFAULT_QUIET_END,
    CONF_LOCATIONS: [
        {
            CONF_LOCATION_NAME: TEST_LOCATION_NAME,
            "latitude": TEST_LAT,
            "longitude": TEST_LON,
            CONF_LOCAL_AQI: False,
            CONF_LOCAL_AQI_CODE: DEFAULT_LOCAL_AQI_CODE,
        }
    ],
}

AQ_CURRENT_RESPONSE = {
    "dateTime": "2026-04-22T12:00:00Z",
    "regionCode": "us",
    "indexes": [
        {
            "code": "uaqi",
            "aqi": 45,
            "aqiDisplay": "45",
            "category": "Good",
            "dominantPollutant": "pm25",
        }
    ],
    "pollutants": [
        {
            "code": "pm25",
            "displayName": "PM2.5",
            "fullName": "Fine particles",
            "concentration": {"value": 5.2, "units": "MICROGRAMS_PER_CUBIC_METER"},
            "additionalInfo": {"sources": "Traffic", "effects": "Respiratory"},
        }
    ],
    "healthRecommendations": {"generalPopulation": "Air quality is good."},
}

AQ_FORECAST_RESPONSE = {"hourlyForecasts": []}

POLLEN_RESPONSE = {
    "dailyInfo": [
        {
            "date": {"year": 2026, "month": 4, "day": 22},
            "pollenTypeInfo": [
                {
                    "code": "TREE",
                    "displayName": "Tree",
                    "inSeason": True,
                    "indexInfo": {"value": 2, "category": "Low"},
                }
            ],
            "plantInfo": [
                {
                    "code": "ALDER",
                    "displayName": "Alder",
                    "inSeason": True,
                    "indexInfo": {
                        "value": 1,
                        "category": "Very Low",
                        "color": {"green": 0.8},
                    },
                    "plantDescription": {
                        "type": "TREE",
                        "family": "Betulaceae",
                        "season": "Spring",
                        "crossReaction": "None",
                        "specialColors": {"text": "Brown"},
                    },
                }
            ],
        }
    ]
}

WEATHER_CURRENT_RESPONSE = {
    "currentConditions": {
        "time": "2026-04-22T12:00:00Z",
        "isDaytime": True,
        "weatherCondition": {"type": "CLEAR"},
        "temperature": {"degrees": 15.0, "unit": "CELSIUS"},
        "feelsLikeTemperature": {"degrees": 13.0, "unit": "CELSIUS"},
        "dewPoint": {"degrees": 8.0, "unit": "CELSIUS"},
        "humidity": 60,
        "windSpeed": {"value": 10.0, "unit": "KILOMETERS_PER_HOUR"},
        "windDirection": {"degrees": 270},
        "windGust": {"value": 15.0, "unit": "KILOMETERS_PER_HOUR"},
        "pressure": {"meanSeaLevelPressure": 1013.0},
        "visibility": {"distance": 16.0, "unit": "KILOMETERS"},
        "cloudCover": 10,
        "precipitation": {
            "qpf": {"quantity": 0.0, "unit": "MILLIMETERS"},
            "probability": {"percent": 5},
        },
        "thunderstormProbability": 2,
        "heatIndex": {"degrees": 16.0, "unit": "CELSIUS"},
        "windChill": {"degrees": 12.0, "unit": "CELSIUS"},
    }
}

WEATHER_HOURLY_RESPONSE = {"forecastHours": []}
WEATHER_DAILY_RESPONSE = {"forecastDays": []}
WEATHER_ALERTS_RESPONSE = {"alerts": []}


@pytest.fixture
def mock_config_entry():
    """Return a mock config entry."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    return MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_ENTRY_DATA,
        options=MOCK_ENTRY_OPTIONS,
        entry_id=ENTRY_ID,
        unique_id=TEST_UNIQUE_ID,
        version=3,
    )


def register_api_mocks(aioclient_mock) -> None:
    """Register all API mock responses with aioclient_mock."""
    aioclient_mock.post(
        re.compile(r".*airquality\.googleapis\.com.*currentConditions.*"),
        json=AQ_CURRENT_RESPONSE,
    )
    aioclient_mock.post(
        re.compile(r".*airquality\.googleapis\.com.*forecast.*"),
        json=AQ_FORECAST_RESPONSE,
    )
    aioclient_mock.get(
        re.compile(r".*pollen\.googleapis\.com.*"),
        json=POLLEN_RESPONSE,
    )
    aioclient_mock.get(
        re.compile(r".*weather\.googleapis\.com.*currentConditions.*"),
        json=WEATHER_CURRENT_RESPONSE,
    )
    aioclient_mock.get(
        re.compile(r".*weather\.googleapis\.com.*hours.*"),
        json=WEATHER_HOURLY_RESPONSE,
    )
    aioclient_mock.get(
        re.compile(r".*weather\.googleapis\.com.*days.*"),
        json=WEATHER_DAILY_RESPONSE,
    )
    aioclient_mock.get(
        re.compile(r".*weather\.googleapis\.com.*alerts.*"),
        json=WEATHER_ALERTS_RESPONSE,
    )


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable custom integrations for all tests that use hass."""


if sys.platform == "win32":
    @pytest.fixture(scope="session")
    def event_loop_policy():
        """Use SelectorEventLoop on Windows to avoid IocpProactor/pytest-socket conflict."""
        return asyncio.WindowsSelectorEventLoopPolicy()
