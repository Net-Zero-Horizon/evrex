"""
Charging demand profile generation.

Generates 24-hour charging demand profiles for three scenarios:
- Uncontrolled: charge on plug-in (evening peak)
- Time-of-Use shifted: respond to tariff signals (night off-peak)
- Optimized: smart charging fills demand valleys
"""

from __future__ import annotations

import numpy as np

from ..results import ChargingProfile, ChargingScenarioResult


# ══════════════════════════════════════════════════════════════════
# Empirical charging profiles (literature-based shapes)
# ══════════════════════════════════════════════════════════════════

# Uncontrolled home charging — evening peak on arrival
_UNCONTROLLED_PATTERN: dict[str, list[float]] = {
    "light": [
        0.12, 0.08, 0.05, 0.04, 0.04, 0.05,
        0.08, 0.10, 0.08, 0.06, 0.06, 0.06,
        0.06, 0.06, 0.08, 0.12, 0.20, 0.35,
        0.55, 0.65, 0.55, 0.42, 0.30, 0.18,
    ],
    "medium": [
        0.05, 0.04, 0.03, 0.03, 0.04, 0.08,
        0.25, 0.35, 0.30, 0.25, 0.20, 0.18,
        0.15, 0.18, 0.22, 0.28, 0.30, 0.25,
        0.20, 0.15, 0.12, 0.10, 0.08, 0.06,
    ],
    "heavy": [
        0.15, 0.12, 0.10, 0.08, 0.06, 0.08,
        0.12, 0.15, 0.10, 0.08, 0.08, 0.10,
        0.12, 0.12, 0.10, 0.10, 0.12, 0.15,
        0.20, 0.25, 0.30, 0.28, 0.22, 0.18,
    ],
    "buses": [
        0.35, 0.30, 0.25, 0.25, 0.20, 0.05,
        0.02, 0.02, 0.05, 0.08, 0.10, 0.12,
        0.15, 0.12, 0.08, 0.05, 0.02, 0.02,
        0.05, 0.10, 0.15, 0.25, 0.30, 0.35,
    ],
}

# Time-of-use shifted — move to off-peak hours
_TOU_PATTERN: dict[str, list[float]] = {
    "light": [
        0.30, 0.35, 0.38, 0.35, 0.30, 0.22,
        0.10, 0.05, 0.03, 0.03, 0.03, 0.03,
        0.03, 0.03, 0.03, 0.05, 0.08, 0.10,
        0.15, 0.12, 0.10, 0.15, 0.22, 0.28,
    ],
    "medium": [
        0.25, 0.28, 0.30, 0.28, 0.22, 0.10,
        0.05, 0.05, 0.08, 0.10, 0.12, 0.12,
        0.12, 0.10, 0.08, 0.05, 0.05, 0.08,
        0.12, 0.15, 0.18, 0.20, 0.22, 0.25,
    ],
    "heavy": [
        0.30, 0.32, 0.30, 0.28, 0.22, 0.10,
        0.05, 0.05, 0.05, 0.05, 0.08, 0.08,
        0.10, 0.10, 0.08, 0.08, 0.10, 0.12,
        0.15, 0.18, 0.22, 0.25, 0.28, 0.30,
    ],
    "buses": [
        0.40, 0.42, 0.40, 0.38, 0.30, 0.10,
        0.02, 0.02, 0.02, 0.05, 0.08, 0.10,
        0.12, 0.10, 0.05, 0.02, 0.02, 0.02,
        0.05, 0.08, 0.15, 0.25, 0.32, 0.38,
    ],
}


# ══════════════════════════════════════════════════════════════════
# Profile generation
# ══════════════════════════════════════════════════════════════════


def generate_charging_profiles(
    fleet_by_category: dict[str, int],
    ev_categories: dict[str, dict],
    scenario: str = "uncontrolled",
    smart_charging_fraction: float = 0.0,
    base_demand_24h: list[float] | None = None,
) -> ChargingScenarioResult:
    """Generate 24h charging demand profiles for a given scenario.

    Parameters
    ----------
    fleet_by_category : dict
        Number of EVs per category.
    ev_categories : dict
        Technical parameters per category (charging_power, etc.).
    scenario : str
        One of ``"uncontrolled"``, ``"tou_shifted"``, ``"optimized"``.
    smart_charging_fraction : float
        Fraction of fleet participating in smart charging [0, 1].
        Only used for ``"optimized"`` scenario.
    base_demand_24h : list[float], optional
        Base system demand (MW) per hour. Required for ``"optimized"`` scenario.

    Returns
    -------
    ChargingScenarioResult
        Profiles per category and aggregate demand.
    """
    profiles: dict[str, ChargingProfile] = {}
    aggregate = np.zeros(24)

    for cat, count in fleet_by_category.items():
        if count <= 0:
            continue

        charge_kw = ev_categories.get(cat, {}).get("charging_power", 7.0)

        if scenario == "uncontrolled":
            pattern = _UNCONTROLLED_PATTERN.get(cat, _UNCONTROLLED_PATTERN["light"])
        elif scenario == "tou_shifted":
            pattern = _TOU_PATTERN.get(cat, _TOU_PATTERN["light"])
        elif scenario == "optimized":
            pattern = _generate_optimized_pattern(
                count, charge_kw, base_demand_24h, smart_charging_fraction,
            )
        else:
            pattern = _UNCONTROLLED_PATTERN.get(cat, _UNCONTROLLED_PATTERN["light"])

        # Scale pattern to MW
        hourly_mw = [p * count * charge_kw / 1000.0 for p in pattern]

        profiles[cat] = ChargingProfile(
            category=cat,
            scenario=scenario,
            hourly_mw=hourly_mw,
            description=f"{cat} ({scenario}): {count} vehicles x {charge_kw} kW",
        )
        aggregate += np.array(hourly_mw)

    return ChargingScenarioResult(
        scenario=scenario,
        profiles_by_category=profiles,
        aggregate_hourly_mw=aggregate.tolist(),
        peak_demand_mw=float(np.max(aggregate)) if len(aggregate) > 0 else 0.0,
        daily_energy_mwh=float(np.sum(aggregate)) if len(aggregate) > 0 else 0.0,
    )


def _generate_optimized_pattern(
    n_vehicles: int,
    charge_kw: float,
    base_demand_24h: list[float] | None,
    smart_fraction: float,
) -> list[float]:
    """Generate an optimized charging pattern that fills demand valleys."""
    if base_demand_24h is None or len(base_demand_24h) < 24:
        return _TOU_PATTERN["light"]

    demand = np.array(base_demand_24h[:24])
    max_demand = np.max(demand)

    available = max_demand - demand
    total_available = np.sum(available)

    if total_available <= 0:
        return [1.0 / 24] * 24

    pattern_smart = available / total_available
    pattern_uncontrolled = np.array(_UNCONTROLLED_PATTERN["light"])
    pattern_uncontrolled /= np.sum(pattern_uncontrolled)

    pattern = smart_fraction * pattern_smart + (1 - smart_fraction) * pattern_uncontrolled
    pattern /= np.sum(pattern)

    return pattern.tolist()


def generate_all_scenarios(
    fleet_by_category: dict[str, int],
    ev_categories: dict[str, dict],
    smart_charging_fraction: float = 0.5,
    base_demand_24h: list[float] | None = None,
) -> dict[str, ChargingScenarioResult]:
    """Generate all three charging scenarios.

    Returns dict keyed by scenario name.
    """
    results = {}
    for scenario in ("uncontrolled", "tou_shifted", "optimized"):
        results[scenario] = generate_charging_profiles(
            fleet_by_category, ev_categories, scenario,
            smart_charging_fraction=smart_charging_fraction,
            base_demand_24h=base_demand_24h,
        )
    return results
