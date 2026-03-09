"""
Integration helper: adoption curve to EV config conversion.

Fits S-curve parameters from an adoption trajectory and distributes
the fleet across nodes for use in energy system models.
"""

from __future__ import annotations

import logging
from typing import Optional

import numpy as np
from scipy.optimize import curve_fit

from ..config import DEFAULT_CATEGORIES, TransportContext
from ..results import EVAdoptionCurve

logger = logging.getLogger(__name__)


def _logistic_func(t: np.ndarray, K: float, r: float, t_mid: float) -> np.ndarray:
    """Logistic function for curve fitting: K / (1 + exp(-r*(t - t_mid)))."""
    return K / (1.0 + np.exp(-r * (t - t_mid)))


def fit_adoption_to_ev_config(
    curve: EVAdoptionCurve,
    transport: TransportContext,
    num_nodes: int,
    node_demand_fractions: Optional[list[float]] = None,
    charging_profiles: Optional[dict[str, list[float]]] = None,
    v2g_params: Optional[dict] = None,
) -> dict:
    """Convert an EVAdoptionCurve into EV configuration parameters.

    Fits S-curve parameters (max_adoption, growth_rate, mid_point_fraction)
    from the adoption trajectory and distributes fleet across nodes.

    Parameters
    ----------
    curve : EVAdoptionCurve
        Selected adoption scenario.
    transport : TransportContext
        Fleet baseline data.
    num_nodes : int
        Number of system nodes.
    node_demand_fractions : list[float], optional
        Fraction of fleet per node (sums to 1). Equal if not provided.
    charging_profiles : dict[str, list[float]], optional
        24-hour charging patterns per category.
    v2g_params : dict, optional
        V2G participation, power, compensation overrides.

    Returns
    -------
    dict
        Configuration with keys: base_year, target_year, categories,
        initial_soc, fitted_s_curve, method.
    """
    if not curve.years or not curve.penetration:
        return {}

    base_year = curve.years[0]
    target_year = curve.years[-1]
    n_years = len(curve.years)
    total_fleet = sum(transport.fleet_by_category.values())

    # -- Fit S-curve parameters --
    t_data = np.arange(n_years, dtype=float)
    pen_data = np.array(curve.penetration)

    K_guess = max(pen_data[-1], 0.1)
    r_guess = 0.15
    t_mid_guess = n_years * 0.5

    try:
        popt, _ = curve_fit(
            _logistic_func, t_data, pen_data,
            p0=[K_guess, r_guess, t_mid_guess],
            bounds=([0.01, 0.01, 0], [1.5, 1.0, n_years * 2]),
            maxfev=5000,
        )
        K_fit, r_fit, t_mid_fit = popt
    except Exception:
        logger.warning("S-curve fitting failed; using heuristic parameters")
        K_fit = max(pen_data[-1], 0.1)
        r_fit = 0.14
        t_mid_fit = n_years * 0.5

    mid_point_fraction = t_mid_fit / max(n_years - 1, 1)
    mid_point_fraction = max(0.1, min(0.9, mid_point_fraction))

    initial_ev_fleet = max(int(curve.penetration[0] * total_fleet), 1)
    final_ev_fleet = int(curve.penetration[-1] * total_fleet)
    max_adoption = max(final_ev_fleet / max(initial_ev_fleet, 1), 2.0)

    # -- Node distribution --
    if node_demand_fractions is None:
        node_demand_fractions = [1.0 / num_nodes] * num_nodes

    # -- Default charging patterns --
    default_pattern = [
        0.10, 0.08, 0.05, 0.05, 0.05, 0.08,
        0.15, 0.20, 0.15, 0.10, 0.10, 0.10,
        0.10, 0.10, 0.10, 0.15, 0.20, 0.30,
        0.50, 0.60, 0.50, 0.40, 0.30, 0.20,
    ]
    if charging_profiles is None:
        charging_profiles = {cat: list(default_pattern) for cat in DEFAULT_CATEGORIES}

    # -- Default V2G parameters --
    v2g_defaults = {
        "light": {"v2g_power": 5.0, "v2g_participation": 0.3},
        "medium": {"v2g_power": 8.0, "v2g_participation": 0.4},
        "heavy": {"v2g_power": 15.0, "v2g_participation": 0.5},
        "buses": {"v2g_power": 40.0, "v2g_participation": 0.7},
    }
    if v2g_params:
        for cat in v2g_defaults:
            if cat in v2g_params:
                v2g_defaults[cat].update(v2g_params[cat])

    # -- Build categories config --
    battery_caps = {"light": 50.0, "medium": 75.0, "heavy": 150.0, "buses": 300.0}
    charge_powers = {"light": 7.0, "medium": 11.0, "heavy": 22.0, "buses": 50.0}

    categories = {}
    for cat in DEFAULT_CATEGORIES:
        initial_count = transport.fleet_by_category.get(cat, 0)
        quantity = [max(1, int(initial_count * f)) for f in node_demand_fractions]

        categories[cat] = {
            "battery_capacity": battery_caps.get(cat, 50.0),
            "charging_power": charge_powers.get(cat, 7.0),
            "v2g_power": v2g_defaults[cat]["v2g_power"],
            "v2g_participation": v2g_defaults[cat]["v2g_participation"],
            "efficiency_charge": 0.90,
            "efficiency_discharge": 0.90,
            "min_soc": 0.20,
            "max_adoption": round(max_adoption, 1),
            "growth_rate": round(r_fit, 4),
            "mid_point_fraction": round(mid_point_fraction, 3),
            "quantity": quantity,
            "base_pattern": charging_profiles.get(cat, default_pattern),
        }

    # -- Initial SOC per node --
    initial_soc = []
    for ni in range(num_nodes):
        soc_mwh = 0.0
        for cat, cfg in categories.items():
            qty = cfg["quantity"][ni] if ni < len(cfg["quantity"]) else 0
            soc_mwh += qty * cfg["battery_capacity"] * 0.8 / 1000.0
        initial_soc.append(round(soc_mwh, 3))

    return {
        "base_year": base_year,
        "target_year": target_year,
        "categories": categories,
        "initial_soc": initial_soc,
        "fitted_s_curve": {
            "max_adoption": round(max_adoption, 1),
            "growth_rate": round(r_fit, 4),
            "mid_point_fraction": round(mid_point_fraction, 3),
        },
        "method": curve.method,
    }
