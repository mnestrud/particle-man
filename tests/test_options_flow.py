"""Tests for particle_man options flow."""
from __future__ import annotations

import re
from unittest.mock import patch

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.particle_man.const import (
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
    CONF_LATITUDE,
    CONF_LOCATION_NAME,
    CONF_LOCATIONS,
    CONF_LONGITUDE,
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
from tests.conftest import (
    MOCK_ENTRY_DATA,
    MOCK_ENTRY_OPTIONS,
    TEST_LAT,
    TEST_LON,
    TEST_LOCATION_NAME,
)

_PATCH_COVERAGE = "custom_components.particle_man.config_flow._check_api_coverage"
_ALL_OK_STATUSES = {"aq": "ok", "pollen": "ok", "weather": "ok"}


async def test_options_init_shows_form(
    hass: HomeAssistant, mock_config_entry
) -> None:
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "init"


async def test_options_automagic_complete_path(
    hass: HomeAssistant, mock_config_entry
) -> None:
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_AUTOMAGIC_MODE: True}
    )
    assert result["step_id"] == "locations"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"action": "continue"}
    )
    assert result["step_id"] == "quiet_hours"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_QUIET_HOURS_ENABLED: False,
            CONF_QUIET_START: DEFAULT_QUIET_START,
            CONF_QUIET_END: DEFAULT_QUIET_END,
        },
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY


async def test_options_manual_all_apis_path(
    hass: HomeAssistant, mock_config_entry
) -> None:
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_AUTOMAGIC_MODE: False}
    )
    assert result["step_id"] == "locations"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"action": "continue"}
    )
    assert result["step_id"] == "quiet_hours"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_QUIET_HOURS_ENABLED: False,
            CONF_QUIET_START: DEFAULT_QUIET_START,
            CONF_QUIET_END: DEFAULT_QUIET_END,
        },
    )
    assert result["step_id"] == "apis"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_ENABLE_AIR_QUALITY: True,
            CONF_ENABLE_POLLEN: True,
            CONF_ENABLE_WEATHER: True,
            CONF_UPDATE_INTERVAL: 30,
        },
    )
    assert result["step_id"] == "air_quality"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_FORECAST_DAYS: DEFAULT_FORECAST_DAYS,
            CONF_LANGUAGE: DEFAULT_LANGUAGE,
            CONF_LOCAL_AQI: False,
            CONF_LOCAL_AQI_CODE: DEFAULT_LOCAL_AQI_CODE,
        },
    )
    assert result["step_id"] == "weather"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_WEATHER_UNITS: "METRIC",
            CONF_ENABLE_WEATHER_ALERTS: False,
        },
    )
    assert result["step_id"] == "api_limits"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_AQ_MONTHLY_LIMIT: DEFAULT_AQ_MONTHLY_LIMIT,
            CONF_POLLEN_MONTHLY_LIMIT: DEFAULT_POLLEN_MONTHLY_LIMIT,
            CONF_WEATHER_MONTHLY_LIMIT: DEFAULT_WEATHER_MONTHLY_LIMIT,
        },
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY


async def test_options_manual_no_apis_path(
    hass: HomeAssistant, mock_config_entry
) -> None:
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_AUTOMAGIC_MODE: False}
    )

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"action": "continue"}
    )
    assert result["step_id"] == "quiet_hours"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_QUIET_HOURS_ENABLED: False,
            CONF_QUIET_START: DEFAULT_QUIET_START,
            CONF_QUIET_END: DEFAULT_QUIET_END,
        },
    )
    assert result["step_id"] == "apis"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_ENABLE_AIR_QUALITY: False,
            CONF_ENABLE_POLLEN: False,
            CONF_ENABLE_WEATHER: False,
            CONF_UPDATE_INTERVAL: 60,
        },
    )
    assert result["step_id"] == "api_limits"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {}
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY


async def test_options_add_location(
    hass: HomeAssistant, mock_config_entry
) -> None:
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_AUTOMAGIC_MODE: True}
    )
    assert result["step_id"] == "locations"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"action": "add"}
    )
    assert result["step_id"] == "add_location"

    with patch(_PATCH_COVERAGE, return_value=(_ALL_OK_STATUSES, [])):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {
                CONF_LOCATION_NAME: "Portland",
                CONF_LATITUDE: 45.5051,
                CONF_LONGITUDE: -122.6750,
            },
        )
    assert result["step_id"] == "locations"


async def test_options_add_location_coverage_check(
    hass: HomeAssistant, mock_config_entry
) -> None:
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_AUTOMAGIC_MODE: True}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"action": "add"}
    )
    assert result["step_id"] == "add_location"

    coverage_statuses = {"aq": "ok", "pollen": "not_covered", "weather": "ok"}
    with patch(_PATCH_COVERAGE, return_value=(coverage_statuses, ["us_aqi", "can_ec"])):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {
                CONF_LOCATION_NAME: "Remote Town",
                CONF_LATITUDE: 60.0,
                CONF_LONGITUDE: -140.0,
            },
        )
    assert result["step_id"] == "locations"


async def test_options_remove_location(
    hass: HomeAssistant, mock_config_entry
) -> None:
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_AUTOMAGIC_MODE: True}
    )
    assert result["step_id"] == "locations"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"action": "remove"}
    )
    assert result["step_id"] == "remove_location"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_LOCATION_NAME: TEST_LOCATION_NAME}
    )
    assert result["step_id"] == "locations"


async def test_options_locations_empty_cannot_continue(
    hass: HomeAssistant,
) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_ENTRY_DATA,
        options={**MOCK_ENTRY_OPTIONS, CONF_LOCATIONS: []},
        entry_id="empty_locs_entry",
        unique_id="empty_locs_unique",
        version=3,
    )
    entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_AUTOMAGIC_MODE: True}
    )
    assert result["step_id"] == "locations"

    placeholder = result.get("description_placeholders", {}).get("location_list", "")
    assert "No locations" in placeholder

    import voluptuous as vol
    try:
        result["data_schema"]({"action": "continue"})
        can_continue = True
    except vol.Invalid:
        can_continue = False
    assert not can_continue


async def test_options_add_location_empty_name(
    hass: HomeAssistant, mock_config_entry
) -> None:
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_AUTOMAGIC_MODE: True}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"action": "add"}
    )
    assert result["step_id"] == "add_location"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_LOCATION_NAME: "   ",
            CONF_LATITUDE: TEST_LAT,
            CONF_LONGITUDE: TEST_LON,
        },
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "add_location"
    assert result["errors"].get(CONF_LOCATION_NAME) == "location_name_required"


async def test_options_add_location_duplicate_name(
    hass: HomeAssistant, mock_config_entry
) -> None:
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_AUTOMAGIC_MODE: True}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"action": "add"}
    )
    assert result["step_id"] == "add_location"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_LOCATION_NAME: TEST_LOCATION_NAME,
            CONF_LATITUDE: TEST_LAT,
            CONF_LONGITUDE: TEST_LON,
        },
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "add_location"
    assert result["errors"].get(CONF_LOCATION_NAME) == "location_name_duplicate"


async def test_options_add_location_not_enabled(
    hass: HomeAssistant, mock_config_entry
) -> None:
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_AUTOMAGIC_MODE: True}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"action": "add"}
    )
    assert result["step_id"] == "add_location"

    not_enabled_statuses = {"aq": "not_enabled", "pollen": "ok", "weather": "ok"}
    with patch(_PATCH_COVERAGE, return_value=(not_enabled_statuses, [])):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {
                CONF_LOCATION_NAME: "New City",
                CONF_LATITUDE: TEST_LAT,
                CONF_LONGITUDE: TEST_LON,
            },
        )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "add_location"
    assert result["errors"].get("base") == "aq_not_enabled"


async def test_options_air_quality_with_local_aqi(
    hass: HomeAssistant, mock_config_entry
) -> None:
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_AUTOMAGIC_MODE: False}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"action": "continue"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_QUIET_HOURS_ENABLED: False,
            CONF_QUIET_START: DEFAULT_QUIET_START,
            CONF_QUIET_END: DEFAULT_QUIET_END,
        },
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_ENABLE_AIR_QUALITY: True,
            CONF_ENABLE_POLLEN: False,
            CONF_ENABLE_WEATHER: False,
            CONF_UPDATE_INTERVAL: 60,
        },
    )
    assert result["step_id"] == "air_quality"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_FORECAST_DAYS: 3,
            CONF_LANGUAGE: "en",
            CONF_LOCAL_AQI: True,
            CONF_LOCAL_AQI_CODE: "us_aqi",
        },
    )
    assert result["step_id"] == "api_limits"


async def test_options_air_quality_invalid_local_aqi_code(
    hass: HomeAssistant, mock_config_entry
) -> None:
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_AUTOMAGIC_MODE: False}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"action": "continue"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_QUIET_HOURS_ENABLED: False,
            CONF_QUIET_START: DEFAULT_QUIET_START,
            CONF_QUIET_END: DEFAULT_QUIET_END,
        },
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_ENABLE_AIR_QUALITY: True,
            CONF_ENABLE_POLLEN: False,
            CONF_ENABLE_WEATHER: False,
            CONF_UPDATE_INTERVAL: 60,
        },
    )
    assert result["step_id"] == "air_quality"

    flow_obj = hass.config_entries.options._progress[result["flow_id"]]
    flow_obj._available_local_aqi_codes = ["us_aqi", "can_ec"]

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_FORECAST_DAYS: 3,
            CONF_LANGUAGE: "en",
            CONF_LOCAL_AQI: True,
            CONF_LOCAL_AQI_CODE: "jpn_caqi",
        },
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "air_quality"
    assert result["errors"].get(CONF_LOCAL_AQI_CODE) == "local_aqi_unavailable"


async def test_options_api_limits_some_disabled(
    hass: HomeAssistant, mock_config_entry
) -> None:
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_AUTOMAGIC_MODE: False}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"action": "continue"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_QUIET_HOURS_ENABLED: False,
            CONF_QUIET_START: DEFAULT_QUIET_START,
            CONF_QUIET_END: DEFAULT_QUIET_END,
        },
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_ENABLE_AIR_QUALITY: True,
            CONF_ENABLE_POLLEN: False,
            CONF_ENABLE_WEATHER: False,
            CONF_UPDATE_INTERVAL: 60,
        },
    )
    assert result["step_id"] == "air_quality"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_FORECAST_DAYS: DEFAULT_FORECAST_DAYS,
            CONF_LANGUAGE: DEFAULT_LANGUAGE,
            CONF_LOCAL_AQI: False,
            CONF_LOCAL_AQI_CODE: DEFAULT_LOCAL_AQI_CODE,
        },
    )
    assert result["step_id"] == "api_limits"

    schema_keys = [str(k) for k in result["data_schema"].schema.keys()]
    assert CONF_AQ_MONTHLY_LIMIT in schema_keys
    assert CONF_POLLEN_MONTHLY_LIMIT not in schema_keys
    assert CONF_WEATHER_MONTHLY_LIMIT not in schema_keys

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {CONF_AQ_MONTHLY_LIMIT: DEFAULT_AQ_MONTHLY_LIMIT},
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY


# ---------------------------------------------------------------------------
# _next_step dead-code path (line 543) — direct unit test
# ---------------------------------------------------------------------------


def test_next_step_returns_none_after_api_limits() -> None:
    """_next_step('api_limits') hits the end of the order list and returns None (line 543)."""
    from custom_components.particle_man.config_flow import ParticleManOptionsFlow
    flow = ParticleManOptionsFlow()
    flow._options = {CONF_AUTOMAGIC_MODE: False}
    assert flow._next_step("api_limits") is None


# ---------------------------------------------------------------------------
# add_location coverage-check exception (lines 655-656)
# ---------------------------------------------------------------------------


async def test_options_add_location_coverage_exception(
    hass: HomeAssistant, mock_config_entry
) -> None:
    """_check_api_coverage raises → location is added anyway (except block logs and continues)."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_AUTOMAGIC_MODE: True}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"action": "add"}
    )
    assert result["step_id"] == "add_location"

    with patch(_PATCH_COVERAGE, side_effect=RuntimeError("coverage down")):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {
                CONF_LOCATION_NAME: "New City",
                CONF_LATITUDE: TEST_LAT,
                CONF_LONGITUDE: TEST_LON,
            },
        )
    assert result["step_id"] == "locations"


# ---------------------------------------------------------------------------
# Step create_entry fallbacks (lines 759, 831, 879, 906)
# These are dead code (api_limits is always True) but covered via patching _next_step.
# ---------------------------------------------------------------------------


async def _navigate_to_apis(hass: HomeAssistant, entry_id: str) -> tuple[str, str]:
    """Navigate init→locations→quiet_hours→apis; return (flow_id, step_id)."""
    result = await hass.config_entries.options.async_init(entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_AUTOMAGIC_MODE: False}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"action": "continue"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {CONF_QUIET_HOURS_ENABLED: False, CONF_QUIET_START: DEFAULT_QUIET_START, CONF_QUIET_END: DEFAULT_QUIET_END},
    )
    assert result["step_id"] == "apis"
    return result["flow_id"], result["step_id"]


async def test_step_apis_create_entry_no_next_step(
    hass: HomeAssistant, mock_config_entry
) -> None:
    """Line 759: async_step_apis falls through to _create_entry when _next_step is None."""
    mock_config_entry.add_to_hass(hass)
    flow_id, _ = await _navigate_to_apis(hass, mock_config_entry.entry_id)

    flow_obj = hass.config_entries.options._progress[flow_id]
    with patch.object(flow_obj, "_next_step", return_value=None):
        result = await hass.config_entries.options.async_configure(
            flow_id,
            {
                CONF_ENABLE_AIR_QUALITY: True,
                CONF_ENABLE_POLLEN: True,
                CONF_ENABLE_WEATHER: True,
                CONF_UPDATE_INTERVAL: 30,
            },
        )
    assert result["type"] == FlowResultType.CREATE_ENTRY


async def test_step_air_quality_create_entry_no_next_step(
    hass: HomeAssistant, mock_config_entry
) -> None:
    """Line 831: async_step_air_quality falls through to _create_entry when _next_step is None."""
    mock_config_entry.add_to_hass(hass)
    flow_id, _ = await _navigate_to_apis(hass, mock_config_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        flow_id,
        {CONF_ENABLE_AIR_QUALITY: True, CONF_ENABLE_POLLEN: True, CONF_ENABLE_WEATHER: True, CONF_UPDATE_INTERVAL: 30},
    )
    assert result["step_id"] == "air_quality"

    flow_obj = hass.config_entries.options._progress[flow_id]
    with patch.object(flow_obj, "_next_step", return_value=None):
        result = await hass.config_entries.options.async_configure(
            flow_id,
            {
                CONF_FORECAST_DAYS: DEFAULT_FORECAST_DAYS,
                CONF_LANGUAGE: DEFAULT_LANGUAGE,
                CONF_LOCAL_AQI: False,
                CONF_LOCAL_AQI_CODE: DEFAULT_LOCAL_AQI_CODE,
            },
        )
    assert result["type"] == FlowResultType.CREATE_ENTRY


async def test_step_weather_create_entry_no_next_step(
    hass: HomeAssistant, mock_config_entry
) -> None:
    """Line 906: async_step_weather falls through to _create_entry when _next_step is None."""
    mock_config_entry.add_to_hass(hass)
    flow_id, _ = await _navigate_to_apis(hass, mock_config_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        flow_id,
        {CONF_ENABLE_AIR_QUALITY: True, CONF_ENABLE_POLLEN: True, CONF_ENABLE_WEATHER: True, CONF_UPDATE_INTERVAL: 30},
    )
    result = await hass.config_entries.options.async_configure(
        flow_id,
        {CONF_FORECAST_DAYS: DEFAULT_FORECAST_DAYS, CONF_LANGUAGE: DEFAULT_LANGUAGE, CONF_LOCAL_AQI: False, CONF_LOCAL_AQI_CODE: DEFAULT_LOCAL_AQI_CODE},
    )
    assert result["step_id"] == "weather"

    flow_obj = hass.config_entries.options._progress[flow_id]
    with patch.object(flow_obj, "_next_step", return_value=None):
        result = await hass.config_entries.options.async_configure(
            flow_id,
            {CONF_WEATHER_UNITS: "METRIC", CONF_ENABLE_WEATHER_ALERTS: False},
        )
    assert result["type"] == FlowResultType.CREATE_ENTRY
