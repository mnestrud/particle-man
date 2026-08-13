"""Minutecast builder, sensors, and the get_minute_forecast action.

The nowcast is Google's lowest stability tier and its field shapes differ from
every other weather endpoint, so these lean on defensive parsing: bucket width
is read from the data rather than assumed, probability may arrive bare or
nested, and an empty segment list means "clear", not "unavailable".
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.core import HomeAssistant

from custom_components.particle_man.coordinator import ParticleManCoordinator
from custom_components.particle_man.sensor import (
    MinutesUntilPrecipitationSensor,
    PrecipitationEndsInSensor,
    PrecipitationIntensitySensor,
    PrecipitationTypeSensor,
)
from custom_components.particle_man.weather import ParticleManWeather
from tests.conftest import TEST_API_KEY, TEST_LAT, TEST_LON

NOW = datetime(2026, 8, 12, 12, 0, 0, tzinfo=timezone.utc)


def _seg(
    offset_min: float,
    width_min: float = 2,
    *,
    ptype: str = "RAIN",
    probability: Any = 90,
    intensity: str = "LIGHT",
    qpf: float | None = 0.2,
) -> dict[str, Any]:
    start = NOW + timedelta(minutes=offset_min)
    end = start + timedelta(minutes=width_min)
    return {
        "timeFrame": {"startTime": start.isoformat(), "endTime": end.isoformat()},
        "type": ptype,
        "probability": probability,
        "intensity": intensity,
        "qpf": {"quantity": qpf, "unit": "MILLIMETERS"},
        "snowfallAmount": {"quantity": 0.0, "unit": "MILLIMETERS"},
    }


def _payload(segments: list[dict[str, Any]], horizon_hours: float = 6) -> dict[str, Any]:
    return {
        "overallPredictionTimeframe": {
            "startTime": NOW.isoformat(),
            "endTime": (NOW + timedelta(hours=horizon_hours)).isoformat(),
        },
        "timeZone": {"id": "America/Los_Angeles"},
        "segments": segments,
    }


@pytest.fixture
def coord(hass: HomeAssistant, mock_config_entry):
    mock_config_entry.add_to_hass(hass)
    with patch(
        "custom_components.particle_man.coordinator.Store", autospec=True
    ) as store_cls:
        store = AsyncMock()
        store.async_load = AsyncMock(return_value=None)
        store.async_save = AsyncMock()
        store_cls.return_value = store
        c = ParticleManCoordinator(
            hass=hass,
            api_key=TEST_API_KEY,
            latitude=TEST_LAT,
            longitude=TEST_LON,
            location_name="Seattle",
            enable_air_quality=False,
            enable_pollen=False,
            enable_weather=True,
            enable_minutecast=True,
            entry_id="test_entry_id",
            config_entry=mock_config_entry,
        )
        c.data = {}
        yield c


def _build(coord: ParticleManCoordinator, payload: dict[str, Any]) -> dict[str, Any]:
    with patch(
        "custom_components.particle_man.coordinator.dt_util.utcnow", return_value=NOW
    ):
        return coord._build_weather_minute(payload)


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------

def test_bucket_width_is_read_not_assumed(coord) -> None:
    """1, 2 and 5-minute buckets must all yield the same onset.

    Google's own example uses 2-minute buckets despite calling the product
    minute-by-minute, so nothing may hard-code a width.
    """
    onsets = []
    for width in (1, 2, 5):
        segments = [
            _seg(i * width, width, ptype="NONE", intensity="NO_INTENSITY", qpf=0)
            for i in range(int(30 / width))
        ] + [
            _seg(30 + i * width, width) for i in range(int(30 / width))
        ]
        built = _build(coord, _payload(segments))
        assert built["runs"], f"width {width} produced no run"
        onsets.append(built["runs"][0]["start"])
    assert len(set(onsets)) == 1, f"onset differed by bucket width: {onsets}"


def test_low_probability_is_not_precipitation(coord) -> None:
    """Without a threshold this reads 'raining' permanently in drizzly climates."""
    built = _build(coord, _payload([_seg(10, probability=15)]))
    assert built["segments"][0]["precipitation"] is False
    assert built["runs"] == []


def test_no_intensity_is_not_precipitation(coord) -> None:
    built = _build(coord, _payload([_seg(10, intensity="NO_INTENSITY")]))
    assert built["segments"][0]["precipitation"] is False


def test_type_none_is_not_precipitation(coord) -> None:
    built = _build(coord, _payload([_seg(10, ptype="NONE")]))
    assert built["segments"][0]["precipitation"] is False


def test_nested_probability_shape_is_tolerated(coord) -> None:
    """Every other Google weather field nests this as {"percent": n}."""
    built = _build(coord, _payload([_seg(10, probability={"percent": 80})]))
    assert built["segments"][0]["probability"] == 80
    assert built["segments"][0]["precipitation"] is True


def test_past_segments_are_dropped(coord) -> None:
    built = _build(coord, _payload([_seg(-30), _seg(10)]))
    assert len(built["segments"]) == 1


def test_empty_segments_means_clear_not_uncovered(coord) -> None:
    built = _build(coord, _payload([]))
    assert built["segments"] == []
    assert built["runs"] == []
    assert built["covered"] is True


def test_runs_merge_contiguous_and_track_transitions(coord) -> None:
    """A run spanning a rain-to-snow change keeps both types and the worst intensity."""
    segments = [
        _seg(10, ptype="RAIN", intensity="LIGHT"),
        _seg(12, ptype="RAIN", intensity="HEAVY"),
        _seg(14, ptype="SNOW", intensity="MODERATE"),
    ]
    built = _build(coord, _payload(segments))
    assert len(built["runs"]) == 1
    run = built["runs"][0]
    assert run["type"] == "RAIN"
    assert run["types"] == ["RAIN", "SNOW"]
    assert run["max_intensity"] == "HEAVY"


def test_separate_runs_are_not_merged(coord) -> None:
    built = _build(coord, _payload([_seg(10), _seg(60), _seg(62)]))
    assert len(built["runs"]) == 2


# ---------------------------------------------------------------------------
# Sensors
# ---------------------------------------------------------------------------

def _with_data(coord: ParticleManCoordinator, payload: dict[str, Any]) -> None:
    coord.data = {"weather_minute": _build(coord, payload)}


def test_minutes_until_counts_down_without_a_coordinator_update(coord) -> None:
    """The countdown is a function of time, not of when data last arrived.

    Frozen at fetch time it would sit still for the whole 15-minute cycle and
    then jump, which is useless for a "close the windows" automation.
    """
    _with_data(coord, _payload([_seg(30), _seg(32)]))
    sensor = MinutesUntilPrecipitationSensor(coord)

    seen = []
    for elapsed in (0, 5, 10):
        with patch(
            "custom_components.particle_man.sensor.dt_util.utcnow",
            return_value=NOW + timedelta(minutes=elapsed),
        ):
            seen.append(sensor.native_value)

    assert seen == [30, 25, 20]


def test_zero_while_precipitation_is_falling(coord) -> None:
    _with_data(coord, _payload([_seg(-1, 5)]))
    sensor = MinutesUntilPrecipitationSensor(coord)
    with patch(
        "custom_components.particle_man.sensor.dt_util.utcnow", return_value=NOW
    ):
        assert sensor.native_value == 0
        assert sensor.extra_state_attributes["is_precipitating"] is True


def test_none_when_nothing_expected(coord) -> None:
    _with_data(coord, _payload([_seg(10, ptype="NONE", intensity="NO_INTENSITY")]))
    sensor = MinutesUntilPrecipitationSensor(coord)
    with patch(
        "custom_components.particle_man.sensor.dt_util.utcnow", return_value=NOW
    ):
        assert sensor.native_value is None


def test_stale_forecast_reports_nothing(coord) -> None:
    """A six-hour window fetched seven hours ago says nothing about now."""
    _with_data(coord, _payload([_seg(30)]))
    sensor = MinutesUntilPrecipitationSensor(coord)
    with patch(
        "custom_components.particle_man.sensor.dt_util.utcnow",
        return_value=NOW + timedelta(hours=7),
    ):
        assert sensor.native_value is None
        assert sensor.extra_state_attributes["stale"] is True
        assert sensor.available is False


def test_ends_in_only_reports_while_falling(coord) -> None:
    _with_data(coord, _payload([_seg(-1, 11)]))
    ends = PrecipitationEndsInSensor(coord)
    with patch(
        "custom_components.particle_man.sensor.dt_util.utcnow", return_value=NOW
    ):
        assert ends.native_value == 10

    _with_data(coord, _payload([_seg(30)]))
    with patch(
        "custom_components.particle_man.sensor.dt_util.utcnow", return_value=NOW
    ):
        assert PrecipitationEndsInSensor(coord).native_value is None


def test_intensity_and_type_read_the_covering_segment(coord) -> None:
    _with_data(coord, _payload([_seg(-1, 5, ptype="SNOW", intensity="HEAVY")]))
    with patch(
        "custom_components.particle_man.sensor.dt_util.utcnow", return_value=NOW
    ):
        assert PrecipitationIntensitySensor(coord).native_value == "HEAVY"
        assert PrecipitationTypeSensor(coord).native_value == "SNOW"


def test_uncovered_leading_gap_is_unknown_not_clear(coord) -> None:
    """Google's window can start minutes ahead of now; that gap is unknown."""
    _with_data(coord, _payload([_seg(10)]))
    with patch(
        "custom_components.particle_man.sensor.dt_util.utcnow", return_value=NOW
    ):
        assert PrecipitationIntensitySensor(coord).native_value is None


# ---------------------------------------------------------------------------
# Unavailability
# ---------------------------------------------------------------------------

def test_404_disables_minutecast_without_touching_other_endpoints(coord) -> None:
    """Coverage gaps are expected, so they must not back off the weather stack."""
    with patch("custom_components.particle_man.coordinator.async_create_issue") as issue:
        coord._handle_minutecast_unavailable(404)

    assert coord._minutecast_unavailable is True
    assert coord._weather_endpoint_enabled("minutes") is False
    assert issue.called
    # The whole point of per-endpoint error namespaces.
    assert "weather_current" not in coord._api_backoff
    assert "weather_current" not in coord._api_failures


# ---------------------------------------------------------------------------
# get_minute_forecast action
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_action_returns_the_canonical_shape(coord) -> None:
    """Cards built on core's convention need `datetime` and `precipitation`."""
    _with_data(coord, _payload([_seg(2, 2, qpf=0.2), _seg(4, 2, qpf=0.4)]))
    entity = ParticleManWeather(coord)

    with patch(
        "custom_components.particle_man.weather.dt_util.utcnow", return_value=NOW
    ):
        response = await entity.async_get_minute_forecast()

    forecast = response["forecast"]
    assert forecast, "expected entries within the first hour"
    for entry in forecast:
        assert "datetime" in entry
        assert isinstance(entry["precipitation"], float)
    # 0.2 mm over a 2-minute bucket is 6 mm/h.
    assert forecast[0]["precipitation"] == pytest.approx(6.0)


@pytest.mark.asyncio
async def test_action_reports_dry_segments_as_zero(coord) -> None:
    """Omitting dry buckets would make consumers draw gaps instead of dry spells."""
    _with_data(coord, _payload([_seg(2, 2, ptype="NONE", intensity="NO_INTENSITY", qpf=0)]))
    entity = ParticleManWeather(coord)

    with patch(
        "custom_components.particle_man.weather.dt_util.utcnow", return_value=NOW
    ):
        response = await entity.async_get_minute_forecast()

    assert response["forecast"][0]["precipitation"] == 0.0


@pytest.mark.asyncio
async def test_action_is_limited_to_the_first_hour(coord) -> None:
    """The convention expects ~60 minutes; the full window lives on the sensor."""
    segments = [_seg(i * 10, 2) for i in range(30)]  # 5 hours of segments
    _with_data(coord, _payload(segments))
    entity = ParticleManWeather(coord)

    with patch(
        "custom_components.particle_man.weather.dt_util.utcnow", return_value=NOW
    ):
        response = await entity.async_get_minute_forecast()

    assert len(response["forecast"]) == 6  # 0..50 minutes


@pytest.mark.asyncio
async def test_action_empty_without_data(coord) -> None:
    coord.data = {}
    entity = ParticleManWeather(coord)
    response = await entity.async_get_minute_forecast()
    assert response == {"forecast": []}
