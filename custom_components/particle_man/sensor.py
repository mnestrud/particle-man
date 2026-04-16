"""Particle Man sensors."""
from __future__ import annotations

import logging
from datetime import datetime as _datetime
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ATTRIBUTION
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTRIBUTION,
    DOMAIN,
    EPA_BREAKPOINT_POLLUTANTS,
    EPA_COLORS,
    POLLEN_ATTRIBUTION,
    POLLEN_COLORS,
)
from .coordinator import GoogleAirQualityCoordinator

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
    coordinator: GoogleAirQualityCoordinator = entry.runtime_data
    data = coordinator.data or {}

    entities: list[CoordinatorEntity] = [
        AqiSensor(coordinator),
        AqiLevelSensor(coordinator),
        LastApiUpdateSensor(coordinator),
        ApiCallsSensor(coordinator),
    ]

    if "local_aqi" in data:
        entities.append(LocalAqiSensor(coordinator))

    for key in data:
        if key.startswith("pollutant_"):
            code = key[len("pollutant_"):]
            entities.append(PollutantSensor(coordinator, code))
            if code in EPA_BREAKPOINT_POLLUTANTS:
                entities.append(PollutantLevelSensor(coordinator, code))
        elif key.startswith("pollen_type_"):
            ptype = key[len("pollen_type_"):]
            entities.append(PollenTypeSensor(coordinator, ptype))
            entities.append(PollenTypeLevelSensor(coordinator, ptype))
        elif key.startswith("pollen_plant_"):
            pcode = key[len("pollen_plant_"):]
            entities.append(PollenPlantSensor(coordinator, pcode))

    async_add_entities(entities, True)


class _BaseGaqSensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator: GoogleAirQualityCoordinator) -> None:
        super().__init__(coordinator)
        self.coordinator = coordinator

    @property
    def device_info(self) -> dict:
        return {
            "identifiers": {(DOMAIN, self.coordinator.entry_id)},
            "name": "Particle Man",
            "manufacturer": "Google",
            "model": "Air Quality API",
        }


class _BasePollenSensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator: GoogleAirQualityCoordinator) -> None:
        super().__init__(coordinator)
        self.coordinator = coordinator

    @property
    def device_info(self) -> dict:
        return {
            "identifiers": {(DOMAIN, f"{self.coordinator.entry_id}_pollen")},
            "name": "Particle Man Pollen",
            "manufacturer": "Google",
            "model": "Pollen API",
            "via_device": (DOMAIN, self.coordinator.entry_id),
        }


class AqiSensor(_BaseGaqSensor):
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:air-filter"

    def __init__(self, coordinator: GoogleAirQualityCoordinator) -> None:
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
            "forecast": info.get("forecast", []),
            ATTR_ATTRIBUTION: ATTRIBUTION,
        }
        if info.get("health_recommendations") is not None:
            attrs["health_recommendations"] = info["health_recommendations"]
        return attrs


class AqiLevelSensor(_BaseGaqSensor):
    _attr_entity_category = None
    _attr_icon = "mdi:air-filter"

    def __init__(self, coordinator: GoogleAirQualityCoordinator) -> None:
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


class LocalAqiSensor(_BaseGaqSensor):
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:air-filter"

    def __init__(self, coordinator: GoogleAirQualityCoordinator) -> None:
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
            "forecast": info.get("forecast", []),
            ATTR_ATTRIBUTION: ATTRIBUTION,
        }


class PollutantSensor(_BaseGaqSensor):
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: GoogleAirQualityCoordinator, code: str) -> None:
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
            "forecast": info.get("forecast", []),
            ATTR_ATTRIBUTION: ATTRIBUTION,
        }


class PollutantLevelSensor(_BaseGaqSensor):
    _attr_entity_category = None

    def __init__(self, coordinator: GoogleAirQualityCoordinator, code: str) -> None:
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


class PollenTypeSensor(_BasePollenSensor):
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 0

    def __init__(self, coordinator: GoogleAirQualityCoordinator, ptype: str) -> None:
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
            "forecast": info.get("forecast", []),
            "trend": info.get("trend"),
            "expected_peak": info.get("expected_peak"),
            ATTR_ATTRIBUTION: POLLEN_ATTRIBUTION,
        }
        if info.get("health_recommendations") is not None:
            attrs["health_recommendations"] = info["health_recommendations"]
        return attrs


class PollenTypeLevelSensor(_BasePollenSensor):
    _attr_entity_category = None

    def __init__(self, coordinator: GoogleAirQualityCoordinator, ptype: str) -> None:
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
            "color_hex": info.get("color_hex") or POLLEN_COLORS.get(category),
            ATTR_ATTRIBUTION: POLLEN_ATTRIBUTION,
        }


class PollenPlantSensor(_BasePollenSensor):
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 0
    _attr_icon = "mdi:flower-pollen"

    def __init__(self, coordinator: GoogleAirQualityCoordinator, pcode: str) -> None:
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
            "forecast": info.get("forecast", []),
            "trend": info.get("trend"),
            "expected_peak": info.get("expected_peak"),
            ATTR_ATTRIBUTION: POLLEN_ATTRIBUTION,
        }
        for k in ("family", "genus", "season", "cross_reaction", "picture"):
            if info.get(k) is not None:
                attrs[k] = info[k]
        return attrs


class LastApiUpdateSensor(_BaseGaqSensor):
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:clock-check-outline"

    def __init__(self, coordinator: GoogleAirQualityCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry_id}_last_api_update"

    @property
    def name(self) -> str:
        return "Last API Update"

    @property
    def native_value(self) -> _datetime | None:
        dt_str = self.coordinator.data.get("aqi", {}).get("datetime")
        if not dt_str:
            return None
        try:
            return _datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return None


class ApiCallsSensor(_BaseGaqSensor):
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:api"

    def __init__(self, coordinator: GoogleAirQualityCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry_id}_api_calls_session"

    @property
    def name(self) -> str:
        return "API Calls (Session)"

    @property
    def native_value(self) -> int:
        c = self.coordinator
        return c._aq_current_calls + c._aq_forecast_calls + c._pollen_calls

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        c = self.coordinator
        interval_min = c.update_interval.total_seconds() / 60
        cycles_per_day = 24 * 60 / interval_min
        aq_per_day = round((1 + c.forecast_days) * cycles_per_day)
        pollen_per_day = round(cycles_per_day)
        return {
            "aq_current_calls": c._aq_current_calls,
            "aq_forecast_calls": c._aq_forecast_calls,
            "pollen_calls": c._pollen_calls,
            "session_start": c._session_start.isoformat(),
            "update_interval_minutes": int(interval_min),
            "projected_aq_calls_per_day": aq_per_day,
            "projected_pollen_calls_per_day": pollen_per_day,
            "projected_aq_calls_per_month": aq_per_day * 30,
            "projected_pollen_calls_per_month": pollen_per_day * 30,
            "aq_free_tier_monthly": 10000,
            "pollen_free_tier_monthly": 5000,
            ATTR_ATTRIBUTION: ATTRIBUTION,
        }
