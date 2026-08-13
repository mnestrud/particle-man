"""Tests for the harmonized severity model (const.py severity module).

The model is additive presentation metadata: each reading's rank within its
own canonical scale. These tests pin the ladders, the rank functions, and the
action-level boundaries so a silent reorder or off-by-one can't ship.
"""
from __future__ import annotations

import pytest

from custom_components.particle_man.const import (
    _MINUTECAST_INTENSITY_ORDER,
    ALERT_SEVERITY_MAX,
    ALERT_SEVERITY_ORDER,
    AQ_ACTION_MIN_UAQI,
    EPA_CATEGORY_ORDER,
    EPA_COLORS,
    EPA_SEVERITY_MAX,
    MINUTECAST_SEVERITY_MAX,
    POLLEN_ACTION_MIN_UPI,
    UAQI_CATEGORY_COLORS,
    UAQI_SEVERITY_MAX,
    UPI_SEVERITY_MAX,
    alert_severity_rank,
    epa_severity,
    uaqi_severity,
)


# ---------------------------------------------------------------------------
# UAQI — inverted scale, severity from documented numeric bands
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    ("aqi", "rank"),
    [
        (100, 0),  # Excellent
        (80, 0),
        (79, 1),   # Good
        (60, 1),
        (59, 2),   # Moderate
        (40, 2),
        (39, 3),   # Low
        (20, 3),
        (19, 4),   # Poor
        (1, 4),
        (0, 4),    # uaqi 0 shares the Poor category
    ],
)
def test_uaqi_severity_bands(aqi: int, rank: int) -> None:
    assert uaqi_severity(aqi) == rank


def test_uaqi_severity_non_numeric() -> None:
    assert uaqi_severity(None) is None
    assert uaqi_severity("45") is None  # type: ignore[arg-type]


def test_uaqi_severity_higher_value_never_more_severe() -> None:
    ranks = [uaqi_severity(v) for v in range(0, 101)]
    assert ranks == sorted(ranks, reverse=True)
    assert max(r for r in ranks if r is not None) == UAQI_SEVERITY_MAX


def test_uaqi_fallback_colors_cover_every_category() -> None:
    # 5 distinct strings; index 0 reuses "Poor air quality".
    assert len(UAQI_CATEGORY_COLORS) == 5
    assert all(c.startswith("#") and len(c) == 7 for c in UAQI_CATEGORY_COLORS.values())


# ---------------------------------------------------------------------------
# EPA pollutant ladder
# ---------------------------------------------------------------------------

def test_epa_ladder_matches_color_map() -> None:
    assert set(EPA_CATEGORY_ORDER) == set(EPA_COLORS)
    assert EPA_SEVERITY_MAX == 5


@pytest.mark.parametrize(
    ("category", "rank"),
    [("Good", 0), ("Moderate", 1), ("Hazardous", 5), (None, None), ("bogus", None)],
)
def test_epa_severity(category: str | None, rank: int | None) -> None:
    assert epa_severity(category) == rank


# ---------------------------------------------------------------------------
# Alerts
# ---------------------------------------------------------------------------

def test_alert_ladder() -> None:
    assert ALERT_SEVERITY_ORDER == ("MINOR", "MODERATE", "SEVERE", "EXTREME")
    assert ALERT_SEVERITY_MAX == 3
    assert alert_severity_rank("EXTREME") == 3
    assert alert_severity_rank("MINOR") == 0
    assert alert_severity_rank("SEVERITY_UNKNOWN") is None
    assert alert_severity_rank(None) is None


# ---------------------------------------------------------------------------
# Minutecast + UPI scale constants
# ---------------------------------------------------------------------------

def test_minutecast_scale() -> None:
    assert max(_MINUTECAST_INTENSITY_ORDER.values()) == MINUTECAST_SEVERITY_MAX


def test_upi_scale() -> None:
    assert UPI_SEVERITY_MAX == 5


# ---------------------------------------------------------------------------
# Action-level boundaries (policy constants — pinned so a change is loud)
# ---------------------------------------------------------------------------

def test_action_levels() -> None:
    # AQ (user-confirmed): only Good/Excellent quiet; the Moderate band acts.
    assert AQ_ACTION_MIN_UAQI == 60
    assert uaqi_severity(AQ_ACTION_MIN_UAQI) == 1
    assert uaqi_severity(AQ_ACTION_MIN_UAQI - 1) == 2
    # Pollen (user-confirmed): only None/Very Low quiet; Low acts.
    assert POLLEN_ACTION_MIN_UPI == 2


def test_uaqi_severity_colors_match_ladder() -> None:
    from custom_components.particle_man.const import (
        UAQI_SEVERITY_COLORS,
        UAQI_ZERO_COLOR,
    )

    assert len(UAQI_SEVERITY_COLORS) == UAQI_SEVERITY_MAX + 1
    # Low band (severity 3) is orange per the official table — the API's
    # gradient wrongly returns green there (channel transposition bug).
    assert UAQI_SEVERITY_COLORS[3] == "#ff8c00"
    assert UAQI_ZERO_COLOR == "#800000"
