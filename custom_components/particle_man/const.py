"""Constants for Particle Man integration."""
import calendar as _cal
import math
from dataclasses import dataclass
from datetime import datetime as _dt
from functools import reduce
from zoneinfo import ZoneInfo

DOMAIN = "particle_man"

# --- Config entry keys (data — identity, never changes) ---
CONF_API_KEY = "api_key"

# --- Location list (stored in options) ---
CONF_LOCATIONS = "locations"       # list of location dicts
CONF_LOCATION_NAME = "name"        # key within a location dict

# --- Legacy location keys (used in per-location dicts AND for migration from v1 data) ---
CONF_LATITUDE = "latitude"
CONF_LONGITUDE = "longitude"

# --- Options keys ---
CONF_AUTOMAGIC_MODE = "automagic_mode"   # replaces enforce_limits
CONF_ENFORCE_LIMITS = "enforce_limits"   # migration read-only — do not use in new code
CONF_UPDATE_INTERVAL = "update_interval"
CONF_FORECAST_DAYS = "forecast_days"
CONF_LANGUAGE = "language_code"
CONF_LOCAL_AQI = "enable_local_aqi"
CONF_LOCAL_AQI_CODE = "local_aqi_code"
CONF_HEALTH_RECS = "include_health_recommendations"
CONF_PLANT_DESCRIPTIONS = "include_plant_descriptions"

# API enable toggles
CONF_ENABLE_AIR_QUALITY = "enable_air_quality"
CONF_ENABLE_POLLEN = "enable_pollen"
CONF_ENABLE_WEATHER = "enable_weather"
CONF_ENABLE_WEATHER_ALERTS = "enable_weather_alerts"
CONF_WEATHER_UNITS = "weather_units"  # "METRIC" | "IMPERIAL"
CONF_WEATHER_HOURLY_HOURS = "weather_hourly_hours"
CONF_ENABLE_MINUTECAST = "enable_minutecast"

# API limit options (manual mode only)
CONF_AQ_MONTHLY_LIMIT = "aq_monthly_limit"
CONF_POLLEN_MONTHLY_LIMIT = "pollen_monthly_limit"
CONF_WEATHER_MONTHLY_LIMIT = "weather_monthly_limit"

# Quiet hours (always-visible)
CONF_QUIET_HOURS_ENABLED = "quiet_hours_enabled"
CONF_QUIET_START = "quiet_start"
CONF_QUIET_END = "quiet_end"

# --- Defaults ---
DEFAULT_AUTOMAGIC_MODE = True
DEFAULT_UPDATE_INTERVAL = 20  # minutes
DEFAULT_FORECAST_DAYS = 5
DEFAULT_LANGUAGE = "en"
DEFAULT_LOCAL_AQI = False
DEFAULT_LOCAL_AQI_CODE = "us_aqi"

DEFAULT_ENABLE_AIR_QUALITY = True
DEFAULT_ENABLE_POLLEN = True
DEFAULT_ENABLE_WEATHER = True
DEFAULT_ENABLE_WEATHER_ALERTS = True
DEFAULT_WEATHER_UNITS = "METRIC"

# Hourly forecast horizon. Google caps forecast/hours pageSize at 24, so each
# 24-hour block is one extra billable page — only multiples of 24 avoid waste.
DEFAULT_WEATHER_HOURLY_HOURS = 120
WEATHER_HOURLY_HOURS_CHOICES = (24, 48, 72, 120, 240)

# Minutecast is Experimental (pre-GA) at Google and its billing is undocumented,
# so it is opt-in and budgeted as if billed.
DEFAULT_ENABLE_MINUTECAST = False

# Corrected free-tier limits (Google Maps Platform)
DEFAULT_AQ_MONTHLY_LIMIT = 10000
DEFAULT_POLLEN_MONTHLY_LIMIT = 5000
DEFAULT_WEATHER_MONTHLY_LIMIT = 10000

DEFAULT_QUIET_HOURS_ENABLED = True
DEFAULT_QUIET_START = "23:00:00"
DEFAULT_QUIET_END = "05:00:00"

# --- Polling rate constants ---
_AQ_CALLS_PER_POLL = 2
_POLLEN_CALLS_PER_POLL = 1
_WEATHER_CALLS_PER_POLL = 3

# Fallback constant (31-day worst case) used in tests and type stubs.
# Live code always calls _billing_month_days() instead.
_MINUTES_PER_MONTH = 31 * 24 * 60  # 44,640

# Google data refresh cadence — AQ updates hourly; pollen models update once daily.
# Both are fetched at the same 60-min interval to match the AQ refresh rate.
_AQ_FETCH_INTERVAL_MINUTES = 60
_POLLEN_FETCH_INTERVAL_MINUTES = 60

# Single source of truth for the automagic safety margin.
_AUTOMAGIC_BUFFER = 1.05


def _billing_month_days() -> int:
    """Actual days in the current Google billing month (Pacific Time)."""
    today = _dt.now(_PACIFIC_TZ)
    return _cal.monthrange(today.year, today.month)[1]


def _quiet_active_minutes_per_month(quiet_start: str, quiet_end: str) -> int:
    """Polling minutes available per month when quiet hours are enabled."""
    days = _billing_month_days()

    def _to_min(s: str) -> int:
        parts = s.split(":")
        return int(parts[0]) * 60 + int(parts[1])

    start = _to_min(quiet_start)
    end = _to_min(quiet_end)
    quiet_min = (end - start) if end > start else (24 * 60 - start + end)
    return days * (24 * 60 - quiet_min)


def safe_interval_minutes(
    num_locations: int,
    enabled_apis: dict[str, tuple[int, int]],  # api → (calls_per_poll, monthly_limit)
    minutes_per_month: int | None = None,
) -> int:
    """Minimum safe polling interval to stay within monthly limit (with 5% buffer)."""
    if minutes_per_month is None:
        minutes_per_month = _billing_month_days() * 24 * 60
    intervals = [
        math.ceil(minutes_per_month * calls * num_locations * _AUTOMAGIC_BUFFER / limit)
        for calls, limit in enabled_apis.values()
        if limit > 0
    ]
    return max(15, max(intervals)) if intervals else 15


# ---------------------------------------------------------------------------
# Weather per-endpoint refresh budget
#
# Weather endpoints no longer share one poll interval. Each refreshes on its own
# cadence, and the budget is expressed as calls-per-month rather than a single
# calls-per-poll scalar:
#
#     monthly_calls(endpoint) = ceil(E / cadence) * pages * num_locations
#     constraint: sum(enabled endpoints) * buffer <= monthly_limit
#
# where E is the effective polling minutes per billing month.
# ---------------------------------------------------------------------------

# Endpoint identifiers — also the keys of every per-endpoint dict below.
W_CURRENT = "current"
W_HOURS = "hours"
W_DAYS = "days"
W_ALERTS = "alerts"
W_MINUTES = "minutes"
WEATHER_ENDPOINTS = (W_CURRENT, W_HOURS, W_DAYS, W_ALERTS, W_MINUTES)

# Base cadence in minutes, derived from Google's own data regeneration rates
# (current conditions 15 min, hourly 30 min, daily 30 min). Where we poll slower
# than Google regenerates, that is deliberate: the content changes slowly and the
# saved calls buy forecast length instead.
_WEATHER_BASE_CADENCE: dict[str, int] = {
    W_CURRENT: 15,    # matches regeneration exactly
    W_HOURS: 60,      # deliberate 2x under-poll
    W_DAYS: 180,      # deliberate 6x under-poll
    W_ALERTS: 30,     # latency-sensitive
    W_MINUTES: 15,    # nowcast is useless if stale
}

# Hard ceiling on automagic stretch. None = unbounded. An alert or a current
# reading delivered an hour late is not worth the quota it saves; a daily
# forecast an extra six hours old still is.
_WEATHER_MAX_CADENCE: dict[str, int | None] = {
    W_CURRENT: 60,
    W_HOURS: None,
    W_DAYS: None,
    W_ALERTS: 60,
    W_MINUTES: 30,
}

# Preserved first -> last when quota runs short.
_WEATHER_PRIORITY = (W_ALERTS, W_CURRENT, W_HOURS, W_DAYS, W_MINUTES)

_WEATHER_HOURLY_PAGE_SIZE = 24    # Google's hard cap on forecast/hours pageSize
_WEATHER_HOURLY_MAX_PAGES = 10    # 240 h API max; also a runaway-token guard
_WEATHER_HOURLY_PAGE_LADDER = (5, 3, 2, 1)

# Beyond this, a long hourly forecast is so stale that fewer pages refreshed
# more often is the better trade.
_WEATHER_HOURS_CADENCE_SANITY = 720  # 12 h

# Smallest coordinator wake interval. Ticks are cheap (no API calls unless an
# endpoint is due), but there is no point waking more often than this.
_MIN_TICK_MINUTES = 5

# Cadences are quantized onto this grid so they stay human-legible and remain
# exact multiples of the coordinator tick.
_CADENCE_GRID = (15, 20, 30, 45, 60, 90, 120, 180, 240, 360, 480, 720, 1440)

# Minutecast interpretation
_MINUTECAST_PROBABILITY_THRESHOLD = 50
_MINUTECAST_INTENSITY_ORDER: dict[str, int] = {
    "NO_INTENSITY": 0, "LIGHT": 1, "MODERATE": 2, "HEAVY": 3,
}
_MINUTECAST_HORIZON_MINUTES = 360


@dataclass(frozen=True)
class WeatherPlan:
    """Resolved per-endpoint refresh plan for one config entry."""

    cadences: dict[str, int]        # endpoint -> minutes; always tick multiples
    pages: dict[str, int]           # endpoint -> billable events per refresh
    tick_minutes: int               # master coordinator interval
    monthly_calls: dict[str, int]   # endpoint -> projected calls/month, all locations
    total_monthly_calls: int        # sum, before the safety buffer
    scale_factor: float             # k actually applied
    dropped: tuple[str, ...]        # endpoints disabled to fit the budget
    hourly_hours: int               # after any page-ladder reduction
    degraded: bool                  # True if anything was stretched or dropped


def weather_hourly_pages(hourly_hours: int) -> int:
    """Billable pages for an N-hour forecast (pageSize caps at 24)."""
    pages = math.ceil(max(1, hourly_hours) / _WEATHER_HOURLY_PAGE_SIZE)
    return max(1, min(pages, _WEATHER_HOURLY_MAX_PAGES))


def weather_endpoint_calls(
    cadence_minutes: int, pages: int, effective_minutes: int, num_locations: int
) -> int:
    """Projected billable events per month for one endpoint."""
    if cadence_minutes <= 0:
        return 0
    return math.ceil(effective_minutes / cadence_minutes) * pages * num_locations


def _active_endpoints(enable_alerts: bool, enable_minutecast: bool) -> list[str]:
    active = [W_CURRENT, W_HOURS, W_DAYS]
    if enable_alerts:
        active.append(W_ALERTS)
    if enable_minutecast:
        active.append(W_MINUTES)
    return active


def _solve_scale(
    active: list[str],
    pages: dict[str, int],
    effective_minutes: int,
    num_locations: int,
    budget: float,
    use_caps: bool,
) -> tuple[dict[str, int], float] | None:
    """Closed-form scale factor k, solved iteratively as per-endpoint caps bind.

    Caps are step functions of k, so this converges in at most len(active)
    iterations. Returns None when the capped endpoints alone exceed the budget.
    """
    uncapped = set(active)
    capped: dict[str, int] = {}
    k = 1.0

    while True:
        frozen = sum(
            weather_endpoint_calls(cap, pages[name], effective_minutes, num_locations)
            for name, cap in capped.items()
        )
        remaining = budget - frozen
        if remaining <= 0:
            return None
        base_calls = sum(
            weather_endpoint_calls(
                _WEATHER_BASE_CADENCE[name], pages[name], effective_minutes, num_locations
            )
            for name in uncapped
        )
        if not uncapped or base_calls <= 0:
            break
        k = max(1.0, base_calls / remaining)
        if not use_caps:
            break
        newly = {
            name
            for name in uncapped
            if (cap := _WEATHER_MAX_CADENCE[name]) is not None
            and _WEATHER_BASE_CADENCE[name] * k > cap
        }
        if not newly:
            break
        uncapped -= newly
        for name in newly:
            cap = _WEATHER_MAX_CADENCE[name]
            assert cap is not None
            capped[name] = cap

    cadences: dict[str, int] = {}
    for name in active:
        if name in capped:
            cadences[name] = capped[name]
        else:
            cadences[name] = max(
                _WEATHER_BASE_CADENCE[name], math.ceil(_WEATHER_BASE_CADENCE[name] * k)
            )
    return cadences, k


def _quantize(cadences: dict[str, int]) -> tuple[int, dict[str, int]]:
    """Pick a coordinator tick that every cadence is an exact multiple of.

    Gates only fire on ticks, so a cadence that isn't a tick multiple silently
    realizes as the next tick boundary — reporting the unrounded value would be
    a lie. Prefer the GCD, which keeps every cadence exactly as solved; fall back
    to rounding onto the grid when the GCD is too small to be a sane wake
    interval. Rounding up can only reduce call volume, never increase it.
    """
    values = list(cadences.values())
    tick = reduce(math.gcd, values)
    if tick >= _MIN_TICK_MINUTES and tick % _MIN_TICK_MINUTES == 0:
        # The GCD is itself a round interval, so every cadence survives exactly.
        return tick, dict(cadences)
    # An arbitrary GCD (say 27) would preserve exactness at the cost of cadences
    # no user can read. Snap to the grid instead and accept the rounding.
    smallest = min(values)
    tick = next((g for g in _CADENCE_GRID if g >= smallest), smallest)
    return tick, {name: math.ceil(c / tick) * tick for name, c in cadences.items()}


def _total_calls(
    cadences: dict[str, int],
    pages: dict[str, int],
    effective_minutes: int,
    num_locations: int,
) -> tuple[dict[str, int], int]:
    per = {
        name: weather_endpoint_calls(c, pages[name], effective_minutes, num_locations)
        for name, c in cadences.items()
    }
    return per, sum(per.values())


def _reclaim_slack(
    cadences: dict[str, int],
    pages: dict[str, int],
    tick: int,
    effective_minutes: int,
    num_locations: int,
    budget: float,
) -> dict[str, int]:
    """Spend leftover budget by stepping high-priority endpoints back down.

    Quantizing always rounds up, which can leave a sizeable slice of the budget
    unspent. Walk the priority order and pull each endpoint down one grid level
    while it still fits.
    """
    result = dict(cadences)
    for name in _WEATHER_PRIORITY:
        if name not in result:
            continue
        while True:
            current = result[name]
            lower = [g for g in _CADENCE_GRID if g < current and g >= tick and g % tick == 0]
            if not lower:
                break
            candidate = max(lower)
            if candidate < _WEATHER_BASE_CADENCE[name]:
                break
            trial = dict(result)
            trial[name] = candidate
            _, total = _total_calls(trial, pages, effective_minutes, num_locations)
            if total > budget:
                break
            result = trial
    return result


def solve_weather_plan(
    *,
    num_locations: int,
    effective_minutes: int,
    monthly_limit: int,
    enable_alerts: bool,
    enable_minutecast: bool,
    hourly_hours: int = DEFAULT_WEATHER_HOURLY_HOURS,
    automagic: bool = True,
    manual_tick_minutes: int | None = None,
    buffer: float = _AUTOMAGIC_BUFFER,
) -> WeatherPlan:
    """Resolve per-endpoint cadences that keep monthly weather calls in budget."""
    num_locations = max(1, num_locations)
    active = _active_endpoints(enable_alerts, enable_minutecast)
    requested_pages = weather_hourly_pages(hourly_hours)

    def _build(
        cadences: dict[str, int],
        pages: dict[str, int],
        k: float,
        hours: int,
        dropped: tuple[str, ...],
        degraded: bool,
    ) -> WeatherPlan:
        tick, quantized = _quantize(cadences)
        if monthly_limit > 0:
            quantized = _reclaim_slack(
                quantized, pages, tick, effective_minutes, num_locations,
                monthly_limit / buffer,
            )
        per, total = _total_calls(quantized, pages, effective_minutes, num_locations)
        return WeatherPlan(
            cadences=quantized,
            pages=pages,
            tick_minutes=tick,
            monthly_calls=per,
            total_monthly_calls=total,
            scale_factor=round(k, 3),
            dropped=dropped,
            hourly_hours=hours,
            degraded=degraded,
        )

    def _pages_for(count: int) -> dict[str, int]:
        return {name: (count if name == W_HOURS else 1) for name in active}

    # Manual mode: CONF_UPDATE_INTERVAL keeps its existing meaning ("never poll
    # faster than this"), mapped onto the base cadences. No solve, no new UI.
    if not automagic:
        tick_floor = manual_tick_minutes or DEFAULT_UPDATE_INTERVAL
        cadences = {
            name: max(_WEATHER_BASE_CADENCE[name], tick_floor) for name in active
        }
        return _build(cadences, _pages_for(requested_pages), 1.0, hourly_hours, (), False)

    # No enforced limit: everything at base cadence.
    if monthly_limit <= 0:
        cadences = {name: _WEATHER_BASE_CADENCE[name] for name in active}
        return _build(cadences, _pages_for(requested_pages), 1.0, hourly_hours, (), False)

    budget = monthly_limit / buffer

    # Degradation ladder. Capped scaling is preferred because it protects the
    # latency-sensitive endpoints; uniform scaling is the fallback when the caps
    # themselves cannot be afforded. Page reduction comes last and only when the
    # hourly forecast would otherwise be refreshed absurdly rarely.
    # (pages, use_caps, keep_minutecast). Dropping an opted-in minutecast is
    # preferred over serving it far past its cap: a 6-hour nowcast refreshed
    # every 90 minutes tells you nothing useful.
    attempts: list[tuple[int, bool, bool]] = [
        (requested_pages, True, True),
        (requested_pages, False, True),
        (requested_pages, True, False),
        (requested_pages, False, False),
    ]
    for p in _WEATHER_HOURLY_PAGE_LADDER:
        if p < requested_pages:
            attempts += [(p, False, True), (p, False, False)]

    minutes_cap = _WEATHER_MAX_CADENCE[W_MINUTES]
    fallback: WeatherPlan | None = None

    for page_count, use_caps, keep_minutes in attempts:
        if not keep_minutes and W_MINUTES not in active:
            continue  # nothing to drop; identical to the keep_minutes attempt
        endpoints = (
            active if keep_minutes else [n for n in active if n != W_MINUTES]
        )
        pages = {name: (page_count if name == W_HOURS else 1) for name in endpoints}
        solved = _solve_scale(
            endpoints, pages, effective_minutes, num_locations, budget, use_caps
        )
        if solved is None:
            continue
        cadences, k = solved
        dropped: tuple[str, ...] = (
            () if keep_minutes or W_MINUTES not in active else (W_MINUTES,)
        )
        hours = page_count * _WEATHER_HOURLY_PAGE_SIZE
        degraded = bool(k > 1.0 or page_count < requested_pages or dropped)
        plan = _build(cadences, pages, k, hours, dropped, degraded)
        if plan.total_monthly_calls > budget:
            continue
        if fallback is None:
            fallback = plan
        stale_hours = plan.cadences[W_HOURS] > _WEATHER_HOURS_CADENCE_SANITY
        stale_minutes = (
            W_MINUTES in plan.cadences
            and minutes_cap is not None
            and plan.cadences[W_MINUTES] > minutes_cap
        )
        if not stale_hours and not stale_minutes:
            return plan

    if fallback is not None:
        return fallback

    # Pathological input (e.g. a limit so small nothing fits): park everything at
    # the slowest grid cadence rather than returning an unusable plan.
    endpoints = [n for n in active if n != W_MINUTES]
    pages = {name: 1 for name in endpoints}
    cadences = {name: _CADENCE_GRID[-1] for name in endpoints}
    return _build(
        cadences, pages, 1.0, _WEATHER_HOURLY_PAGE_SIZE,
        (W_MINUTES,) if W_MINUTES in active else (), True,
    )


# --- API URLs ---
BASE_URL = "https://airquality.googleapis.com/v1"
POLLEN_API_URL = "https://pollen.googleapis.com/v1/forecast:lookup"
WEATHER_API_URL = "https://weather.googleapis.com/v1"

# --- Attributions ---
ATTRIBUTION = "Data provided by Google Air Quality API"
POLLEN_ATTRIBUTION = "Data provided by Google Pollen API"
WEATHER_ATTRIBUTION = "Data provided by Google Weather API"

# --- Billing period timezone ---
# Google resets quotas at midnight Pacific Time on the 1st of each month
_PACIFIC_TZ = ZoneInfo("America/Los_Angeles")

# --- Google Weather condition → HA condition mapping ---
# CLEAR is handled at runtime (sunny vs clear-night based on isDaytime)
CONDITION_MAP: dict[str, str] = {
    "MOSTLY_CLEAR": "partlycloudy",
    "PARTLY_CLOUDY": "partlycloudy",
    "MOSTLY_CLOUDY": "cloudy",
    "CLOUDY": "cloudy",
    "OVERCAST": "cloudy",
    "WINDY": "windy",
    "BREEZY": "windy",
    "DRIZZLE": "rainy",
    "LIGHT_RAIN": "rainy",
    "RAIN": "rainy",
    "HEAVY_RAIN": "pouring",
    "RAIN_SHOWERS": "rainy",
    "HEAVY_RAIN_SHOWERS": "pouring",
    "THUNDERSTORM": "lightning-rainy",
    "THUNDERSTORM_WITH_RAIN": "lightning-rainy",
    "SCATTERED_THUNDERSTORMS": "lightning-rainy",
    "LIGHTNING": "lightning",
    "LIGHT_SNOW": "snowy",
    "SNOW": "snowy",
    "HEAVY_SNOW": "snowy",
    "SNOW_SHOWERS": "snowy",
    "BLIZZARD": "snowy",
    "SLEET": "hail",
    "HAIL": "hail",
    "FREEZING_RAIN": "hail",
    "FREEZING_DRIZZLE": "hail",
    "ICE_PELLETS": "hail",
    "WINTRY_MIX": "hail",
    "FOG": "fog",
    "HAZE": "fog",
    "SMOKE": "fog",
    "DUST": "exceptional",
    "SAND": "exceptional",
    "TORNADO": "exceptional",
    "HURRICANE": "exceptional",
    "TROPICAL_STORM": "exceptional",
}

# Extra computations always requested for current conditions
CURRENT_EXTRA_COMPUTATIONS_BASE = [
    "POLLUTANT_ADDITIONAL_INFO",
    "DOMINANT_POLLUTANT_CONCENTRATION",
    "POLLUTANT_CONCENTRATION",
]

# Extra computations always requested for forecast
FORECAST_EXTRA_COMPUTATIONS = [
    "DOMINANT_POLLUTANT_CONCENTRATION",
    "POLLUTANT_CONCENTRATION",
]

# Available local AQI index codes
LOCAL_AQI_CODES = [
    "us_aqi",
    "can_ec",
    "gbr_defra",
    "deu_uba",
    "fra_atmo",
    "chn_mep",
    "ind_cpcb",
    "jpn_caqi",
    "mex_sedema",
    "nld_lki",
    "sgp_nea",
    "kor_keco",
    "esp_calidad",
]

# Pollutants with published EPA AQI breakpoints — only these get a _level sensor
EPA_BREAKPOINT_POLLUTANTS = {"pm25", "pm10", "o3", "no2", "co", "so2"}

# EPA AQI health category color map (hex)
EPA_COLORS: dict[str, str] = {
    "Good": "#00e400",
    "Moderate": "#ffff00",
    "Unhealthy for Sensitive Groups": "#ff7e00",
    "Unhealthy": "#ff0000",
    "Very Unhealthy": "#8f3f97",
    "Hazardous": "#7e0023",
}

# Google Universal Pollen Index (UPI) category color map (hex)
POLLEN_COLORS: dict[str, str] = {
    "None": "#9e9e9e",
    "Very Low": "#009E3A",
    "Low": "#84CF33",
    "Moderate": "#FFBA00",
    "High": "#FF7600",
    "Very High": "#FF0000",
}

# ---------------------------------------------------------------------------
# EPA AQI breakpoints (2024 NAAQS revision for PM2.5; 2015 for O3; current otherwise)
# Format: (canonical_unit, [(upper_bound_inclusive, category), ...])
# ---------------------------------------------------------------------------
EPA_BREAKPOINTS: dict[str, tuple[str, list[tuple[float, str]]]] = {
    # PM2.5 24-hour (µg/m³) — Good ceiling lowered to 9.0 per 2024 revision
    "pm25": ("μg/m³", [
        (9.0,   "Good"),
        (35.4,  "Moderate"),
        (55.4,  "Unhealthy for Sensitive Groups"),
        (125.4, "Unhealthy"),
        (225.4, "Very Unhealthy"),
        (float("inf"), "Hazardous"),
    ]),
    # PM10 24-hour (µg/m³)
    "pm10": ("μg/m³", [
        (54.0,  "Good"),
        (154.0, "Moderate"),
        (254.0, "Unhealthy for Sensitive Groups"),
        (354.0, "Unhealthy"),
        (424.0, "Very Unhealthy"),
        (float("inf"), "Hazardous"),
    ]),
    # Ozone 8-hour running average (ppm) — 2015 NAAQS 0.070 ppm standard
    "o3": ("ppm", [
        (0.054, "Good"),
        (0.070, "Moderate"),
        (0.085, "Unhealthy for Sensitive Groups"),
        (0.105, "Unhealthy"),
        (0.200, "Very Unhealthy"),
        (float("inf"), "Hazardous"),
    ]),
    # NO2 1-hour (ppb)
    "no2": ("ppb", [
        (53.0,    "Good"),
        (100.0,   "Moderate"),
        (360.0,   "Unhealthy for Sensitive Groups"),
        (649.0,   "Unhealthy"),
        (1249.0,  "Very Unhealthy"),
        (float("inf"), "Hazardous"),
    ]),
    # CO 8-hour running average (ppm)
    "co": ("ppm", [
        (4.4,  "Good"),
        (9.4,  "Moderate"),
        (12.4, "Unhealthy for Sensitive Groups"),
        (15.4, "Unhealthy"),
        (30.4, "Very Unhealthy"),
        (float("inf"), "Hazardous"),
    ]),
    # SO2 1-hour (ppb)
    "so2": ("ppb", [
        (35.0,  "Good"),
        (75.0,  "Moderate"),
        (185.0, "Unhealthy for Sensitive Groups"),
        (304.0, "Unhealthy"),
        (604.0, "Very Unhealthy"),
        (float("inf"), "Hazardous"),
    ]),
}

# Molecular weights (g/mol) for µg/m³ ↔ ppb/ppm conversion at 25°C, 1 atm
GAS_MW: dict[str, float] = {"no2": 46.0, "o3": 48.0, "co": 28.0, "so2": 64.0}
MOLAR_VOL = 24.45  # L/mol at 25°C, 1 atm

# ---------------------------------------------------------------------------
# Harmonized severity model (additive presentation metadata for consumers)
#
# Each domain keeps its own canonical scale — Google UAQI bands, EPA AQI
# categories, Google UPI, CAP alert severities, minutecast intensities.
# `severity` is a reading's RANK within its own scale (0 = least severe) and
# `severity_max` the scale's top rank, so a card can draw uniform geometry
# (severity / severity_max) without any cross-domain equivalence being
# asserted. Never derive behavior from these; the canonical fields stay
# authoritative.
# ---------------------------------------------------------------------------

# UAQI severity from the numeric index — locale-independent, unlike the
# localized category strings. Bands per the official UAQI table
# (developers.google.com/maps/documentation/air-quality/laqis):
# 80-100 Excellent, 60-79 Good, 40-59 Moderate, 20-39 Low, 0-19 Poor.
# Higher UAQI = better air, hence the inverted rank.
_UAQI_BAND_FLOORS: tuple[tuple[int, int], ...] = (
    (80, 0),  # Excellent air quality
    (60, 1),  # Good air quality
    (40, 2),  # Moderate air quality
    (20, 3),  # Low air quality
    (0, 4),   # Poor air quality (uaqi 0-19)
)
UAQI_SEVERITY_MAX = 4

# Official per-category UAQI colors (RED_GREEN palette, laqis table) — used
# only as a fallback when the API response omits the index `color` field.
UAQI_CATEGORY_COLORS: dict[str, str] = {
    "Excellent air quality": "#009e3a",
    "Good air quality": "#84cf33",
    "Moderate air quality": "#ffff00",
    "Low air quality": "#ff8c00",
    "Poor air quality": "#ff0000",  # uaqi 1-19; uaqi 0 is maroon #800000
}

# EPA AQI category ladder (order = severity rank). Same vocabulary as
# EPA_BREAKPOINTS/EPA_COLORS — integration-computed, so locale-stable.
EPA_CATEGORY_ORDER: tuple[str, ...] = (
    "Good",
    "Moderate",
    "Unhealthy for Sensitive Groups",
    "Unhealthy",
    "Very Unhealthy",
    "Hazardous",
)
EPA_SEVERITY_MAX = len(EPA_CATEGORY_ORDER) - 1

# Google UPI is already ordinal: severity == index value (0 None … 5 Very High).
UPI_SEVERITY_MAX = 5

# publicAlerts severity enum, least → most severe. SEVERITY_UNKNOWN (and any
# future value) maps to severity None.
ALERT_SEVERITY_ORDER: tuple[str, ...] = ("MINOR", "MODERATE", "SEVERE", "EXTREME")
ALERT_SEVERITY_MAX = len(ALERT_SEVERITY_ORDER) - 1

MINUTECAST_SEVERITY_MAX = 3  # ranks in _MINUTECAST_INTENSITY_ORDER

# --- Action levels ---------------------------------------------------------
# Google documents no "act at this level" boundary for AQ or pollen, so these
# are explicit policy choices (user-confirmed 2026-08-13), each anchored to a
# canonical scale:
# - AQ: anything below the "Good air quality" band acts — i.e. "Moderate air
#   quality" (uaqi 40-59) and worse are surfaced; only Good/Excellent are quiet.
# - Pollutants: EPA "Good" is quiet — matches the existing elevated_pollutants
#   logic in the AQ advisory (anything above Good is surfaced).
# - Pollen: UPI "Low" (2) and above act; only None/Very Low are quiet.
# Alerts are never quiet.
AQ_ACTION_MIN_UAQI = 60          # below_action_level when uaqi >= 60
POLLUTANT_ACTION_CATEGORY = "Good"  # below_action_level when epa_category == Good
POLLEN_ACTION_MIN_UPI = 2        # below_action_level when index < 2


def uaqi_severity(aqi: float | None) -> int | None:
    """Rank of a Universal AQI value within the official band ladder."""
    if not isinstance(aqi, (int, float)):
        return None
    for floor, rank in _UAQI_BAND_FLOORS:
        if aqi >= floor:
            return rank
    return UAQI_SEVERITY_MAX


def epa_severity(category: str | None) -> int | None:
    """Rank of an EPA AQI category within the EPA ladder."""
    try:
        return EPA_CATEGORY_ORDER.index(category)
    except ValueError:
        return None


def alert_severity_rank(severity: str | None) -> int | None:
    """Rank of a publicAlerts severity enum value; unknown values → None."""
    try:
        return ALERT_SEVERITY_ORDER.index(severity)
    except ValueError:
        return None
