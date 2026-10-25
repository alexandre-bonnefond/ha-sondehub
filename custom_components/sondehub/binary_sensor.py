"""Binary sensors."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity
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
            RadiusBinarySensor(c, "sonde_nearby", "in_flight_radius"),
            RadiusBinarySensor(c, "landing_nearby", "in_landing_radius"),
        ]
    )


class RadiusBinarySensor(SondeHubEntity, BinarySensorEntity):
    """ON while at least one sonde is inside the relevant radius."""

    def __init__(self, coordinator: SondeHubCoordinator, key: str, data_key: str) -> None:
        super().__init__(coordinator, key)
        self._data_key = data_key

    @property
    def is_on(self) -> bool:
        return bool(self.coordinator.data[self._data_key])

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        serials = self.coordinator.data[self._data_key]
        attrs: dict[str, Any] = {"serials": serials}
        if serials:
            attrs.update(
                sonde_attrs(
                    self.coordinator.data["sondes"][serials[0]],
                    at_landing=self._data_key == "in_landing_radius",
                )
            )
        return attrs
