"""Tests for the per-endpoint weather refresh budget solver.

Pure functions — no hass, no fixtures, no I/O.
"""
from __future__ import annotations

import pytest

from custom_components.particle_man.const import (
    _AUTOMAGIC_BUFFER,
    _WEATHER_BASE_CADENCE,
    _WEATHER_HOURS_CADENCE_SANITY,
    _WEATHER_MAX_CADENCE,
    DEFAULT_WEATHER_HOURLY_HOURS,
    W_ALERTS,
    W_CURRENT,
    W_DAYS,
    W_HOURS,
    W_MINUTES,
    WEATHER_HOURLY_HOURS_CHOICES,
    solve_weather_plan,
    weather_endpoint_calls,
    weather_hourly_pages,
)

# 31-day month with the default 23:00-05:00 quiet hours: 31 * 18 * 60.
E_QUIET = 33480
# Same month with quiet hours disabled.
E_FULL = 31 * 24 * 60
LIMIT = 10000


def _plan(locations=1, minutecast=False, limit=LIMIT, **kw):
    return solve_weather_plan(
        num_locations=locations,
        effective_minutes=kw.pop("effective_minutes", E_QUIET),
        monthly_limit=limit,
        enable_alerts=kw.pop("enable_alerts", True),
        enable_minutecast=minutecast,
        **kw,
    )


# ---------------------------------------------------------------------------
# Page arithmetic
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    ("hours", "pages"),
    [(1, 1), (24, 1), (25, 2), (48, 2), (72, 3), (120, 5), (240, 10), (10_000, 10)],
)
def test_hourly_pages(hours: int, pages: int) -> None:
    """pageSize caps at 24, so N hours costs ceil(N/24) pages, capped at 10."""
    assert weather_hourly_pages(hours) == pages


def test_hourly_choices_are_whole_pages() -> None:
    """Every offered horizon is a multiple of 24 — no wasted partial page."""
    for hours in WEATHER_HOURLY_HOURS_CHOICES:
        assert hours % 24 == 0
        assert weather_hourly_pages(hours) == hours // 24


def test_endpoint_calls() -> None:
    assert weather_endpoint_calls(60, 1, E_QUIET, 1) == 558
    assert weather_endpoint_calls(60, 5, E_QUIET, 1) == 2790
    assert weather_endpoint_calls(60, 5, E_QUIET, 2) == 5580
    assert weather_endpoint_calls(0, 1, E_QUIET, 1) == 0


# ---------------------------------------------------------------------------
# The documented base case
# ---------------------------------------------------------------------------

def test_single_location_runs_at_base_cadence() -> None:
    """One location fits at base cadence with no scaling at all."""
    plan = _plan()
    assert plan.cadences == {W_CURRENT: 15, W_HOURS: 60, W_DAYS: 180, W_ALERTS: 30}
    assert plan.tick_minutes == 15
    assert plan.pages[W_HOURS] == 5
    assert plan.hourly_hours == DEFAULT_WEATHER_HOURLY_HOURS
    assert plan.total_monthly_calls == 6324
    assert plan.scale_factor == 1.0
    assert plan.dropped == ()
    assert plan.degraded is False


def test_single_location_with_minutecast() -> None:
    """Minutecast fits at one location without degrading anything else."""
    plan = _plan(minutecast=True)
    assert plan.cadences[W_MINUTES] == 15
    assert plan.total_monthly_calls == 8556
    assert plan.total_monthly_calls * _AUTOMAGIC_BUFFER <= LIMIT
    assert plan.degraded is False


def test_per_endpoint_breakdown_sums_to_total() -> None:
    plan = _plan(minutecast=True)
    assert sum(plan.monthly_calls.values()) == plan.total_monthly_calls
    assert plan.monthly_calls[W_CURRENT] == 2232
    assert plan.monthly_calls[W_HOURS] == 2790
    assert plan.monthly_calls[W_DAYS] == 186
    assert plan.monthly_calls[W_ALERTS] == 1116
    assert plan.monthly_calls[W_MINUTES] == 2232


# ---------------------------------------------------------------------------
# Scaling
# ---------------------------------------------------------------------------

def test_two_locations_scale_uniformly() -> None:
    """No cap binds at two locations, so everything stretches by the same k."""
    plan = _plan(locations=2)
    assert plan.scale_factor > 1.0
    assert plan.degraded is True
    assert plan.dropped == ()
    assert plan.cadences == {W_CURRENT: 20, W_HOURS: 80, W_DAYS: 240, W_ALERTS: 40}


def test_alerts_cap_binds_before_uniform_scaling_would() -> None:
    """Latency-sensitive endpoints stop stretching at their cap.

    Uniform scaling at five locations would push alerts past 100 minutes; the
    cap holds it at 60 and the slack is taken out of the forecast endpoints.
    """
    plan = _plan(locations=5)
    assert plan.cadences[W_ALERTS] <= _WEATHER_MAX_CADENCE[W_ALERTS]
    assert plan.cadences[W_CURRENT] <= _WEATHER_MAX_CADENCE[W_CURRENT]
    assert plan.cadences[W_HOURS] > plan.cadences[W_ALERTS]


def test_minutecast_dropped_rather_than_served_stale() -> None:
    """Past its cap, minutecast is dropped — a 90-minute nowcast is useless."""
    plan = _plan(locations=5, minutecast=True)
    assert plan.dropped == (W_MINUTES,)
    assert W_MINUTES not in plan.cadences
    assert plan.degraded is True


def test_minutecast_kept_while_it_fits_its_cap() -> None:
    for locations in (1, 2, 3):
        plan = _plan(locations=locations, minutecast=True)
        assert plan.dropped == (), f"dropped at {locations} locations"
        assert plan.cadences[W_MINUTES] <= _WEATHER_MAX_CADENCE[W_MINUTES]


def test_pages_reduced_before_hourly_goes_badly_stale() -> None:
    """At high location counts a shorter, fresher forecast beats a stale long one."""
    plan = _plan(locations=20)
    assert plan.cadences[W_HOURS] <= _WEATHER_HOURS_CADENCE_SANITY
    assert plan.hourly_hours < DEFAULT_WEATHER_HOURLY_HOURS
    assert plan.pages[W_HOURS] == plan.hourly_hours // 24
    assert plan.degraded is True


# ---------------------------------------------------------------------------
# Invariants — the ones that actually matter
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("locations", range(1, 21))
@pytest.mark.parametrize("minutecast", [False, True])
@pytest.mark.parametrize("effective_minutes", [E_QUIET, E_FULL])
def test_budget_is_never_exceeded(
    locations: int, minutecast: bool, effective_minutes: int
) -> None:
    """The whole point: projected usage always stays inside the buffered limit."""
    plan = _plan(
        locations=locations, minutecast=minutecast, effective_minutes=effective_minutes
    )
    assert plan.total_monthly_calls * _AUTOMAGIC_BUFFER <= LIMIT


@pytest.mark.parametrize("locations", range(1, 21))
@pytest.mark.parametrize("minutecast", [False, True])
def test_cadences_are_tick_multiples(locations: int, minutecast: bool) -> None:
    """Gates only fire on ticks, so a cadence that isn't a tick multiple is a lie."""
    plan = _plan(locations=locations, minutecast=minutecast)
    assert 0 < plan.tick_minutes <= min(plan.cadences.values())
    for name, cadence in plan.cadences.items():
        assert cadence % plan.tick_minutes == 0, f"{name}={cadence} vs tick {plan.tick_minutes}"


@pytest.mark.parametrize("locations", range(1, 21))
@pytest.mark.parametrize("minutecast", [False, True])
def test_never_faster_than_base(locations: int, minutecast: bool) -> None:
    """Scaling only ever slows endpoints down — never outrun Google's refresh."""
    plan = _plan(locations=locations, minutecast=minutecast)
    for name, cadence in plan.cadences.items():
        assert cadence >= _WEATHER_BASE_CADENCE[name]


@pytest.mark.parametrize("locations", range(1, 21))
def test_undegraded_plans_are_unscaled(locations: int) -> None:
    """`degraded` must not lie: a clean plan has no scaling and no drops."""
    plan = _plan(locations=locations)
    if not plan.degraded:
        assert plan.scale_factor == 1.0
        assert plan.dropped == ()
        assert plan.hourly_hours == DEFAULT_WEATHER_HOURLY_HOURS


# ---------------------------------------------------------------------------
# Modes and edge cases
# ---------------------------------------------------------------------------

def test_unlimited_quota_uses_base_cadence() -> None:
    plan = _plan(locations=10, minutecast=True, limit=0)
    assert plan.cadences == dict(_WEATHER_BASE_CADENCE)
    assert plan.scale_factor == 1.0
    assert plan.degraded is False


def test_manual_mode_floors_at_the_configured_interval() -> None:
    """Manual mode keeps CONF_UPDATE_INTERVAL's meaning: never poll faster.

    The tick lands on the GCD (10) rather than the fastest cadence (20), so the
    30-minute alerts cadence survives intact instead of being rounded to 40.
    """
    plan = _plan(locations=4, automagic=False, manual_tick_minutes=20)
    assert plan.cadences == {W_CURRENT: 20, W_HOURS: 60, W_DAYS: 180, W_ALERTS: 30}
    assert plan.tick_minutes == 10
    assert plan.scale_factor == 1.0
    assert plan.degraded is False


def test_manual_mode_ignores_the_budget() -> None:
    """Manual mode is the user's explicit choice — it does not get second-guessed."""
    plan = _plan(locations=20, automagic=False, manual_tick_minutes=15)
    assert plan.cadences[W_CURRENT] == 15
    assert plan.total_monthly_calls > LIMIT


def test_alerts_disabled_is_not_budgeted() -> None:
    plan = _plan(enable_alerts=False)
    assert W_ALERTS not in plan.cadences
    assert W_ALERTS not in plan.monthly_calls
    assert plan.total_monthly_calls == 6324 - 1116


def test_shorter_horizon_costs_proportionally_less() -> None:
    short = _plan(hourly_hours=24)
    long = _plan(hourly_hours=120)
    assert short.pages[W_HOURS] == 1
    assert long.pages[W_HOURS] == 5
    assert short.monthly_calls[W_HOURS] * 5 == long.monthly_calls[W_HOURS]


def test_absurd_limit_still_returns_a_usable_plan() -> None:
    """A limit too small for anything must degrade, not crash or return junk."""
    plan = _plan(locations=20, minutecast=True, limit=1)
    assert plan.degraded is True
    assert plan.cadences
    assert all(c > 0 for c in plan.cadences.values())
    assert plan.tick_minutes > 0
