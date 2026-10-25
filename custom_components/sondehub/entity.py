"""Shared entity base."""

from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SondeHubCoordinator


def sonde_attrs(info: dict[str, Any] | None) -> dict[str, Any]:
    """Attributes describing one sonde (and its landing, if known)."""
    if not info:
        return {}
    landing = info.get("landing") or {}
    return {
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
