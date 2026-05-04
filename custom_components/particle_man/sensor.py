"""Particle Man sensors."""
from __future__ import annotations

import calendar as _calendar
import logging
from datetime import date as _date
from datetime import datetime as _datetime
from collections.abc import Callable
from typing import Any, cast

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ATTRIBUTION, PERCENTAGE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.const import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTRIBUTION,
    DOMAIN,
    EPA_BREAKPOINT_POLLUTANTS,
    EPA_COLORS,
    POLLEN_ATTRIBUTION,
    POLLEN_COLORS,
    WEATHER_ATTRIBUTION,
    _AQ_CALLS_PER_POLL,
    _PACIFIC_TZ,
    _POLLEN_CALLS_PER_POLL,
    _billing_month_days,
    _quiet_active_minutes_per_month,
)
from .coordinator import ParticleManCoordinator

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1

_POLLUTANT_ICONS: dict[str, str] = {
    "o3": "mdi:weather-sunny-alert",
    "no2": "mdi:car-exhaust",
    "no": "mdi:car-exhaust",
    "nox": "mdi:car-exhaust",
    "so2": "mdi:factory",
    "nh3": "mdi:molecule",
    "c6h6": "mdi:molecule",
    "nmhc": "mdi:molecule",
    "co": "mdi:truck",
}
_POLLEN_TYPE_ICONS: dict[str, str] = {
    "grass": "mdi:grass",
    "tree": "mdi:tree",
    "weed": "mdi:flower-tulip",
}


def _add_dynamic_entities(
    coordinator: ParticleManCoordinator,
    data: dict[str, Any],
    known: set[str],
    out: list[SensorEntity],
) -> None:
    """Append entities for data keys not yet tracked in `known`."""
    if coordinator.enable_air_quality:
        if "local_aqi" in data and "local_aqi" not in known:
            out.append(LocalAqiSensor(coordinator))
            known.add("local_aqi")
        for key in data:
            if key.startswith("pollutant_") and key not in known:
                code = key[len("pollutant_"):]
                out.append(PollutantSensor(coordinator, code))
                known.add(key)
                level_key = f"{key}_level"
                if code in EPA_BREAKPOINT_POLLUTANTS and level_key not in known:
                    out.append(PollutantLevelSensor(coordinator, code))
                    known.add(level_key)

    if coordinator.enable_pollen:
        for key in data:
            if key.startswith("pollen_type_") and key not in known:
                ptype = key[len("pollen_type_"):]
                out.append(PollenTypeSensor(coordinator, ptype))
                out.append(PollenTypeLevelSensor(coordinator, ptype))
                known.add(key)
            elif key.startswith("pollen_plant_") and key not in known:
                pcode = key[len("pollen_plant_"):]
                out.append(PollenPlantSensor(coordinator, pcode))
                known.add(key)

    if coordinator.enable_weather and "weather_current" in data and "weather_current" not in known:
        out.extend([
            ThunderstormProbabilitySensor(coordinator),
            HeatIndexSensor(coordinator),
            WindChillSensor(coordinator),
            UvIndexCategorySensor(coordinator),
        ])
        known.add("weather_current")


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up all sensors from config entry."""
    runtime = entry.runtime_data
    coordinators: dict[str, ParticleManCoordinator] = runtime.get("coordinators", {})

    if not coordinators:
        return

    entities: list[SensorEntity] = []

    # Shared diagnostics — one set per entry (monthly usage is pooled across all locations)
    first_coordinator = next(iter(coordinators.values()))
    entities.append(LastApiUpdateSensor(first_coordinator))
    if first_coordinator.enable_air_quality:
        entities.append(MonthlyAqUsageSensor(first_coordinator))
    if first_coordinator.enable_pollen:
        entities.append(MonthlyPollenUsageSensor(first_coordinator))
    if first_coordinator.enable_weather:
        entities.append(MonthlyWeatherUsageSensor(first_coordinator))

    # Per-location sensors
    for coordinator in coordinators.values():
        known: set[str] = set()

        # Static per-location entities (always present when API is enabled)
        if coordinator.enable_air_quality:
            entities.extend([
                AqiSensor(coordinator),
                AqiLevelSensor(coordinator),
                AirQualityAdvisorySensor(coordinator),
            ])
        if coordinator.enable_pollen:
            entities.append(PollenAdvisorySensor(coordinator))
        if coordinator.enable_weather and coordinator.enable_weather_alerts:
            entities.extend([
                WeatherAlertCountSensor(coordinator),
                WeatherAlertSeveritySensor(coordinator),
                WeatherAlertEventTypesSensor(coordinator),
            ])

        # Dynamic entities — initial pass from first-refresh data
        _add_dynamic_entities(coordinator, coordinator.data or {}, known, entities)

        # Subscribe to future updates to pick up new keys (e.g. new pollen species)
        def _make_listener(
            coord: ParticleManCoordinator, known_keys: set[str]
        ) -> Callable[[], None]:
            def _listener() -> None:
                new: list[SensorEntity] = []
                _add_dynamic_entities(coord, coord.data or {}, known_keys, new)
                if new:
                    async_add_entities(new, True)
            return _listener

        entry.async_on_unload(
            coordinator.async_add_listener(_make_listener(coordinator, known))
        )

    async_add_entities(entities, True)


# ---------------------------------------------------------------------------
# Base classes
# ---------------------------------------------------------------------------

class _BaseGaqSensor(CoordinatorEntity[ParticleManCoordinator], SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator: ParticleManCoordinator) -> None:
        super().__init__(coordinator)
        self.coordinator = coordinator

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self.coordinator.entry_id}_{self.coordinator.location_slug}")},
            name=f"{self.coordinator.location_name} Pollution",
            manufacturer="Google",
            model="Air Quality API",
        )


class _BasePollenSensor(CoordinatorEntity[ParticleManCoordinator], SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator: ParticleManCoordinator) -> None:
        super().__init__(coordinator)
        self.coordinator = coordinator

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self.coordinator.entry_id}_{self.coordinator.location_slug}_pollen")},
            name=f"{self.coordinator.location_name} Pollen",
            manufacturer="Google",
            model="Pollen API",
            via_device=(DOMAIN, f"{self.coordinator.entry_id}_{self.coordinator.location_slug}"),
        )


class _BaseWeatherSensor(CoordinatorEntity[ParticleManCoordinator], SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator: ParticleManCoordinator) -> None:
        super().__init__(coordinator)
        self.coordinator = coordinator

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self.coordinator.entry_id}_{self.coordinator.location_slug}_weather")},
            name=f"{self.coordinator.location_name} Weather",
            manufacturer="Google",
            model="Weather API",
            via_device=(DOMAIN, f"{self.coordinator.entry_id}_{self.coordinator.location_slug}"),
        )


class _BaseDiagnosticSensor(CoordinatorEntity[ParticleManCoordinator], SensorEntity):
    """Shared diagnostics device — one per entry (monthly API usage is per API key)."""
    _attr_has_entity_name = True

    def __init__(self, coordinator: ParticleManCoordinator) -> None:
        super().__init__(coordinator)
        self.coordinator = coordinator

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self.coordinator.entry_id}_diagnostics")},
            name="Particle Man Diagnostics",
            manufacturer="Google",
            model="Particle Man",
        )


# ---------------------------------------------------------------------------
# Air Quality sensors
# ---------------------------------------------------------------------------

class AqiSensor(_BaseGaqSensor):
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_device_class = SensorDeviceClass.AQI
    _attr_translation_key = "aqi"
    _unrecorded_attributes = frozenset({"hourly_forecast"})

    def __init__(self, coordinator: ParticleManCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry_id}_{coordinator.location_slug}_aqi"

    @property
    def native_value(self) -> int | None:
        val = self.coordinator.data.get("aqi", {}).get("value")
        return int(val) if isinstance(val, (int, float)) else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        info = cast(dict[str, Any], self.coordinator.data.get("aqi", {}))
        attrs: dict[str, Any] = {
            "category": info.get("category"),
            "dominant_pollutant": info.get("dominant_pollutant"),
            "region_code": info.get("region_code"),
            "last_updated": info.get("datetime"),
            "trend": info.get("trend"),
            "daily_forecast": info.get("daily_forecast", []),
            "hourly_forecast": info.get("hourly_forecast", []),
            ATTR_ATTRIBUTION: ATTRIBUTION,
        }
        if info.get("health_recommendations") is not None:
            attrs["health_recommendations"] = info["health_recommendations"]
        return attrs


class AqiLevelSensor(_BaseGaqSensor):
    _attr_entity_category = None
    _attr_translation_key = "aqi_level"

    def __init__(self, coordinator: ParticleManCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry_id}_{coordinator.location_slug}_aqi_level"

    @property
    def native_value(self) -> str | None:
        val = self.coordinator.data.get("aqi", {}).get("category")
        return str(val) if val is not None else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        info = cast(dict[str, Any], self.coordinator.data.get("aqi", {}))
        return {
            "aqi": info.get("value"),
            "dominant_pollutant": info.get("dominant_pollutant"),
            ATTR_ATTRIBUTION: ATTRIBUTION,
        }


class AirQualityAdvisorySensor(_BaseGaqSensor):
    _attr_translation_key = "aq_advisory"

    def __init__(self, coordinator: ParticleManCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry_id}_{coordinator.location_slug}_aq_advisory"

    @property
    def native_value(self) -> str | None:
        val = self.coordinator.data.get("aq_advisory", {}).get("value")
        return str(val) if val is not None else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        info = cast(dict[str, Any], self.coordinator.data.get("aq_advisory", {}))
        attrs: dict[str, Any] = {
            "aqi": info.get("aqi"),
            "category": info.get("category"),
            "dominant_pollutant": info.get("dominant_pollutant"),
            "elevated_pollutants": info.get("elevated_pollutants", []),
            "trend": info.get("trend"),
            ATTR_ATTRIBUTION: ATTRIBUTION,
        }
        if info.get("health_recommendations") is not None:
            attrs["health_recommendations"] = info["health_recommendations"]
        return attrs


class LocalAqiSensor(_BaseGaqSensor):
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_device_class = SensorDeviceClass.AQI
    _attr_icon = "mdi:air-filter"
    _unrecorded_attributes = frozenset({"hourly_forecast"})

    def __init__(self, coordinator: ParticleManCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry_id}_{coordinator.location_slug}_local_aqi"

    @property
    def _info(self) -> dict[str, Any]:
        return cast(dict[str, Any], self.coordinator.data.get("local_aqi", {}))

    @property
    def name(self) -> str:
        return self._info.get("display_name") or "Local AQI"

    @property
    def native_value(self) -> int | None:
        val = self._info.get("value")
        return int(val) if isinstance(val, (int, float)) else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        info = self._info
        return {
            "category": info.get("category"),
            "aqi_display": info.get("display"),
            "dominant_pollutant": info.get("dominant_pollutant"),
            "index_code": info.get("code"),
            "trend": info.get("trend"),
            "daily_forecast": info.get("daily_forecast", []),
            "hourly_forecast": info.get("hourly_forecast", []),
            ATTR_ATTRIBUTION: ATTRIBUTION,
        }


class PollutantSensor(_BaseGaqSensor):
    _attr_state_class = SensorStateClass.MEASUREMENT
    _unrecorded_attributes = frozenset({"hourly_forecast"})

    def __init__(self, coordinator: ParticleManCoordinator, code: str) -> None:
        super().__init__(coordinator)
        self.code = code
        self._attr_unique_id = f"{coordinator.entry_id}_{coordinator.location_slug}_pollutant_{code}"

    @property
    def _info(self) -> dict[str, Any]:
        return cast(dict[str, Any], self.coordinator.data.get(f"pollutant_{self.code}", {}))

    @property
    def name(self) -> str:
        return str(self._info.get("display_name") or self.code.upper())

    @property
    def native_value(self) -> float | None:
        return self._info.get("value")

    @property
    def native_unit_of_measurement(self) -> str | None:
        return self._info.get("units")

    @property
    def icon(self) -> str:
        return _POLLUTANT_ICONS.get(self.code, "mdi:smoke")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        info = self._info
        return {
            "full_name": info.get("full_name"),
            "epa_category": info.get("epa_category"),
            "is_dominant": info.get("is_dominant"),
            "sources": info.get("sources"),
            "effects": info.get("effects"),
            "trend": info.get("trend"),
            "daily_forecast": info.get("daily_forecast", []),
            "hourly_forecast": info.get("hourly_forecast", []),
            ATTR_ATTRIBUTION: ATTRIBUTION,
        }


class PollutantLevelSensor(_BaseGaqSensor):
    _attr_entity_category = None
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: ParticleManCoordinator, code: str) -> None:
        super().__init__(coordinator)
        self.code = code
        self._attr_unique_id = f"{coordinator.entry_id}_{coordinator.location_slug}_pollutant_{code}_level"

    @property
    def _info(self) -> dict[str, Any]:
        return cast(dict[str, Any], self.coordinator.data.get(f"pollutant_{self.code}", {}))

    @property
    def name(self) -> str:
        return f"{self._info.get('display_name') or self.code.upper()} Level"

    @property
    def native_value(self) -> str | None:
        return self._info.get("epa_category")

    @property
    def icon(self) -> str:
        return _POLLUTANT_ICONS.get(self.code, "mdi:smoke")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        info = self._info
        category = info.get("epa_category")
        return {
            "concentration": info.get("value"),
            "units": info.get("units"),
            "color_hex": EPA_COLORS.get(category) if category else None,
            ATTR_ATTRIBUTION: ATTRIBUTION,
        }


# ---------------------------------------------------------------------------
# Pollen sensors
# ---------------------------------------------------------------------------

class PollenAdvisorySensor(_BasePollenSensor):
    _attr_translation_key = "pollen_advisory"

    def __init__(self, coordinator: ParticleManCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry_id}_{coordinator.location_slug}_pollen_advisory"

    @property
    def native_value(self) -> str | None:
        val = self.coordinator.data.get("pollen_advisory", {}).get("value")
        return str(val) if val is not None else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        info = cast(dict[str, Any], self.coordinator.data.get("pollen_advisory", {}))
        attrs: dict[str, Any] = {
            "dominant_type": info.get("dominant_type"),
            "dominant_index": info.get("dominant_index"),
            "in_season_types": info.get("in_season_types", []),
            "all_levels": info.get("all_levels", {}),
            ATTR_ATTRIBUTION: POLLEN_ATTRIBUTION,
        }
        if info.get("health_recommendations") is not None:
            attrs["health_recommendations"] = info["health_recommendations"]
        return attrs


class PollenTypeSensor(_BasePollenSensor):
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 0

    def __init__(self, coordinator: ParticleManCoordinator, ptype: str) -> None:
        super().__init__(coordinator)
        self.ptype = ptype
        self._attr_unique_id = f"{coordinator.entry_id}_{coordinator.location_slug}_pollen_type_{ptype}"

    @property
    def _info(self) -> dict[str, Any]:
        return cast(dict[str, Any], self.coordinator.data.get(f"pollen_type_{self.ptype}", {}))

    @property
    def name(self) -> str:
        return f"{self._info.get('display_name') or self.ptype.title()} Pollen"

    @property
    def native_value(self) -> int | None:
        val = self._info.get("value")
        return int(val) if isinstance(val, (int, float)) else None

    @property
    def icon(self) -> str:
        return _POLLEN_TYPE_ICONS.get(self.ptype, "mdi:flower-pollen")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        info = self._info
        attrs: dict[str, Any] = {
            "category": info.get("category"),
            "in_season": info.get("in_season"),
            "color_hex": info.get("color_hex"),
            "trend": info.get("trend"),
            "expected_peak": info.get("expected_peak"),
            "daily_forecast": info.get("forecast", []),
            ATTR_ATTRIBUTION: POLLEN_ATTRIBUTION,
        }
        if info.get("health_recommendations") is not None:
            attrs["health_recommendations"] = info["health_recommendations"]
        return attrs


class PollenTypeLevelSensor(_BasePollenSensor):
    _attr_entity_category = None
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: ParticleManCoordinator, ptype: str) -> None:
        super().__init__(coordinator)
        self.ptype = ptype
        self._attr_unique_id = f"{coordinator.entry_id}_{coordinator.location_slug}_pollen_type_{ptype}_level"

    @property
    def _info(self) -> dict[str, Any]:
        return cast(dict[str, Any], self.coordinator.data.get(f"pollen_type_{self.ptype}", {}))

    @property
    def name(self) -> str:
        return f"{self._info.get('display_name') or self.ptype.title()} Pollen Level"

    @property
    def native_value(self) -> str | None:
        val = self._info.get("category")
        return str(val) if val is not None else None

    @property
    def icon(self) -> str:
        return _POLLEN_TYPE_ICONS.get(self.ptype, "mdi:flower-pollen")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        info = self._info
        category = info.get("category")
        return {
            "index": info.get("value"),
            "in_season": info.get("in_season"),
            "color_hex": info.get("color_hex") or (POLLEN_COLORS.get(category) if category else None),
            ATTR_ATTRIBUTION: POLLEN_ATTRIBUTION,
        }


class PollenPlantSensor(_BasePollenSensor):
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 0
    _attr_icon = "mdi:flower-pollen"
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: ParticleManCoordinator, pcode: str) -> None:
        super().__init__(coordinator)
        self.pcode = pcode
        self._attr_unique_id = f"{coordinator.entry_id}_{coordinator.location_slug}_pollen_plant_{pcode}"

    @property
    def _info(self) -> dict[str, Any]:
        return cast(dict[str, Any], self.coordinator.data.get(f"pollen_plant_{self.pcode}", {}))

    @property
    def name(self) -> str:
        return f"{self._info.get('display_name') or self.pcode.title()} Pollen"

    @property
    def native_value(self) -> int | None:
        val = self._info.get("value")
        return int(val) if isinstance(val, (int, float)) else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        info = self._info
        attrs: dict[str, Any] = {
            "category": info.get("category"),
            "in_season": info.get("in_season"),
            "color_hex": info.get("color_hex"),
            "trend": info.get("trend"),
            "expected_peak": info.get("expected_peak"),
            "daily_forecast": info.get("forecast", []),
            ATTR_ATTRIBUTION: POLLEN_ATTRIBUTION,
        }
        for k in ("family", "genus", "season", "cross_reaction", "picture"):
            if info.get(k) is not None:
                attrs[k] = info[k]
        return attrs


# ---------------------------------------------------------------------------
# Weather sensors
# ---------------------------------------------------------------------------

_SEVERITY_ORDER: dict[str, int] = {"MINOR": 1, "MODERATE": 2, "SEVERE": 3, "EXTREME": 4}


class WeatherAlertCountSensor(_BaseWeatherSensor):
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_translation_key = "weather_alert_count"

    def __init__(self, coordinator: ParticleManCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry_id}_{coordinator.location_slug}_weather_alert_count"

    @property
    def native_value(self) -> int:
        alerts = self.coordinator.data.get("weather_alerts", [])
        return len(alerts) if isinstance(alerts, list) else 0

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        alerts = self.coordinator.data.get("weather_alerts", [])
        severities = [a.get("severity", "") for a in alerts if a.get("severity")]
        highest = max(severities, key=lambda s: _SEVERITY_ORDER.get(s, 0), default=None) if severities else None
        return {
            "alerts": alerts,
            "highest_severity": highest,
            "active_event_types": sorted({a.get("event_type") for a in alerts if a.get("event_type")}),
            ATTR_ATTRIBUTION: WEATHER_ATTRIBUTION,
        }


class WeatherAlertSeveritySensor(_BaseWeatherSensor):
    _attr_translation_key = "weather_alert_highest_severity"

    def __init__(self, coordinator: ParticleManCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry_id}_{coordinator.location_slug}_weather_alert_highest_severity"

    @property
    def native_value(self) -> str | None:
        alerts = self.coordinator.data.get("weather_alerts", [])
        if not isinstance(alerts, list) or not alerts:
            return None
        severities = [a.get("severity") for a in alerts if a.get("severity")]
        return max(severities, key=lambda s: _SEVERITY_ORDER.get(s, 0)) if severities else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {ATTR_ATTRIBUTION: WEATHER_ATTRIBUTION}


class WeatherAlertEventTypesSensor(_BaseWeatherSensor):
    _attr_translation_key = "weather_alert_active_event_types"

    def __init__(self, coordinator: ParticleManCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry_id}_{coordinator.location_slug}_weather_alert_active_event_types"

    @property
    def native_value(self) -> str | None:
        alerts = self.coordinator.data.get("weather_alerts", [])
        if not isinstance(alerts, list) or not alerts:
            return None
        event_types = sorted({a.get("event_type") for a in alerts if a.get("event_type")})
        return ", ".join(event_types) if event_types else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {ATTR_ATTRIBUTION: WEATHER_ATTRIBUTION}


class ThunderstormProbabilitySensor(_BaseWeatherSensor):
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_translation_key = "thunderstorm_probability"

    def __init__(self, coordinator: ParticleManCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry_id}_{coordinator.location_slug}_thunderstorm_probability"

    @property
    def native_value(self) -> int | None:
        val = self.coordinator.data.get("weather_current", {}).get("thunderstorm_probability")
        return int(val) if isinstance(val, (int, float)) else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {ATTR_ATTRIBUTION: WEATHER_ATTRIBUTION}


class HeatIndexSensor(_BaseWeatherSensor):
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_translation_key = "heat_index"

    def __init__(self, coordinator: ParticleManCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry_id}_{coordinator.location_slug}_heat_index"

    @property
    def native_value(self) -> float | None:
        val = self.coordinator.data.get("weather_current", {}).get("heat_index")
        return float(val) if isinstance(val, (int, float)) else None

    @property
    def native_unit_of_measurement(self) -> str:
        return (
            UnitOfTemperature.CELSIUS
            if self.coordinator.weather_units == "METRIC"
            else UnitOfTemperature.FAHRENHEIT
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {ATTR_ATTRIBUTION: WEATHER_ATTRIBUTION}


def _uv_category(uv_index: float | None) -> str | None:
    if uv_index is None:
        return None
    if uv_index <= 2:
        return "Low"
    if uv_index <= 5:
        return "Moderate"
    if uv_index <= 7:
        return "High"
    if uv_index <= 10:
        return "Very High"
    return "Extreme"


class WindChillSensor(_BaseWeatherSensor):
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_translation_key = "wind_chill"

    def __init__(self, coordinator: ParticleManCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry_id}_{coordinator.location_slug}_wind_chill"

    @property
    def native_value(self) -> float | None:
        val = self.coordinator.data.get("weather_current", {}).get("wind_chill")
        return float(val) if isinstance(val, (int, float)) else None

    @property
    def native_unit_of_measurement(self) -> str:
        return (
            UnitOfTemperature.CELSIUS
            if self.coordinator.weather_units == "METRIC"
            else UnitOfTemperature.FAHRENHEIT
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {ATTR_ATTRIBUTION: WEATHER_ATTRIBUTION}


class UvIndexCategorySensor(_BaseWeatherSensor):
    _attr_translation_key = "uv_index_category"

    def __init__(self, coordinator: ParticleManCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry_id}_{coordinator.location_slug}_uv_index_category"

    @property
    def native_value(self) -> str | None:
        val = self.coordinator.data.get("weather_current", {}).get("uv_index")
        return _uv_category(float(val) if isinstance(val, (int, float)) else None)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        val = self.coordinator.data.get("weather_current", {}).get("uv_index")
        return {
            "uv_index": val,
            ATTR_ATTRIBUTION: WEATHER_ATTRIBUTION,
        }


# ---------------------------------------------------------------------------
# Diagnostic sensors (shared per entry)
# ---------------------------------------------------------------------------

class LastApiUpdateSensor(_BaseDiagnosticSensor):
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "last_api_update"

    def __init__(self, coordinator: ParticleManCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry_id}_last_api_update"

    @property
    def native_value(self) -> _datetime | None:
        dt_str = self.coordinator.data.get("aqi", {}).get("datetime")
        if not dt_str:
            dt_str = self.coordinator.data.get("weather_current", {}).get("datetime")
        if not dt_str:
            return None
        try:
            return _datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return None


def _billing_projection_attrs(calls: int, limit: int, period_month: str) -> dict[str, Any]:
    """Compute billing projection from Pacific Time monthly period."""
    try:
        year = int(period_month[:4])
        month = int(period_month[5:7])
        period_start = _date(year, month, 1)
        today_pacific = _datetime.now(_PACIFIC_TZ).date()
        days_elapsed = max(1, (today_pacific - period_start).days + 1)
        days_in_month = _calendar.monthrange(year, month)[1]
        days_remaining = max(0, days_in_month - days_elapsed)
        projected = round(calls * days_in_month / days_elapsed)
        calls_per_day = round(calls / days_elapsed, 1)
        pct_used = round(calls / limit * 100, 1) if limit > 0 else 0.0
        pct_projected = round(projected / limit * 100, 1) if limit > 0 else 0.0
        if pct_projected >= 95:
            status = "critical"
        elif pct_projected >= 80:
            status = "warning"
        else:
            status = "ok"
    except (ValueError, TypeError, ZeroDivisionError):
        projected = 0
        calls_per_day = 0.0
        days_remaining = 0
        pct_used = 0.0
        pct_projected = 0.0
        status = "ok"
    return {
        "monthly_limit": limit,
        "projected_monthly": projected,
        "pct_of_limit": pct_used,
        "pct_projected": pct_projected,
        "status": status,
        "billing_period": period_month,
        "days_remaining": days_remaining,
        "calls_per_day": calls_per_day,
    }


def _automagic_assumption_attrs(
    coordinator: ParticleManCoordinator,
    calls_per_poll: int,
    fetch_interval_minutes: int,
) -> dict[str, Any]:
    """Return the assumptions behind a monthly usage projection for a given API."""
    c = coordinator
    quiet_on = c._quiet_hours_enabled
    days = _billing_month_days()
    if quiet_on:
        eff_min = _quiet_active_minutes_per_month(c._quiet_start, c._quiet_end)
        active_hours = round(eff_min / days / 60, 1)
        window = f"{c._quiet_start[:5]}–{c._quiet_end[:5]}"
    else:
        eff_min = days * 24 * 60
        active_hours = 24.0
        window = None
    return {
        "automagic_mode": c.automagic_mode,
        "num_locations": c.num_locations,
        "calls_per_poll": calls_per_poll,
        "fetch_interval_minutes": fetch_interval_minutes,
        "quiet_hours_enabled": quiet_on,
        "quiet_hours_window": window,
        "active_hours_per_day": active_hours,
        "billing_month_days": days,
        "effective_minutes_per_month": eff_min,
        "safety_buffer_pct": 5,
    }


class MonthlyAqUsageSensor(_BaseDiagnosticSensor):
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_native_unit_of_measurement = "calls"
    _attr_translation_key = "monthly_aq_calls"

    def __init__(self, coordinator: ParticleManCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry_id}_monthly_aq_calls"

    @property
    def native_value(self) -> int:
        return int(self.coordinator._cached_tracking.get("aq_calls", 0))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        c = self.coordinator
        tracking = c._cached_tracking
        attrs = _billing_projection_attrs(
            tracking.get("aq_calls", 0),
            c.aq_monthly_limit,
            tracking.get("period_month", ""),
        )
        attrs["shared_total_calls"] = tracking.get("aq_calls", 0)
        attrs["num_locations"] = c.num_locations
        attrs.update(_automagic_assumption_attrs(
            c, _AQ_CALLS_PER_POLL,
            int(c._aq_fetch_interval.total_seconds() // 60),
        ))
        attrs[ATTR_ATTRIBUTION] = ATTRIBUTION
        return attrs


class MonthlyPollenUsageSensor(_BaseDiagnosticSensor):
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_native_unit_of_measurement = "calls"
    _attr_translation_key = "monthly_pollen_calls"

    def __init__(self, coordinator: ParticleManCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry_id}_monthly_pollen_calls"

    @property
    def native_value(self) -> int:
        return int(self.coordinator._cached_tracking.get("pollen_calls", 0))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        c = self.coordinator
        tracking = c._cached_tracking
        attrs = _billing_projection_attrs(
            tracking.get("pollen_calls", 0),
            c.pollen_monthly_limit,
            tracking.get("period_month", ""),
        )
        attrs["shared_total_calls"] = tracking.get("pollen_calls", 0)
        attrs["num_locations"] = c.num_locations
        attrs.update(_automagic_assumption_attrs(
            c, _POLLEN_CALLS_PER_POLL,
            int(c._pollen_fetch_interval.total_seconds() // 60),
        ))
        attrs[ATTR_ATTRIBUTION] = POLLEN_ATTRIBUTION
        return attrs


class MonthlyWeatherUsageSensor(_BaseDiagnosticSensor):
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_native_unit_of_measurement = "calls"
    _attr_translation_key = "monthly_weather_calls"

    def __init__(self, coordinator: ParticleManCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry_id}_monthly_weather_calls"

    @property
    def native_value(self) -> int:
        return int(self.coordinator._cached_tracking.get("weather_calls", 0))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        c = self.coordinator
        tracking = c._cached_tracking
        attrs = _billing_projection_attrs(
            tracking.get("weather_calls", 0),
            c.weather_monthly_limit,
            tracking.get("period_month", ""),
        )
        attrs["shared_total_calls"] = tracking.get("weather_calls", 0)
        attrs["num_locations"] = c.num_locations
        weather_interval_min = int(c.update_interval.total_seconds() // 60) if c.update_interval else 0
        attrs.update(_automagic_assumption_attrs(
            c, c.weather_calls_per_poll, weather_interval_min,
        ))
        attrs[ATTR_ATTRIBUTION] = WEATHER_ATTRIBUTION
        return attrs
