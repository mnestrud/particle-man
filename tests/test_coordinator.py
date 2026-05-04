"""Tests for the particle_man coordinator."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed

from custom_components.particle_man.const import DOMAIN, EPA_BREAKPOINTS
from custom_components.particle_man.coordinator import (
    ParticleManCoordinator,
    ParticleManGlobalState,
    _aq_advisory_level,
    _day_to_datetime,
    _epa_category,
    _normalize_channel,
    _parse_units,
    _rgb_from_api,
    _rgb_to_hex,
    _to_canonical,
    _w_condition,
    _w_degrees,
)
from tests.conftest import (
    AQ_CURRENT_RESPONSE,
    AQ_FORECAST_RESPONSE,
    POLLEN_RESPONSE,
    TEST_API_KEY,
    TEST_LAT,
    TEST_LON,
    TEST_LOCATION_NAME,
    WEATHER_ALERTS_RESPONSE,
    WEATHER_CURRENT_RESPONSE,
    WEATHER_DAILY_RESPONSE,
    WEATHER_HOURLY_RESPONSE,
    register_api_mocks,
)


# ---------------------------------------------------------------------------
# Pure function tests
# ---------------------------------------------------------------------------


def test_parse_units() -> None:
    assert _parse_units("PARTS_PER_BILLION") == "ppb"
    assert _parse_units("PARTS_PER_MILLION") == "ppm"
    assert _parse_units("MICROGRAMS_PER_CUBIC_METER") == "μg/m³"
    assert _parse_units("UNKNOWN") == "μg/m³"


def test_epa_category_pm25() -> None:
    assert _epa_category("pm25", 5.0, "μg/m³") == "Good"
    assert _epa_category("pm25", 20.0, "μg/m³") == "Moderate"
    assert _epa_category("pm25", 45.0, "μg/m³") == "Unhealthy for Sensitive Groups"
    assert _epa_category("pm25", 60.0, "μg/m³") == "Unhealthy"
    assert _epa_category("pm25", 130.0, "μg/m³") == "Very Unhealthy"
    assert _epa_category("pm25", 300.0, "μg/m³") == "Hazardous"


def test_epa_category_pm10() -> None:
    assert _epa_category("pm10", 30.0, "μg/m³") == "Good"
    assert _epa_category("pm10", 100.0, "μg/m³") == "Moderate"


def test_epa_category_o3_ppm() -> None:
    assert _epa_category("o3", 0.040, "ppm") == "Good"
    assert _epa_category("o3", 0.065, "ppm") == "Moderate"


def test_epa_category_no2_ppb() -> None:
    assert _epa_category("no2", 30.0, "ppb") == "Good"
    assert _epa_category("no2", 80.0, "ppb") == "Moderate"


def test_epa_category_none_value() -> None:
    assert _epa_category("pm25", None, "μg/m³") is None


def test_epa_category_unknown_pollutant() -> None:
    assert _epa_category("benzene", 1.0, "μg/m³") is None


def test_to_canonical_same_units() -> None:
    """No conversion when units match."""
    assert _to_canonical(10.0, "μg/m³", "μg/m³", "pm25") == 10.0


def test_to_canonical_ug_to_ppb_no2() -> None:
    """μg/m³ → ppb for NO2 (MW=46)."""
    val_ppb = 10.0 * (24.45 / 46.0)
    result = _to_canonical(10.0, "μg/m³", "ppb", "no2")
    assert abs(result - val_ppb) < 0.001


def test_to_canonical_ppb_to_ppm() -> None:
    """ppb → ppm."""
    result = _to_canonical(1000.0, "ppb", "ppm", "o3")
    assert abs(result - 1.0) < 0.001


def test_to_canonical_ppm_to_ppb() -> None:
    """ppm → ppb."""
    result = _to_canonical(1.0, "ppm", "ppb", "so2")
    assert abs(result - 1000.0) < 0.001


def test_to_canonical_no_mw() -> None:
    """Unknown pollutant: no molecular weight → value unchanged."""
    assert _to_canonical(5.0, "μg/m³", "ppb", "unknown_gas") == 5.0


def test_normalize_channel_float() -> None:
    assert _normalize_channel(0.5) == 128
    assert _normalize_channel(1.0) == 255
    assert _normalize_channel(0.0) == 0


def test_normalize_channel_int() -> None:
    assert _normalize_channel(200) == 200
    assert _normalize_channel(300) == 255
    assert _normalize_channel(-5) == 0


def test_rgb_from_api_valid() -> None:
    assert _rgb_from_api({"red": 1.0, "green": 0.5, "blue": 0.0}) == (255, 128, 0)


def test_rgb_from_api_invalid() -> None:
    assert _rgb_from_api(None) is None
    assert _rgb_from_api({}) is None
    assert _rgb_from_api("bad") is None


def test_rgb_to_hex() -> None:
    assert _rgb_to_hex((255, 0, 0)) == "#ff0000"
    assert _rgb_to_hex((0, 128, 255)) == "#0080ff"
    assert _rgb_to_hex(None) is None


def test_day_to_datetime() -> None:
    result = _day_to_datetime({"year": 2026, "month": 4, "day": 22})
    assert result == "2026-04-22T12:00:00+00:00"


def test_day_to_datetime_missing_key() -> None:
    assert _day_to_datetime({"year": 2026}) is None
    assert _day_to_datetime(None) is None


def test_aq_advisory_level() -> None:
    assert _aq_advisory_level("Very Unhealthy") == "Alert"
    assert _aq_advisory_level("Hazardous") == "Alert"
    assert _aq_advisory_level("Unhealthy") == "Warning"
    assert _aq_advisory_level("Unhealthy for Sensitive Groups") == "Caution"
    assert _aq_advisory_level("Good") == "None"
    assert _aq_advisory_level("Moderate") == "None"
    assert _aq_advisory_level("") == "None"


def test_w_condition_clear_daytime() -> None:
    from custom_components.particle_man.const import CONDITION_MAP
    assert _w_condition({"type": "CLEAR"}, True) == "sunny"
    assert _w_condition({"type": "CLEAR"}, False) == "clear-night"


def test_w_condition_mapped() -> None:
    assert _w_condition({"type": "RAIN"}, True) == "rainy"
    assert _w_condition({"type": "THUNDERSTORM"}, True) == "lightning-rainy"


def test_w_condition_empty() -> None:
    assert _w_condition({}, True) is None
    assert _w_condition(None, True) is None


def test_w_degrees() -> None:
    assert _w_degrees({"degrees": 270.0}) == 270.0
    assert _w_degrees(None) is None
    assert _w_degrees("bad") is None


# ---------------------------------------------------------------------------
# ParticleManGlobalState tests
# ---------------------------------------------------------------------------


def test_global_state_default() -> None:
    state = ParticleManGlobalState()
    assert state.quiet_hours_active(True) is True
    assert state.quiet_hours_active(False) is False


def test_global_state_runtime_override() -> None:
    state = ParticleManGlobalState()
    state.set_quiet_hours_runtime(True)
    assert state.quiet_hours_active(False) is True  # override wins

    state.set_quiet_hours_runtime(False)
    assert state.quiet_hours_active(True) is False  # override wins

    state.set_quiet_hours_runtime(None)
    assert state.quiet_hours_active(True) is True  # back to config


# ---------------------------------------------------------------------------
# ParticleManCoordinator construction and basic properties
# ---------------------------------------------------------------------------


@pytest.fixture
def coordinator(hass: HomeAssistant, mock_config_entry):
    """Return a minimal coordinator for unit testing (no real HTTP calls)."""
    mock_config_entry.add_to_hass(hass)
    with patch(
        "custom_components.particle_man.coordinator.Store",
        autospec=True,
    ) as mock_store_cls:
        mock_store = AsyncMock()
        mock_store.async_load = AsyncMock(return_value=None)
        mock_store.async_save = AsyncMock()
        mock_store_cls.return_value = mock_store

        coord = ParticleManCoordinator(
            hass=hass,
            api_key=TEST_API_KEY,
            latitude=TEST_LAT,
            longitude=TEST_LON,
            location_name=TEST_LOCATION_NAME,
            enable_air_quality=True,
            enable_pollen=True,
            enable_weather=True,
            enable_weather_alerts=True,
            quiet_hours_enabled=False,
            entry_id="test_entry_id",
            config_entry=mock_config_entry,
        )
        yield coord


def test_coordinator_location_slug(coordinator: ParticleManCoordinator) -> None:
    assert coordinator.location_slug == "seattle"


def test_coordinator_forecast_days_clamped(hass: HomeAssistant, mock_config_entry) -> None:
    mock_config_entry.add_to_hass(hass)
    with patch("custom_components.particle_man.coordinator.Store", autospec=True) as ms:
        ms.return_value.async_load = AsyncMock(return_value=None)
        ms.return_value.async_save = AsyncMock()
        c = ParticleManCoordinator(hass=hass, api_key="k", latitude=0, longitude=0,
                                   forecast_days=10, config_entry=mock_config_entry)
    assert c.forecast_days == 5  # clamped to max 5

    with patch("custom_components.particle_man.coordinator.Store", autospec=True) as ms:
        ms.return_value.async_load = AsyncMock(return_value=None)
        ms.return_value.async_save = AsyncMock()
        c2 = ParticleManCoordinator(hass=hass, api_key="k", latitude=0, longitude=0,
                                    forecast_days=0, config_entry=mock_config_entry)
    assert c2.forecast_days == 1  # clamped to min 1


# ---------------------------------------------------------------------------
# Quiet hours tests
# ---------------------------------------------------------------------------


def test_is_quiet_hours_disabled(coordinator: ParticleManCoordinator) -> None:
    coordinator._quiet_hours_enabled = False
    assert coordinator._is_quiet_hours() is False


def test_is_quiet_hours_normal_range(coordinator: ParticleManCoordinator) -> None:
    coordinator._quiet_hours_enabled = True
    coordinator._quiet_start = "10:00:00"
    coordinator._quiet_end = "12:00:00"
    # Time at 11:00 is inside range
    fake_now = datetime(2026, 4, 22, 11, 0, 0)
    with patch("custom_components.particle_man.coordinator.datetime") as mock_dt:
        mock_dt.now.return_value = fake_now
        mock_dt.fromisoformat = datetime.fromisoformat
        assert coordinator._is_quiet_hours() is True


def test_is_quiet_hours_spans_midnight(coordinator: ParticleManCoordinator) -> None:
    coordinator._quiet_hours_enabled = True
    coordinator._quiet_start = "23:00:00"
    coordinator._quiet_end = "05:00:00"
    # 02:00 is inside 23:00–05:00
    fake_2am = datetime(2026, 4, 22, 2, 0, 0)
    # 14:00 is outside
    fake_2pm = datetime(2026, 4, 22, 14, 0, 0)
    with patch("custom_components.particle_man.coordinator.datetime") as mock_dt:
        mock_dt.now.return_value = fake_2am
        mock_dt.fromisoformat = datetime.fromisoformat
        assert coordinator._is_quiet_hours() is True
    with patch("custom_components.particle_man.coordinator.datetime") as mock_dt:
        mock_dt.now.return_value = fake_2pm
        mock_dt.fromisoformat = datetime.fromisoformat
        assert coordinator._is_quiet_hours() is False


def test_is_quiet_hours_invalid_format(coordinator: ParticleManCoordinator) -> None:
    coordinator._quiet_hours_enabled = True
    coordinator._quiet_start = "bad"
    coordinator._quiet_end = "also_bad"
    assert coordinator._is_quiet_hours() is False


# ---------------------------------------------------------------------------
# Backoff tests
# ---------------------------------------------------------------------------


def test_is_backed_off_false_when_no_entry(coordinator: ParticleManCoordinator) -> None:
    assert coordinator._is_backed_off("aq") is False


def test_is_backed_off_true_when_future(coordinator: ParticleManCoordinator) -> None:
    future = datetime.now(timezone.utc) + timedelta(hours=2)
    coordinator._api_backoff["aq"] = future
    assert coordinator._is_backed_off("aq") is True


def test_is_backed_off_clears_expired(coordinator: ParticleManCoordinator) -> None:
    past = datetime.now(timezone.utc) - timedelta(hours=1)
    coordinator._api_backoff["aq"] = past
    assert coordinator._is_backed_off("aq") is False
    assert "aq" not in coordinator._api_backoff


# ---------------------------------------------------------------------------
# Error recording tests
# ---------------------------------------------------------------------------


def test_record_api_error_401_raises_auth_failed(coordinator: ParticleManCoordinator) -> None:
    with pytest.raises(ConfigEntryAuthFailed):
        coordinator._record_api_error("aq", 401)


def test_record_api_error_403_raises_auth_failed(coordinator: ParticleManCoordinator) -> None:
    with pytest.raises(ConfigEntryAuthFailed):
        coordinator._record_api_error("aq", 403)


def test_record_api_error_429_backs_off(coordinator: ParticleManCoordinator) -> None:
    coordinator._record_api_error("aq", 429)
    assert "aq" in coordinator._api_backoff
    assert "aq" in coordinator._api_unavailable_logged


def test_record_api_error_429_exponential_backoff(coordinator: ParticleManCoordinator) -> None:
    coordinator._api_failures["aq"] = 2  # simulate already failed twice
    coordinator._record_api_error("aq", 429)
    # 3rd failure: 2^(3-1) = 4 hours, capped at 8
    until = coordinator._api_backoff.get("aq")
    assert until is not None
    hours_from_now = (until - datetime.now(timezone.utc)).total_seconds() / 3600
    assert 3.5 < hours_from_now < 4.5


def test_record_api_error_500_logs_once(coordinator: ParticleManCoordinator) -> None:
    coordinator._record_api_error("aq", 500)
    assert "aq" in coordinator._api_unavailable_logged
    assert coordinator._api_failures.get("aq") == 1
    # Second call should not log again (just increment counter)
    coordinator._record_api_error("aq", 500)
    assert coordinator._api_failures.get("aq") == 2


def test_record_api_error_generic(coordinator: ParticleManCoordinator) -> None:
    coordinator._record_api_error("pollen")  # no status code
    assert "pollen" in coordinator._api_unavailable_logged
    assert coordinator._api_failures.get("pollen") == 1


def test_clear_api_error_logs_recovery(coordinator: ParticleManCoordinator) -> None:
    coordinator._api_unavailable_logged.add("aq")
    coordinator._api_failures["aq"] = 3
    coordinator._api_backoff["aq"] = datetime.now(timezone.utc) + timedelta(hours=1)
    coordinator._clear_api_error("aq")
    assert "aq" not in coordinator._api_unavailable_logged
    assert "aq" not in coordinator._api_failures
    assert "aq" not in coordinator._api_backoff


def test_clear_api_error_no_op_if_not_logged(coordinator: ParticleManCoordinator) -> None:
    coordinator._clear_api_error("aq")  # should not raise


# ---------------------------------------------------------------------------
# _async_setup tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_load_tracking_new_month(coordinator: ParticleManCoordinator) -> None:
    coordinator._shared_store.async_load = AsyncMock(return_value={"period_month": "2025-01", "aq_calls": 999})
    await coordinator._async_setup()
    current = coordinator._current_billing_month()
    assert coordinator._cached_tracking["period_month"] == current
    assert coordinator._cached_tracking.get("aq_calls", 0) == 0


@pytest.mark.asyncio
async def test_load_tracking_same_month(coordinator: ParticleManCoordinator) -> None:
    current = coordinator._current_billing_month()
    stored = {"period_month": current, "aq_calls": 42, "pollen_calls": 10, "weather_calls": 5}
    coordinator._shared_store.async_load = AsyncMock(return_value=stored)
    await coordinator._async_setup()
    assert coordinator._cached_tracking["aq_calls"] == 42


# ---------------------------------------------------------------------------
# _async_update_data with mocked HTTP
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_data_skips_quiet_hours(coordinator: ParticleManCoordinator) -> None:
    coordinator._quiet_hours_enabled = True
    coordinator._quiet_start = "00:00:00"
    coordinator._quiet_end = "23:59:59"  # always quiet
    coordinator._save_tracking = AsyncMock()
    coordinator.data = {"aqi": {"value": 50}}

    result = await coordinator._async_update_data()
    assert result == {"aqi": {"value": 50}}  # returned unchanged cached data
    coordinator._save_tracking.assert_called_once_with(aq_inc=0, pollen_inc=0, weather_inc=0)


@pytest.mark.asyncio
async def test_update_data_aq_quota_blocked(hass: HomeAssistant, coordinator: ParticleManCoordinator) -> None:
    coordinator._cached_tracking = {
        "period_month": coordinator._current_billing_month(),
        "aq_calls": 10001,  # exceeds limit
        "pollen_calls": 0,
        "weather_calls": 0,
    }
    coordinator.aq_monthly_limit = 10000
    coordinator.automagic_mode = True
    coordinator._save_tracking = AsyncMock()
    coordinator.data = {"weather_current": {"temperature": 20.0}}  # cached data so UpdateFailed isn't raised

    with patch("custom_components.particle_man.coordinator.async_create_issue") as mock_issue:
        with patch("custom_components.particle_man.coordinator.async_delete_issue"):
            # Also need to prevent pollen/weather from failing — disable them
            coordinator.enable_pollen = False
            coordinator.enable_weather = False
            result = await coordinator._async_update_data()
    mock_issue.assert_called()
    # No AQ data added since blocked
    assert "aqi" not in result


@pytest.mark.asyncio
async def test_update_data_auth_failure_raises(
    hass: HomeAssistant, coordinator: ParticleManCoordinator, aioclient_mock
) -> None:
    """A 401 response from AQ API should raise ConfigEntryAuthFailed."""
    import re as re_mod
    aioclient_mock.post(
        re_mod.compile(r".*airquality\.googleapis\.com.*currentConditions.*"),
        status=401,
        json={"error": {"message": "API key invalid"}},
    )
    coordinator._save_tracking = AsyncMock()
    coordinator.enable_pollen = False
    coordinator.enable_weather = False
    coordinator.data = {}

    with pytest.raises(ConfigEntryAuthFailed):
        await coordinator._async_update_data()


@pytest.mark.asyncio
async def test_update_data_successful(
    hass: HomeAssistant, coordinator: ParticleManCoordinator, aioclient_mock
) -> None:
    """Successful update populates data keys."""
    register_api_mocks(aioclient_mock)
    coordinator._save_tracking = AsyncMock()
    coordinator.data = {}

    result = await coordinator._async_update_data()
    assert "aqi" in result
    assert result["aqi"]["value"] == 45
    assert "pollutant_pm25" in result


@pytest.mark.asyncio
async def test_update_data_pollen_success(
    hass: HomeAssistant, coordinator: ParticleManCoordinator, aioclient_mock
) -> None:
    """Pollen update populates pollen keys."""
    register_api_mocks(aioclient_mock)
    coordinator._save_tracking = AsyncMock()
    coordinator.enable_air_quality = False
    coordinator.enable_weather = False
    coordinator.data = {}

    result = await coordinator._async_update_data()
    # At least one pollen_type_ key expected
    pollen_keys = [k for k in result if k.startswith("pollen_")]
    assert pollen_keys


@pytest.mark.asyncio
async def test_update_data_month_rollover(
    hass: HomeAssistant, coordinator: ParticleManCoordinator, aioclient_mock
) -> None:
    """Quota issues are deleted on month rollover."""
    coordinator._cached_tracking = {
        "period_month": "2025-01",  # old month
        "aq_calls": 0,
        "pollen_calls": 0,
        "weather_calls": 0,
    }
    register_api_mocks(aioclient_mock)
    coordinator._save_tracking = AsyncMock()

    with patch("custom_components.particle_man.coordinator.async_delete_issue") as mock_del:
        await coordinator._async_update_data()
    # Should have deleted quota issues for the old period
    assert mock_del.call_count >= 3


@pytest.mark.asyncio
async def test_update_data_raises_when_no_data(
    hass: HomeAssistant, coordinator: ParticleManCoordinator, aioclient_mock
) -> None:
    """UpdateFailed raised when no data and all APIs are disabled."""
    import re as re_mod
    from homeassistant.helpers.update_coordinator import UpdateFailed

    coordinator.enable_air_quality = False
    coordinator.enable_pollen = False
    coordinator.enable_weather = False
    coordinator.data = None
    coordinator._save_tracking = AsyncMock()

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()


# ---------------------------------------------------------------------------
# Additional pure function tests
# ---------------------------------------------------------------------------


def test_to_canonical_ppb_to_ugm3() -> None:
    """ppb → μg/m³ conversion hits line 123."""
    from custom_components.particle_man.const import GAS_MW, MOLAR_VOL
    mw = GAS_MW.get("no2", 46.0)
    result = _to_canonical(100.0, "ppb", "μg/m³", "no2")
    expected = 100.0 * (mw / MOLAR_VOL)
    assert abs(result - expected) < 0.01


def test_epa_category_above_all_breakpoints() -> None:
    """Value exceeding every breakpoint returns last category (line 138)."""
    result = _epa_category("pm25", 9999.0, "μg/m³")
    assert result == "Hazardous"


# ---------------------------------------------------------------------------
# _record_api_error additional paths
# ---------------------------------------------------------------------------


def test_record_api_error_500_persistent_backoff(coordinator: ParticleManCoordinator) -> None:
    """500 error on 3rd failure triggers exponential backoff (lines 332-334)."""
    coordinator._api_failures["aq"] = 2
    coordinator._record_api_error("aq", 500)
    assert "aq" in coordinator._api_backoff
    hours = (coordinator._api_backoff["aq"] - datetime.now(timezone.utc)).total_seconds() / 3600
    assert 1.5 < hours <= 8.5


def test_record_api_error_generic_repeated_failure(coordinator: ParticleManCoordinator) -> None:
    """Generic failure on 2nd+ call logs debug (line 342)."""
    coordinator._api_failures["pollen"] = 1
    coordinator._record_api_error("pollen")
    assert coordinator._api_failures.get("pollen") == 2


# ---------------------------------------------------------------------------
# _async_update_data: AQ backed-off and exception paths
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_data_aq_backed_off(
    hass: HomeAssistant, coordinator: ParticleManCoordinator
) -> None:
    """AQ backed-off debug log hits line 433."""
    future = datetime.now(timezone.utc) + timedelta(hours=2)
    coordinator._api_backoff["aq"] = future
    coordinator.enable_pollen = False
    coordinator.enable_weather = False
    coordinator._save_tracking = AsyncMock()
    coordinator.data = {"aqi": {"value": 30}}
    result = await coordinator._async_update_data()
    assert "aqi" in result


@pytest.mark.asyncio
async def test_update_data_aq_generic_exception(
    hass: HomeAssistant, coordinator: ParticleManCoordinator
) -> None:
    """Generic exception in AQ fetch hits lines 447-449."""
    with patch.object(coordinator, "_fetch_current", side_effect=RuntimeError("net error")):
        coordinator.enable_pollen = False
        coordinator.enable_weather = False
        coordinator._save_tracking = AsyncMock()
        coordinator.data = {"aqi": {"value": 30}}
        await coordinator._async_update_data()
    assert coordinator._api_failures.get("aq") == 1


# ---------------------------------------------------------------------------
# Weather quota / backed-off / exception paths
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_data_weather_quota_blocked(
    hass: HomeAssistant, coordinator: ParticleManCoordinator
) -> None:
    """Weather quota blocked hits lines 459-465."""
    coordinator.enable_air_quality = False
    coordinator.enable_pollen = False
    coordinator.automagic_mode = True
    coordinator.weather_monthly_limit = 10
    coordinator._cached_tracking = {
        "period_month": coordinator._current_billing_month(),
        "aq_calls": 0, "pollen_calls": 0, "weather_calls": 10,
    }
    coordinator._save_tracking = AsyncMock()
    coordinator.data = {"weather_current": {}}
    with patch("custom_components.particle_man.coordinator.async_create_issue") as mock_issue:
        with patch("custom_components.particle_man.coordinator.async_delete_issue"):
            await coordinator._async_update_data()
    mock_issue.assert_called()


@pytest.mark.asyncio
async def test_update_data_weather_backed_off(
    hass: HomeAssistant, coordinator: ParticleManCoordinator
) -> None:
    """Weather backed-off debug log hits line 471."""
    future = datetime.now(timezone.utc) + timedelta(hours=2)
    coordinator._api_backoff["weather"] = future
    coordinator.enable_air_quality = False
    coordinator.enable_pollen = False
    coordinator._save_tracking = AsyncMock()
    coordinator.data = {"weather_current": {}}
    result = await coordinator._async_update_data()
    assert result is not None


@pytest.mark.asyncio
async def test_update_data_weather_client_response_error(
    hass: HomeAssistant, coordinator: ParticleManCoordinator, aioclient_mock
) -> None:
    """ClientResponseError from weather build hits line 503-504."""
    import aiohttp
    register_api_mocks(aioclient_mock)
    err = aiohttp.ClientResponseError(request_info=MagicMock(), history=(), status=503)
    with patch.object(coordinator, "_build_weather_data", side_effect=err):
        coordinator.enable_air_quality = False
        coordinator.enable_pollen = False
        coordinator._save_tracking = AsyncMock()
        coordinator.data = {"weather_current": {}}
        await coordinator._async_update_data()
    assert coordinator._api_failures.get("weather") == 1


@pytest.mark.asyncio
async def test_update_data_weather_generic_exception(
    hass: HomeAssistant, coordinator: ParticleManCoordinator, aioclient_mock
) -> None:
    """Generic exception from weather build hits lines 505-507."""
    register_api_mocks(aioclient_mock)
    with patch.object(coordinator, "_build_weather_data", side_effect=RuntimeError("build error")):
        coordinator.enable_air_quality = False
        coordinator.enable_pollen = False
        coordinator._save_tracking = AsyncMock()
        coordinator.data = {"weather_current": {}}
        await coordinator._async_update_data()
    assert coordinator._api_failures.get("weather") == 1


# ---------------------------------------------------------------------------
# Pollen: not-due / quota / backed-off / exception with carryover
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_data_pollen_not_due(
    hass: HomeAssistant, coordinator: ParticleManCoordinator
) -> None:
    """Pollen not-due debug log hits lines 513-516."""
    coordinator.enable_air_quality = False
    coordinator.enable_weather = False
    coordinator._last_pollen_fetch = datetime.now(timezone.utc)
    coordinator._save_tracking = AsyncMock()
    coordinator.data = {"pollen_advisory": {"value": "Low"}}
    result = await coordinator._async_update_data()
    assert result is not None


@pytest.mark.asyncio
async def test_update_data_pollen_quota_blocked(
    hass: HomeAssistant, coordinator: ParticleManCoordinator
) -> None:
    """Pollen quota blocked hits lines 524-530."""
    coordinator.enable_air_quality = False
    coordinator.enable_weather = False
    coordinator.automagic_mode = True
    coordinator.pollen_monthly_limit = 5
    coordinator._cached_tracking = {
        "period_month": coordinator._current_billing_month(),
        "aq_calls": 0, "pollen_calls": 5, "weather_calls": 0,
    }
    coordinator._save_tracking = AsyncMock()
    coordinator.data = {"pollen_advisory": {"value": "Low"}}
    with patch("custom_components.particle_man.coordinator.async_create_issue") as mock_issue:
        with patch("custom_components.particle_man.coordinator.async_delete_issue"):
            await coordinator._async_update_data()
    mock_issue.assert_called()


@pytest.mark.asyncio
async def test_update_data_pollen_backed_off(
    hass: HomeAssistant, coordinator: ParticleManCoordinator
) -> None:
    """Pollen backed-off debug log hits line 536."""
    future = datetime.now(timezone.utc) + timedelta(hours=2)
    coordinator._api_backoff["pollen"] = future
    coordinator.enable_air_quality = False
    coordinator.enable_weather = False
    coordinator._save_tracking = AsyncMock()
    coordinator.data = {"pollen_advisory": {"value": "Low"}}
    result = await coordinator._async_update_data()
    assert result is not None


@pytest.mark.asyncio
async def test_update_data_pollen_client_error_with_carryover(
    hass: HomeAssistant, coordinator: ParticleManCoordinator, aioclient_mock
) -> None:
    """Pollen ClientResponseError carries over cached pollen data (lines 545-550)."""
    import re as re_mod
    aioclient_mock.get(
        re_mod.compile(r".*pollen\.googleapis\.com.*"),
        status=400,
        json={"error": "bad"},
    )
    coordinator.enable_air_quality = False
    coordinator.enable_weather = False
    coordinator._save_tracking = AsyncMock()
    coordinator.data = {"pollen_type_tree": {"value": 3}}
    result = await coordinator._async_update_data()
    assert "pollen_type_tree" in result


@pytest.mark.asyncio
async def test_update_data_pollen_generic_exception_with_carryover(
    hass: HomeAssistant, coordinator: ParticleManCoordinator
) -> None:
    """Generic pollen exception carries over cached data (lines 551-557)."""
    with patch.object(coordinator, "_fetch_pollen", side_effect=RuntimeError("timeout")):
        coordinator.enable_air_quality = False
        coordinator.enable_weather = False
        coordinator._save_tracking = AsyncMock()
        coordinator.data = {"pollen_type_tree": {"value": 3}}
        result = await coordinator._async_update_data()
    assert "pollen_type_tree" in result


# ---------------------------------------------------------------------------
# Fetch methods: local AQI / health recs / 400 error log paths
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_data_with_local_aqi_and_health_recs(
    hass: HomeAssistant, coordinator: ParticleManCoordinator, aioclient_mock
) -> None:
    """enable_local_aqi + include_health_recs hits lines 576, 578, 615."""
    register_api_mocks(aioclient_mock)
    coordinator.enable_local_aqi = True
    coordinator.include_health_recs = True
    coordinator.enable_pollen = False
    coordinator.enable_weather = False
    coordinator._save_tracking = AsyncMock()
    coordinator.data = {}
    result = await coordinator._async_update_data()
    assert "aqi" in result


@pytest.mark.asyncio
async def test_fetch_current_400_logs_error(
    hass: HomeAssistant, coordinator: ParticleManCoordinator, aioclient_mock
) -> None:
    """400 from AQ current endpoint triggers error log + catch (lines 590-594)."""
    import re as re_mod
    aioclient_mock.post(
        re_mod.compile(r".*airquality.*currentConditions.*"),
        status=400,
        json={"error": "bad"},
    )
    coordinator.enable_pollen = False
    coordinator.enable_weather = False
    coordinator._save_tracking = AsyncMock()
    coordinator.data = {"aqi": {}}
    await coordinator._async_update_data()
    assert coordinator._api_failures.get("aq") == 1


@pytest.mark.asyncio
async def test_fetch_forecast_400_logs_error(
    hass: HomeAssistant, coordinator: ParticleManCoordinator, aioclient_mock
) -> None:
    """400 from AQ forecast endpoint triggers error log (lines 622-623)."""
    import re as re_mod
    aioclient_mock.post(
        re_mod.compile(r".*airquality.*currentConditions.*"),
        json=AQ_CURRENT_RESPONSE,
    )
    aioclient_mock.post(
        re_mod.compile(r".*airquality.*forecast.*"),
        status=400,
        json={"error": "bad"},
    )
    coordinator.enable_pollen = False
    coordinator.enable_weather = False
    coordinator._save_tracking = AsyncMock()
    coordinator.data = {"aqi": {}}
    await coordinator._async_update_data()
    assert coordinator._api_failures.get("aq") == 1


@pytest.mark.asyncio
async def test_fetch_pollen_400_logs_error(
    hass: HomeAssistant, coordinator: ParticleManCoordinator, aioclient_mock
) -> None:
    """400 from pollen endpoint triggers error log (lines 649-653)."""
    import re as re_mod
    aioclient_mock.get(
        re_mod.compile(r".*pollen\.googleapis\.com.*"),
        status=400,
        json={"error": "bad"},
    )
    coordinator.enable_air_quality = False
    coordinator.enable_weather = False
    coordinator._save_tracking = AsyncMock()
    coordinator.data = {"pollen_advisory": {"value": "None"}}
    await coordinator._async_update_data()
    assert coordinator._api_failures.get("pollen") == 1


@pytest.mark.asyncio
async def test_fetch_weather_current_400_logs_error(
    hass: HomeAssistant, coordinator: ParticleManCoordinator, aioclient_mock
) -> None:
    """400 from weather current endpoint triggers error log (lines 672-676)."""
    import re as re_mod
    aioclient_mock.get(
        re_mod.compile(r".*weather\.googleapis\.com.*currentConditions.*"),
        status=400,
        json={"error": "bad"},
    )
    aioclient_mock.get(
        re_mod.compile(r".*weather\.googleapis\.com.*hours.*"),
        json=WEATHER_HOURLY_RESPONSE,
    )
    aioclient_mock.get(
        re_mod.compile(r".*weather\.googleapis\.com.*days.*"),
        json=WEATHER_DAILY_RESPONSE,
    )
    aioclient_mock.get(
        re_mod.compile(r".*weather\.googleapis\.com.*alerts.*"),
        json=WEATHER_ALERTS_RESPONSE,
    )
    coordinator.enable_air_quality = False
    coordinator.enable_pollen = False
    coordinator._save_tracking = AsyncMock()
    coordinator.data = {"weather_current": {}}
    result = await coordinator._async_update_data()
    assert result is not None


@pytest.mark.asyncio
async def test_fetch_weather_hourly_400_logs_error(
    hass: HomeAssistant, coordinator: ParticleManCoordinator, aioclient_mock
) -> None:
    """400 from weather hourly endpoint triggers error log (lines 693-697)."""
    import re as re_mod
    aioclient_mock.get(
        re_mod.compile(r".*weather\.googleapis\.com.*currentConditions.*"),
        json=WEATHER_CURRENT_RESPONSE,
    )
    aioclient_mock.get(
        re_mod.compile(r".*weather\.googleapis\.com.*hours.*"),
        status=400,
        json={"error": "bad"},
    )
    aioclient_mock.get(
        re_mod.compile(r".*weather\.googleapis\.com.*days.*"),
        json=WEATHER_DAILY_RESPONSE,
    )
    aioclient_mock.get(
        re_mod.compile(r".*weather\.googleapis\.com.*alerts.*"),
        json=WEATHER_ALERTS_RESPONSE,
    )
    coordinator.enable_air_quality = False
    coordinator.enable_pollen = False
    coordinator._save_tracking = AsyncMock()
    coordinator.data = {"weather_current": {}}
    result = await coordinator._async_update_data()
    assert result is not None


@pytest.mark.asyncio
async def test_fetch_weather_daily_400_logs_error(
    hass: HomeAssistant, coordinator: ParticleManCoordinator, aioclient_mock
) -> None:
    """400 from weather daily endpoint triggers error log (lines 714-718)."""
    import re as re_mod
    aioclient_mock.get(
        re_mod.compile(r".*weather\.googleapis\.com.*currentConditions.*"),
        json=WEATHER_CURRENT_RESPONSE,
    )
    aioclient_mock.get(
        re_mod.compile(r".*weather\.googleapis\.com.*hours.*"),
        json=WEATHER_HOURLY_RESPONSE,
    )
    aioclient_mock.get(
        re_mod.compile(r".*weather\.googleapis\.com.*days.*"),
        status=400,
        json={"error": "bad"},
    )
    aioclient_mock.get(
        re_mod.compile(r".*weather\.googleapis\.com.*alerts.*"),
        json=WEATHER_ALERTS_RESPONSE,
    )
    coordinator.enable_air_quality = False
    coordinator.enable_pollen = False
    coordinator._save_tracking = AsyncMock()
    coordinator.data = {"weather_current": {}}
    result = await coordinator._async_update_data()
    assert result is not None


@pytest.mark.asyncio
async def test_fetch_weather_alerts_success(
    hass: HomeAssistant, coordinator: ParticleManCoordinator, aioclient_mock
) -> None:
    """Successful weather alerts fetch hits line 737 (return json)."""
    import re as re_mod
    aioclient_mock.get(
        re_mod.compile(r".*weather\.googleapis\.com.*currentConditions.*"),
        json=WEATHER_CURRENT_RESPONSE,
    )
    aioclient_mock.get(
        re_mod.compile(r".*weather\.googleapis\.com.*hours.*"),
        json=WEATHER_HOURLY_RESPONSE,
    )
    aioclient_mock.get(
        re_mod.compile(r".*weather\.googleapis\.com.*days.*"),
        json=WEATHER_DAILY_RESPONSE,
    )
    aioclient_mock.get(
        re_mod.compile(r".*weather\.googleapis\.com.*alerts.*", re_mod.IGNORECASE),
        json=WEATHER_ALERTS_RESPONSE,
    )
    coordinator.enable_air_quality = False
    coordinator.enable_pollen = False
    coordinator._save_tracking = AsyncMock()
    coordinator.data = {"weather_current": {}}
    result = await coordinator._async_update_data()
    assert result is not None


@pytest.mark.asyncio
async def test_fetch_weather_alerts_400_logs_error(
    hass: HomeAssistant, coordinator: ParticleManCoordinator, aioclient_mock
) -> None:
    """400 from weather alerts endpoint triggers error log (lines 731-737)."""
    import re as re_mod
    aioclient_mock.get(
        re_mod.compile(r".*weather\.googleapis\.com.*currentConditions.*"),
        json=WEATHER_CURRENT_RESPONSE,
    )
    aioclient_mock.get(
        re_mod.compile(r".*weather\.googleapis\.com.*hours.*"),
        json=WEATHER_HOURLY_RESPONSE,
    )
    aioclient_mock.get(
        re_mod.compile(r".*weather\.googleapis\.com.*days.*"),
        json=WEATHER_DAILY_RESPONSE,
    )
    aioclient_mock.get(
        re_mod.compile(r".*weather\.googleapis\.com.*alerts.*", re_mod.IGNORECASE),
        status=400,
        json={"error": "bad"},
    )
    coordinator.enable_air_quality = False
    coordinator.enable_pollen = False
    coordinator._save_tracking = AsyncMock()
    coordinator.data = {"weather_current": {}}
    result = await coordinator._async_update_data()
    assert result is not None


# ---------------------------------------------------------------------------
# _build_data: fallback uaqi and local AQI paths
# ---------------------------------------------------------------------------


def test_build_data_fallback_uaqi(coordinator: ParticleManCoordinator) -> None:
    """When no 'uaqi' index, uses indexes[0] as fallback (line 750)."""
    current: dict[str, Any] = {
        "dateTime": "2026-04-22T12:00:00Z",
        "regionCode": "us",
        "indexes": [
            {
                "code": "custom_index",
                "aqi": 55,
                "aqiDisplay": "55",
                "category": "Moderate",
                "dominantPollutant": "o3",
            }
        ],
        "pollutants": [],
    }
    result = coordinator._build_data(current, [])
    assert result["aqi"]["value"] == 55


def test_build_data_with_local_aqi_index(coordinator: ParticleManCoordinator) -> None:
    """Local AQI path builds local_aqi entry (lines 779-786)."""
    coordinator.enable_local_aqi = True
    coordinator.local_aqi_code = "usa_epa"
    current: dict[str, Any] = {
        "dateTime": "2026-04-22T12:00:00Z",
        "regionCode": "us",
        "indexes": [
            {"code": "uaqi", "aqi": 45, "aqiDisplay": "45", "category": "Good", "dominantPollutant": "pm25"},
            {"code": "usa_epa", "aqi": 52, "aqiDisplay": "52", "category": "Good",
             "dominantPollutant": "pm25", "displayName": "US EPA"},
        ],
        "pollutants": [],
    }
    result = coordinator._build_data(current, [])
    assert "local_aqi" in result
    assert result["local_aqi"]["value"] == 52


# ---------------------------------------------------------------------------
# _build_aqi_hourly_forecast / _build_pollutant_hourly_forecast
# ---------------------------------------------------------------------------


def test_build_aqi_hourly_forecast_with_data(coordinator: ParticleManCoordinator) -> None:
    """AQI hourly forecast with uaqi + local entries (lines 847-860)."""
    hours: list[dict[str, Any]] = [
        {
            "dateTime": "2026-04-22T13:00:00Z",
            "indexes": [
                {"code": "uaqi", "aqi": 50, "category": "Good", "dominantPollutant": "pm25"},
                {"code": "usa_epa", "aqi": 55, "category": "Moderate"},
            ],
        },
        {
            "dateTime": "2026-04-22T14:00:00Z",
            "indexes": [
                {"code": "uaqi", "aqi": 60, "category": "Moderate", "dominantPollutant": "o3"},
            ],
        },
    ]
    uaqi_hourly, local_hourly = coordinator._build_aqi_hourly_forecast(hours)
    assert len(uaqi_hourly) == 2
    assert uaqi_hourly[0]["aqi"] == 50
    assert len(local_hourly) == 1
    assert local_hourly[0]["aqi"] == 55


def test_build_pollutant_hourly_forecast_with_data(coordinator: ParticleManCoordinator) -> None:
    """Pollutant hourly forecast aggregation (lines 872-879)."""
    hours: list[dict[str, Any]] = [
        {
            "dateTime": "2026-04-22T13:00:00Z",
            "pollutants": [
                {"code": "pm25", "concentration": {"value": 12.0, "units": "MICROGRAMS_PER_CUBIC_METER"}},
                {"code": "o3", "concentration": {"value": 0.05, "units": "PARTS_PER_MILLION"}},
            ],
        },
        {
            "dateTime": "2026-04-22T14:00:00Z",
            "pollutants": [
                {"code": "pm25", "concentration": {"value": 15.0, "units": "MICROGRAMS_PER_CUBIC_METER"}},
            ],
        },
    ]
    result = coordinator._build_pollutant_hourly_forecast(hours)
    assert "pm25" in result
    assert len(result["pm25"]) == 2
    assert result["pm25"][0]["value"] == 12.0
    assert "o3" in result


# ---------------------------------------------------------------------------
# _build_aqi_daily_forecast / _build_pollutant_daily_forecast
# ---------------------------------------------------------------------------


def test_build_aqi_daily_forecast_with_data(coordinator: ParticleManCoordinator) -> None:
    """AQI daily forecast aggregation with dt parsing (lines 894-926)."""
    hours: list[dict[str, Any]] = [
        {
            "dateTime": "2026-04-22T01:00:00Z",
            "indexes": [
                {"code": "uaqi", "aqi": 40, "category": "Good"},
                {"code": "usa_epa", "aqi": 45, "category": "Good"},
            ],
        },
        {
            "dateTime": "2026-04-22T02:00:00Z",
            "indexes": [
                {"code": "uaqi", "aqi": 60, "category": "Moderate"},
            ],
        },
        {
            "dateTime": "2026-04-23T01:00:00Z",
            "indexes": [
                {"code": "uaqi", "aqi": 35, "category": "Good"},
            ],
        },
        {
            "dateTime": "not-a-date",
            "indexes": [{"code": "uaqi", "aqi": 99, "category": "Hazardous"}],
        },
    ]
    uaqi_daily, local_daily = coordinator._build_aqi_daily_forecast(hours)
    assert len(uaqi_daily) >= 1
    aqi_values = {d["aqi"] for d in uaqi_daily}
    assert 60 in aqi_values  # peak of day April 22


def test_build_pollutant_daily_forecast_with_data(coordinator: ParticleManCoordinator) -> None:
    """Pollutant daily forecast aggregation (lines 933-963)."""
    hours: list[dict[str, Any]] = [
        {
            "dateTime": "2026-04-22T01:00:00Z",
            "pollutants": [
                {"code": "pm25", "concentration": {"value": 10.0, "units": "MICROGRAMS_PER_CUBIC_METER"}},
            ],
        },
        {
            "dateTime": "2026-04-22T02:00:00Z",
            "pollutants": [
                {"code": "pm25", "concentration": {"value": 20.0, "units": "MICROGRAMS_PER_CUBIC_METER"}},
            ],
        },
        {
            "dateTime": "2026-04-23T01:00:00Z",
            "pollutants": [
                {"code": "pm25", "concentration": {"value": 5.0, "units": "MICROGRAMS_PER_CUBIC_METER"}},
            ],
        },
        {
            "dateTime": "invalid-date",
            "pollutants": [
                {"code": "pm25", "concentration": {"value": 999.0, "units": "MICROGRAMS_PER_CUBIC_METER"}},
            ],
        },
    ]
    result = coordinator._build_pollutant_daily_forecast(hours)
    assert "pm25" in result
    assert result["pm25"][0]["max"] == 20.0


# ---------------------------------------------------------------------------
# _build_pollen_data edge cases
# ---------------------------------------------------------------------------


def test_build_pollen_data_non_dict_response(coordinator: ParticleManCoordinator) -> None:
    """Non-dict response returns empty dict (line 973)."""
    assert coordinator._build_pollen_data("not a dict") == {}  # type: ignore[arg-type]


def test_build_pollen_data_empty_daily(coordinator: ParticleManCoordinator) -> None:
    """Empty or non-list dailyInfo returns empty dict (line 977)."""
    assert coordinator._build_pollen_data({"dailyInfo": []}) == {}
    assert coordinator._build_pollen_data({"dailyInfo": "bad"}) == {}  # type: ignore[arg-type]


def test_build_pollen_data_non_dict_items(coordinator: ParticleManCoordinator) -> None:
    """Non-dict items in type/plant lists are skipped (lines 990, 1000)."""
    response: dict[str, Any] = {
        "dailyInfo": [
            {
                "date": {"year": 2026, "month": 4, "day": 22},
                "pollenTypeInfo": [
                    "not_a_dict",
                    None,
                    {"code": "TREE", "displayName": "Tree", "indexInfo": {"value": 2, "category": "Low"}},
                ],
                "plantInfo": [
                    "not_a_dict",
                    {"code": "ALDER", "displayName": "Alder", "indexInfo": {"value": 1, "category": "VL"}},
                ],
            }
        ]
    }
    result = coordinator._build_pollen_data(response)
    assert "pollen_type_tree" in result


def test_build_pollen_data_unknown_category_in_advisory(coordinator: ParticleManCoordinator) -> None:
    """Unknown pollen category in advisory causes ValueError caught silently (lines 1084-1085)."""
    response: dict[str, Any] = {
        "dailyInfo": [
            {
                "date": {"year": 2026, "month": 4, "day": 22},
                "pollenTypeInfo": [
                    {
                        "code": "TREE",
                        "displayName": "Tree",
                        "inSeason": True,
                        "indexInfo": {"value": 2, "category": "UNKNOWN_CATEGORY"},
                    }
                ],
                "plantInfo": [],
            }
        ]
    }
    result = coordinator._build_pollen_data(response)
    assert "pollen_advisory" in result


# ---------------------------------------------------------------------------
# _build_pollen_forecast edge cases
# ---------------------------------------------------------------------------


def test_build_pollen_forecast_skip_null_date(coordinator: ParticleManCoordinator) -> None:
    """Null date in daily entry → dt_str=None → continue (line 1110)."""
    daily: list[dict[str, Any]] = [
        {"date": {"year": 2026, "month": 4, "day": 22}},  # day 0 (today)
        {"date": None},  # day 1: dt_str=None → skipped
    ]
    by_day: list[dict[str, Any]] = [{}, {}]
    result = coordinator._build_pollen_forecast(daily, by_day, "TREE", kind="type")
    assert result == []


def test_build_pollen_forecast_i_beyond_by_day(coordinator: ParticleManCoordinator) -> None:
    """i >= len(by_day) uses empty dict (line 1111)."""
    daily: list[dict[str, Any]] = [
        {"date": {"year": 2026, "month": 4, "day": 22}},
        {"date": {"year": 2026, "month": 4, "day": 23}},
        {"date": {"year": 2026, "month": 4, "day": 24}},
    ]
    by_day: list[dict[str, Any]] = [{}]  # shorter → i >= len(by_day) for days 1, 2
    result = coordinator._build_pollen_forecast(daily, by_day, "TREE", kind="type")
    assert len(result) == 2
    assert result[0]["index"] is None


def test_build_pollen_forecast_with_full_data(coordinator: ParticleManCoordinator) -> None:
    """Normal case with color data (lines 1112-1122)."""
    daily: list[dict[str, Any]] = [
        {"date": {"year": 2026, "month": 4, "day": 22}},
        {"date": {"year": 2026, "month": 4, "day": 23}},
    ]
    by_day: list[dict[str, Any]] = [
        {},
        {"TREE": {"indexInfo": {"value": 3, "category": "Moderate", "color": {"red": 1.0, "green": 0.5}}}},
    ]
    result = coordinator._build_pollen_forecast(daily, by_day, "TREE", kind="type")
    assert len(result) == 1
    assert result[0]["index"] == 3
    assert result[0]["color_hex"] is not None


# ---------------------------------------------------------------------------
# _build_weather_hourly / _build_weather_daily / _build_weather_alerts
# ---------------------------------------------------------------------------


def test_build_weather_hourly_with_data(coordinator: ParticleManCoordinator) -> None:
    """Weather hourly builder with actual entries (lines 1175-1197)."""
    hourly: dict[str, Any] = {
        "forecastHours": [
            {
                "interval": {"startTime": "2026-04-22T13:00:00Z"},
                "isDaytime": True,
                "weatherCondition": {"type": "RAIN"},
                "temperature": {"degrees": 14.0},
                "relativeHumidity": 80,
                "wind": {
                    "speed": {"value": 15.0},
                    "direction": {"degrees": 180},
                    "gust": {"value": 25.0},
                },
                "precipitation": {"probability": {"percent": 70}},
                "airPressure": {"meanSeaLevelMillibars": 1008.0},
                "cloudCover": {"percent": 90},
                "uvIndex": 1,
            },
            {
                "isDaytime": True,
                # no datetime → excluded from result
            },
        ]
    }
    result = coordinator._build_weather_hourly(hourly)
    assert len(result) == 1
    assert result[0]["native_temperature"] == 14.0
    assert result[0]["condition"] == "rainy"
    assert result[0]["cloud_coverage"] == 90


def test_build_weather_hourly_int_cloud_cover(coordinator: ParticleManCoordinator) -> None:
    """cloudCover as int uses value directly (line 1181)."""
    hourly: dict[str, Any] = {
        "forecastHours": [
            {
                "interval": {"startTime": "2026-04-22T13:00:00Z"},
                "cloudCover": 75,
                "isDaytime": True,
            }
        ]
    }
    result = coordinator._build_weather_hourly(hourly)
    assert len(result) == 1
    assert result[0]["cloud_coverage"] == 75


def test_build_weather_daily_with_data(coordinator: ParticleManCoordinator) -> None:
    """Weather daily builder with day+night entries (lines 1200-1269)."""
    daily: dict[str, Any] = {
        "forecastDays": [
            {
                "displayDate": {"year": 2026, "month": 4, "day": 22},
                "maxTemperature": {"degrees": 20.0},
                "minTemperature": {"degrees": 10.0},
                "feelsLikeMaxTemperature": {"degrees": 19.0},
                "feelsLikeMinTemperature": {"degrees": 8.0},
                "daytimeForecast": {
                    "weatherCondition": {"type": "CLEAR"},
                    "wind": {"speed": {"value": 12.0}, "direction": {"degrees": 270}, "gust": {"value": 18.0}},
                    "precipitation": {"probability": {"percent": 10}, "qpf": {"quantity": 2.0}},
                    "relativeHumidity": 45,
                    "cloudCover": {"percent": 20},
                    "uvIndex": 5,
                },
                "nighttimeForecast": {
                    "weatherCondition": {"type": "CLEAR"},
                    "wind": {"speed": {"value": 8.0}, "direction": {"degrees": 260}},
                    "precipitation": {"probability": {"percent": 5}, "qpf": {"quantity": 3.5}},
                    "relativeHumidity": 60,
                    "cloudCover": 15,
                },
            },
            {
                "displayDate": {"year": 2026},  # missing month/day → skipped
            },
        ]
    }
    daily_list, twice_daily_list = coordinator._build_weather_daily(daily)
    assert len(daily_list) == 1
    assert daily_list[0]["native_temperature"] == 20.0
    # Apparent temperature comes from feelsLikeMaxTemperature at day level
    assert daily_list[0]["native_apparent_temperature"] == 19.0
    # Daily precipitation = daytime QPF + nighttime QPF
    assert daily_list[0]["native_precipitation"] == pytest.approx(5.5)
    assert len(twice_daily_list) == 2
    # Twice-daily daytime uses feelsLikeMax, nighttime uses feelsLikeMin
    day_entry = next(e for e in twice_daily_list if e["is_daytime"])
    night_entry = next(e for e in twice_daily_list if not e["is_daytime"])
    assert day_entry["native_apparent_temperature"] == 19.0
    assert night_entry["native_apparent_temperature"] == 8.0


def test_build_weather_alerts_with_data(coordinator: ParticleManCoordinator) -> None:
    """Weather alerts builder with actual alert (lines 1264-1276)."""
    alerts: dict[str, Any] = {
        "publicAlerts": [
            {
                "alertHeadline": "Wind Advisory",
                "severity": "MODERATE_SEVERITY",
                "event": {"type": "WIND_ADVISORY"},
                "areaDescription": "Seattle Metro",
                "effectiveTime": "2026-04-22T12:00:00Z",
                "expireTime": "2026-04-22T20:00:00Z",
                "description": "Strong winds expected",
                "instruction": "Secure outdoor items",
            }
        ]
    }
    result = coordinator._build_weather_alerts(alerts)
    assert len(result) == 1
    assert result[0]["title"] == "Wind Advisory"
    assert result[0]["severity"] == "MODERATE"


# ---------------------------------------------------------------------------
# _compute_trend (pollen) and _compute_peak
# ---------------------------------------------------------------------------


def test_compute_hourly_trend_rising(coordinator: ParticleManCoordinator) -> None:
    """_compute_hourly_trend with rising data hits lines 1300-1313."""
    result = coordinator._compute_hourly_trend([10.0, 20.0, 30.0, 40.0, 50.0])
    assert result == "rising"


def test_compute_hourly_trend_falling(coordinator: ParticleManCoordinator) -> None:
    result = coordinator._compute_hourly_trend([50.0, 40.0, 30.0, 20.0, 10.0])
    assert result == "falling"


def test_compute_hourly_trend_stable_flat_values(coordinator: ParticleManCoordinator) -> None:
    result = coordinator._compute_hourly_trend([20.0, 20.0, 20.0, 20.0])
    assert result == "stable"


def test_compute_hourly_trend_too_few_values(coordinator: ParticleManCoordinator) -> None:
    result = coordinator._compute_hourly_trend([10.0, 20.0])
    assert result == "stable"


def test_compute_trend_up(coordinator: ParticleManCoordinator) -> None:
    forecast = [{"index": 5, "datetime": "2026-04-23T12:00:00+00:00", "category": "Moderate"}]
    assert coordinator._compute_trend(2, forecast) == "up"


def test_compute_trend_down(coordinator: ParticleManCoordinator) -> None:
    forecast = [{"index": 1, "datetime": "2026-04-23T12:00:00+00:00", "category": "Very Low"}]
    assert coordinator._compute_trend(4, forecast) == "down"


def test_compute_trend_flat(coordinator: ParticleManCoordinator) -> None:
    forecast = [{"index": 3, "datetime": "2026-04-23T12:00:00+00:00", "category": "Moderate"}]
    assert coordinator._compute_trend(3, forecast) == "flat"


def test_compute_trend_none_current(coordinator: ParticleManCoordinator) -> None:
    forecast = [{"index": 5}]
    assert coordinator._compute_trend(None, forecast) is None


def test_compute_trend_none_tomorrow(coordinator: ParticleManCoordinator) -> None:
    forecast = [{"index": None}]
    assert coordinator._compute_trend(3, forecast) is None


def test_compute_trend_empty_forecast(coordinator: ParticleManCoordinator) -> None:
    assert coordinator._compute_trend(3, []) is None


def test_compute_peak_with_entries(coordinator: ParticleManCoordinator) -> None:
    """_compute_peak returns entry with max index (lines 1319-1322)."""
    forecast = [
        {"index": 2, "datetime": "2026-04-23T12:00:00+00:00", "category": "Low"},
        {"index": 5, "datetime": "2026-04-24T12:00:00+00:00", "category": "Moderate"},
        {"index": 1, "datetime": "2026-04-25T12:00:00+00:00", "category": "Very Low"},
    ]
    result = coordinator._compute_peak(forecast)
    assert result is not None
    assert result["index"] == 5


def test_compute_peak_empty(coordinator: ParticleManCoordinator) -> None:
    assert coordinator._compute_peak([]) is None


def test_compute_peak_no_numeric_index(coordinator: ParticleManCoordinator) -> None:
    forecast = [{"index": None}, {"category": "Low"}]
    assert coordinator._compute_peak(forecast) is None


# ---------------------------------------------------------------------------
# Coordinator fetch interval instance attributes
# ---------------------------------------------------------------------------


def test_coordinator_default_fetch_intervals(coordinator: ParticleManCoordinator) -> None:
    """Defaults: 60-min intervals from module constants."""
    assert coordinator._aq_fetch_interval == timedelta(hours=1)
    assert coordinator._pollen_fetch_interval == timedelta(hours=1)


def test_coordinator_custom_fetch_intervals(hass: HomeAssistant, mock_config_entry) -> None:
    """Custom fetch intervals are stored as instance attrs."""
    mock_config_entry.add_to_hass(hass)
    with patch("custom_components.particle_man.coordinator.Store", autospec=True) as ms:
        ms.return_value.async_load = AsyncMock(return_value=None)
        ms.return_value.async_save = AsyncMock()
        c = ParticleManCoordinator(
            hass=hass,
            api_key=TEST_API_KEY,
            latitude=TEST_LAT,
            longitude=TEST_LON,
            aq_fetch_interval=timedelta(minutes=90),
            pollen_fetch_interval=timedelta(minutes=120),
            weather_calls_per_poll=4,
            config_entry=mock_config_entry,
        )
    assert c._aq_fetch_interval == timedelta(minutes=90)
    assert c._pollen_fetch_interval == timedelta(minutes=120)
    assert c.weather_calls_per_poll == 4
