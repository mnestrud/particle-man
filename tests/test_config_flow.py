"""Tests for Particle Man config flow and options flow."""
import pytest
from unittest.mock import patch

from homeassistant import config_entries, data_entry_flow

from custom_components.particle_man.const import (
    CONF_API_KEY,
    CONF_AUTOMAGIC_MODE,
    CONF_ENABLE_AIR_QUALITY,
    CONF_ENABLE_POLLEN,
    CONF_ENABLE_WEATHER,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_QUIET_END,
    CONF_QUIET_HOURS_ENABLED,
    CONF_QUIET_START,
    DOMAIN,
)

from .conftest import MOCK_API_KEY, MOCK_LAT, MOCK_LON

USER_INPUT = {
    CONF_API_KEY: MOCK_API_KEY,
    CONF_LATITUDE: MOCK_LAT,
    CONF_LONGITUDE: MOCK_LON,
}

_OK_COVERAGE = ({"aq": "ok", "pollen": "ok", "weather": "ok"}, [])
_INVALID_AUTH_COVERAGE = ({"aq": "invalid_auth", "pollen": "ok", "weather": "ok"}, [])
_CANNOT_CONNECT_COVERAGE = ({"aq": "cannot_connect", "pollen": "ok", "weather": "ok"}, [])


# ---------------------------------------------------------------------------
# Config flow
# ---------------------------------------------------------------------------

async def test_config_flow_shows_form(hass):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_config_flow_success(hass):
    with patch(
        "custom_components.particle_man.config_flow._check_api_coverage",
        return_value=_OK_COVERAGE,
    ), patch(
        "custom_components.particle_man.async_setup_entry",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=USER_INPUT
        )

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_API_KEY] == MOCK_API_KEY


async def test_config_flow_invalid_auth(hass):
    with patch(
        "custom_components.particle_man.config_flow._check_api_coverage",
        return_value=_INVALID_AUTH_COVERAGE,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=USER_INPUT
        )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"]["base"] == "invalid_auth"


async def test_config_flow_bad_request_is_invalid_auth(hass):
    with patch(
        "custom_components.particle_man.config_flow._check_api_coverage",
        return_value=_INVALID_AUTH_COVERAGE,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=USER_INPUT
        )

    assert result["errors"]["base"] == "invalid_auth"


async def test_config_flow_cannot_connect(hass):
    with patch(
        "custom_components.particle_man.config_flow._check_api_coverage",
        return_value=_CANNOT_CONNECT_COVERAGE,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=USER_INPUT
        )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"]["base"] == "cannot_connect"


async def test_config_flow_unknown_error(hass):
    with patch(
        "custom_components.particle_man.config_flow._check_api_coverage",
        side_effect=RuntimeError("unexpected"),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=USER_INPUT
        )

    assert result["errors"]["base"] == "unknown"


async def test_config_flow_duplicate_location_aborted(hass):
    with patch(
        "custom_components.particle_man.config_flow._check_api_coverage",
        return_value=_OK_COVERAGE,
    ), patch(
        "custom_components.particle_man.async_setup_entry",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=USER_INPUT
        )

        # Second entry for same API key should abort
        result2 = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result2 = await hass.config_entries.flow.async_configure(
            result2["flow_id"], user_input=USER_INPUT
        )

    assert result2["type"] == data_entry_flow.FlowResultType.ABORT
    assert result2["reason"] == "already_configured"


# ---------------------------------------------------------------------------
# Options flow
# ---------------------------------------------------------------------------

async def test_options_flow_shows_form(hass, mock_config_entry):
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "init"


async def test_options_flow_saves_flattened_options(hass, mock_config_entry):
    mock_config_entry.add_to_hass(hass)

    # Step 1: init
    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={CONF_AUTOMAGIC_MODE: True}
    )
    assert result["step_id"] == "locations"

    # Step 2: locations — mock_config_entry already has one location, so "continue" is available
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={"action": "continue"}
    )
    assert result["step_id"] == "quiet_hours"

    # Step 3: quiet hours
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_QUIET_HOURS_ENABLED: False,
            CONF_QUIET_START: "22:00:00",
            CONF_QUIET_END: "06:00:00",
        },
    )
    assert result["step_id"] == "apis"

    # Step 4: apis — in automagic mode, creates entry directly after this step
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_ENABLE_AIR_QUALITY: True,
            CONF_ENABLE_POLLEN: True,
            CONF_ENABLE_WEATHER: True,
        },
    )

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_AUTOMAGIC_MODE] is True
    assert result["data"][CONF_ENABLE_AIR_QUALITY] is True
