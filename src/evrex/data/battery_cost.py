"""
Bundled BNEF battery pack cost data and projections.

Lithium-ion battery pack costs ($/kWh, volume-weighted average).
Source: BloombergNEF Lithium-Ion Battery Price Survey 2024.
"""

from __future__ import annotations


# Historical battery pack costs
BNEF_BATTERY_COSTS: dict[int, float] = {
    2013: 684,
    2014: 592,
    2015: 381,
    2016: 296,
    2017: 226,
    2018: 185,
    2019: 161,
    2020: 140,
    2021: 141,
    2022: 151,  # temporary increase (supply chain)
    2023: 139,
    2024: 115,
}


def project_battery_costs(
    annual_decline_rate: float = 0.07,
    target_year: int = 2050,
    floor_cost: float = 40.0,
) -> dict[int, float]:
    """Project battery costs forward from BNEF 2024 baseline.

    Parameters
    ----------
    annual_decline_rate : float
        Annual cost decline rate (fraction, e.g. 0.07 = 7%/year).
    target_year : int
        Last year to project (inclusive).
    floor_cost : float
        Manufacturing cost floor ($/kWh).

    Returns
    -------
    dict[int, float]
        Year-to-cost trajectory (historical + projected).
    """
    trajectory: dict[int, float] = dict(BNEF_BATTERY_COSTS)
    base_cost = trajectory[2024]

    for year in range(2025, target_year + 1):
        dt = year - 2024
        projected = base_cost * (1 - annual_decline_rate) ** dt
        trajectory[year] = round(max(floor_cost, projected), 1)

    return trajectory
