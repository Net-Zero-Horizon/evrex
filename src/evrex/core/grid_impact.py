"""
Grid impact assessment for EV charging and V2G.

Evaluates peak shaving, valley filling, arbitrage revenue, and
overall net V2G program value.
"""

from __future__ import annotations

import numpy as np

from ..results import GridImpactResult, V2GPotential


def assess_grid_impact(
    base_demand_24h: list[float],
    ev_charging_24h: list[float],
    v2g_potential: V2GPotential,
    electricity_prices_24h: list[float] | None = None,
    v2g_compensation_per_mwh: float = 50.0,
    grid_reinforcement_cost_per_mw: float = 500000.0,
) -> GridImpactResult:
    """Assess the impact of EV charging and V2G on the power grid.

    Parameters
    ----------
    base_demand_24h : list[float]
        Base system demand per hour (MW), 24 values.
    ev_charging_24h : list[float]
        Aggregate EV charging demand per hour (MW).
    v2g_potential : V2GPotential
        V2G capacity analysis from ``compute_v2g_potential()``.
    electricity_prices_24h : list[float], optional
        Electricity prices per hour ($/MWh). Synthetic if not provided.
    v2g_compensation_per_mwh : float
        V2G discharge compensation rate ($/MWh).
    grid_reinforcement_cost_per_mw : float
        Cost of grid capacity upgrade per MW ($/MW).

    Returns
    -------
    GridImpactResult
        Comprehensive grid impact metrics.
    """
    base = np.array(base_demand_24h[:24])
    ev = np.array(ev_charging_24h[:24])
    v2g_mw = np.array(v2g_potential.max_v2g_power_mw[:24])

    # Synthetic electricity prices if not provided
    if electricity_prices_24h is None or len(electricity_prices_24h) < 24:
        hours = np.arange(24)
        morning = 40 * np.exp(-0.5 * ((hours - 9) / 1.5) ** 2)
        evening = 60 * np.exp(-0.5 * ((hours - 20) / 2.0) ** 2)
        prices = 50 + morning + evening
    else:
        prices = np.array(electricity_prices_24h[:24])

    # -- Net load profiles --
    load_with_ev = base + ev
    # V2G dispatched during high-price hours (top 8 hours)
    price_rank = np.argsort(-prices)
    v2g_dispatch = np.zeros(24)
    for h in price_rank[:8]:
        v2g_dispatch[h] = v2g_mw[h]
    net_load = load_with_ev - v2g_dispatch

    # -- Peak shaving --
    peak_with_ev = float(np.max(load_with_ev))
    peak_after_v2g = float(np.max(net_load))
    peak_shaving = max(0, peak_with_ev - peak_after_v2g)

    # -- Valley filling --
    valley_before = float(np.min(base))
    valley_after = float(np.min(net_load))
    valley_filling = max(0, valley_after - valley_before)

    # -- Peak-to-valley ratio --
    peak_before = float(np.max(base))
    ptv_before = peak_before / max(valley_before, 1) if valley_before > 0 else float("inf")
    ptv_after = peak_after_v2g / max(valley_after, 1) if valley_after > 0 else float("inf")

    # -- RE curtailment reduction estimate --
    total_v2g_energy = float(np.sum(v2g_dispatch))
    re_curtailment_reduction = min(15.0, total_v2g_energy / max(np.sum(base), 1) * 100)

    # -- Frequency regulation capacity --
    freq_reg = float(np.mean(v2g_mw)) * 0.5

    # -- Economic analysis --
    arbitrage_daily = 0.0
    for h in range(24):
        if v2g_dispatch[h] > 0:
            arbitrage_daily += v2g_dispatch[h] * prices[h] / 1000
    arbitrage_annual = arbitrage_daily * 365

    # Avoided grid reinforcement
    avoided_mw = max(0, peak_with_ev - peak_after_v2g)
    avoided_reinforcement = avoided_mw * grid_reinforcement_cost_per_mw

    # Net V2G program value
    v2g_revenue = total_v2g_energy * v2g_compensation_per_mwh * 365 / 1000
    net_value = arbitrage_annual + avoided_reinforcement + v2g_revenue

    return GridImpactResult(
        base_demand_24h=base.tolist(),
        ev_charging_24h=ev.tolist(),
        v2g_discharge_24h=v2g_dispatch.tolist(),
        net_load_24h=net_load.tolist(),
        peak_shaving_mw=round(peak_shaving, 2),
        valley_filling_mw=round(valley_filling, 2),
        peak_to_valley_before=round(ptv_before, 3),
        peak_to_valley_after=round(ptv_after, 3),
        re_curtailment_reduction_pct=round(re_curtailment_reduction, 2),
        frequency_regulation_mw=round(freq_reg, 2),
        arbitrage_revenue_annual=round(arbitrage_annual, 0),
        avoided_reinforcement=round(avoided_reinforcement, 0),
        net_v2g_value=round(net_value, 0),
    )


def compute_fleet_evolution_metrics(
    years: list[int],
    fleet_ev_by_year: list[int],
    fleet_by_category_by_year: dict[str, list[int]],
    ev_categories: dict[str, dict],
    base_demand_annual_gwh: float = 100.0,
) -> dict:
    """Compute yearly metrics for fleet evolution visualization.

    Parameters
    ----------
    years : list[int]
        Year labels.
    fleet_ev_by_year : list[int]
        Total EV fleet per year.
    fleet_by_category_by_year : dict
        Per-category fleet per year.
    ev_categories : dict
        Technical parameters.
    base_demand_annual_gwh : float
        Base system annual demand for percentage computation.

    Returns
    -------
    dict
        Keys: years, total_ev, energy_gwh, peak_mw, ev_demand_pct, v2g_capacity_mw.
    """
    n = len(years)
    energy_gwh = []
    peak_mw = []
    ev_pct = []
    v2g_cap = []

    for i in range(n):
        e = 0.0
        p = 0.0
        v = 0.0
        for cat in fleet_by_category_by_year:
            count = (
                fleet_by_category_by_year[cat][i]
                if i < len(fleet_by_category_by_year[cat])
                else 0
            )
            params = ev_categories.get(cat, {})
            charge_kw = params.get("charging_power", 7.0)
            v2g_kw = params.get("v2g_power", 5.0)
            v2g_part = params.get("v2g_participation", 0.3)
            consumption = params.get("energy_consumption", 18.0)
            daily_km = params.get("avg_daily_km", 40.0)

            annual_gwh = count * daily_km * 365 * consumption / 100.0 / 0.9 / 1e6
            e += annual_gwh
            p += count * 0.25 * charge_kw / 1000.0
            v += count * 0.6 * v2g_part * v2g_kw / 1000.0

        energy_gwh.append(round(e, 3))
        peak_mw.append(round(p, 2))
        ev_pct.append(round(e / max(base_demand_annual_gwh, 1) * 100, 2))
        v2g_cap.append(round(v, 2))

    return {
        "years": years,
        "total_ev": fleet_ev_by_year,
        "energy_gwh": energy_gwh,
        "peak_mw": peak_mw,
        "ev_demand_pct": ev_pct,
        "v2g_capacity_mw": v2g_cap,
    }
