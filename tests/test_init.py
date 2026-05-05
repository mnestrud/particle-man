"""Tests for particle_man __init__ (setup/unload/stale device removal)."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.core import HomeAssistant

from custom_components.particle_man.const import DOMAIN
from custom_components.particle_man import _opt, _remove_stale_devices
from tests.conftest import ENTRY_ID, register_api_mocks


# ---------------------------------------------------------------------------
# _opt helper
# ---------------------------------------------------------------------------


def test_opt_from_options() -> None:
    from pytest_homeassistant_custom_component.common import MockConfigEntry
    entry = MockConfigEntry(domain=DOMAIN, data={"key": "from_data"}, options={"key": "from_options"})
    assert _opt(entry, "key", "default") == "from_options"


def test_opt_fallback_to_data() -> None:
    from pytest_homeassistant_custom_component.common import MockConfigEntry
    entry = MockConfigEntry(domain=DOMAIN, data={"key": "from_data"}, options={})
    assert _opt(entry, "key", "default") == "from_data"


def test_opt_fallback_to_default() -> None:
    from pytest_homeassistant_custom_component.common import MockConfigEntry
    entry = MockConfigEntry(domain=DOMAIN, data={}, options={})
    assert _opt(entry, "missing", "default_val") == "default_val"


# ---------------------------------------------------------------------------
# async_setup_entry
# ---------------------------------------------------------------------------


async def test_setup_entry_no_locations(
    hass: HomeAssistant, mock_config_entry
) -> None:
    """Setup with no locations should succeed and create empty runtime_data."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry
    from custom_components.particle_man.const import CONF_LOCATIONS

    entry = MockConfigEntry(
        domain=DOMAIN,
        data=mock_config_entry.data,
        options={**mock_config_entry.options, CONF_LOCATIONS: []},
        entry_id=ENTRY_ID,
        version=3,
    )
    entry.add_to_hass(hass)

    with patch(
        "custom_components.particle_man.async_forward_entry_setups",
        return_value=True,
    ) if False else patch("homeassistant.config_entries.ConfigEntries.async_forward_entry_setups", return_value=True):
        result = await hass.config_entries.async_setup(entry.entry_id)
    assert result is True
    assert entry.runtime_data["coordinators"] == {}


async def test_setup_entry_with_location(
    hass: HomeAssistant, mock_config_entry, aioclient_mock
) -> None:
    """Setup with a location creates a coordinator."""
    register_api_mocks(aioclient_mock)
    mock_config_entry.add_to_hass(hass)

    with patch(
        "custom_components.particle_man.coordinator.Store", autospec=True
    ) as mock_store_cls:
        mock_store_cls.return_value.async_load = AsyncMock(return_value=None)
        mock_store_cls.return_value.async_save = AsyncMock()
        result = await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert result is True
    assert "coordinators" in mock_config_entry.runtime_data
    assert len(mock_config_entry.runtime_data["coordinators"]) == 1


async def test_unload_entry(
    hass: HomeAssistant, mock_config_entry, aioclient_mock
) -> None:
    """Unloading should return True and unload all platforms."""
    register_api_mocks(aioclient_mock)
    mock_config_entry.add_to_hass(hass)

    with patch(
        "custom_components.particle_man.coordinator.Store", autospec=True
    ) as mock_store_cls:
        mock_store_cls.return_value.async_load = AsyncMock(return_value=None)
        mock_store_cls.return_value.async_save = AsyncMock()
        await hass.config_entries.async_setup(mock_config_entry.entry_id)

    result = await hass.config_entries.async_unload(mock_config_entry.entry_id)
    assert result is True


# ---------------------------------------------------------------------------
# _remove_stale_devices
# ---------------------------------------------------------------------------


def test_remove_stale_devices_noop_when_all_valid(
    hass: HomeAssistant, mock_config_entry
) -> None:
    """No devices removed when all are in expected set."""
    from homeassistant.helpers import device_registry as dr
    from custom_components.particle_man.coordinator import ParticleManCoordinator

    mock_config_entry.add_to_hass(hass)
    dev_reg = dr.async_get(hass)
    # Register a device for Seattle
    dev_reg.async_get_or_create(
        config_entry_id=ENTRY_ID,
        identifiers={(DOMAIN, f"{ENTRY_ID}_seattle")},
        name="Seattle Pollution",
    )

    coord_mock = MagicMock()
    coord_mock.location_slug = "seattle"
    coordinators = {"Seattle": coord_mock}

    initial_count = len(dr.async_entries_for_config_entry(dev_reg, ENTRY_ID))
    _remove_stale_devices(hass, mock_config_entry, coordinators, True, True, True)
    final_count = len(dr.async_entries_for_config_entry(dev_reg, ENTRY_ID))
    assert final_count == initial_count


@pytest.mark.asyncio
async def test_async_reload_entry(
    hass: HomeAssistant, mock_config_entry
) -> None:
    """_async_reload_entry calls async_reload on the config entry (line 198)."""
    from custom_components.particle_man import _async_reload_entry

    mock_config_entry.add_to_hass(hass)
    with patch.object(hass.config_entries, "async_reload", return_value=True) as mock_reload:
        await _async_reload_entry(hass, mock_config_entry)
    mock_reload.assert_called_once_with(mock_config_entry.entry_id)


def test_remove_stale_devices_removes_orphan(
    hass: HomeAssistant, mock_config_entry
) -> None:
    """Orphaned device (old location no longer configured) is removed."""
    from homeassistant.helpers import device_registry as dr

    mock_config_entry.add_to_hass(hass)
    dev_reg = dr.async_get(hass)
    # Register an orphaned device
    dev_reg.async_get_or_create(
        config_entry_id=ENTRY_ID,
        identifiers={(DOMAIN, f"{ENTRY_ID}_old_location")},
        name="Old Location",
    )

    _remove_stale_devices(
        hass, mock_config_entry, {}, True, True, True
    )  # no coordinators = all orphaned
    remaining = dr.async_entries_for_config_entry(dev_reg, ENTRY_ID)
    # old_location device should be removed
    remaining_ids = {
        ident for d in remaining for ident in d.identifiers
    }
    assert (DOMAIN, f"{ENTRY_ID}_old_location") not in remaining_ids
