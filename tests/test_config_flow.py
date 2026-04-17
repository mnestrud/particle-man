"""Tests for Particle Man config flow and options flow."""
import pytest
from unittest.mock import MagicMock, patch
import aiohttp

from homeassistant import config_entries, data_entry_flow

from custom_components.particle_man.const import (
    CONF_API_KEY,
    CONF_FORECAST_DAYS,
    CONF_LANGUAGE,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_UPDATE_INTERVAL,
    DOMAIN,
)

from .conftest import MOCK_API_KEY, MOCK_LAT, MOCK_LON

USER_INPUT = {
    CONF_API_KEY: MOCK_API_KEY,
    CONF_LATITUDE: MOCK_LAT,
    CONF_LONGITUDE: MOCK_LON,
    CONF_UPDATE_INTERVAL: 60,
}

OPTIONS_INPUT = {
    "location": {
        CONF_LATITUDE: MOCK_LAT,
        CONF_LONGITUDE: MOCK_LON,
        CONF_UPDATE_INTERVAL: 30,
    },
    "forecast": {
        CONF_FORECAST_DAYS: 3,
        CONF_LANGUAGE: "en",
    },
    "air_quality": {
        "enable_local_aqi": False,
        "local_aqi_code": "us_aqi",
        "include_health_recommendations": False,
    },
    "pollen": {
        "include_plant_sensors": True,
        "include_plant_descriptions": True,
    },
    "api_limits": {
        "aq_monthly_limit": 10000,
        "pollen_monthly_limit": 5000,
        "reset_day": 1,
        "enforce_limits": False,
    },
}


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
        "custom_components.particle_man.config_flow._validate_api_key",
        return_value=None,
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
    assert result["data"][CONF_LATITUDE] == MOCK_LAT
    assert result["data"][CONF_LONGITUDE] == MOCK_LON


async def test_config_flow_invalid_auth(hass):
    err = aiohttp.ClientResponseError(MagicMock(), (), status=403, message="Forbidden")
    with patch(
        "custom_components.particle_man.config_flow._validate_api_key",
        side_effect=err,
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
    err = aiohttp.ClientResponseError(MagicMock(), (), status=400, message="Bad Request")
    with patch(
        "custom_components.particle_man.config_flow._validate_api_key",
        side_effect=err,
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
        "custom_components.particle_man.config_flow._validate_api_key",
        side_effect=aiohttp.ClientError("connection refused"),
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
        "custom_components.particle_man.config_flow._validate_api_key",
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
        "custom_components.particle_man.config_flow._validate_api_key",
        return_value=None,
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

        # Second entry for same lat/lon should abort
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

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input=OPTIONS_INPUT
    )

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    # Sections should be flattened into a single dict
    assert result["data"][CONF_UPDATE_INTERVAL] == 30
    assert result["data"][CONF_FORECAST_DAYS] == 3
    assert result["data"][CONF_LATITUDE] == MOCK_LAT
    assert result["data"]["enforce_limits"] is False
