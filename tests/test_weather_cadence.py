"""Per-endpoint weather cadence, pagination and quota-filter behaviour.

These cover the parts of the refactor that the existing suite cannot see:
endpoints refreshing independently, the carry-forward that keeps un-refreshed
data alive, and paginated hourly fetches that must count every billable page.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMockResponse,
)

from custom_components.particle_man.const import (
    W_ALERTS,
    W_CURRENT,
    W_DAYS,
    W_HOURS,
    solve_weather_plan,
)
from custom_components.particle_man.coordinator import ParticleManCoordinator
from tests.conftest import (
    TEST_API_KEY,
    TEST_LAT,
    TEST_LON,
    register_api_mocks,
)

T0 = datetime(2026, 8, 12, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def coord(hass: HomeAssistant, mock_config_entry):
    """Coordinator with a known plan: current 15m, hours 60m, days 180m, alerts 30m."""
    mock_config_entry.add_to_hass(hass)
    plan = solve_weather_plan(
        num_locations=1,
        effective_minutes=33480,
        monthly_limit=10000,
        enable_alerts=True,
        enable_minutecast=False,
    )
    with patch(
        "custom_components.particle_man.coordinator.Store", autospec=True
    ) as mock_store_cls:
        store = AsyncMock()
        store.async_load = AsyncMock(return_value=None)
        store.async_save = AsyncMock()
        mock_store_cls.return_value = store
        c = ParticleManCoordinator(
            hass=hass,
            api_key=TEST_API_KEY,
            latitude=TEST_LAT,
            longitude=TEST_LON,
            location_name="Seattle",
            enable_air_quality=False,
            enable_pollen=False,
            enable_weather=True,
            enable_weather_alerts=True,
            quiet_hours_enabled=False,
            weather_plan=plan,
            entry_id="test_entry_id",
            config_entry=mock_config_entry,
        )
        c._save_tracking = AsyncMock()
        c.data = {}
        yield c


async def _tick(coord: ParticleManCoordinator, when: datetime) -> dict[str, Any]:
    """Run one coordinator update at a fixed wall-clock time."""
    with patch(
        "custom_components.particle_man.coordinator.dt_util.utcnow", return_value=when
    ):
        result = await coord._async_update_data()
    coord.data = result
    return result


def _weather_inc(coord: ParticleManCoordinator) -> int:
    return coord._save_tracking.await_args.kwargs["weather_inc"]


# ---------------------------------------------------------------------------
# Gating
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_first_tick_fetches_everything(coord, aioclient_mock) -> None:
    register_api_mocks(aioclient_mock)
    await _tick(coord, T0)
    assert set(coord._last_weather_endpoint_fetch) == {W_CURRENT, W_HOURS, W_DAYS, W_ALERTS}


@pytest.mark.asyncio
async def test_only_due_endpoints_refetch(coord, aioclient_mock) -> None:
    """15 minutes later only current conditions is due."""
    register_api_mocks(aioclient_mock)
    await _tick(coord, T0)
    await _tick(coord, T0 + timedelta(minutes=15))

    assert coord._last_weather_endpoint_fetch[W_CURRENT] == T0 + timedelta(minutes=15)
    assert coord._last_weather_endpoint_fetch[W_HOURS] == T0
    assert coord._last_weather_endpoint_fetch[W_DAYS] == T0
    # current only: pages[current] == 1
    assert _weather_inc(coord) == 1


@pytest.mark.asyncio
async def test_carry_forward_preserves_unrefreshed_data(coord, aioclient_mock) -> None:
    """The most important regression: a partial tick must not erase forecasts.

    _build_weather_data used to write every key unconditionally, so a tick that
    only fetched current conditions would overwrite the hourly forecast with [].
    """
    # The shared fixtures return empty forecasts, which cannot distinguish
    # "preserved" from "erased". Serve real entries first — aioclient_mock uses
    # the first matching registration.
    aioclient_mock.get(
        re.compile(r".*weather\.googleapis\.com.*forecast/hours.*"),
        json=_page(0, 1),
    )
    register_api_mocks(aioclient_mock)

    first = await _tick(coord, T0)
    hourly_before = first["weather_hourly"]
    daily_before = first["weather_daily"]
    assert len(hourly_before) == 24, "fixture should produce a populated forecast"

    second = await _tick(coord, T0 + timedelta(minutes=15))

    assert second["weather_hourly"] == hourly_before
    assert second["weather_daily"] == daily_before
    assert second["weather_current"]


@pytest.mark.asyncio
async def test_cadence_survives_early_scheduling_drift(coord, aioclient_mock) -> None:
    """HA schedules each tick fractionally early; that must not stretch cadences.

    Without slack the accumulated drift makes `elapsed >= cadence` false on the
    tick where the hourly forecast is due, silently turning 60 minutes into 75.
    """
    register_api_mocks(aioclient_mock)
    await _tick(coord, T0)

    drift = timedelta(milliseconds=-900)
    for i in range(1, 5):
        await _tick(coord, T0 + timedelta(minutes=15 * i) + drift * i)

    # The 60-minute endpoint must have refreshed on the fourth tick.
    assert coord._last_weather_endpoint_fetch[W_HOURS] > T0


@pytest.mark.asyncio
async def test_alerts_run_twice_as_often_as_hourly(coord, aioclient_mock) -> None:
    register_api_mocks(aioclient_mock)
    await _tick(coord, T0)
    await _tick(coord, T0 + timedelta(minutes=30))

    assert coord._last_weather_endpoint_fetch[W_ALERTS] == T0 + timedelta(minutes=30)
    assert coord._last_weather_endpoint_fetch[W_HOURS] == T0


# ---------------------------------------------------------------------------
# Quota filtering
# ---------------------------------------------------------------------------

def test_quota_filter_reserves_for_alerts_and_current(coord) -> None:
    """Near the limit, only the safety-relevant endpoints keep running."""
    coord._cached_tracking = {"weather_calls": 9600, "period_month": "2026-08"}
    allowed, blocked = coord._weather_quota_filter([W_ALERTS, W_CURRENT, W_HOURS, W_DAYS])
    assert set(allowed) == {W_ALERTS, W_CURRENT}
    assert blocked is True


def test_quota_filter_drops_by_reverse_priority(coord) -> None:
    """With only a few calls left, the cheapest-to-lose endpoints go first."""
    coord._cached_tracking = {"weather_calls": 9998, "period_month": "2026-08"}
    allowed, blocked = coord._weather_quota_filter([W_ALERTS, W_CURRENT, W_HOURS, W_DAYS])
    assert blocked is True
    assert W_HOURS not in allowed          # costs 5 pages
    assert set(allowed) <= {W_ALERTS, W_CURRENT}


def test_quota_filter_inactive_in_manual_mode(coord) -> None:
    """Manual limits are advisory; the user asked for this interval explicitly."""
    coord.automagic_mode = False
    coord._cached_tracking = {"weather_calls": 999999, "period_month": "2026-08"}
    allowed, blocked = coord._weather_quota_filter([W_ALERTS, W_CURRENT, W_HOURS])
    assert allowed == [W_ALERTS, W_CURRENT, W_HOURS]
    assert blocked is False


# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------

def _page(index: int, count: int, hours_per_page: int = 24) -> dict[str, Any]:
    body: dict[str, Any] = {
        "timeZone": {"id": "America/Los_Angeles"},
        "forecastHours": [
            {
                "interval": {"startTime": f"2026-08-12T{(index * hours_per_page + h) % 24:02d}:00:00Z"},
                "temperature": {"degrees": 20},
            }
            for h in range(hours_per_page)
        ],
    }
    if index + 1 < count:
        body["nextPageToken"] = str(index + 1)
    return body


def _paged_hours(pages: int, fail_at: int | None = None, runaway: bool = False):
    """aioclient_mock side_effect serving a paginated forecast/hours response."""
    seen: dict[str, int] = {"calls": 0}

    async def _side_effect(method, url, data):
        seen["calls"] += 1
        index = int(url.query.get("pageToken", "0"))
        if fail_at is not None and index == fail_at:
            return AiohttpClientMockResponse(
                method, url, status=400, text='{"error": {"message": "invalid token"}}'
            )
        if runaway:
            body = _page(0, 99)          # always advertises another page
            body["nextPageToken"] = str(index + 1)
            return AiohttpClientMockResponse(method, url, json=body)
        return AiohttpClientMockResponse(method, url, json=_page(index, pages))

    return _side_effect, seen


def _register_hours(aioclient_mock, side_effect) -> None:
    aioclient_mock.get(
        re.compile(r".*weather\.googleapis\.com.*forecast/hours.*"),
        side_effect=side_effect,
    )


@pytest.mark.asyncio
async def test_pagination_walks_every_page(coord, aioclient_mock) -> None:
    side_effect, seen = _paged_hours(pages=5)
    _register_hours(aioclient_mock, side_effect)

    from homeassistant.helpers.aiohttp_client import async_get_clientsession

    result = await coord._fetch_weather_hourly(async_get_clientsession(coord.hass))

    assert seen["calls"] == 5
    assert result.calls == 5, "every page is a separate billable event"
    assert result.partial is False
    assert len(result.payload["forecastHours"]) == 120
    assert "nextPageToken" not in result.payload


@pytest.mark.asyncio
async def test_first_page_failure_discards_and_records(coord, aioclient_mock) -> None:
    """If page 1 fails there is nothing usable; the previous forecast stands."""
    side_effect, _ = _paged_hours(pages=5, fail_at=0)
    _register_hours(aioclient_mock, side_effect)
    from homeassistant.helpers.aiohttp_client import async_get_clientsession

    result = await coord._fetch_weather_hourly(async_get_clientsession(coord.hass))

    assert result.calls == 1, "the failed request still crossed the wire"
    assert result.payload is None
    assert result.status == 400
    assert result.partial is False


@pytest.mark.asyncio
async def test_late_page_failure_keeps_partial(coord, aioclient_mock) -> None:
    """A token expiring mid-run is a data condition, not an outage.

    Keep the pages already paid for — a fresh 48-hour forecast beats a stale
    120-hour one — and do not trip the backoff.
    """
    side_effect, _ = _paged_hours(pages=5, fail_at=2)
    _register_hours(aioclient_mock, side_effect)
    from homeassistant.helpers.aiohttp_client import async_get_clientsession

    result = await coord._fetch_weather_hourly(async_get_clientsession(coord.hass))

    assert result.calls == 3, "two good pages plus the failed one"
    assert result.partial is True
    assert len(result.payload["forecastHours"]) == 48


@pytest.mark.asyncio
async def test_repeated_truncation_reduces_page_count(coord, aioclient_mock) -> None:
    """Stop paying for a page that reliably fails."""
    side_effect, _ = _paged_hours(pages=5, fail_at=2)
    _register_hours(aioclient_mock, side_effect)
    from homeassistant.helpers.aiohttp_client import async_get_clientsession

    session = async_get_clientsession(coord.hass)
    assert coord._hourly_pages_effective == 5
    for _ in range(3):
        await coord._fetch_weather_hourly(session)

    assert coord._hourly_pages_effective == 2


@pytest.mark.asyncio
async def test_runaway_token_is_capped(coord, aioclient_mock) -> None:
    """A server that always advertises another page cannot drain the quota."""
    side_effect, seen = _paged_hours(pages=99, runaway=True)
    _register_hours(aioclient_mock, side_effect)
    from homeassistant.helpers.aiohttp_client import async_get_clientsession

    result = await coord._fetch_weather_hourly(async_get_clientsession(coord.hass))

    assert seen["calls"] == coord._hourly_pages_effective == 5
    assert result.calls == 5
