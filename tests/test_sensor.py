"""Tests for particle_man sensor platform."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.core import HomeAssistant

from custom_components.particle_man.const import DOMAIN
from custom_components.particle_man.coordinator import ParticleManCoordinator
from custom_components.particle_man.sensor import (
    AirQualityAdvisorySensor,
    AqiLevelSensor,
    AqiSensor,
    HeatIndexSensor,
    LastApiUpdateSensor,
    LocalAqiSensor,
    MonthlyAqUsageSensor,
    MonthlyPollenUsageSensor,
    MonthlyWeatherUsageSensor,
    PollenAdvisorySensor,
    PollenPlantSensor,
    PollenTypeLevelSensor,
    PollenTypeSensor,
    PollutantLevelSensor,
    PollutantSensor,
    ThunderstormProbabilitySensor,
    WindChillSensor,
    WeatherAlertCountSensor,
    WeatherAlertSeveritySensor,
    WeatherAlertEventTypesSensor,
    _add_dynamic_entities,
)
from tests.conftest import ENTRY_ID, TEST_LAT, TEST_LON, TEST_LOCATION_NAME, TEST_API_KEY


@pytest.fixture
def coord(hass: HomeAssistant, mock_config_entry) -> ParticleManCoordinator:
    """Return a coordinator with test data loaded."""
    mock_config_entry.add_to_hass(hass)
    with patch("custom_components.particle_man.coordinator.Store", autospec=True) as ms:
        ms.return_value.async_load = AsyncMock(return_value=None)
        ms.return_value.async_save = AsyncMock()
        c = ParticleManCoordinator(
            hass=hass,
            api_key=TEST_API_KEY,
            latitude=TEST_LAT,
            longitude=TEST_LON,
            location_name=TEST_LOCATION_NAME,
            enable_air_quality=True,
            enable_pollen=True,
            enable_weather=True,
            enable_weather_alerts=True,
            enable_local_aqi=True,
            quiet_hours_enabled=False,
            entry_id=ENTRY_ID,
            config_entry=mock_config_entry,
        )
    c.data = {
        "aqi": {
            "value": 45,
            "category": "Good",
            "dominant_pollutant": "pm25",
            "daily_forecast": [],
            "hourly_forecast": [],
            "trend": "Stable",
            "health_recommendations": {"generalPopulation": "Fine."},
        },
        "aq_advisory": {
            "value": "None",
            "aqi": 45,
            "category": "Good",
            "dominant_pollutant": "pm25",
            "elevated_pollutants": [],
            "trend": "Stable",
        },
        "local_aqi": {
            "value": 42,
            "category": "Good",
            "display_name": "US AQI",
            "display": "42",
            "code": "us_aqi",
            "daily_forecast": [],
            "hourly_forecast": [],
        },
        "pollutant_pm25": {
            "code": "pm25",
            "display_name": "PM2.5",
            "full_name": "Fine particles",
            "value": 5.2,
            "units": "μg/m³",
            "epa_category": "Good",
            "sources": "Traffic",
            "effects": "Respiratory",
            "is_dominant": True,
            "daily_forecast": [],
            "hourly_forecast": [],
            "trend": "Stable",
        },
        "pollutant_o3": {
            "code": "o3",
            "display_name": "Ozone",
            "full_name": "Ozone",
            "value": 0.035,
            "units": "ppm",
            "epa_category": "Good",
            "is_dominant": False,
            "daily_forecast": [],
            "hourly_forecast": [],
        },
        "pollen_type_tree": {
            "display_name": "Tree",
            "value": 2,
            "category": "Low",
            "in_season": True,
        },
        "pollen_plant_alder": {
            "display_name": "Alder",
            "value": 1,
            "category": "Very Low",
            "in_season": True,
            "color_hex": "#00ff00",
            "type": "TREE",
            "family": "Betulaceae",
        },
        "weather_current": {
            "temperature": 15.0,
            "feels_like": 13.0,
            "dew_point": 8.0,
            "humidity": 60,
            "wind_speed": 10.0,
            "wind_direction": 270,
            "wind_gust": 15.0,
            "pressure": 1013.0,
            "visibility": 16.0,
            "cloud_cover": 10,
            "precipitation_probability": 5,
            "precipitation_qpf": 0.0,
            "condition": "sunny",
            "thunderstorm_probability": 2,
            "heat_index": 16.0,
            "wind_chill": 12.0,
        },
    }
    c._cached_tracking = {
        "period_month": "2026-04",
        "aq_calls": 100,
        "pollen_calls": 50,
        "weather_calls": 75,
    }
    return c


# ---------------------------------------------------------------------------
# _add_dynamic_entities
# ---------------------------------------------------------------------------


def test_add_dynamic_entities_aq(coord: ParticleManCoordinator) -> None:
    known: set[str] = set()
    out: list = []
    _add_dynamic_entities(coord, coord.data, known, out)
    types = [type(e).__name__ for e in out]
    assert "LocalAqiSensor" in types
    assert "PollutantSensor" in types
    assert "PollutantLevelSensor" in types  # pm25 has EPA breakpoints


def test_add_dynamic_entities_no_duplicates(coord: ParticleManCoordinator) -> None:
    known: set[str] = set()
    out: list = []
    _add_dynamic_entities(coord, coord.data, known, out)
    count1 = len(out)
    _add_dynamic_entities(coord, coord.data, known, out)  # known is populated now
    assert len(out) == count1  # no new entities added


def test_add_dynamic_entities_pollen(coord: ParticleManCoordinator) -> None:
    known: set[str] = set()
    out: list = []
    _add_dynamic_entities(coord, coord.data, known, out)
    types = [type(e).__name__ for e in out]
    assert "PollenTypeSensor" in types
    assert "PollenTypeLevelSensor" in types
    assert "PollenPlantSensor" in types


def test_add_dynamic_entities_weather(coord: ParticleManCoordinator) -> None:
    known: set[str] = set()
    out: list = []
    _add_dynamic_entities(coord, coord.data, known, out)
    types = [type(e).__name__ for e in out]
    assert "ThunderstormProbabilitySensor" in types
    assert "HeatIndexSensor" in types
    assert "WindChillSensor" in types


def test_add_dynamic_entities_disabled_aq(coord: ParticleManCoordinator) -> None:
    coord.enable_air_quality = False
    known: set[str] = set()
    out: list = []
    _add_dynamic_entities(coord, coord.data, known, out)
    types = [type(e).__name__ for e in out]
    assert "PollutantSensor" not in types
    assert "LocalAqiSensor" not in types


def test_add_dynamic_entities_no_level_sensor_for_unknown_pollutant(coord: ParticleManCoordinator) -> None:
    """Pollutants without EPA breakpoints don't get a level sensor."""
    known: set[str] = set()
    out: list = []
    # o3 has EPA breakpoints, pm25 also — but add a non-EPA pollutant
    coord.data["pollutant_benzene"] = {"value": 1.0}
    _add_dynamic_entities(coord, coord.data, known, out)
    types = [type(e).__name__ for e in out]
    # Should have level sensor for pm25 and o3 but not benzene
    level_sensors = [e for e in out if isinstance(e, PollutantLevelSensor)]
    codes = {e.code for e in level_sensors}
    assert "benzene" not in codes


# ---------------------------------------------------------------------------
# AqiSensor
# ---------------------------------------------------------------------------


def test_aqi_sensor_state(coord: ParticleManCoordinator) -> None:
    s = AqiSensor(coord)
    assert s.native_value == 45
    assert s.device_class == SensorDeviceClass.AQI


def test_aqi_sensor_attributes(coord: ParticleManCoordinator) -> None:
    s = AqiSensor(coord)
    attrs = s.extra_state_attributes
    assert attrs["category"] == "Good"
    assert attrs["dominant_pollutant"] == "pm25"
    assert "health_recommendations" in attrs


def test_aqi_sensor_none_data(coord: ParticleManCoordinator) -> None:
    coord.data = {}
    s = AqiSensor(coord)
    assert s.native_value is None


# ---------------------------------------------------------------------------
# AqiLevelSensor
# ---------------------------------------------------------------------------


def test_aqi_level_sensor_state(coord: ParticleManCoordinator) -> None:
    s = AqiLevelSensor(coord)
    assert s.native_value == "Good"


# ---------------------------------------------------------------------------
# AirQualityAdvisorySensor
# ---------------------------------------------------------------------------


def test_aq_advisory_sensor_state(coord: ParticleManCoordinator) -> None:
    s = AirQualityAdvisorySensor(coord)
    assert s.native_value == "None"


# ---------------------------------------------------------------------------
# LocalAqiSensor
# ---------------------------------------------------------------------------


def test_local_aqi_sensor_state(coord: ParticleManCoordinator) -> None:
    s = LocalAqiSensor(coord)
    assert s.native_value == 42
    assert s.name == "US AQI"
    assert s.device_class == SensorDeviceClass.AQI


def test_local_aqi_sensor_fallback_name(coord: ParticleManCoordinator) -> None:
    coord.data["local_aqi"] = {"value": 42}
    s = LocalAqiSensor(coord)
    assert s.name == "Local AQI"


# ---------------------------------------------------------------------------
# PollutantSensor
# ---------------------------------------------------------------------------


def test_pollutant_sensor_state(coord: ParticleManCoordinator) -> None:
    s = PollutantSensor(coord, "pm25")
    assert s.native_value == 5.2
    assert s.native_unit_of_measurement == "μg/m³"
    assert s.name == "PM2.5"


def test_pollutant_sensor_icon_known(coord: ParticleManCoordinator) -> None:
    s = PollutantSensor(coord, "o3")
    assert s.icon == "mdi:weather-sunny-alert"


def test_pollutant_sensor_icon_unknown(coord: ParticleManCoordinator) -> None:
    s = PollutantSensor(coord, "benzene")
    assert s.icon == "mdi:smoke"


# ---------------------------------------------------------------------------
# PollutantLevelSensor
# ---------------------------------------------------------------------------


def test_pollutant_level_sensor(coord: ParticleManCoordinator) -> None:
    s = PollutantLevelSensor(coord, "pm25")
    assert s.native_value == "Good"
    assert s._attr_entity_registry_enabled_default is False


# ---------------------------------------------------------------------------
# PollenTypeSensor
# ---------------------------------------------------------------------------


def test_pollen_type_sensor_state(coord: ParticleManCoordinator) -> None:
    s = PollenTypeSensor(coord, "tree")
    assert s.native_value == 2
    assert s.extra_state_attributes.get("category") == "Low"


def test_pollen_type_level_sensor(coord: ParticleManCoordinator) -> None:
    s = PollenTypeLevelSensor(coord, "tree")
    assert s.native_value == "Low"
    assert s._attr_entity_registry_enabled_default is False


# ---------------------------------------------------------------------------
# PollenPlantSensor
# ---------------------------------------------------------------------------


def test_pollen_plant_sensor_state(coord: ParticleManCoordinator) -> None:
    s = PollenPlantSensor(coord, "alder")
    assert s.native_value == 1


# ---------------------------------------------------------------------------
# Weather sensors
# ---------------------------------------------------------------------------


def test_thunderstorm_probability_sensor(coord: ParticleManCoordinator) -> None:
    s = ThunderstormProbabilitySensor(coord)
    assert s.native_value == 2
    assert s.native_unit_of_measurement == "%"


def test_heat_index_sensor(coord: ParticleManCoordinator) -> None:
    s = HeatIndexSensor(coord)
    assert s.native_value == 16.0


def test_wind_chill_sensor(coord: ParticleManCoordinator) -> None:
    s = WindChillSensor(coord)
    assert s.native_value == 12.0


# ---------------------------------------------------------------------------
# Diagnostic sensors
# ---------------------------------------------------------------------------


def test_last_api_update_sensor(coord: ParticleManCoordinator) -> None:
    s = LastApiUpdateSensor(coord)
    assert s.unique_id == f"{ENTRY_ID}_last_api_update"


def test_monthly_aq_usage_sensor(coord: ParticleManCoordinator) -> None:
    s = MonthlyAqUsageSensor(coord)
    assert s.native_value == 100


def test_monthly_pollen_usage_sensor(coord: ParticleManCoordinator) -> None:
    s = MonthlyPollenUsageSensor(coord)
    assert s.native_value == 50


def test_monthly_weather_usage_sensor(coord: ParticleManCoordinator) -> None:
    s = MonthlyWeatherUsageSensor(coord)
    assert s.native_value == 75


# ---------------------------------------------------------------------------
# Entity identity
# ---------------------------------------------------------------------------


def test_entity_has_entity_name_true(coord: ParticleManCoordinator) -> None:
    for SensorClass in [AqiSensor, AqiLevelSensor, AirQualityAdvisorySensor]:
        s = SensorClass(coord)
        assert s._attr_has_entity_name is True


def test_entity_unique_ids_distinct(coord: ParticleManCoordinator) -> None:
    s1 = AqiSensor(coord)
    s2 = AqiLevelSensor(coord)
    s3 = PollutantSensor(coord, "pm25")
    assert len({s1.unique_id, s2.unique_id, s3.unique_id}) == 3


def test_pollen_advisory_sensor(coord: ParticleManCoordinator) -> None:
    coord.data["pollen_advisory"] = {"value": "Low", "dominant_type": "TREE", "types": []}
    s = PollenAdvisorySensor(coord)
    assert s.native_value == "Low"


def test_weather_alert_count_sensor_zero(coord: ParticleManCoordinator) -> None:
    coord.data["weather_alerts"] = []
    s = WeatherAlertCountSensor(coord)
    assert s.native_value == 0


# ---------------------------------------------------------------------------
# Additional coverage tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sensor_setup_entry_no_coordinators(
    hass: HomeAssistant, mock_config_entry
) -> None:
    """async_setup_entry returns early with no coordinators (line 106)."""
    from custom_components.particle_man.sensor import async_setup_entry

    mock_config_entry.add_to_hass(hass)
    mock_config_entry.runtime_data = {"coordinators": {}, "global_state": MagicMock()}

    entities_added: list = []

    def mock_add(entities, update_before_add: bool = False) -> None:
        entities_added.extend(entities)

    await async_setup_entry(hass, mock_config_entry, mock_add)
    assert entities_added == []


def test_aq_advisory_sensor_with_health_recs(coord: ParticleManCoordinator) -> None:
    """AirQualityAdvisorySensor with health_recs in attributes (line 319)."""
    coord.data["aq_advisory"] = {
        "value": "Caution",
        "aqi": 55,
        "category": "Unhealthy for Sensitive Groups",
        "dominant_pollutant": "pm25",
        "elevated_pollutants": ["PM2.5"],
        "trend": "rising",
        "health_recommendations": {"generalPopulation": "Reduce outdoor activity."},
    }
    s = AirQualityAdvisorySensor(coord)
    attrs = s.extra_state_attributes
    assert "health_recommendations" in attrs


def test_local_aqi_sensor_extra_attributes(coord: ParticleManCoordinator) -> None:
    """LocalAqiSensor extra_state_attributes (lines 348-349)."""
    s = LocalAqiSensor(coord)
    attrs = s.extra_state_attributes
    assert "category" in attrs
    assert "index_code" in attrs
    assert attrs["index_code"] == "us_aqi"


def test_pollutant_level_sensor_extra_attributes(coord: ParticleManCoordinator) -> None:
    """PollutantLevelSensor extra_state_attributes (lines 433-435)."""
    s = PollutantLevelSensor(coord, "pm25")
    attrs = s.extra_state_attributes
    assert "concentration" in attrs
    assert "units" in attrs
    assert "color_hex" in attrs


def test_pollen_advisory_sensor_with_health_recs(coord: ParticleManCoordinator) -> None:
    """PollenAdvisorySensor includes health_recs when present (line 471)."""
    coord.data["pollen_advisory"] = {
        "value": "Moderate",
        "dominant_type": "TREE",
        "dominant_index": 3,
        "in_season_types": ["Tree"],
        "all_levels": {"Tree": "Moderate"},
        "health_recommendations": {"generalPopulation": "Take antihistamines."},
    }
    s = PollenAdvisorySensor(coord)
    attrs = s.extra_state_attributes
    assert "health_recommendations" in attrs


def test_pollen_type_sensor_with_health_recs(coord: ParticleManCoordinator) -> None:
    """PollenTypeSensor includes health_recs when present (line 514)."""
    coord.data["pollen_type_tree"] = {
        "display_name": "Tree",
        "value": 3,
        "category": "Moderate",
        "in_season": True,
        "forecast": [],
        "health_recommendations": {"generalPopulation": "Limit outdoor time."},
    }
    s = PollenTypeSensor(coord, "tree")
    attrs = s.extra_state_attributes
    assert "health_recommendations" in attrs


def test_pollen_type_level_sensor_extra_attributes(coord: ParticleManCoordinator) -> None:
    """PollenTypeLevelSensor extra_state_attributes (lines 546-548)."""
    s = PollenTypeLevelSensor(coord, "tree")
    attrs = s.extra_state_attributes
    assert "index" in attrs
    assert "in_season" in attrs
    assert "color_hex" in attrs


def test_pollen_plant_sensor_extra_attributes_with_fields(coord: ParticleManCoordinator) -> None:
    """PollenPlantSensor optional field attrs (lines 582-595)."""
    coord.data["pollen_plant_alder"] = {
        "display_name": "Alder",
        "value": 1,
        "category": "Very Low",
        "in_season": True,
        "color_hex": "#00cc00",
        "family": "Betulaceae",
        "genus": "Alnus",
        "season": "Spring",
        "cross_reaction": "None",
        "picture": "https://example.com/alder.jpg",
        "forecast": [],
    }
    s = PollenPlantSensor(coord, "alder")
    attrs = s.extra_state_attributes
    assert attrs.get("family") == "Betulaceae"
    assert attrs.get("picture") == "https://example.com/alder.jpg"


def test_last_api_update_from_weather_fallback(coord: ParticleManCoordinator) -> None:
    """LastApiUpdateSensor falls back to weather_current datetime (line 722)."""
    coord.data = {"weather_current": {"datetime": "2026-04-22T12:00:00Z"}}
    s = LastApiUpdateSensor(coord)
    assert s.native_value is not None


def test_last_api_update_returns_none_when_no_data(coord: ParticleManCoordinator) -> None:
    """LastApiUpdateSensor returns None when no datetime available (line 724)."""
    coord.data = {}
    s = LastApiUpdateSensor(coord)
    assert s.native_value is None


def test_last_api_update_returns_none_for_invalid_datetime(coord: ParticleManCoordinator) -> None:
    """LastApiUpdateSensor returns None for unparseable datetime string (lines 727-728)."""
    coord.data = {"aqi": {"datetime": "not-a-valid-datetime-string"}}
    s = LastApiUpdateSensor(coord)
    assert s.native_value is None


def test_billing_projection_critical_status(coord: ParticleManCoordinator) -> None:
    """_billing_projection_attrs with ≥95% projected → critical (line 744)."""
    from datetime import date as _date
    from custom_components.particle_man.sensor import _billing_projection_attrs

    with patch("custom_components.particle_man.sensor._datetime") as mock_dt:
        mock_dt.now.return_value.date.return_value = _date(2026, 4, 15)
        attrs = _billing_projection_attrs(50, 100, "2026-04")
    assert attrs["status"] == "critical"


def test_billing_projection_warning_status(coord: ParticleManCoordinator) -> None:
    """_billing_projection_attrs with 95-99% projected → warning."""
    from datetime import date as _date
    from custom_components.particle_man.sensor import _billing_projection_attrs

    with patch("custom_components.particle_man.sensor._datetime") as mock_dt:
        mock_dt.now.return_value.date.return_value = _date(2026, 4, 15)
        attrs = _billing_projection_attrs(48, 100, "2026-04")
    assert attrs["status"] == "warning"


def test_billing_projection_invalid_period(coord: ParticleManCoordinator) -> None:
    """_billing_projection_attrs with invalid period hits except block (lines 749-753)."""
    from custom_components.particle_man.sensor import _billing_projection_attrs

    attrs = _billing_projection_attrs(50, 100, "not-a-valid-period")
    assert attrs["status"] == "ok"
    assert attrs["projected_monthly"] == 0


# ---------------------------------------------------------------------------
# _uv_category and UvIndexCategorySensor
# ---------------------------------------------------------------------------


def test_uv_category_none() -> None:
    from custom_components.particle_man.sensor import _uv_category
    assert _uv_category(None) is None


@pytest.mark.parametrize("value,expected", [
    (0.0, "Low"),
    (2.0, "Low"),
    (2.1, "Moderate"),
    (5.0, "Moderate"),
    (5.1, "High"),
    (7.0, "High"),
    (7.1, "Very High"),
    (10.0, "Very High"),
    (10.1, "Extreme"),
    (15.0, "Extreme"),
])
def test_uv_category_branches(value: float, expected: str) -> None:
    from custom_components.particle_man.sensor import _uv_category
    assert _uv_category(value) == expected


def test_uv_index_category_sensor_native_value(coord: ParticleManCoordinator) -> None:
    from custom_components.particle_man.sensor import UvIndexCategorySensor
    coord.data["weather_current"] = {"uv_index": 6}
    s = UvIndexCategorySensor(coord)
    assert s.native_value == "High"


def test_uv_index_category_sensor_none_when_missing(coord: ParticleManCoordinator) -> None:
    from custom_components.particle_man.sensor import UvIndexCategorySensor
    coord.data["weather_current"] = {}
    s = UvIndexCategorySensor(coord)
    assert s.native_value is None


def test_uv_index_category_sensor_attributes(coord: ParticleManCoordinator) -> None:
    from custom_components.particle_man.sensor import UvIndexCategorySensor
    coord.data["weather_current"] = {"uv_index": 3}
    s = UvIndexCategorySensor(coord)
    attrs = s.extra_state_attributes
    assert attrs["uv_index"] == 3
    assert "attribution" in attrs


# ---------------------------------------------------------------------------
# WeatherAlertCountSensor, WeatherAlertSeveritySensor, WeatherAlertEventTypesSensor
# ---------------------------------------------------------------------------

SAMPLE_ALERTS = [
    {"severity": "SEVERE", "event_type": "TORNADO_WARNING"},
    {"severity": "MODERATE", "event_type": "FLOOD_WATCH"},
    {"severity": "SEVERE", "event_type": "TORNADO_WARNING"},
]


def test_weather_alert_count_with_alerts(coord: ParticleManCoordinator) -> None:
    coord.data["weather_alerts"] = SAMPLE_ALERTS
    s = WeatherAlertCountSensor(coord)
    assert s.native_value == 3


def test_weather_alert_count_attributes(coord: ParticleManCoordinator) -> None:
    coord.data["weather_alerts"] = SAMPLE_ALERTS
    s = WeatherAlertCountSensor(coord)
    attrs = s.extra_state_attributes
    assert attrs["highest_severity"] == "SEVERE"
    assert set(attrs["active_event_types"]) == {"TORNADO_WARNING", "FLOOD_WATCH"}
    assert "attribution" in attrs


def test_weather_alert_count_no_alerts(coord: ParticleManCoordinator) -> None:
    coord.data["weather_alerts"] = []
    s = WeatherAlertCountSensor(coord)
    assert s.native_value == 0
    assert s.extra_state_attributes["highest_severity"] is None


def test_weather_alert_severity_returns_highest(coord: ParticleManCoordinator) -> None:
    coord.data["weather_alerts"] = SAMPLE_ALERTS
    s = WeatherAlertSeveritySensor(coord)
    assert s.native_value == "SEVERE"


def test_weather_alert_severity_ordering(coord: ParticleManCoordinator) -> None:
    coord.data["weather_alerts"] = [
        {"severity": "MINOR", "event_type": "WIND_ADVISORY"},
        {"severity": "EXTREME", "event_type": "TORNADO_EMERGENCY"},
        {"severity": "MODERATE", "event_type": "FLOOD_WARNING"},
    ]
    s = WeatherAlertSeveritySensor(coord)
    assert s.native_value == "EXTREME"


def test_weather_alert_severity_none_when_no_alerts(coord: ParticleManCoordinator) -> None:
    coord.data["weather_alerts"] = []
    s = WeatherAlertSeveritySensor(coord)
    assert s.native_value is None


def test_weather_alert_severity_none_when_key_absent(coord: ParticleManCoordinator) -> None:
    coord.data.pop("weather_alerts", None)
    s = WeatherAlertSeveritySensor(coord)
    assert s.native_value is None


def test_weather_alert_event_types_sorted_unique(coord: ParticleManCoordinator) -> None:
    coord.data["weather_alerts"] = SAMPLE_ALERTS
    s = WeatherAlertEventTypesSensor(coord)
    assert s.native_value == "FLOOD_WATCH, TORNADO_WARNING"


def test_weather_alert_event_types_none_when_no_alerts(coord: ParticleManCoordinator) -> None:
    coord.data["weather_alerts"] = []
    s = WeatherAlertEventTypesSensor(coord)
    assert s.native_value is None


def test_weather_alert_event_types_none_when_key_absent(coord: ParticleManCoordinator) -> None:
    coord.data.pop("weather_alerts", None)
    s = WeatherAlertEventTypesSensor(coord)
    assert s.native_value is None


def test_weather_alert_sensors_attribution(coord: ParticleManCoordinator) -> None:
    coord.data["weather_alerts"] = SAMPLE_ALERTS
    for sensor_cls in (WeatherAlertSeveritySensor, WeatherAlertEventTypesSensor):
        s = sensor_cls(coord)
        assert "attribution" in s.extra_state_attributes


# ---------------------------------------------------------------------------
# Monthly usage sensor assumption attributes
# ---------------------------------------------------------------------------


def test_monthly_aq_assumption_attrs_present(coord: ParticleManCoordinator) -> None:
    coord._cached_tracking = {"aq_calls": 100, "period_month": "2026-05"}
    sensor = MonthlyAqUsageSensor(coord)
    attrs = sensor.extra_state_attributes
    for key in (
        "automagic_mode", "num_locations", "calls_per_poll", "fetch_interval_minutes",
        "quiet_hours_enabled", "billing_month_days", "effective_minutes_per_month",
        "safety_buffer_pct", "days_remaining", "calls_per_day",
    ):
        assert key in attrs, f"Missing key: {key}"


def test_monthly_pollen_assumption_attrs_present(coord: ParticleManCoordinator) -> None:
    coord._cached_tracking = {"pollen_calls": 50, "period_month": "2026-05"}
    sensor = MonthlyPollenUsageSensor(coord)
    attrs = sensor.extra_state_attributes
    for key in (
        "automagic_mode", "calls_per_poll", "fetch_interval_minutes",
        "billing_month_days", "effective_minutes_per_month",
    ):
        assert key in attrs, f"Missing key: {key}"


def test_monthly_weather_assumption_attrs_present(coord: ParticleManCoordinator) -> None:
    coord._cached_tracking = {"weather_calls": 200, "period_month": "2026-05"}
    sensor = MonthlyWeatherUsageSensor(coord)
    attrs = sensor.extra_state_attributes
    for key in (
        "automagic_mode", "calls_per_poll", "fetch_interval_minutes",
        "billing_month_days", "effective_minutes_per_month",
        "days_remaining", "calls_per_day",
    ):
        assert key in attrs, f"Missing key: {key}"


def test_monthly_aq_fetch_interval_reflected_in_attrs(coord: ParticleManCoordinator) -> None:
    from datetime import timedelta
    coord._aq_fetch_interval = timedelta(minutes=90)
    coord._cached_tracking = {"aq_calls": 0, "period_month": "2026-05"}
    attrs = MonthlyAqUsageSensor(coord).extra_state_attributes
    assert attrs["fetch_interval_minutes"] == 90


def test_monthly_billing_projection_days_remaining(coord: ParticleManCoordinator) -> None:
    coord._cached_tracking = {"aq_calls": 200, "period_month": "2026-05"}
    attrs = MonthlyAqUsageSensor(coord).extra_state_attributes
    assert "days_remaining" in attrs
    assert attrs["days_remaining"] >= 0


def test_monthly_quiet_hours_window_none_when_disabled(coord: ParticleManCoordinator) -> None:
    coord._quiet_hours_enabled = False
    coord._cached_tracking = {"aq_calls": 0, "period_month": "2026-05"}
    attrs = MonthlyAqUsageSensor(coord).extra_state_attributes
    assert attrs["quiet_hours_window"] is None
    assert attrs["active_hours_per_day"] == 24.0
