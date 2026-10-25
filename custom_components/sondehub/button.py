"""Buttons."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import SondeHubConfigEntry, SondeHubCoordinator
from .entity import SondeHubControlEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: SondeHubConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities([CheckNowButton(entry.runtime_data)])


class CheckNowButton(SondeHubControlEntity, ButtonEntity):
    """Poll SondeHub immediately, including landing predictions."""

    def __init__(self, coordinator: SondeHubCoordinator) -> None:
        super().__init__(coordinator, "check_now")

    async def async_press(self) -> None:
        await self.coordinator.async_check_now()
