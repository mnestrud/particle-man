"""Constants for Particle Man integration."""

DOMAIN = "particle_man"

# --- Config entry keys ---
CONF_API_KEY = "api_key"
CONF_LATITUDE = "latitude"
CONF_LONGITUDE = "longitude"
CONF_UPDATE_INTERVAL = "update_interval"
CONF_FORECAST_DAYS = "forecast_days"
CONF_LANGUAGE = "language_code"
CONF_LOCAL_AQI = "enable_local_aqi"
CONF_LOCAL_AQI_CODE = "local_aqi_code"
CONF_HEALTH_RECS = "include_health_recommendations"
CONF_PLANT_SENSORS = "include_plant_sensors"
CONF_PLANT_DESCRIPTIONS = "include_plant_descriptions"

# --- Defaults ---
DEFAULT_UPDATE_INTERVAL = 60  # minutes
DEFAULT_FORECAST_DAYS = 5
DEFAULT_LANGUAGE = "en"
DEFAULT_LOCAL_AQI = False
DEFAULT_LOCAL_AQI_CODE = "us_aqi"
DEFAULT_HEALTH_RECS = False
DEFAULT_PLANT_SENSORS = True
DEFAULT_PLANT_DESCRIPTIONS = True

# --- API ---
BASE_URL = "https://airquality.googleapis.com/v1"
POLLEN_API_URL = "https://pollen.googleapis.com/v1/forecast:lookup"
ATTRIBUTION = "Data provided by Google Air Quality API"
POLLEN_ATTRIBUTION = "Data provided by Google Pollen API"

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
