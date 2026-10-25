"""Data coordinator: polls SondeHub, computes distances, fires events."""

from __future__ import annotations

import logging
import time
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import SondeHubClient, SondeHubError, parse_telemetry
from .const import (
    CHECK_NOW_COOLDOWN,
    CONF_FLIGHT_RADIUS,
    CONF_LANDING_RADIUS,
    CONF_PREDICTION_INTERVAL,
    CONF_SCAN_INTERVAL,
    CONF_WATCH_RADIUS,
    DEFAULT_FLIGHT_RADIUS,
    DEFAULT_LANDING_RADIUS,
    DEFAULT_PREDICTION_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_WATCH_RADIUS,
    DESCENT_THRESHOLD,
    DOMAIN,
    EVENT_LANDING_NEARBY,
    EVENT_SONDE_NEARBY,
    LAST_SECONDS,
    NOTIFIED_TTL,
)
from .util import bearing_deg, haversine_km

_LOGGER = logging.getLogger(__name__)

# Options that can change without reloading the config entry.
LIVE_OPTIONS = (CONF_SCAN_INTERVAL, CONF_PREDICTION_INTERVAL)

type SondeHubConfigEntry = ConfigEntry[SondeHubCoordinator]


def entry_config(entry: ConfigEntry) -> dict[str, Any]:
    """Entry data overlaid with its options."""
    return {**entry.data, **entry.options}


class SondeHubCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Fetch sondes around the configured location."""

    config_entry: SondeHubConfigEntry

    def __init__(self, hass: HomeAssistant, entry: SondeHubConfigEntry) -> None:
        cfg = entry_config(entry)
        self.lat: float = float(cfg[CONF_LATITUDE])
        self.lon: float = float(cfg[CONF_LONGITUDE])
        self.flight_radius = float(cfg.get(CONF_FLIGHT_RADIUS, DEFAULT_FLIGHT_RADIUS))
        self.landing_radius = float(cfg.get(CONF_LANDING_RADIUS, DEFAULT_LANDING_RADIUS))
        self.watch_radius = max(
            float(cfg.get(CONF_WATCH_RADIUS, DEFAULT_WATCH_RADIUS)),
            self.flight_radius,
        )
        self.prediction_interval = int(
            cfg.get(CONF_PREDICTION_INTERVAL, DEFAULT_PREDICTION_INTERVAL)
        )
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            config_entry=entry,
            update_interval=timedelta(
                seconds=int(cfg.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL))
            ),
            # "Check now" runs immediately; presses during the cooldown are
            # merged into a single extra request at the end of it.
            request_refresh_debouncer=Debouncer(
                hass, _LOGGER, cooldown=CHECK_NOW_COOLDOWN, immediate=True
            ),
        )
        self.client = SondeHubClient(async_get_clientsession(hass))
        self._landing_cache: dict[str, dict[str, Any] | None] = {}
        self._landings_fetched_at = 0.0
        self._force_landings = False
        self._reload_snapshot = self._non_live_options(entry)
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
    # Request frequency

    @property
    def scan_interval(self) -> int:
        return int(self.update_interval.total_seconds())

    @staticmethod
    def _non_live_options(entry: ConfigEntry) -> dict[str, Any]:
        return {k: v for k, v in entry_config(entry).items() if k not in LIVE_OPTIONS}

    @callback
    def async_apply_options(self) -> bool:
        """Apply changed intervals in place. Returns False if a reload is needed."""
        entry = self.config_entry
        if self._non_live_options(entry) != self._reload_snapshot:
            return False
        cfg = entry_config(entry)
        self.prediction_interval = int(
            cfg.get(CONF_PREDICTION_INTERVAL, DEFAULT_PREDICTION_INTERVAL)
        )
        scan = int(cfg.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL))
        if scan != self.scan_interval:
            self.update_interval = timedelta(seconds=scan)
            # Re-arm the pending timer so the new interval counts from now
            # instead of after the (possibly much longer) old one.
            if self._unsub_refresh:
                self._schedule_refresh()
        self.async_update_listeners()
        return True

    async def async_check_now(self) -> None:
        """Refresh positions and landing predictions right away."""
        self._force_landings = True
        await self.async_request_refresh()

    # ------------------------------------------------------------------ #

    async def _async_landings(self, serials: list[str]) -> dict[str, dict[str, Any] | None]:
        """Landing predictions, refreshed in one batched request when due."""
        if not serials:
            self._force_landings = False
            return {}
        now = time.monotonic()
        due = (
            self._force_landings
            or now - self._landings_fetched_at >= self.prediction_interval
            or any(s not in self._landing_cache for s in serials)
        )
        if due:
            try:
                fetched = await self.client.async_get_landings(serials)
            except SondeHubError as err:
                _LOGGER.debug("Landing predictions unavailable: %s", err)
            else:
                self._landing_cache = fetched
                self._landings_fetched_at = now
                self._force_landings = False
        return {s: self._landing_cache.get(s) for s in serials}

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

        landings = await self._async_landings(list(sondes))
        for serial, info in sondes.items():
            landing = landings[serial]
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
            "checked_at": dt_util.utcnow(),
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
