"""Config & options flow."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
)

from .api import SondeHubClient, SondeHubError
from .const import (
    CONF_FLIGHT_RADIUS,
    CONF_LANDING_RADIUS,
    CONF_SCAN_INTERVAL,
    CONF_WATCH_RADIUS,
    DEFAULT_FLIGHT_RADIUS,
    DEFAULT_LANDING_RADIUS,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_WATCH_RADIUS,
    DOMAIN,
)


def _km(min_: int, max_: int, step: int = 5) -> NumberSelector:
    return NumberSelector(
        NumberSelectorConfig(
            min=min_, max=max_, step=step,
            unit_of_measurement="km", mode=NumberSelectorMode.BOX,
        )
    )


def _interval() -> NumberSelector:
    return NumberSelector(
        NumberSelectorConfig(
            min=60, max=600, step=10,
            unit_of_measurement="s", mode=NumberSelectorMode.BOX,
        )
    )


def _tuning_schema(get) -> dict:
    return {
        vol.Required(CONF_FLIGHT_RADIUS, default=get(CONF_FLIGHT_RADIUS, DEFAULT_FLIGHT_RADIUS)): _km(5, 1000),
        vol.Required(CONF_LANDING_RADIUS, default=get(CONF_LANDING_RADIUS, DEFAULT_LANDING_RADIUS)): _km(1, 500),
        vol.Required(CONF_WATCH_RADIUS, default=get(CONF_WATCH_RADIUS, DEFAULT_WATCH_RADIUS)): _km(50, 1000, 10),
        vol.Required(CONF_SCAN_INTERVAL, default=get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)): _interval(),
    }


class SondeHubConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry) -> SondeHubOptionsFlow:
        return SondeHubOptionsFlow()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            lat, lon = user_input[CONF_LATITUDE], user_input[CONF_LONGITUDE]
            await self.async_set_unique_id(f"{round(lat, 3)}_{round(lon, 3)}")
            self._abort_if_unique_id_configured()
            client = SondeHubClient(async_get_clientsession(self.hass))
            try:
                await client.async_get_sondes(lat, lon, 10_000, 600)
            except SondeHubError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(title=user_input[CONF_NAME], data=user_input)

        get = (user_input or {}).get
        schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default=get(CONF_NAME, "SondeHub")): str,
                vol.Required(CONF_LATITUDE, default=get(CONF_LATITUDE, self.hass.config.latitude)): vol.Coerce(float),
                vol.Required(CONF_LONGITUDE, default=get(CONF_LONGITUDE, self.hass.config.longitude)): vol.Coerce(float),
                **_tuning_schema(get),
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)


class SondeHubOptionsFlow(OptionsFlow):
    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        entry = self.config_entry

        def get(key: str, default: Any) -> Any:
            return entry.options.get(key, entry.data.get(key, default))

        return self.async_show_form(
            step_id="init", data_schema=vol.Schema(_tuning_schema(get))
        )
