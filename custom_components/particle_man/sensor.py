"""Particle Man sensors."""
from __future__ import annotations

import calendar as _calendar
import logging
from datetime import date as _date
from datetime import datetime as _datetime
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ATTRIBUTION, PERCENTAGE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTRIBUTION,
    CONF_API_KEY,
    DOMAIN,
    EPA_BREAKPOINT_POLLUTANTS,
    EPA_COLORS,
    POLLEN_ATTRIBUTION,
    POLLEN_COLORS,
    WEATHER_ATTRIBUTION,
    _PACIFIC_TZ,
)
from .coordinator import ParticleManCoordinator

_LOGGER = logging.getLogger(__name__)

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


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up all sensors from config entry."""
    coordinator: ParticleManCoordinator = entry.runtime_data
    data = coordinator.data or {}
    entities: list[SensorEntity] = [LastApiUpdateSensor(coordinator)]

    # --- Air Quality ---
    if coordinator.enable_air_quality:
        entities.extend([
            AqiSensor(coordinator),
            AqiLevelSensor(coordinator),
            AirQualityAdvisorySensor(coordinator),
            MonthlyAqUsageSensor(coordinator),
        ])
        if "local_aqi" in data:
            entities.append(LocalAqiSensor(coordinator))
        for key in data:
            if key.startswith("pollutant_"):
                code = key[len("pollutant_"):]
                entities.append(PollutantSensor(coordinator, code))
                if code in EPA_BREAKPOINT_POLLUTANTS:
                    entities.append(PollutantLevelSensor(coordinator, code))

    # --- Pollen ---
    if coordinator.enable_pollen:
        entities.extend([
            PollenAdvisorySensor(coordinator),
            MonthlyPollenUsageSensor(coordinator),
        ])
        for key in data:
            if key.startswith("pollen_type_"):
                ptype = key[len("pollen_type_"):]
                entities.append(PollenTypeSensor(coordinator, ptype))
                entities.append(PollenTypeLevelSensor(coordinator, ptype))
            elif key.startswith("pollen_plant_"):
                pcode = key[len("pollen_plant_"):]
                entities.append(PollenPlantSensor(coordinator, pcode))

    # --- Weather ---
    if coordinator.enable_weather:
        entities.append(MonthlyWeatherUsageSensor(coordinator))
        if "weather_current" in data:
            entities.extend([
                ThunderstormProbabilitySensor(coordinator),
                HeatIndexSensor(coordinator),
                WindChillSensor(coordinator),
            ])
        if coordinator.enable_weather_alerts:
            entities.append(WeatherAlertsSensor(coordinator))

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
            identifiers={(DOMAIN, self.coordinator.entry_id)},
            name="Particle Man Pollution",
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
            identifiers={(DOMAIN, f"{self.coordinator.entry_id}_pollen")},
            name="Particle Man Pollen",
            manufacturer="Google",
            model="Pollen API",
            via_device=(DOMAIN, self.coordinator.entry_id),
        )


class _BaseWeatherSensor(CoordinatorEntity[ParticleManCoordinator], SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator: ParticleManCoordinator) -> None:
        super().__init__(coordinator)
        self.coordinator = coordinator

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self.coordinator.entry_id}_weather")},
            name="Particle Man Weather",
            manufacturer="Google",
            model="Weather API",
            via_device=(DOMAIN, self.coordinator.entry_id),
        )


class _BaseDiagnosticSensor(CoordinatorEntity[ParticleManCoordinator], SensorEntity):
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
            model="Air Quality API",
            via_device=(DOMAIN, self.coordinator.entry_id),
        )


# ---------------------------------------------------------------------------
# Air Quality sensors
# ---------------------------------------------------------------------------

class AqiSensor(_BaseGaqSensor):
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:air-filter"
    _unrecorded_attributes = frozenset({"hourly_forecast"})

    def __init__(self, coordinator: ParticleManCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry_id}_aqi"

    @property
    def name(self) -> str:
        return "Universal AQI"

    @property
    def native_value(self) -> int | None:
        return self.coordinator.data.get("aqi", {}).get("value")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        info = self.coordinator.data.get("aqi", {})
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
    _attr_icon = "mdi:air-filter"

    def __init__(self, coordinator: ParticleManCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry_id}_aqi_level"

    @property
    def name(self) -> str:
        return "Universal AQI Level"

    @property
    def native_value(self) -> str | None:
        return self.coordinator.data.get("aqi", {}).get("category")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        info = self.coordinator.data.get("aqi", {})
        return {
            "aqi": info.get("value"),
            "dominant_pollutant": info.get("dominant_pollutant"),
            ATTR_ATTRIBUTION: ATTRIBUTION,
        }


class AirQualityAdvisorySensor(_BaseGaqSensor):
    _attr_icon = "mdi:shield-alert-outline"

    def __init__(self, coordinator: ParticleManCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry_id}_aq_advisory"

    @property
    def name(self) -> str:
        return "Air Quality Advisory"

    @property
    def native_value(self) -> str | None:
        return self.coordinator.data.get("aq_advisory", {}).get("value")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        info = self.coordinator.data.get("aq_advisory", {})
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
    _attr_icon = "mdi:air-filter"
    _unrecorded_attributes = frozenset({"hourly_forecast"})

    def __init__(self, coordinator: ParticleManCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry_id}_local_aqi"

    @property
    def _info(self) -> dict:
        return self.coordinator.data.get("local_aqi", {})

    @property
    def name(self) -> str:
        return self._info.get("display_name") or "Local AQI"

    @property
    def native_value(self) -> int | None:
        return self._info.get("value")

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
        self._attr_unique_id = f"{coordinator.entry_id}_pollutant_{code}"

    @property
    def _info(self) -> dict:
        return self.coordinator.data.get(f"pollutant_{self.code}", {})

    @property
    def name(self) -> str:
        return self._info.get("display_name", self.code.upper())

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

    def __init__(self, coordinator: ParticleManCoordinator, code: str) -> None:
        super().__init__(coordinator)
        self.code = code
        self._attr_unique_id = f"{coordinator.entry_id}_pollutant_{code}_level"

    @property
    def _info(self) -> dict:
        return self.coordinator.data.get(f"pollutant_{self.code}", {})

    @property
    def name(self) -> str:
        return f"{self._info.get('display_name', self.code.upper())} Level"

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
    _attr_icon = "mdi:flower-pollen"

    def __init__(self, coordinator: ParticleManCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry_id}_pollen_advisory"

    @property
    def name(self) -> str:
        return "Pollen Advisory"

    @property
    def native_value(self) -> str | None:
        return self.coordinator.data.get("pollen_advisory", {}).get("value")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        info = self.coordinator.data.get("pollen_advisory", {})
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
        self._attr_unique_id = f"{coordinator.entry_id}_pollen_type_{ptype}"

    @property
    def _info(self) -> dict:
        return self.coordinator.data.get(f"pollen_type_{self.ptype}", {})

    @property
    def name(self) -> str:
        return f"{self._info.get('display_name', self.ptype.title())} Pollen"

    @property
    def native_value(self) -> int | None:
        return self._info.get("value")

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

    def __init__(self, coordinator: ParticleManCoordinator, ptype: str) -> None:
        super().__init__(coordinator)
        self.ptype = ptype
        self._attr_unique_id = f"{coordinator.entry_id}_pollen_type_{ptype}_level"

    @property
    def _info(self) -> dict:
        return self.coordinator.data.get(f"pollen_type_{self.ptype}", {})

    @property
    def name(self) -> str:
        return f"{self._info.get('display_name', self.ptype.title())} Pollen Level"

    @property
    def native_value(self) -> str | None:
        return self._info.get("category")

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

    def __init__(self, coordinator: ParticleManCoordinator, pcode: str) -> None:
        super().__init__(coordinator)
        self.pcode = pcode
        self._attr_unique_id = f"{coordinator.entry_id}_pollen_plant_{pcode}"

    @property
    def _info(self) -> dict:
        return self.coordinator.data.get(f"pollen_plant_{self.pcode}", {})

    @property
    def name(self) -> str:
        return f"{self._info.get('display_name', self.pcode.title())} Pollen"

    @property
    def native_value(self) -> int | None:
        return self._info.get("value")

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

class WeatherAlertsSensor(_BaseWeatherSensor):
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:alert-circle-outline"

    def __init__(self, coordinator: ParticleManCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry_id}_weather_alerts"

    @property
    def name(self) -> str:
        return "Weather Alerts"

    @property
    def native_value(self) -> int:
        return len(self.coordinator.data.get("weather_alerts", []))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        alerts = self.coordinator.data.get("weather_alerts", [])
        severities = [a.get("severity", "") for a in alerts if a.get("severity")]
        _order = {"MINOR": 1, "MODERATE": 2, "SEVERE": 3, "EXTREME": 4}
        highest = max(severities, key=lambda s: _order.get(s, 0), default=None) if severities else None
        return {
            "alerts": alerts,
            "highest_severity": highest,
            "active_event_types": list({a.get("event_type") for a in alerts if a.get("event_type")}),
            ATTR_ATTRIBUTION: WEATHER_ATTRIBUTION,
        }


class ThunderstormProbabilitySensor(_BaseWeatherSensor):
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_icon = "mdi:weather-lightning"

    def __init__(self, coordinator: ParticleManCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry_id}_thunderstorm_probability"

    @property
    def name(self) -> str:
        return "Thunderstorm Probability"

    @property
    def native_value(self) -> int | None:
        return self.coordinator.data.get("weather_current", {}).get("thunderstorm_probability")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {ATTR_ATTRIBUTION: WEATHER_ATTRIBUTION}


class HeatIndexSensor(_BaseWeatherSensor):
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_device_class = SensorDeviceClass.TEMPERATURE

    def __init__(self, coordinator: ParticleManCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry_id}_heat_index"

    @property
    def name(self) -> str:
        return "Heat Index"

    @property
    def native_value(self) -> float | None:
        return self.coordinator.data.get("weather_current", {}).get("heat_index")

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


class WindChillSensor(_BaseWeatherSensor):
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_device_class = SensorDeviceClass.TEMPERATURE

    def __init__(self, coordinator: ParticleManCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry_id}_wind_chill"

    @property
    def name(self) -> str:
        return "Wind Chill"

    @property
    def native_value(self) -> float | None:
        return self.coordinator.data.get("weather_current", {}).get("wind_chill")

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


# ---------------------------------------------------------------------------
# Diagnostic sensors
# ---------------------------------------------------------------------------

class LastApiUpdateSensor(_BaseDiagnosticSensor):
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:clock-check-outline"

    def __init__(self, coordinator: ParticleManCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry_id}_last_api_update"

    @property
    def name(self) -> str:
        return "Last API Update"

    @property
    def native_value(self) -> _datetime | None:
        dt_str = self.coordinator.data.get("aqi", {}).get("datetime")
        if not dt_str:
            # Fall back to weather timestamp if AQ not enabled
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
        projected = round(calls * days_in_month / days_elapsed)
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
    }


def _locations_sharing_key(coordinator: ParticleManCoordinator) -> int:
    """Count config entries using the same API key."""
    return sum(
        1 for e in coordinator.hass.config_entries.async_entries(DOMAIN)
        if e.data.get(CONF_API_KEY) == coordinator.api_key
    )


class MonthlyAqUsageSensor(_BaseDiagnosticSensor):
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:api"
    _attr_native_unit_of_measurement = "calls"

    def __init__(self, coordinator: ParticleManCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry_id}_monthly_aq_calls"

    @property
    def name(self) -> str:
        return "AQ API Calls (Monthly)"

    @property
    def native_value(self) -> int:
        return self.coordinator._cached_tracking.get("aq_calls", 0)

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
        attrs["locations_sharing_key"] = _locations_sharing_key(c)
        attrs[ATTR_ATTRIBUTION] = ATTRIBUTION
        return attrs


class MonthlyPollenUsageSensor(_BaseDiagnosticSensor):
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:flower-pollen-outline"
    _attr_native_unit_of_measurement = "calls"

    def __init__(self, coordinator: ParticleManCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry_id}_monthly_pollen_calls"

    @property
    def name(self) -> str:
        return "Pollen API Calls (Monthly)"

    @property
    def native_value(self) -> int:
        return self.coordinator._cached_tracking.get("pollen_calls", 0)

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
        attrs["locations_sharing_key"] = _locations_sharing_key(c)
        attrs[ATTR_ATTRIBUTION] = POLLEN_ATTRIBUTION
        return attrs


class MonthlyWeatherUsageSensor(_BaseDiagnosticSensor):
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:weather-partly-cloudy"
    _attr_native_unit_of_measurement = "calls"

    def __init__(self, coordinator: ParticleManCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry_id}_monthly_weather_calls"

    @property
    def name(self) -> str:
        return "Weather API Calls (Monthly)"

    @property
    def native_value(self) -> int:
        return self.coordinator._cached_tracking.get("weather_calls", 0)

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
        attrs["locations_sharing_key"] = _locations_sharing_key(c)
        attrs[ATTR_ATTRIBUTION] = WEATHER_ATTRIBUTION
        return attrs
