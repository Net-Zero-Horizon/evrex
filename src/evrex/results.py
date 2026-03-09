"""
Result dataclasses for EV fleet assessment.

Provides output data structures from adoption modeling and V2G analysis.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class EVAdoptionCurve:
    """Result of an EV adoption model run."""

    method: str  # "logistic", "bass", "tco_parity", "policy_driven"
    years: list[int] = field(default_factory=list)
    penetration: list[float] = field(default_factory=list)  # EV share [0..1]
    fleet_by_category: dict[str, list[int]] = field(default_factory=dict)
    total_fleet_ev: list[int] = field(default_factory=list)
    energy_demand_gwh: list[float] = field(default_factory=list)
    peak_charging_mw: list[float] = field(default_factory=list)
    confidence_low: list[float] = field(default_factory=list)
    confidence_high: list[float] = field(default_factory=list)
    parameters: dict = field(default_factory=dict)


@dataclass
class EVValidationData:
    """Observed EV fleet data for model validation."""

    label: str
    years: list[int] = field(default_factory=list)
    ev_stock: list[int] = field(default_factory=list)
    source: str = "manual"  # "iea", "user_csv", "manual"


@dataclass
class ChargingProfile:
    """24-hour charging demand profile for one category and scenario."""

    category: str
    scenario: str       # "uncontrolled" | "tou_shifted" | "optimized"
    hourly_mw: list[float] = field(default_factory=list)  # 24 values
    description: str = ""


@dataclass
class ChargingScenarioResult:
    """Aggregate charging demand for a complete scenario."""

    scenario: str
    profiles_by_category: dict[str, ChargingProfile] = field(default_factory=dict)
    aggregate_hourly_mw: list[float] = field(default_factory=list)  # 24 values
    peak_demand_mw: float = 0.0
    daily_energy_mwh: float = 0.0


@dataclass
class V2GPotential:
    """V2G technical potential assessment results."""

    hourly_connected_fraction: list[float] = field(default_factory=list)  # 24 values
    hourly_available_soc_mwh: list[float] = field(default_factory=list)   # 24 values
    max_v2g_power_mw: list[float] = field(default_factory=list)           # 24 values
    daily_v2g_energy_mwh: float = 0.0
    annual_v2g_potential_gwh: float = 0.0
    degradation_cost_per_kwh: float = 0.0
    breakeven_compensation: float = 0.0     # $/MWh


@dataclass
class DegradationResult:
    """Battery degradation analysis output."""

    chemistry: str                          # "NMC" or "LFP"
    cycles_per_day: float = 0.0
    depth_of_discharge: float = 0.0
    cycle_life_remaining_pct: float = 100.0
    calendar_aging_pct_per_year: float = 2.0
    total_degradation_pct_per_year: float = 0.0
    degradation_cost_per_kwh: float = 0.0   # $/kWh cycled
    breakeven_compensation: float = 0.0     # $/MWh


@dataclass
class GridImpactResult:
    """Grid impact assessment results."""

    base_demand_24h: list[float] = field(default_factory=list)
    ev_charging_24h: list[float] = field(default_factory=list)
    v2g_discharge_24h: list[float] = field(default_factory=list)
    net_load_24h: list[float] = field(default_factory=list)
    peak_shaving_mw: float = 0.0
    valley_filling_mw: float = 0.0
    peak_to_valley_before: float = 0.0
    peak_to_valley_after: float = 0.0
    re_curtailment_reduction_pct: float = 0.0
    frequency_regulation_mw: float = 0.0
    arbitrage_revenue_annual: float = 0.0
    avoided_reinforcement: float = 0.0
    net_v2g_value: float = 0.0
