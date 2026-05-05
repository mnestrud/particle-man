"""Tests for particle_man diagnostics platform."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.core import HomeAssistant

from custom_components.particle_man.const import CONF_API_KEY, DOMAIN
from tests.conftest import ENTRY_ID, register_api_mocks


async def test_diagnostics_redacts_api_key(
    hass: HomeAssistant, mock_config_entry, aioclient_mock
) -> None:
    """API key is redacted in diagnostics output."""
    register_api_mocks(aioclient_mock)
    mock_config_entry.add_to_hass(hass)

    with patch(
        "custom_components.particle_man.coordinator.Store", autospec=True
    ) as mock_store_cls:
        mock_store_cls.return_value.async_load = AsyncMock(return_value=None)
        mock_store_cls.return_value.async_save = AsyncMock()
        await hass.config_entries.async_setup(mock_config_entry.entry_id)

    from custom_components.particle_man.diagnostics import async_get_config_entry_diagnostics

    result = await async_get_config_entry_diagnostics(hass, mock_config_entry)
    assert isinstance(result, dict)
    # API key must not appear in the output
    import json
    result_str = json.dumps(result)
    assert mock_config_entry.data[CONF_API_KEY] not in result_str


async def test_diagnostics_contains_coordinator_data(
    hass: HomeAssistant, mock_config_entry, aioclient_mock
) -> None:
    """Diagnostics includes coordinator data keys."""
    register_api_mocks(aioclient_mock)
    mock_config_entry.add_to_hass(hass)

    with patch(
        "custom_components.particle_man.coordinator.Store", autospec=True
    ) as mock_store_cls:
        mock_store_cls.return_value.async_load = AsyncMock(return_value=None)
        mock_store_cls.return_value.async_save = AsyncMock()
        await hass.config_entries.async_setup(mock_config_entry.entry_id)

    from custom_components.particle_man.diagnostics import async_get_config_entry_diagnostics

    result = await async_get_config_entry_diagnostics(hass, mock_config_entry)
    assert "entry" in result
