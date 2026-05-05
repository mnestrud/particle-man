"""Tests for particle_man config flow."""
from __future__ import annotations

import re
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.particle_man.config_flow import (
    _build_coverage_notes,
    _check_api_coverage,
    _classify_api_error,
    _projected_usage,
    _usage_summary,
)
from custom_components.particle_man.const import (
    CONF_API_KEY,
    CONF_LATITUDE,
    CONF_LOCATION_NAME,
    CONF_LONGITUDE,
    DOMAIN,
    _billing_month_days,
    _quiet_active_minutes_per_month,
    safe_interval_minutes,
)
from tests.conftest import (
    AQ_CURRENT_RESPONSE,
    POLLEN_RESPONSE,
    WEATHER_CURRENT_RESPONSE,
    TEST_API_KEY,
    TEST_LAT,
    TEST_LON,
    register_api_mocks,
)


# ---------------------------------------------------------------------------
# Pure function tests
# ---------------------------------------------------------------------------


def test_classify_api_error_service_disabled() -> None:
    body = {"error": {"message": "API has not been used", "details": []}}
    assert _classify_api_error(403, body) == "not_enabled"


def test_classify_api_error_service_disabled_reason() -> None:
    body = {
        "error": {
            "message": "",
            "details": [{"reason": "SERVICE_DISABLED"}],
        }
    }
    assert _classify_api_error(403, body) == "not_enabled"


def test_classify_api_error_invalid_auth_403() -> None:
    assert _classify_api_error(403, {}) == "invalid_auth"


def test_classify_api_error_invalid_auth_401() -> None:
    assert _classify_api_error(401, {}) == "invalid_auth"


def test_classify_api_error_invalid_auth_400() -> None:
    assert _classify_api_error(400, {}) == "invalid_auth"


def test_classify_api_error_cannot_connect() -> None:
    assert _classify_api_error(500, {}) == "cannot_connect"
    assert _classify_api_error(503, {}) == "cannot_connect"


def test_projected_usage() -> None:
    # Pass explicit minutes_per_month so the result is deterministic regardless of current month.
    # 44640 min/month (31 days) / 30 min interval * 3 calls/poll * 1 location = 4464
    assert _projected_usage(30, 1, 3, minutes_per_month=31 * 24 * 60) == 4464
    # 43200 min/month (30 days) / 30 min interval * 3 calls/poll * 1 location = 4320
    assert _projected_usage(30, 1, 3, minutes_per_month=30 * 24 * 60) == 4320


def test_usage_summary_no_apis() -> None:
    result = _usage_summary(30, 1, False, False, False, False, 0, 0, 0)
    assert "No APIs enabled" in result


def test_usage_summary_all_apis() -> None:
    result = _usage_summary(30, 1, True, True, True, False, 10000, 5000, 10000)
    assert "Air Quality" in result
    assert "Pollen" in result
    assert "Weather" in result


# ---------------------------------------------------------------------------
# Config flow: async_step_user
# ---------------------------------------------------------------------------


async def test_user_step_shows_form(hass: HomeAssistant) -> None:
    """Initial GET shows the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_user_step_success(
    hass: HomeAssistant, aioclient_mock
) -> None:
    """Successful API validation creates config entry."""
    register_api_mocks(aioclient_mock)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    assert result["type"] == FlowResultType.FORM

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_API_KEY: TEST_API_KEY,
            CONF_LOCATION_NAME: "Home",
            CONF_LATITUDE: TEST_LAT,
            CONF_LONGITUDE: TEST_LON,
        },
    )
    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["data"][CONF_API_KEY] == TEST_API_KEY


async def test_user_step_invalid_auth(
    hass: HomeAssistant, aioclient_mock
) -> None:
    """401 from API shows invalid_auth error."""
    aioclient_mock.post(
        re.compile(r".*airquality\.googleapis\.com.*"),
        status=401,
        json={"error": {"message": "API key invalid"}},
    )
    aioclient_mock.get(
        re.compile(r".*pollen\.googleapis\.com.*"),
        status=401,
        json={},
    )
    aioclient_mock.get(
        re.compile(r".*weather\.googleapis\.com.*"),
        status=401,
        json={},
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_API_KEY: "bad_key",
            CONF_LOCATION_NAME: "Home",
            CONF_LATITUDE: TEST_LAT,
            CONF_LONGITUDE: TEST_LON,
        },
    )
    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"].get("base") == "invalid_auth"


async def test_user_step_cannot_connect(
    hass: HomeAssistant, aioclient_mock
) -> None:
    """Connection error shows cannot_connect error."""
    import aiohttp

    aioclient_mock.post(
        re.compile(r".*airquality\.googleapis\.com.*"),
        exc=aiohttp.ClientConnectionError("connection refused"),
    )
    aioclient_mock.get(
        re.compile(r".*pollen\.googleapis\.com.*"),
        exc=aiohttp.ClientConnectionError("connection refused"),
    )
    aioclient_mock.get(
        re.compile(r".*weather\.googleapis\.com.*"),
        exc=aiohttp.ClientConnectionError("connection refused"),
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_API_KEY: TEST_API_KEY,
            CONF_LOCATION_NAME: "Home",
            CONF_LATITUDE: TEST_LAT,
            CONF_LONGITUDE: TEST_LON,
        },
    )
    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"].get("base") == "cannot_connect"


async def test_user_step_duplicate_entry(
    hass: HomeAssistant, aioclient_mock, mock_config_entry
) -> None:
    """Duplicate API key aborts."""
    register_api_mocks(aioclient_mock)
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_API_KEY: TEST_API_KEY,  # same key as mock_config_entry
            CONF_LOCATION_NAME: "Home",
            CONF_LATITUDE: TEST_LAT,
            CONF_LONGITUDE: TEST_LON,
        },
    )
    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "already_configured"


# ---------------------------------------------------------------------------
# Reauth flow
# ---------------------------------------------------------------------------


async def test_reauth_confirm_success(
    hass: HomeAssistant, aioclient_mock, mock_config_entry
) -> None:
    """Reauth with valid key updates entry and aborts."""
    register_api_mocks(aioclient_mock)
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "reauth", "entry_id": mock_config_entry.entry_id},
        data=mock_config_entry.data,
    )
    assert result["step_id"] in ("reauth_confirm", "reauth")

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_API_KEY: "new_valid_key"},
    )
    assert result2["type"] in (FlowResultType.ABORT, FlowResultType.CREATE_ENTRY)


async def test_reauth_confirm_invalid_key(
    hass: HomeAssistant, aioclient_mock, mock_config_entry
) -> None:
    """Reauth with invalid key shows error."""
    aioclient_mock.post(
        re.compile(r".*airquality.*"),
        status=403,
        json={},
    )
    aioclient_mock.get(re.compile(r".*pollen.*"), status=403, json={})
    aioclient_mock.get(re.compile(r".*weather.*"), status=403, json={})
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "reauth", "entry_id": mock_config_entry.entry_id},
        data=mock_config_entry.data,
    )
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_API_KEY: "bad_key"},
    )
    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"].get("base") == "invalid_auth"


# ---------------------------------------------------------------------------
# Reconfigure flow
# ---------------------------------------------------------------------------


async def test_reconfigure_shows_form(
    hass: HomeAssistant, mock_config_entry
) -> None:
    """Reconfigure flow shows form."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": "reconfigure",
            "entry_id": mock_config_entry.entry_id,
        },
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reconfigure"


async def test_reconfigure_success(
    hass: HomeAssistant, aioclient_mock, mock_config_entry
) -> None:
    """Successful reconfigure updates the API key."""
    register_api_mocks(aioclient_mock)
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": "reconfigure",
            "entry_id": mock_config_entry.entry_id,
        },
    )
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_API_KEY: "new_reconfigured_key"},
    )
    assert result2["type"] in (FlowResultType.ABORT, FlowResultType.CREATE_ENTRY)


# ---------------------------------------------------------------------------
# _build_coverage_notes
# ---------------------------------------------------------------------------


def test_build_coverage_notes_empty() -> None:
    statuses = {"aq": "ok", "pollen": "ok", "weather": "ok"}
    result = _build_coverage_notes(statuses)
    assert result == ""


def test_build_coverage_notes_not_covered() -> None:
    statuses = {"aq": "not_covered", "pollen": "ok", "weather": "ok"}
    result = _build_coverage_notes(statuses)
    assert "Air Quality" in result
    assert "not_covered" not in result


# ---------------------------------------------------------------------------
# _check_api_coverage
# ---------------------------------------------------------------------------


async def test_check_api_coverage_with_local_aqi(
    hass: HomeAssistant, aioclient_mock
) -> None:
    aioclient_mock.post(
        re.compile(r".*airquality\.googleapis\.com.*currentConditions.*"),
        status=200,
        json={
            "indexes": [
                {"code": "uaqi", "aqi": 45},
                {"code": "usa_epa", "aqi": 50},
            ]
        },
    )
    aioclient_mock.get(
        re.compile(r".*pollen\.googleapis\.com.*"),
        status=200,
        json={},
    )
    aioclient_mock.get(
        re.compile(r".*weather\.googleapis\.com.*currentConditions.*"),
        status=200,
        json={},
    )

    statuses, codes = await _check_api_coverage(hass, TEST_API_KEY, TEST_LAT, TEST_LON)
    assert statuses["aq"] == "ok"
    assert statuses["pollen"] == "ok"
    assert statuses["weather"] == "ok"
    assert "usa_epa" in codes
    assert "uaqi" not in codes


async def test_check_api_coverage_not_covered_aq(
    hass: HomeAssistant, aioclient_mock
) -> None:
    aioclient_mock.post(
        re.compile(r".*airquality\.googleapis\.com.*currentConditions.*"),
        status=404,
        json={},
    )
    aioclient_mock.get(
        re.compile(r".*pollen\.googleapis\.com.*"),
        status=200,
        json={},
    )
    aioclient_mock.get(
        re.compile(r".*weather\.googleapis\.com.*currentConditions.*"),
        status=200,
        json={},
    )

    statuses, codes = await _check_api_coverage(hass, TEST_API_KEY, TEST_LAT, TEST_LON)
    assert statuses["aq"] == "not_covered"
    assert statuses["pollen"] == "ok"
    assert statuses["weather"] == "ok"


async def test_check_api_coverage_not_covered_pollen(
    hass: HomeAssistant, aioclient_mock
) -> None:
    aioclient_mock.post(
        re.compile(r".*airquality\.googleapis\.com.*currentConditions.*"),
        status=200,
        json={"indexes": []},
    )
    aioclient_mock.get(
        re.compile(r".*pollen\.googleapis\.com.*"),
        status=404,
        json={},
    )
    aioclient_mock.get(
        re.compile(r".*weather\.googleapis\.com.*currentConditions.*"),
        status=200,
        json={},
    )

    statuses, _ = await _check_api_coverage(hass, TEST_API_KEY, TEST_LAT, TEST_LON)
    assert statuses["pollen"] == "not_covered"
    assert statuses["aq"] == "ok"


async def test_check_api_coverage_not_covered_weather(
    hass: HomeAssistant, aioclient_mock
) -> None:
    aioclient_mock.post(
        re.compile(r".*airquality\.googleapis\.com.*currentConditions.*"),
        status=200,
        json={"indexes": []},
    )
    aioclient_mock.get(
        re.compile(r".*pollen\.googleapis\.com.*"),
        status=200,
        json={},
    )
    aioclient_mock.get(
        re.compile(r".*weather\.googleapis\.com.*currentConditions.*"),
        status=404,
        json={},
    )

    statuses, _ = await _check_api_coverage(hass, TEST_API_KEY, TEST_LAT, TEST_LON)
    assert statuses["weather"] == "not_covered"
    assert statuses["aq"] == "ok"


# ---------------------------------------------------------------------------
# Config flow: error paths
# ---------------------------------------------------------------------------


async def test_user_step_not_enabled(
    hass: HomeAssistant, aioclient_mock
) -> None:
    aioclient_mock.post(
        re.compile(r".*airquality\.googleapis\.com.*"),
        status=403,
        json={"error": {"message": "", "details": [{"reason": "SERVICE_DISABLED"}]}},
    )
    aioclient_mock.get(
        re.compile(r".*pollen\.googleapis\.com.*"),
        status=403,
        json={"error": {"message": "", "details": [{"reason": "SERVICE_DISABLED"}]}},
    )
    aioclient_mock.get(
        re.compile(r".*weather\.googleapis\.com.*"),
        status=403,
        json={"error": {"message": "", "details": [{"reason": "SERVICE_DISABLED"}]}},
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_API_KEY: TEST_API_KEY,
            CONF_LOCATION_NAME: "Home",
            CONF_LATITUDE: TEST_LAT,
            CONF_LONGITUDE: TEST_LON,
        },
    )
    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"].get("base") in (
        "aq_not_enabled", "pollen_not_enabled", "weather_not_enabled"
    )


async def test_user_step_unknown_error(
    hass: HomeAssistant,
) -> None:
    with patch(
        "custom_components.particle_man.config_flow._check_api_coverage",
        side_effect=RuntimeError("boom"),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_API_KEY: TEST_API_KEY,
                CONF_LOCATION_NAME: "Home",
                CONF_LATITUDE: TEST_LAT,
                CONF_LONGITUDE: TEST_LON,
            },
        )
    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"].get("base") == "unknown"


async def test_reauth_not_enabled(
    hass: HomeAssistant, aioclient_mock, mock_config_entry
) -> None:
    aioclient_mock.post(
        re.compile(r".*airquality\.googleapis\.com.*"),
        status=403,
        json={"error": {"message": "", "details": [{"reason": "SERVICE_DISABLED"}]}},
    )
    aioclient_mock.get(
        re.compile(r".*pollen\.googleapis\.com.*"),
        status=403,
        json={"error": {"message": "", "details": [{"reason": "SERVICE_DISABLED"}]}},
    )
    aioclient_mock.get(
        re.compile(r".*weather\.googleapis\.com.*"),
        status=403,
        json={"error": {"message": "", "details": [{"reason": "SERVICE_DISABLED"}]}},
    )
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "reauth", "entry_id": mock_config_entry.entry_id},
        data=mock_config_entry.data,
    )
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_API_KEY: "some_key"},
    )
    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"].get("base") in (
        "aq_not_enabled", "pollen_not_enabled", "weather_not_enabled"
    )


async def test_reauth_unknown_error(
    hass: HomeAssistant, mock_config_entry
) -> None:
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "reauth", "entry_id": mock_config_entry.entry_id},
        data=mock_config_entry.data,
    )
    with patch(
        "custom_components.particle_man.config_flow._check_api_coverage",
        side_effect=RuntimeError("boom"),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_KEY: "some_key"},
        )
    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"].get("base") == "unknown"


async def test_reconfigure_invalid_key(
    hass: HomeAssistant, aioclient_mock, mock_config_entry
) -> None:
    aioclient_mock.post(
        re.compile(r".*airquality\.googleapis\.com.*"),
        status=401,
        json={},
    )
    aioclient_mock.get(re.compile(r".*pollen\.googleapis\.com.*"), status=401, json={})
    aioclient_mock.get(re.compile(r".*weather\.googleapis\.com.*"), status=401, json={})
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": "reconfigure",
            "entry_id": mock_config_entry.entry_id,
        },
    )
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_API_KEY: "bad_key"},
    )
    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"].get("base") == "invalid_auth"


async def test_reconfigure_unknown_error(
    hass: HomeAssistant, mock_config_entry
) -> None:
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": "reconfigure",
            "entry_id": mock_config_entry.entry_id,
        },
    )
    with patch(
        "custom_components.particle_man.config_flow._check_api_coverage",
        side_effect=RuntimeError("boom"),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_KEY: "some_key"},
        )
    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"].get("base") == "unknown"


async def test_check_api_coverage_non_json_error_body(
    hass: HomeAssistant, aioclient_mock
) -> None:
    """Non-JSON error response body hits except Exception: body_data = {} (lines 171, 194, 218)."""
    aioclient_mock.post(
        re.compile(r".*airquality\.googleapis\.com.*"),
        status=500,
        text="Internal Server Error",
    )
    aioclient_mock.get(
        re.compile(r".*pollen\.googleapis\.com.*"),
        status=500,
        text="Internal Server Error",
    )
    aioclient_mock.get(
        re.compile(r".*weather\.googleapis\.com.*"),
        status=500,
        text="Internal Server Error",
    )

    statuses, codes = await _check_api_coverage(hass, TEST_API_KEY, TEST_LAT, TEST_LON)
    assert statuses["aq"] == "cannot_connect"
    assert statuses["pollen"] == "cannot_connect"
    assert statuses["weather"] == "cannot_connect"
    assert codes == []


async def test_reconfigure_not_enabled(
    hass: HomeAssistant, aioclient_mock, mock_config_entry
) -> None:
    """Lines 445-446: reconfigure shows not_enabled error when API is SERVICE_DISABLED."""
    aioclient_mock.post(
        re.compile(r".*airquality\.googleapis\.com.*"),
        status=403,
        json={"error": {"message": "", "details": [{"reason": "SERVICE_DISABLED"}]}},
    )
    aioclient_mock.get(
        re.compile(r".*pollen\.googleapis\.com.*"),
        status=403,
        json={"error": {"message": "", "details": [{"reason": "SERVICE_DISABLED"}]}},
    )
    aioclient_mock.get(
        re.compile(r".*weather\.googleapis\.com.*"),
        status=403,
        json={"error": {"message": "", "details": [{"reason": "SERVICE_DISABLED"}]}},
    )
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "reconfigure", "entry_id": mock_config_entry.entry_id},
    )
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_API_KEY: "some_key"},
    )
    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"].get("base") in (
        "aq_not_enabled", "pollen_not_enabled", "weather_not_enabled"
    )


# ---------------------------------------------------------------------------
# const.py helper function tests
# ---------------------------------------------------------------------------


def test_billing_month_days_is_valid() -> None:
    days = _billing_month_days()
    assert 28 <= days <= 31


def test_quiet_active_minutes_no_wrap() -> None:
    # 22:00–08:00 = 10 quiet hours/day, 14 active hours/day
    active = _quiet_active_minutes_per_month("22:00:00", "08:00:00")
    days = _billing_month_days()
    assert active == days * 14 * 60


def test_quiet_active_minutes_midnight_spanning() -> None:
    # 23:00–05:00 = 6 quiet hours/day, 18 active hours/day
    active = _quiet_active_minutes_per_month("23:00:00", "05:00:00")
    days = _billing_month_days()
    assert active == days * 18 * 60


def test_safe_interval_minutes_applies_buffer() -> None:
    # 1 location, 3 calls/poll, 10000 limit, 44640 min/month (31 days)
    # raw = ceil(44640 * 3 * 1 * 1.05 / 10000) = ceil(14.0616) = 15
    result = safe_interval_minutes(1, {"weather": (3, 10000)}, 44640)
    assert result == 15


def test_safe_interval_minutes_floors_at_15() -> None:
    result = safe_interval_minutes(1, {}, 44640)
    assert result == 15


def test_safe_interval_minutes_scales_with_locations() -> None:
    # 7 locations, 2 calls/poll, 10000 limit, 44640 min/month
    # raw = ceil(44640 * 2 * 7 * 1.05 / 10000) = ceil(65.6064) = 66
    result = safe_interval_minutes(7, {"aq": (2, 10000)}, 44640)
    assert result == 66


def test_usage_summary_uses_minutes_per_month() -> None:
    # 30-day month: AQ projected = round(43200 / 60 * 2 * 1) = 1440
    result_30 = _usage_summary(30, 1, True, False, False, False, 10000, 5000, 10000,
                               minutes_per_month=30 * 24 * 60)
    # 31-day month: AQ projected = round(44640 / 60 * 2 * 1) = 1488
    result_31 = _usage_summary(30, 1, True, False, False, False, 10000, 5000, 10000,
                               minutes_per_month=31 * 24 * 60)
    assert "1440" in result_30
    assert "1488" in result_31
