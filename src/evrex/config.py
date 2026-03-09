"""
Configuration dataclasses for EV fleet assessment.

Provides input data structures for adoption modeling and V2G analysis.
"""

from __future__ import annotations

from dataclasses import dataclass, field


# Default EV categories and their typical parameters
DEFAULT_CATEGORIES = ("light", "medium", "heavy", "buses")

# Category share of total EV fleet (evolves over time — light faster)
DEFAULT_CATEGORY_SHARES: dict[str, tuple[float, float]] = {
    # (initial_share, final_share)  — interpolated linearly
    "light": (0.75, 0.65),
    "medium": (0.12, 0.18),
    "heavy": (0.08, 0.10),
    "buses": (0.05, 0.07),
}

# Default energy consumption by category (kWh per 100 km)
DEFAULT_ENERGY_CONSUMPTION: dict[str, float] = {
    "light": 18.0,
    "medium": 25.0,
    "heavy": 55.0,
    "buses": 80.0,
}

# Default connected-time profile (fraction of fleet plugged in)
DEFAULT_CONNECTED_PROFILE = [
    0.85, 0.88, 0.90, 0.90, 0.88, 0.80,  # 00-05: most parked at home
    0.60, 0.40, 0.30, 0.25, 0.25, 0.25,  # 06-11: morning commute
    0.30, 0.30, 0.28, 0.25, 0.30, 0.40,  # 12-17: afternoon
    0.55, 0.65, 0.72, 0.78, 0.82, 0.85,  # 18-23: evening return
]


@dataclass
class TransportContext:
    """Transport sector baseline data for a study region."""

    country_iso: str = ""
    fleet_by_category: dict[str, int] = field(
        default_factory=lambda: {"light": 1000, "medium": 200, "heavy": 50, "buses": 30},
    )
    avg_daily_km: dict[str, float] = field(
        default_factory=lambda: {"light": 40.0, "medium": 80.0, "heavy": 150.0, "buses": 200.0},
    )
    energy_consumption: dict[str, float] = field(
        default_factory=lambda: dict(DEFAULT_ENERGY_CONSUMPTION),
    )
    charging_stations: int = 0
    road_density_km2: float = 0.0
    population: int = 1_000_000


@dataclass
class EVMacroData:
    """Macroeconomic and policy data for EV adoption modeling."""

    country_iso: str = ""
    gdp_per_capita: float = 5000.0              # USD
    urbanization_pct: float = 75.0              # %
    population: int = 1_000_000
    inflation_rate: float = 0.03
    gdp_growth_rate: float = 0.03
    # EV-specific economics
    ev_price: dict[str, float] = field(
        default_factory=lambda: {
            "light": 35000.0, "medium": 55000.0,
            "heavy": 120000.0, "buses": 300000.0,
        },
    )
    ice_price: dict[str, float] = field(
        default_factory=lambda: {
            "light": 25000.0, "medium": 40000.0,
            "heavy": 90000.0, "buses": 250000.0,
        },
    )
    battery_cost_per_kwh: float = 140.0         # $/kWh pack-level
    battery_cost_decline_rate: float = 0.08     # annual decline fraction
    fuel_price_gasoline: float = 1.20           # $/L
    fuel_price_diesel: float = 1.10             # $/L
    electricity_tariff: float = 0.15            # $/kWh
    maintenance_diff_annual: float = 500.0      # $ ICE higher than EV
    # Policy instruments
    ice_phaseout_year: int = 0                  # 0 = no ban
    ev_subsidy_pct: float = 0.0                 # % of purchase price
    registration_tax_diff: float = 0.0          # $ ICE higher than EV
    emission_target_pct: float = 0.0            # % reduction target
    # Trajectories (optional)
    battery_cost_trajectory: dict[int, float] = field(default_factory=dict)
