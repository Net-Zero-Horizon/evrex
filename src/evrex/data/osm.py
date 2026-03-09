"""
OpenStreetMap data fetchers for EV infrastructure.

Queries the Overpass API for charging stations and road network density.
Includes automatic retry with exponential backoff for transient errors.
"""

from __future__ import annotations

import logging
import math
import time

logger = logging.getLogger(__name__)

_OVERPASS_URL = "https://overpass-api.de/api/interpreter"
_OVERPASS_HEADERS = {"User-Agent": "EVreX/1.0"}
_OVERPASS_MAX_RETRIES = 3
_OVERPASS_BACKOFF = (5, 15, 30)


def _overpass_post(query: str, timeout: int = 60) -> dict:
    """Post an Overpass query with automatic retries on transient errors.

    Retries on HTTP 429 (rate limit) and 5xx (server errors) with
    exponential backoff.
    """
    import requests

    last_exc: Exception | None = None
    for attempt in range(_OVERPASS_MAX_RETRIES):
        try:
            resp = requests.post(
                _OVERPASS_URL,
                data={"data": query},
                headers=_OVERPASS_HEADERS,
                timeout=timeout,
            )
            if resp.status_code == 429 or resp.status_code >= 500:
                wait = _OVERPASS_BACKOFF[min(attempt, len(_OVERPASS_BACKOFF) - 1)]
                logger.warning(
                    "Overpass returned %d, retrying in %ds (attempt %d/%d)",
                    resp.status_code, wait, attempt + 1, _OVERPASS_MAX_RETRIES,
                )
                time.sleep(wait)
                continue
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.ConnectionError as exc:
            last_exc = exc
            wait = _OVERPASS_BACKOFF[min(attempt, len(_OVERPASS_BACKOFF) - 1)]
            logger.warning(
                "Overpass connection error, retrying in %ds (attempt %d/%d)",
                wait, attempt + 1, _OVERPASS_MAX_RETRIES,
            )
            time.sleep(wait)
        except requests.exceptions.Timeout as exc:
            last_exc = exc
            wait = _OVERPASS_BACKOFF[min(attempt, len(_OVERPASS_BACKOFF) - 1)]
            logger.warning(
                "Overpass timeout, retrying in %ds (attempt %d/%d)",
                wait, attempt + 1, _OVERPASS_MAX_RETRIES,
            )
            time.sleep(wait)

    raise last_exc or RuntimeError("Overpass query failed after retries")


def fetch_charging_stations(
    bounds: tuple[float, float, float, float],
) -> dict:
    """Query Overpass API for EV charging stations within bounds.

    Parameters
    ----------
    bounds : tuple
        (south, west, north, east) bounding box in degrees.

    Returns
    -------
    dict
        Keys: charging_stations (int), parking_areas (int),
        station_locations (list of {lat, lon}).
    """
    south, west, north, east = bounds
    bbox = f"{south},{west},{north},{east}"

    # -- Charging stations --
    query_charging = f"""
    [out:json][timeout:30];
    (
      node["amenity"="charging_station"]({bbox});
      way["amenity"="charging_station"]({bbox});
    );
    out center;
    """
    data = _overpass_post(query_charging, timeout=45)

    stations = []
    for el in data.get("elements", []):
        lat = el.get("lat") or el.get("center", {}).get("lat")
        lon = el.get("lon") or el.get("center", {}).get("lon")
        if lat and lon:
            stations.append({"lat": lat, "lon": lon})

    # Rate limit between queries
    time.sleep(2.0)

    # -- Parking areas --
    query_parking = f"""
    [out:json][timeout:30];
    (
      node["amenity"="parking"]({bbox});
      way["amenity"="parking"]({bbox});
    );
    out count;
    """
    data2 = _overpass_post(query_parking, timeout=45)
    parking_count = len(data2.get("elements", []))
    for el in data2.get("elements", []):
        if "tags" in el and "total" in el["tags"]:
            parking_count = int(el["tags"]["total"])
            break

    return {
        "charging_stations": len(stations),
        "parking_areas": parking_count,
        "station_locations": stations,
    }


def fetch_road_density(
    bounds: tuple[float, float, float, float],
) -> dict:
    """Compute road density (km of road per km^2) within bounds.

    Parameters
    ----------
    bounds : tuple
        (south, west, north, east) bounding box in degrees.

    Returns
    -------
    dict
        Keys: road_density_km2 (float), total_road_km (float),
        road_segments (int).
    """
    south, west, north, east = bounds
    bbox = f"{south},{west},{north},{east}"

    query = f"""
    [out:json][timeout:60];
    (
      way["highway"~"motorway|trunk|primary|secondary|tertiary"]({bbox});
    );
    out count;
    """
    data = _overpass_post(query, timeout=90)

    road_count = 0
    for el in data.get("elements", []):
        if "tags" in el and "total" in el["tags"]:
            road_count = int(el["tags"]["total"])
            break

    # Estimate total road km from count (avg segment ~1.5 km)
    est_road_km = road_count * 1.5

    # Domain area in km^2
    lat_span = abs(north - south) * 111.0
    lon_span = (
        abs(east - west)
        * 111.0
        * math.cos(math.radians((south + north) / 2))
    )
    area_km2 = max(lat_span * lon_span, 0.01)

    road_density = est_road_km / area_km2

    return {
        "road_density_km2": round(road_density, 2),
        "total_road_km": round(est_road_km, 1),
        "road_segments": road_count,
    }
