"""Constants for Particle Man integration."""
import calendar as _cal
import math
from datetime import datetime as _dt
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
