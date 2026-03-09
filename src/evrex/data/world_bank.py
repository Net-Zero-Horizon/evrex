"""
World Bank and IMF data fetchers for EV macro-economic indicators.

Fetches GDP per capita, urbanization, population, vehicle ownership (WB)
and GDP growth, inflation (IMF).
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

_WB_EV_INDICATORS = {
    "gdp_per_capita": "NY.GDP.PCAP.CD",
    "urbanization_pct": "SP.URB.TOTL.IN.ZS",
    "population": "SP.POP.TOTL",
    "vehicles_per_1000": "IS.VEH.NVEH.P3",
}

_IMF_INDICATORS = {
    "gdp_growth_rate": "NGDP_RPCH",
    "inflation_rate": "PCPIPCH",
}


def fetch_world_bank_ev_data(country_iso: str) -> dict[str, Any]:
    """Fetch EV-relevant indicators from the World Bank API.

    Parameters
    ----------
    country_iso : str
        ISO-3 country code (e.g. ``"USA"``, ``"DEU"``).

    Returns
    -------
    dict
        Keys: gdp_per_capita, urbanization_pct, population,
        vehicles_per_1000. Values may be None if unavailable.
    """
    import requests

    iso = country_iso.upper()
    results: dict[str, Any] = {}

    for key, code in _WB_EV_INDICATORS.items():
        url = (
            f"https://api.worldbank.org/v2/country/{iso}"
            f"/indicator/{code}"
            f"?format=json&per_page=30&date=2000:2025"
        )
        try:
            resp = requests.get(url, timeout=20)
            resp.raise_for_status()
            payload = resp.json()

            if (
                not isinstance(payload, list)
                or len(payload) < 2
                or payload[1] is None
            ):
                results[key] = None
                continue

            entries = payload[1]
            latest = None
            for entry in entries:
                if entry.get("value") is not None:
                    latest = entry["value"]
                    break
            results[key] = latest
        except Exception:
            logger.warning("Failed to fetch WB indicator %s for %s", key, iso)
            results[key] = None

    return results


def fetch_imf_ev_data(country_iso: str) -> dict[str, Any]:
    """Fetch GDP growth and inflation from the IMF DataMapper API.

    Parameters
    ----------
    country_iso : str
        ISO-3 country code.

    Returns
    -------
    dict
        Keys: gdp_growth_rate, inflation_rate (as fractions).
        Values may be None if unavailable.
    """
    import requests

    iso = country_iso.upper()
    results: dict[str, Any] = {}

    for key, code in _IMF_INDICATORS.items():
        url = (
            f"https://www.imf.org/external/datamapper/api/v1/{code}/{iso}"
        )
        try:
            resp = requests.get(url, timeout=20)
            resp.raise_for_status()
            payload = resp.json()

            values = (
                payload.get("values", {})
                .get(code, {})
                .get(iso, {})
            )

            if not values:
                results[key] = None
                continue

            sorted_years = sorted(values.keys(), reverse=True)
            latest_val = None
            for yr in sorted_years:
                v = values[yr]
                if v is not None and v != "":
                    latest_val = float(v) / 100.0
                    break
            results[key] = latest_val
        except Exception:
            logger.warning("Failed to fetch IMF indicator %s for %s", key, iso)
            results[key] = None

    return results
