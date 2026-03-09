"""
Vehicle-to-Grid (V2G) technical potential assessment.

Computes hourly V2G discharge capacity and available energy
based on fleet connectivity and battery SOC windows.
"""

from __future__ import annotations

import numpy as np

from ..config import DEFAULT_CONNECTED_PROFILE
from ..results import V2GPotential


def compute_v2g_potential(
    fleet_by_category: dict[str, int],
    ev_categories: dict[str, dict],
    connected_profile: list[float] | None = None,
    v2g_min_soc: float = 0.30,
    v2g_max_soc: float = 0.90,
) -> V2GPotential:
    """Compute hourly V2G capacity and energy availability.

    Parameters
    ----------
    fleet_by_category : dict
        Number of EVs per category.
    ev_categories : dict
        Technical parameters per category.
    connected_profile : list[float], optional
        24h fraction of fleet connected (plugged in). Default provided.
    v2g_min_soc : float
        Minimum SOC reserved for driving (fraction).
    v2g_max_soc : float
        Maximum SOC at which V2G can begin discharging.

    Returns
    -------
    V2GPotential
        Hourly V2G capacity and energy metrics.
    """
    if connected_profile is None:
        connected_profile = list(DEFAULT_CONNECTED_PROFILE)

    max_v2g_mw = np.zeros(24)
    available_soc_mwh = np.zeros(24)

    for cat, count in fleet_by_category.items():
        if count <= 0:
            continue

        params = ev_categories.get(cat, {})
        v2g_power_kw = params.get("v2g_power", 5.0)
        v2g_participation = params.get("v2g_participation", 0.3)
        battery_kwh = params.get("battery_capacity", 50.0)
        discharge_eff = params.get("efficiency_discharge", 0.90)

        for h in range(24):
            connected = connected_profile[h]
            n_v2g = count * connected * v2g_participation

            power_mw = n_v2g * v2g_power_kw * discharge_eff / 1000.0
            max_v2g_mw[h] += power_mw

            soc_window = v2g_max_soc - v2g_min_soc
            energy_mwh = n_v2g * battery_kwh * soc_window * discharge_eff / 1000.0
            available_soc_mwh[h] += energy_mwh

    daily_energy = float(np.sum(max_v2g_mw))
    annual_gwh = daily_energy * 365 / 1000.0

    return V2GPotential(
        hourly_connected_fraction=connected_profile,
        hourly_available_soc_mwh=available_soc_mwh.tolist(),
        max_v2g_power_mw=max_v2g_mw.tolist(),
        daily_v2g_energy_mwh=daily_energy,
        annual_v2g_potential_gwh=annual_gwh,
    )
