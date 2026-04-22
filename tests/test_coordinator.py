"""Tests for ParticleManCoordinator."""
from contextlib import ExitStack

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import aiohttp

from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.particle_man.coordinator import (
    ParticleManCoordinator,
    _epa_category,
)

from .conftest import (
    MOCK_API_KEY,
    MOCK_LAT,
    MOCK_LON,
    MOCK_AQ_CURRENT,
    MOCK_AQ_FORECAST_HOURS,
    MOCK_POLLEN,
)

MOCK_WEATHER_CURRENT = {}
MOCK_WEATHER_HOURLY = {}
MOCK_WEATHER_DAILY = {}


@pytest.fixture
def coordinator(hass):
    with patch(
        "custom_components.particle_man.coordinator.async_get_clientsession",
        return_value=MagicMock(),
    ):
        yield ParticleManCoordinator(
            hass=hass,
            api_key=MOCK_API_KEY,
            latitude=MOCK_LAT,
            longitude=MOCK_LON,
            entry_id="test_entry",
        )


def _all_fetch_mocks(coordinator, *, aq_error=None, pollen_error=None, weather_error=None):
    """Return tuple of patch context managers that mock all fetch methods."""
    return (
        patch.object(
            coordinator, "_fetch_current",
            AsyncMock(side_effect=aq_error, return_value=None if aq_error else MOCK_AQ_CURRENT),
        ),
        patch.object(
            coordinator, "_fetch_forecast",
            AsyncMock(return_value=MOCK_AQ_FORECAST_HOURS),
        ),
        patch.object(
            coordinator, "_fetch_pollen",
            AsyncMock(side_effect=pollen_error, return_value=None if pollen_error else MOCK_POLLEN),
        ),
        patch.object(
            coordinator, "_fetch_weather_current",
            AsyncMock(side_effect=weather_error, return_value=None if weather_error else MOCK_WEATHER_CURRENT),
        ),
        patch.object(coordinator, "_fetch_weather_hourly", AsyncMock(return_value=MOCK_WEATHER_HOURLY)),
        patch.object(coordinator, "_fetch_weather_daily", AsyncMock(return_value=MOCK_WEATHER_DAILY)),
        patch.object(coordinator, "_save_tracking", AsyncMock()),
    )


# ---------------------------------------------------------------------------
# Coordinator init
# ---------------------------------------------------------------------------

async def test_coordinator_init(coordinator):
    assert coordinator.api_key == MOCK_API_KEY
    assert coordinator.latitude == MOCK_LAT
    assert coordinator.longitude == MOCK_LON
    assert coordinator._cached_tracking.get("aq_calls", 0) == 0
    assert coordinator._cached_tracking.get("pollen_calls", 0) == 0
    assert coordinator.forecast_days == 5
    assert coordinator.automagic_mode is True  # default is True (protects free tier)


# ---------------------------------------------------------------------------
# Poll cycle
# ---------------------------------------------------------------------------

async def test_update_success(coordinator):
    with ExitStack() as stack:
        for mock in _all_fetch_mocks(coordinator):
            stack.enter_context(mock)
        data = await coordinator._async_update_data()

    assert "aqi" in data
    assert data["aqi"]["value"] == 50
    assert data["aqi"]["category"] == "Good air quality"
    assert data["aqi"]["dominant_pollutant"] == "pm25"
    assert "pollutant_pm25" in data
    assert data["pollutant_pm25"]["value"] == 5.2
    assert data["pollutant_pm25"]["epa_category"] == "Good"
    assert "pollen_type_grass" in data
    assert "aq_advisory" in data


async def test_aq_error_keeps_cached_data(coordinator):
    """AQ fetch errors log a warning and preserve previously fetched data."""
    coordinator.data = {"aqi": {"value": 42, "category": "Moderate"}}

    err = aiohttp.ClientResponseError(None, (), status=403, message="Forbidden")
    with ExitStack() as stack:
        for mock in _all_fetch_mocks(coordinator, aq_error=err):
            stack.enter_context(mock)
        data = await coordinator._async_update_data()

    # Cached AQ data preserved; pollen was fetched successfully
    assert data["aqi"]["value"] == 42
    assert "pollen_type_grass" in data


async def test_all_apis_fail_no_cached_data_raises(coordinator):
    """UpdateFailed raised only when all APIs fail and there is no cached data."""
    with ExitStack() as stack:
        for mock in _all_fetch_mocks(
            coordinator,
            aq_error=Exception("aq down"),
            pollen_error=Exception("pollen down"),
            weather_error=Exception("weather down"),
        ):
            stack.enter_context(mock)
        with pytest.raises(UpdateFailed, match="No data available"):
            await coordinator._async_update_data()


async def test_pollen_failure_preserves_previous_data(coordinator):
    old_pollen = {"pollen_type_grass": {"value": 2, "category": "Low"}}
    coordinator.data = {**old_pollen}

    with (
        patch.object(coordinator, "_fetch_current", AsyncMock(return_value=MOCK_AQ_CURRENT)),
        patch.object(coordinator, "_fetch_forecast", AsyncMock(return_value=MOCK_AQ_FORECAST_HOURS)),
        patch.object(coordinator, "_fetch_pollen", AsyncMock(side_effect=Exception("pollen down"))),
        patch.object(coordinator, "_fetch_weather_current", AsyncMock(return_value=MOCK_WEATHER_CURRENT)),
        patch.object(coordinator, "_fetch_weather_hourly", AsyncMock(return_value=MOCK_WEATHER_HOURLY)),
        patch.object(coordinator, "_fetch_weather_daily", AsyncMock(return_value=MOCK_WEATHER_DAILY)),
        patch.object(coordinator, "_save_tracking", AsyncMock()),
    ):
        data = await coordinator._async_update_data()

    assert data.get("pollen_type_grass") == {"value": 2, "category": "Low"}


# ---------------------------------------------------------------------------
# Quiet hours
# ---------------------------------------------------------------------------

async def test_quiet_hours_returns_cached(coordinator):
    coordinator._quiet_hours_enabled = True
    coordinator._quiet_start = "00:00:00"
    coordinator._quiet_end = "23:59:59"
    coordinator.data = {"aqi": {"value": 55}}

    data = await coordinator._async_update_data()
    assert data == {"aqi": {"value": 55}}


# ---------------------------------------------------------------------------
# API limit enforcement
# ---------------------------------------------------------------------------

async def test_aq_limit_skips_fetch(coordinator):
    """When AQ limit is reached, AQ fetch is skipped and cached data is preserved."""
    coordinator.automagic_mode = True
    coordinator.aq_monthly_limit = 10
    coordinator._cached_tracking["aq_calls"] = 10
    coordinator.data = {"aqi": {"value": 99, "category": "Hazardous"}}

    with (
        patch.object(coordinator, "_fetch_current", AsyncMock()) as mock_current,
        patch.object(coordinator, "_fetch_forecast", AsyncMock()) as mock_forecast,
        patch.object(coordinator, "_fetch_pollen", AsyncMock(return_value=MOCK_POLLEN)),
        patch.object(coordinator, "_fetch_weather_current", AsyncMock(return_value=MOCK_WEATHER_CURRENT)),
        patch.object(coordinator, "_fetch_weather_hourly", AsyncMock(return_value=MOCK_WEATHER_HOURLY)),
        patch.object(coordinator, "_fetch_weather_daily", AsyncMock(return_value=MOCK_WEATHER_DAILY)),
        patch.object(coordinator, "_save_tracking", AsyncMock()),
    ):
        data = await coordinator._async_update_data()

    mock_current.assert_not_called()
    mock_forecast.assert_not_called()
    assert data["aqi"]["value"] == 99


async def test_limits_not_enforced_when_disabled(coordinator):
    coordinator.automagic_mode = False
    coordinator.aq_monthly_limit = 1
    coordinator._cached_tracking["aq_calls"] = 999

    with ExitStack() as stack:
        for mock in _all_fetch_mocks(coordinator):
            stack.enter_context(mock)
        data = await coordinator._async_update_data()

    assert "aqi" in data


# ---------------------------------------------------------------------------
# Pure-function unit tests
# ---------------------------------------------------------------------------

def test_epa_category_pm25_good():
    assert _epa_category("pm25", 5.0, "μg/m³") == "Good"


def test_epa_category_pm25_moderate():
    assert _epa_category("pm25", 12.0, "μg/m³") == "Moderate"


def test_epa_category_pm25_hazardous():
    assert _epa_category("pm25", 300.0, "μg/m³") == "Hazardous"


def test_epa_category_unknown_pollutant():
    assert _epa_category("xyz", 100.0, "μg/m³") is None


def test_epa_category_none_value():
    assert _epa_category("pm25", None, "μg/m³") is None


def test_compute_hourly_trend_rising():
    values = [10.0, 11.0, 12.0, 13.0, 14.0, 15.0]
    assert ParticleManCoordinator._compute_hourly_trend(values) == "rising"


def test_compute_hourly_trend_falling():
    values = [15.0, 14.0, 13.0, 12.0, 11.0, 10.0]
    assert ParticleManCoordinator._compute_hourly_trend(values) == "falling"


def test_compute_hourly_trend_stable():
    values = [50.0, 50.0, 50.0, 50.0, 50.0]
    assert ParticleManCoordinator._compute_hourly_trend(values) == "stable"


def test_compute_hourly_trend_insufficient_data():
    assert ParticleManCoordinator._compute_hourly_trend([50.0, 51.0]) == "stable"


def test_compute_pollen_trend_up():
    assert ParticleManCoordinator._compute_trend(2, [{"index": 5}]) == "up"


def test_compute_pollen_trend_down():
    assert ParticleManCoordinator._compute_trend(5, [{"index": 2}]) == "down"


def test_compute_pollen_trend_flat():
    assert ParticleManCoordinator._compute_trend(3, [{"index": 3}]) == "flat"


def test_compute_pollen_trend_no_forecast():
    assert ParticleManCoordinator._compute_trend(3, []) is None
