"""Data coordinator: polls SondeHub, computes distances, fires events."""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import SondeHubClient, SondeHubError, parse_telemetry
from .const import (
    CONF_FLIGHT_RADIUS,
    CONF_LANDING_RADIUS,
    CONF_SCAN_INTERVAL,
    CONF_WATCH_RADIUS,
    DEFAULT_FLIGHT_RADIUS,
    DEFAULT_LANDING_RADIUS,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_WATCH_RADIUS,
    DESCENT_THRESHOLD,
    DOMAIN,
    EVENT_LANDING_NEARBY,
    EVENT_SONDE_NEARBY,
    LAST_SECONDS,
    NOTIFIED_TTL,
    PREDICTION_TTL,
)
from .util import bearing_deg, haversine_km

_LOGGER = logging.getLogger(__name__)

type SondeHubConfigEntry = ConfigEntry[SondeHubCoordinator]


class SondeHubCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Fetch sondes around the configured location."""

    config_entry: SondeHubConfigEntry

    def __init__(self, hass: HomeAssistant, entry: SondeHubConfigEntry) -> None:
        cfg = {**entry.data, **entry.options}
        self.lat: float = float(cfg[CONF_LATITUDE])
        self.lon: float = float(cfg[CONF_LONGITUDE])
        self.flight_radius = float(cfg.get(CONF_FLIGHT_RADIUS, DEFAULT_FLIGHT_RADIUS))
        self.landing_radius = float(cfg.get(CONF_LANDING_RADIUS, DEFAULT_LANDING_RADIUS))
        self.watch_radius = max(
            float(cfg.get(CONF_WATCH_RADIUS, DEFAULT_WATCH_RADIUS)),
            self.flight_radius,
        )
        interval = int(cfg.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL))
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            config_entry=entry,
            update_interval=timedelta(seconds=interval),
        )
        self.client = SondeHubClient(async_get_clientsession(hass))
        self._landing_cache: dict[str, tuple[float, dict[str, Any] | None]] = {}
        self._store: Store[dict[str, dict[str, float]]] = Store(
            hass, 1, f"{DOMAIN}_{entry.entry_id}"
        )
        self._notified: dict[str, dict[str, float]] = {"flight": {}, "landing": {}}

    async def async_setup(self) -> None:
        """Load the persisted list of already-notified sondes."""
        stored = await self._store.async_load()
        if stored:
            self._notified = {
                "flight": stored.get("flight", {}),
                "landing": stored.get("landing", {}),
            }

    # ------------------------------------------------------------------ #

    async def _landing_for(self, serial: str) -> dict[str, Any] | None:
        now = time.monotonic()
        cached = self._landing_cache.get(serial)
        if cached and now - cached[0] < PREDICTION_TTL:
            return cached[1]
        try:
            landing = await self.client.async_get_landing(serial)
        except SondeHubError as err:
            _LOGGER.debug("No prediction for %s: %s", serial, err)
            return cached[1] if cached else None
        self._landing_cache[serial] = (now, landing)
        return landing

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            frames = await self.client.async_get_sondes(
                self.lat, self.lon, self.watch_radius * 1000, LAST_SECONDS
            )
        except SondeHubError as err:
            raise UpdateFailed(str(err)) from err

        sondes: dict[str, dict[str, Any]] = {}
        for frame in frames:
            info = parse_telemetry(frame)
            if info is None:
                continue
            info["distance_km"] = round(
                haversine_km(self.lat, self.lon, info["latitude"], info["longitude"]), 1
            )
            info["bearing"] = round(
                bearing_deg(self.lat, self.lon, info["latitude"], info["longitude"])
            )
            info["descending"] = (
                info["vel_v"] is not None and info["vel_v"] < DESCENT_THRESHOLD
            )
            sondes[info["serial"]] = info

        # Landing predictions (one small request per candidate sonde, cached).
        landings = await asyncio.gather(*(self._landing_for(s) for s in sondes))
        for info, landing in zip(sondes.values(), landings, strict=True):
            if landing:
                landing = dict(landing)
                landing["distance_km"] = round(
                    haversine_km(
                        self.lat, self.lon, landing["latitude"], landing["longitude"]
                    ),
                    1,
                )
                landing["bearing"] = round(
                    bearing_deg(
                        self.lat, self.lon, landing["latitude"], landing["longitude"]
                    )
                )
            info["landing"] = landing

        for serial in list(self._landing_cache):
            if serial not in sondes:
                del self._landing_cache[serial]

        in_flight = sorted(
            (s for s, i in sondes.items() if i["distance_km"] <= self.flight_radius),
            key=lambda s: sondes[s]["distance_km"],
        )
        in_landing = sorted(
            (
                s
                for s, i in sondes.items()
                if i["landing"] and i["landing"]["distance_km"] <= self.landing_radius
            ),
            key=lambda s: sondes[s]["landing"]["distance_km"],
        )

        self._fire_events(sondes, in_flight, in_landing)

        nearest = min(sondes, key=lambda s: sondes[s]["distance_km"], default=None)
        with_landing = [s for s, i in sondes.items() if i["landing"]]
        nearest_landing = min(
            with_landing, key=lambda s: sondes[s]["landing"]["distance_km"], default=None
        )
        return {
            "sondes": sondes,
            "nearest": nearest,
            "nearest_landing": nearest_landing,
            "in_flight_radius": in_flight,
            "in_landing_radius": in_landing,
        }

    # ------------------------------------------------------------------ #

    def _fire_events(
        self,
        sondes: dict[str, dict[str, Any]],
        in_flight: list[str],
        in_landing: list[str],
    ) -> None:
        now = time.time()
        for kind in self._notified:
            self._notified[kind] = {
                s: ts for s, ts in self._notified[kind].items() if now - ts < NOTIFIED_TTL
            }

        changed = False
        for serial in in_flight:
            if serial not in self._notified["flight"]:
                self._notified["flight"][serial] = now
                changed = True
                self.hass.bus.async_fire(EVENT_SONDE_NEARBY, self._event_data(sondes[serial]))
        for serial in in_landing:
            if serial not in self._notified["landing"]:
                self._notified["landing"][serial] = now
                changed = True
                self.hass.bus.async_fire(EVENT_LANDING_NEARBY, self._event_data(sondes[serial]))
        if changed:
            self._store.async_delay_save(lambda: self._notified, 1)

    @staticmethod
    def _event_data(info: dict[str, Any]) -> dict[str, Any]:
        landing = info.get("landing") or {}
        lat = landing.get("latitude", info["latitude"])
        lon = landing.get("longitude", info["longitude"])
        return {
            "serial": info["serial"],
            "type": info["type"],
            "subtype": info["subtype"],
            "frequency": info["frequency"],
            "latitude": info["latitude"],
            "longitude": info["longitude"],
            "altitude": info["altitude"],
            "vertical_speed": info["vel_v"],
            "descending": info["descending"],
            "distance_km": info["distance_km"],
            "bearing": info["bearing"],
            "landing_latitude": landing.get("latitude"),
            "landing_longitude": landing.get("longitude"),
            "landing_distance_km": landing.get("distance_km"),
            "landing_bearing": landing.get("bearing"),
            "landing_time": landing.get("time"),
            "landed": landing.get("landed", False),
            "sondehub_url": f"https://sondehub.org/{info['serial']}",
            "maps_url": f"https://www.google.com/maps?q={lat},{lon}",
        }
