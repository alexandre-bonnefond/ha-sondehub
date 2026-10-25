"""Minimal async client for the SondeHub v2 API."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import UTC, datetime
from typing import Any

import aiohttp

from .const import API_BASE, PREDICTION_BATCH_SIZE, RATE_LIMIT_BACKOFF, USER_AGENT

_LOGGER = logging.getLogger(__name__)
HEADERS = {"User-Agent": USER_AGENT}


class SondeHubError(Exception):
    """Raised on any API/communication error."""


class SondeHubRateLimited(SondeHubError):
    """Raised when SondeHub answered 429, or while we are backing off from it."""


def _num(value: Any, default: float | None = None) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _truthy(value: Any) -> bool:
    return str(value).strip().lower() in ("1", "true", "yes")


def _norm_lon(lon: float) -> float:
    """Tawhiri uses 0..360 longitudes; HA/Sondehub use -180..180."""
    return lon - 360 if lon > 180 else lon


def _iso(ts: Any) -> str | None:
    """Unix timestamp -> ISO 8601 UTC string."""
    value = _num(ts)
    if value is None:
        return None
    return datetime.fromtimestamp(value, UTC).isoformat()


def parse_telemetry(frame: dict[str, Any]) -> dict[str, Any] | None:
    """Normalise one telemetry frame. Returns None if unusable."""
    serial = frame.get("serial")
    lat = _num(frame.get("lat"))
    lon = _num(frame.get("lon"))
    if not serial or lat is None or lon is None:
        return None
    return {
        "serial": str(serial),
        "type": frame.get("type"),
        "subtype": frame.get("subtype"),
        "frequency": _num(frame.get("frequency")),
        "latitude": lat,
        "longitude": _norm_lon(lon),
        "altitude": _num(frame.get("alt")),
        "vel_v": _num(frame.get("vel_v")),
        "vel_h": _num(frame.get("vel_h")),
        "heading": _num(frame.get("heading")),
        "datetime": frame.get("datetime"),
    }


def _last_point(raw: Any) -> tuple[float, float, str | None] | None:
    """Extract the final (lat, lon, time) of a trajectory, tolerating several shapes."""
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except ValueError:
            return None
    # Tawhiri-style: {"prediction": [{"stage": ..., "trajectory": [...]}, ...]}
    if isinstance(raw, dict) and isinstance(raw.get("prediction"), list):
        stages = raw["prediction"]
        raw = stages[-1].get("trajectory") if stages else None
    if isinstance(raw, list) and raw and isinstance(raw[-1], dict):
        point = raw[-1]
        lat = _num(point.get("lat", point.get("latitude")))
        lon = _num(point.get("lon", point.get("longitude")))
        if lat is not None and lon is not None:
            return lat, _norm_lon(lon), _iso(point.get("time"))
    return None


def parse_prediction(item: dict[str, Any]) -> dict[str, Any] | None:
    """Normalise one /predictions entry into a landing position.

    The entry's own latitude/longitude/time describe the sonde when the
    prediction was computed; the landing is the end of the trajectory.
    """
    landed = _truthy(item.get("landed"))
    point = _last_point(item.get("data"))
    if point is not None:
        lat, lon, landing_time = point
    elif landed:
        lat, lon = _num(item.get("latitude")), _num(item.get("longitude"))
        landing_time = item.get("time")
    else:
        return None
    if lat is None or lon is None:
        return None
    return {
        "latitude": lat,
        "longitude": _norm_lon(lon),
        "time": landing_time,
        "landed": landed,
    }


class SondeHubClient:
    """Thin wrapper around aiohttp."""

    def __init__(self, session: aiohttp.ClientSession) -> None:
        self._session = session
        self._blocked_until = 0.0

    async def _get(self, path: str, params: dict[str, Any]) -> Any:
        wait = self._blocked_until - time.monotonic()
        if wait > 0:
            raise SondeHubRateLimited(
                f"Rate limited by SondeHub, not calling {path} for another {wait:.0f} s"
            )
        _LOGGER.debug("GET %s %s", path, params)
        try:
            async with asyncio.timeout(20):
                async with self._session.get(
                    f"{API_BASE}{path}", params=params, headers=HEADERS
                ) as resp:
                    if resp.status == 429:
                        retry = _num(resp.headers.get("Retry-After"), RATE_LIMIT_BACKOFF)
                        self._blocked_until = time.monotonic() + retry
                        raise SondeHubRateLimited(
                            f"SondeHub rate limit hit on {path}, backing off {retry:.0f} s;"
                            " consider a longer update interval"
                        )
                    resp.raise_for_status()
                    return await resp.json(content_type=None)
        except (aiohttp.ClientError, TimeoutError, ValueError) as err:
            raise SondeHubError(f"Error calling {path}: {err}") from err

    async def async_get_sondes(
        self, lat: float, lon: float, distance_m: float, last_s: int
    ) -> list[dict[str, Any]]:
        """Return the latest raw frame of each sonde around a point."""
        data = await self._get(
            "/sondes",
            {"lat": lat, "lon": lon, "distance": int(distance_m), "last": last_s},
        )
        frames: list[dict[str, Any]] = []
        if not isinstance(data, dict):
            return frames
        for serial, value in data.items():
            if not isinstance(value, dict) or not value:
                continue
            # {serial: {datetime: frame}} (documented) or {serial: frame}
            frame = value if "lat" in value else value[max(value)]
            if isinstance(frame, dict):
                frame.setdefault("serial", serial)
                frames.append(frame)
        return frames

    async def async_get_landings(
        self, serials: list[str]
    ) -> dict[str, dict[str, Any] | None]:
        """Return the predicted (or actual) landing of several sondes.

        /predictions accepts a comma-separated list of serials, so this costs
        one request per PREDICTION_BATCH_SIZE sondes instead of one per sonde.
        """
        landings: dict[str, dict[str, Any] | None] = dict.fromkeys(serials)
        for i in range(0, len(serials), PREDICTION_BATCH_SIZE):
            batch = serials[i : i + PREDICTION_BATCH_SIZE]
            data = await self._get("/predictions", {"vehicles": ",".join(batch)})
            if not isinstance(data, list):
                continue
            for item in data:
                if isinstance(item, dict) and item.get("vehicle") in landings:
                    landings[item["vehicle"]] = parse_prediction(item)
        return landings
