"""Shared fixtures and mock payloads for Particle Man tests."""
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable custom integrations for all tests."""
    yield

from custom_components.particle_man.const import (
    CONF_API_KEY,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_UPDATE_INTERVAL,
    DOMAIN,
)

MOCK_API_KEY = "fake_key_abc123"
MOCK_LAT = 41.8781
MOCK_LON = -87.6298

MOCK_AQ_CURRENT = {
    "dateTime": "2024-01-15T12:00:00Z",
    "regionCode": "us",
    "indexes": [
        {
            "code": "uaqi",
            "displayName": "Universal AQI",
            "aqi": 50,
            "aqiDisplay": "50",
            "category": "Good air quality",
            "dominantPollutant": "pm25",
        }
    ],
    "pollutants": [
        {
            "code": "pm25",
            "displayName": "PM2.5",
            "fullName": "Fine particulate matter (<2.5µm)",
            "concentration": {"value": 5.2, "units": "MICROGRAMS_PER_CUBIC_METER"},
            "additionalInfo": {"sources": "Multiple", "effects": "Respiratory"},
        }
    ],
}

MOCK_AQ_FORECAST_HOURS = [
    {
        "dateTime": "2024-01-15T13:00:00Z",
        "indexes": [
            {
                "code": "uaqi",
                "aqi": 48,
                "category": "Good air quality",
                "dominantPollutant": "pm25",
            }
        ],
        "pollutants": [
            {
                "code": "pm25",
                "concentration": {"value": 4.5, "units": "MICROGRAMS_PER_CUBIC_METER"},
            }
        ],
    }
]

MOCK_POLLEN = {
    "dailyInfo": [
        {
            "date": {"year": 2024, "month": 1, "day": 15},
            "pollenTypeInfo": [
                {
                    "code": "GRASS",
                    "displayName": "Grass",
                    "inSeason": False,
                    "indexInfo": {
                        "value": 0,
                        "category": "None",
                        "color": {"red": 0.619, "green": 0.619, "blue": 0.619},
                    },
                }
            ],
            "plantInfo": [],
        },
        {
            "date": {"year": 2024, "month": 1, "day": 16},
            "pollenTypeInfo": [
                {
                    "code": "GRASS",
                    "displayName": "Grass",
                    "inSeason": False,
                    "indexInfo": {
                        "value": 0,
                        "category": "None",
                        "color": {"red": 0.619, "green": 0.619, "blue": 0.619},
                    },
                }
            ],
            "plantInfo": [],
        },
    ]
}


@pytest.fixture
def mock_config_entry():
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_API_KEY: MOCK_API_KEY,
            CONF_LATITUDE: MOCK_LAT,
            CONF_LONGITUDE: MOCK_LON,
            CONF_UPDATE_INTERVAL: 60,
        },
        entry_id="test_entry_id",
    )
