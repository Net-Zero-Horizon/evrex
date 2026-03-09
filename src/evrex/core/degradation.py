"""
Battery degradation modeling for V2G cycling.

Uses Wohler-type curve to estimate capacity loss from V2G charge/discharge
cycles, with separate parameters for NMC and LFP chemistries.
"""

from __future__ import annotations

from ..results import DegradationResult


# Cycle life parameters by chemistry (cycles at 80% DoD to 80% capacity)
CYCLE_LIFE_PARAMS: dict[str, dict] = {
    "NMC": {
        "cycles_80pct_dod": 2000,
        "dod_exponent": 1.5,
        "calendar_pct_per_year": 2.5,
        "cost_per_kwh_new": 140.0,
    },
    "LFP": {
        "cycles_80pct_dod": 4000,
        "dod_exponent": 1.2,
        "calendar_pct_per_year": 1.5,
        "cost_per_kwh_new": 100.0,
    },
}


def compute_battery_degradation(
    v2g_cycles_per_day: float = 0.5,
    battery_capacity_kwh: float = 50.0,
    depth_of_discharge: float = 0.30,
    chemistry: str = "NMC",
    battery_cost_per_kwh: float | None = None,
) -> DegradationResult:
    """Model battery degradation from V2G cycling.

    Uses Wohler-type curve: equivalent cycles at reference DoD = actual
    cycles x (actual_DoD / ref_DoD)^exponent.

    Parameters
    ----------
    v2g_cycles_per_day : float
        Average number of V2G charge/discharge cycles per day.
    battery_capacity_kwh : float
        Battery capacity in kWh.
    depth_of_discharge : float
        Average DoD for V2G cycling (fraction, e.g. 0.30 = 30%).
    chemistry : str
        Battery chemistry: ``"NMC"`` or ``"LFP"``.
    battery_cost_per_kwh : float, optional
        Battery replacement cost. Uses default for chemistry if None.

    Returns
    -------
    DegradationResult
        Degradation metrics and break-even compensation.
    """
    params = CYCLE_LIFE_PARAMS.get(chemistry, CYCLE_LIFE_PARAMS["NMC"])
    ref_dod = 0.80
    ref_cycles = params["cycles_80pct_dod"]
    exponent = params["dod_exponent"]
    calendar_pct = params["calendar_pct_per_year"]

    if battery_cost_per_kwh is None:
        battery_cost_per_kwh = params["cost_per_kwh_new"]

    # Equivalent cycles at reference DoD
    dod_factor = (depth_of_discharge / ref_dod) ** exponent
    equivalent_cycles_per_day = v2g_cycles_per_day * dod_factor

    # Annual equivalent cycles
    annual_eq_cycles = equivalent_cycles_per_day * 365

    # Cycle degradation (% capacity lost per year)
    cycle_deg_pct = (annual_eq_cycles / ref_cycles) * 20.0

    # Total degradation
    total_deg_pct = cycle_deg_pct + calendar_pct

    # Remaining cycle life as percentage
    if total_deg_pct > 0:
        remaining_pct = max(0, 100 - total_deg_pct)
    else:
        remaining_pct = 100.0

    # Degradation cost per kWh cycled
    energy_per_cycle = battery_capacity_kwh * depth_of_discharge
    annual_throughput_kwh = v2g_cycles_per_day * 365 * energy_per_cycle
    annual_battery_value_loss = (
        (cycle_deg_pct / 20.0) * battery_capacity_kwh * battery_cost_per_kwh
    )
    if annual_throughput_kwh > 0:
        deg_cost_per_kwh = annual_battery_value_loss / annual_throughput_kwh
    else:
        deg_cost_per_kwh = 0.0

    # Break-even compensation ($/MWh)
    breakeven = deg_cost_per_kwh * 1000.0

    return DegradationResult(
        chemistry=chemistry,
        cycles_per_day=v2g_cycles_per_day,
        depth_of_discharge=depth_of_discharge,
        cycle_life_remaining_pct=remaining_pct,
        calendar_aging_pct_per_year=calendar_pct,
        total_degradation_pct_per_year=round(total_deg_pct, 3),
        degradation_cost_per_kwh=round(deg_cost_per_kwh, 4),
        breakeven_compensation=round(breakeven, 2),
    )
