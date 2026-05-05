"""Tests for particle_man switch platform."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.core import HomeAssistant

from custom_components.particle_man.coordinator import ParticleManGlobalState
from custom_components.particle_man.switch import QuietHoursSwitch
from tests.conftest import ENTRY_ID


@pytest.fixture
def global_state() -> ParticleManGlobalState:
    return ParticleManGlobalState()


def test_switch_unique_id(global_state: ParticleManGlobalState) -> None:
    s = QuietHoursSwitch(global_state, ENTRY_ID, False)
    assert s.unique_id == f"{ENTRY_ID}_quiet_hours"


def test_switch_translation_key(global_state: ParticleManGlobalState) -> None:
    s = QuietHoursSwitch(global_state, ENTRY_ID, False)
    assert s._attr_translation_key == "quiet_hours"


def test_switch_is_on_when_quiet_hours_enabled(global_state: ParticleManGlobalState) -> None:
    s = QuietHoursSwitch(global_state, ENTRY_ID, True)
    assert s.is_on is True


def test_switch_is_off_when_quiet_hours_disabled(global_state: ParticleManGlobalState) -> None:
    s = QuietHoursSwitch(global_state, ENTRY_ID, False)
    assert s.is_on is False


async def test_switch_turn_on(hass: HomeAssistant) -> None:
    gs = ParticleManGlobalState()
    s = QuietHoursSwitch(gs, ENTRY_ID, False)
    s.hass = hass
    with patch.object(s, "async_write_ha_state"):
        await s.async_turn_on()
    assert gs.quiet_hours_active(True) is True


async def test_switch_turn_off(hass: HomeAssistant) -> None:
    gs = ParticleManGlobalState()
    s = QuietHoursSwitch(gs, ENTRY_ID, True)
    s.hass = hass
    with patch.object(s, "async_write_ha_state"):
        await s.async_turn_off()
    assert gs.quiet_hours_active(False) is False
