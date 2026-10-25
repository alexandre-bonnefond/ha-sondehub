"""SondeHub radiosonde tracker integration."""

from __future__ import annotations

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import SondeHubConfigEntry, SondeHubCoordinator

PLATFORMS = [Platform.BINARY_SENSOR, Platform.BUTTON, Platform.NUMBER, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: SondeHubConfigEntry) -> bool:
    coordinator = SondeHubCoordinator(hass, entry)
    await coordinator.async_setup()
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: SondeHubConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_options_updated(hass: HomeAssistant, entry: SondeHubConfigEntry) -> None:
    # Interval changes are applied live; anything else needs a reload.
    if not entry.runtime_data.async_apply_options():
        await hass.config_entries.async_reload(entry.entry_id)
