"""Shared entity base."""

from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SondeHubCoordinator


def sonde_attrs(info: dict[str, Any] | None, at_landing: bool = False) -> dict[str, Any]:
    """Attributes describing one sonde (and its landing, if known).

    Maps place an entity at its latitude/longitude attributes. With
    ``at_landing`` they point at the predicted landing spot instead of the
    sonde, whose position stays available as sonde_latitude/sonde_longitude.
    """
    if not info:
        return {}
    landing = info.get("landing") or {}
    attrs = {
        "serial": info["serial"],
        "sonde_type": info["type"],
        "frequency_mhz": info["frequency"],
        "latitude": info["latitude"],
        "longitude": info["longitude"],
        "altitude_m": info["altitude"],
        "vertical_speed_ms": info["vel_v"],
        "descending": info["descending"],
        "distance_km": info["distance_km"],
        "bearing": info["bearing"],
        "last_frame": info["datetime"],
        "landing_latitude": landing.get("latitude"),
        "landing_longitude": landing.get("longitude"),
        "landing_distance_km": landing.get("distance_km"),
        "landing_bearing": landing.get("bearing"),
        "landing_time": landing.get("time"),
        "landed": landing.get("landed"),
    }
    if at_landing and landing:
        attrs["sonde_latitude"] = attrs["latitude"]
        attrs["sonde_longitude"] = attrs["longitude"]
        attrs["latitude"] = landing["latitude"]
        attrs["longitude"] = landing["longitude"]
    return attrs


class SondeHubEntity(CoordinatorEntity[SondeHubCoordinator]):
    _attr_has_entity_name = True

    def __init__(self, coordinator: SondeHubCoordinator, key: str) -> None:
        super().__init__(coordinator)
        entry = coordinator.config_entry
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_translation_key = key
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="SondeHub",
            entry_type=DeviceEntryType.SERVICE,
        )


class SondeHubControlEntity(SondeHubEntity):
    """Controls stay usable while the API is failing, e.g. to retry or slow down."""

    @property
    def available(self) -> bool:
        return True
