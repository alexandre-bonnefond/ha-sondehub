"""Number entities: request frequency, adjustable from dashboards and automations."""

from __future__ import annotations

from homeassistant.components.number import NumberDeviceClass, NumberEntity, NumberMode
from homeassistant.const import EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_PREDICTION_INTERVAL,
    CONF_SCAN_INTERVAL,
    INTERVAL_STEP,
    MAX_INTERVAL,
    MIN_INTERVAL,
)
from .coordinator import SondeHubConfigEntry, SondeHubCoordinator
from .entity import SondeHubControlEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: SondeHubConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    c = entry.runtime_data
    async_add_entities(
        [
            IntervalNumber(c, "update_interval", CONF_SCAN_INTERVAL),
            IntervalNumber(c, "prediction_interval", CONF_PREDICTION_INTERVAL),
        ]
    )


class IntervalNumber(SondeHubControlEntity, NumberEntity):
    """Seconds between two requests to one SondeHub endpoint.

    The value is stored in the entry options, so it is the same setting as in
    the integration's "Configure" dialog and survives restarts.
    """

    _attr_entity_category = EntityCategory.CONFIG
    _attr_device_class = NumberDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS
    _attr_mode = NumberMode.BOX
    _attr_native_min_value = MIN_INTERVAL
    _attr_native_max_value = MAX_INTERVAL
    _attr_native_step = INTERVAL_STEP

    def __init__(self, coordinator: SondeHubCoordinator, key: str, option: str) -> None:
        super().__init__(coordinator, key)
        self._option = option

    @property
    def native_value(self) -> int:
        if self._option == CONF_SCAN_INTERVAL:
            return self.coordinator.scan_interval
        return self.coordinator.prediction_interval

    async def async_set_native_value(self, value: float) -> None:
        entry = self.coordinator.config_entry
        self.hass.config_entries.async_update_entry(
            entry, options={**entry.options, self._option: int(value)}
        )
