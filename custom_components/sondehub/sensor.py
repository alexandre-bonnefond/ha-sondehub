"""Sensors."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import UnitOfLength
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import SondeHubConfigEntry, SondeHubCoordinator
from .entity import SondeHubEntity, sonde_attrs


async def async_setup_entry(
    hass: HomeAssistant, entry: SondeHubConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    c = entry.runtime_data
    async_add_entities(
        [
            NearestSondeDistance(c),
            NearestLandingDistance(c),
            SondesInRange(c),
        ]
    )


class NearestSondeDistance(SondeHubEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.DISTANCE
    _attr_native_unit_of_measurement = UnitOfLength.KILOMETERS
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: SondeHubCoordinator) -> None:
        super().__init__(coordinator, "nearest_sonde_distance")

    @property
    def native_value(self) -> float | None:
        s = self.coordinator.data["nearest"]
        return self.coordinator.data["sondes"][s]["distance_km"] if s else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        s = self.coordinator.data["nearest"]
        return sonde_attrs(self.coordinator.data["sondes"].get(s)) if s else {}


class NearestLandingDistance(SondeHubEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.DISTANCE
    _attr_native_unit_of_measurement = UnitOfLength.KILOMETERS
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: SondeHubCoordinator) -> None:
        super().__init__(coordinator, "nearest_landing_distance")

    @property
    def native_value(self) -> float | None:
        s = self.coordinator.data["nearest_landing"]
        if not s:
            return None
        return self.coordinator.data["sondes"][s]["landing"]["distance_km"]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        s = self.coordinator.data["nearest_landing"]
        return sonde_attrs(self.coordinator.data["sondes"].get(s)) if s else {}


class SondesInRange(SondeHubEntity, SensorEntity):
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: SondeHubCoordinator) -> None:
        super().__init__(coordinator, "sondes_in_range")

    @property
    def native_value(self) -> int:
        return len(self.coordinator.data["in_flight_radius"])

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"serials": self.coordinator.data["in_flight_radius"]}
