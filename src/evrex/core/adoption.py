"""
EV fleet electrification adoption models.

Provides four modeling approaches adapted for transport electrification:
1. Logistic regression — macro-economic and transport drivers
2. Bass diffusion — innovation/imitation dynamics
3. TCO-parity — total cost of ownership comparison EV vs ICE
4. Policy-driven — mandate/ban-based fleet transition targets

Each method returns an ``EVAdoptionCurve`` with year-by-year fleet
evolution and energy demand projections.
"""

from __future__ import annotations

import logging
import math
from typing import Optional

import numpy as np

from ..config import (
    DEFAULT_CATEGORIES,
    DEFAULT_CATEGORY_SHARES,
    DEFAULT_ENERGY_CONSUMPTION,
    EVMacroData,
    TransportContext,
)
from ..results import EVAdoptionCurve

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════


def _total_fleet(transport: TransportContext) -> int:
    """Return total vehicle fleet across all categories."""
    return sum(transport.fleet_by_category.values())


def _category_shares_at(t_frac: float) -> dict[str, float]:
    """Interpolate category shares at fraction *t_frac* in [0, 1]."""
    shares = {}
    for cat, (s0, sf) in DEFAULT_CATEGORY_SHARES.items():
        shares[cat] = s0 + (sf - s0) * t_frac
    # Normalize to sum = 1
    total = sum(shares.values())
    return {k: v / total for k, v in shares.items()}


def _compute_energy_metrics(
    fleet_ev: int,
    category_shares: dict[str, float],
    transport: TransportContext,
    charging_efficiency: float = 0.90,
    simultaneous_charging_fraction: float = 0.25,
) -> tuple[float, float]:
    """Return (energy_demand_gwh, peak_charging_mw) for a given EV fleet size."""
    energy_gwh = 0.0
    peak_mw = 0.0
    for cat, share in category_shares.items():
        n_cat = fleet_ev * share
        daily_km = transport.avg_daily_km.get(cat, 40.0)
        consumption_kwh_100km = transport.energy_consumption.get(
            cat, DEFAULT_ENERGY_CONSUMPTION.get(cat, 20.0),
        )
        # Annual energy (GWh) = vehicles * daily_km * 365 * kWh/100km / 100 / eff / 1e6
        annual_gwh = (
            n_cat * daily_km * 365 * consumption_kwh_100km
            / 100.0 / charging_efficiency / 1e6
        )
        energy_gwh += annual_gwh

        # Peak charging (MW) = vehicles * simultaneous * avg_charging_power / 1000
        avg_charge_kw = {"light": 7.0, "medium": 11.0, "heavy": 22.0, "buses": 50.0}
        p_kw = avg_charge_kw.get(cat, 7.0)
        peak_mw += n_cat * simultaneous_charging_fraction * p_kw / 1000.0

    return energy_gwh, peak_mw


def _build_fleet_breakdown(
    penetration: list[float],
    years: list[int],
    total_fleet: int,
    transport: TransportContext,
) -> tuple[dict[str, list[int]], list[int], list[float], list[float]]:
    """Build per-category fleet, total EV fleet, energy, and peak MW lists."""
    n_years = len(years)
    fleet_by_cat: dict[str, list[int]] = {c: [] for c in DEFAULT_CATEGORIES}
    total_ev: list[int] = []
    energy: list[float] = []
    peak: list[float] = []

    for i, pen in enumerate(penetration):
        t_frac = i / max(n_years - 1, 1)
        shares = _category_shares_at(t_frac)
        fleet_ev = int(pen * total_fleet)
        total_ev.append(fleet_ev)

        for cat in DEFAULT_CATEGORIES:
            fleet_by_cat[cat].append(int(fleet_ev * shares.get(cat, 0.0)))

        e_gwh, p_mw = _compute_energy_metrics(fleet_ev, shares, transport)
        energy.append(round(e_gwh, 3))
        peak.append(round(p_mw, 2))

    return fleet_by_cat, total_ev, energy, peak


# ══════════════════════════════════════════════════════════════════
# Method 1: Logistic Regression (transport-specific)
# ══════════════════════════════════════════════════════════════════


def run_ev_logistic_adoption(
    macro: EVMacroData,
    transport: TransportContext,
    base_year: int = 2025,
    target_year: int = 2050,
    coefficients: Optional[dict] = None,
) -> EVAdoptionCurve:
    """Logistic regression adoption model with transport-specific drivers.

    The EV penetration evolves as fuel savings grow, EV costs decline,
    charging infrastructure expands, and GDP increases.

    Parameters
    ----------
    macro : EVMacroData
        Macroeconomic and EV-specific cost data.
    transport : TransportContext
        Current vehicle fleet baseline.
    base_year : int
        First year of the projection.
    target_year : int
        Last year of the projection (inclusive).
    coefficients : dict, optional
        Override regression coefficients.

    Returns
    -------
    EVAdoptionCurve
        Year-by-year adoption trajectory.
    """
    coeff = {
        "beta_0": -3.5,
        "beta_fuel_savings": 3.0,
        "beta_ev_price_ratio": -2.0,
        "beta_charging_infra": 0.5,
        "beta_gdp": 0.00003,
        "beta_urban": 0.015,
    }
    if coefficients:
        coeff.update(coefficients)

    years = list(range(base_year, target_year + 1))
    penetration = []
    total_fleet = _total_fleet(transport)

    for yr in years:
        t = yr - base_year

        # Project battery cost -> EV price decline
        if yr in macro.battery_cost_trajectory:
            bat_cost = macro.battery_cost_trajectory[yr]
        else:
            bat_cost = macro.battery_cost_per_kwh * (
                1 - macro.battery_cost_decline_rate
            ) ** t

        # Fuel cost savings per year (light vehicle representative)
        daily_km = transport.avg_daily_km.get("light", 40.0)
        annual_km = daily_km * 365
        fuel_cost_annual = annual_km * 7.0 / 100.0 * macro.fuel_price_gasoline
        elec_cost_annual = (
            annual_km * DEFAULT_ENERGY_CONSUMPTION["light"]
            / 100.0 * macro.electricity_tariff
        )
        fuel_savings = max(0, fuel_cost_annual - elec_cost_annual) / 1000.0

        # EV/ICE price ratio (declining over time)
        ev_avg = np.mean(list(macro.ev_price.values()))
        ice_avg = np.mean(list(macro.ice_price.values()))
        bat_reduction = (macro.battery_cost_per_kwh - bat_cost) * 50
        ev_effective = max(ev_avg - bat_reduction - ev_avg * macro.ev_subsidy_pct, 1)
        price_ratio = ev_effective / max(ice_avg, 1)

        # Charging infrastructure density
        infra_density = (
            transport.charging_stations / max(transport.population / 1000, 1)
        )
        if penetration:
            infra_density *= 1 + penetration[-1] * 10

        # GDP projection
        gdp = macro.gdp_per_capita * (1 + macro.gdp_growth_rate) ** t
        urban = macro.urbanization_pct

        z = (
            coeff["beta_0"]
            + coeff["beta_fuel_savings"] * fuel_savings
            + coeff["beta_ev_price_ratio"] * price_ratio
            + coeff["beta_charging_infra"] * infra_density
            + coeff["beta_gdp"] * gdp
            + coeff["beta_urban"] * urban
        )
        prob = 1.0 / (1.0 + math.exp(-max(-500, min(500, z))))
        penetration.append(prob)

    fleet_by_cat, total_ev, energy, peak = _build_fleet_breakdown(
        penetration, years, total_fleet, transport,
    )

    return EVAdoptionCurve(
        method="logistic",
        years=years,
        penetration=penetration,
        fleet_by_category=fleet_by_cat,
        total_fleet_ev=total_ev,
        energy_demand_gwh=energy,
        peak_charging_mw=peak,
        parameters=coeff,
    )


# ══════════════════════════════════════════════════════════════════
# Method 2: Bass Diffusion
# ══════════════════════════════════════════════════════════════════


def run_ev_bass_diffusion(
    transport: TransportContext,
    base_year: int = 2025,
    target_year: int = 2050,
    p: float = 0.02,
    q: float = 0.40,
    initial_penetration: float = 0.005,
) -> EVAdoptionCurve:
    """Bass diffusion model for EV adoption: innovation (p) + imitation (q).

    F(t) = (1 - exp(-(p+q)t)) / (1 + (q/p)exp(-(p+q)t))

    Parameters
    ----------
    transport : TransportContext
        Current vehicle fleet baseline.
    base_year : int
        First year of the projection.
    target_year : int
        Last year of the projection (inclusive).
    p : float
        Innovation coefficient (external influence, policy push).
    q : float
        Imitation coefficient (social influence, visibility).
    initial_penetration : float
        Current EV fleet share at base year.

    Returns
    -------
    EVAdoptionCurve
        Year-by-year adoption trajectory.
    """
    years = list(range(base_year, target_year + 1))
    penetration = []
    total_fleet = _total_fleet(transport)

    # Find t_offset such that F(t_offset) = initial_penetration
    t_offset = 0.0
    if initial_penetration > 0.0001:
        for t_try in np.linspace(0, 60, 600):
            exp_val = math.exp(-(p + q) * t_try)
            f_val = (1.0 - exp_val) / (1.0 + (q / max(p, 1e-9)) * exp_val)
            if f_val >= initial_penetration:
                t_offset = t_try
                break

    for yr in years:
        t = (yr - base_year) + t_offset
        exp_val = math.exp(max(-500, -(p + q) * t))
        f_val = (1.0 - exp_val) / (1.0 + (q / max(p, 1e-9)) * exp_val)
        f_val = max(0.0, min(1.0, f_val))
        penetration.append(f_val)

    fleet_by_cat, total_ev, energy, peak = _build_fleet_breakdown(
        penetration, years, total_fleet, transport,
    )

    return EVAdoptionCurve(
        method="bass",
        years=years,
        penetration=penetration,
        fleet_by_category=fleet_by_cat,
        total_fleet_ev=total_ev,
        energy_demand_gwh=energy,
        peak_charging_mw=peak,
        parameters={"p": p, "q": q, "initial_penetration": initial_penetration},
    )


# ══════════════════════════════════════════════════════════════════
# Method 3: TCO-Parity (Total Cost of Ownership)
# ══════════════════════════════════════════════════════════════════


def run_ev_tco_parity(
    macro: EVMacroData,
    transport: TransportContext,
    base_year: int = 2025,
    target_year: int = 2050,
    vehicle_lifetime_years: int = 15,
    price_sensitivity: float = 8.0,
) -> EVAdoptionCurve:
    """TCO-parity adoption: compares total cost of EV vs ICE ownership.

    For each year, computes lifetime TCO for a new EV and new ICE vehicle.
    Adoption follows sigmoid(sensitivity * (TCO_ICE - TCO_EV) / TCO_ICE).

    Parameters
    ----------
    macro : EVMacroData
        Macroeconomic and EV-specific cost data.
    transport : TransportContext
        Current vehicle fleet baseline.
    base_year : int
        First year of the projection.
    target_year : int
        Last year of the projection (inclusive).
    vehicle_lifetime_years : int
        Average vehicle ownership duration for TCO calculation.
    price_sensitivity : float
        Steepness of the sigmoid response to TCO gap.

    Returns
    -------
    EVAdoptionCurve
        Year-by-year adoption trajectory.
    """
    years = list(range(base_year, target_year + 1))
    penetration = []
    total_fleet = _total_fleet(transport)

    for yr in years:
        t = yr - base_year
        tco_gaps = []

        for cat in DEFAULT_CATEGORIES:
            # EV purchase price (declining with battery costs)
            if yr in macro.battery_cost_trajectory:
                bat_cost = macro.battery_cost_trajectory[yr]
            else:
                bat_cost = macro.battery_cost_per_kwh * (
                    1 - macro.battery_cost_decline_rate
                ) ** t

            bat_cap = {"light": 50, "medium": 75, "heavy": 150, "buses": 300}
            ev_base = macro.ev_price.get(cat, 35000.0)
            bat_savings = (macro.battery_cost_per_kwh - bat_cost) * bat_cap.get(cat, 50)
            ev_purchase = max(ev_base - bat_savings, ev_base * 0.4)
            ev_purchase *= 1 - macro.ev_subsidy_pct

            ice_purchase = macro.ice_price.get(cat, 25000.0)

            # Annual operating costs
            daily_km = transport.avg_daily_km.get(cat, 40.0)
            annual_km = daily_km * 365

            # ICE fuel cost
            fuel_eff = {"light": 7.0, "medium": 10.0, "heavy": 25.0, "buses": 35.0}
            fuel_type = "diesel" if cat in ("heavy", "buses") else "gasoline"
            fuel_price = (
                macro.fuel_price_diesel if fuel_type == "diesel"
                else macro.fuel_price_gasoline
            )
            fuel_price *= (1 + 0.02) ** t
            ice_fuel_annual = annual_km * fuel_eff.get(cat, 7.0) / 100.0 * fuel_price

            # EV electricity cost
            consumption = transport.energy_consumption.get(
                cat, DEFAULT_ENERGY_CONSUMPTION.get(cat, 18.0),
            )
            ev_elec_annual = annual_km * consumption / 100.0 * macro.electricity_tariff

            # Maintenance differential
            maint_diff = macro.maintenance_diff_annual
            if cat in ("heavy", "buses"):
                maint_diff *= 2.0

            # Registration tax
            reg_diff = macro.registration_tax_diff

            # Lifetime TCO
            n = vehicle_lifetime_years
            tco_ice = ice_purchase + n * (ice_fuel_annual + reg_diff)
            tco_ev = ev_purchase + n * ev_elec_annual
            tco_ice_total = tco_ice + n * maint_diff

            gap_frac = (tco_ice_total - tco_ev) / max(tco_ice_total, 1)
            tco_gaps.append(gap_frac)

        # Weighted average TCO gap across categories
        avg_gap = np.mean(tco_gaps)
        prob = 1.0 / (1.0 + math.exp(-price_sensitivity * avg_gap))
        prob = max(0.0, min(1.0, prob))
        penetration.append(prob)

    fleet_by_cat, total_ev, energy, peak = _build_fleet_breakdown(
        penetration, years, total_fleet, transport,
    )

    return EVAdoptionCurve(
        method="tco_parity",
        years=years,
        penetration=penetration,
        fleet_by_category=fleet_by_cat,
        total_fleet_ev=total_ev,
        energy_demand_gwh=energy,
        peak_charging_mw=peak,
        parameters={
            "vehicle_lifetime_years": vehicle_lifetime_years,
            "price_sensitivity": price_sensitivity,
        },
    )


# ══════════════════════════════════════════════════════════════════
# Method 4: Policy-Driven (Mandate/Ban-based)
# ══════════════════════════════════════════════════════════════════


def run_ev_policy_driven(
    macro: EVMacroData,
    transport: TransportContext,
    base_year: int = 2025,
    target_year: int = 2050,
    vehicle_avg_lifetime: int = 15,
) -> EVAdoptionCurve:
    """Policy-driven adoption based on ICE phase-out mandates.

    If an ICE ban year is set, new EV sales share ramps linearly to 100%
    by that year. Fleet stock is computed via a scrappage model:
    each cohort survives for ``vehicle_avg_lifetime`` years.

    If no ban year, uses emission reduction target to derive required
    EV share trajectory.

    Parameters
    ----------
    macro : EVMacroData
        Policy parameters (ICE ban year, emission target).
    transport : TransportContext
        Current vehicle fleet baseline.
    base_year : int
        First year of the projection.
    target_year : int
        Last year of the projection (inclusive).
    vehicle_avg_lifetime : int
        Average vehicle lifetime for scrappage model.

    Returns
    -------
    EVAdoptionCurve
        Year-by-year adoption trajectory.
    """
    years = list(range(base_year, target_year + 1))
    total_fleet = _total_fleet(transport)
    ban_year = macro.ice_phaseout_year

    # -- Compute new-sales EV share trajectory --
    sales_share = []
    for yr in years:
        if ban_year > base_year:
            current_share = 0.02
            if yr >= ban_year:
                share = 1.0
            else:
                progress = (yr - base_year) / max(ban_year - base_year, 1)
                share = current_share + (1.0 - current_share) * progress
        elif macro.emission_target_pct > 0:
            progress = (yr - base_year) / max(target_year - base_year, 1)
            target_share = macro.emission_target_pct / 100.0
            share = target_share * progress
        else:
            t = yr - base_year
            share = 0.02 * (1 + 0.05) ** t
            share = min(share, 0.5)
        sales_share.append(min(1.0, share))

    # -- Scrappage model: fleet stock from cumulative sales --
    replacement_rate = 1.0 / vehicle_avg_lifetime
    annual_sales = total_fleet * replacement_rate

    n_years = len(years)
    cohorts = np.zeros(n_years)
    for i in range(n_years):
        cohorts[i] = annual_sales * sales_share[i]

    # Fleet stock in year j = sum of surviving cohorts
    penetration = []
    for j in range(n_years):
        ev_stock = 0.0
        for i in range(j + 1):
            age = j - i
            if age < vehicle_avg_lifetime:
                ev_stock += cohorts[i]
        pen = min(1.0, ev_stock / max(total_fleet, 1))
        penetration.append(pen)

    fleet_by_cat, total_ev, energy, peak = _build_fleet_breakdown(
        penetration, years, total_fleet, transport,
    )

    return EVAdoptionCurve(
        method="policy_driven",
        years=years,
        penetration=penetration,
        fleet_by_category=fleet_by_cat,
        total_fleet_ev=total_ev,
        energy_demand_gwh=energy,
        peak_charging_mw=peak,
        parameters={
            "ice_phaseout_year": ban_year,
            "emission_target_pct": macro.emission_target_pct,
            "vehicle_avg_lifetime": vehicle_avg_lifetime,
            "sales_share_trajectory": sales_share,
        },
    )
