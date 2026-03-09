"""
EVreX -- EV Resource eXchange

A Python library for electric vehicle fleet electrification assessment,
adoption modeling, charging demand characterization, V2G potential analysis,
battery degradation modeling, and grid impact assessment.

Modules:
- evrex.core: Adoption models, charging profiles, V2G, degradation, grid impact
- evrex.data: OSM, World Bank, IMF, IEA, BNEF data fetchers
"""

__version__ = "0.1.0"
__author__ = "EVreX Development Team"

from .config import (
    DEFAULT_CATEGORIES,
    DEFAULT_CATEGORY_SHARES,
    DEFAULT_CONNECTED_PROFILE,
    DEFAULT_ENERGY_CONSUMPTION,
    EVMacroData,
    TransportContext,
)
from .results import (
    ChargingProfile,
    ChargingScenarioResult,
    DegradationResult,
    EVAdoptionCurve,
    EVValidationData,
    GridImpactResult,
    V2GPotential,
)
from .core.adoption import (
    run_ev_bass_diffusion,
    run_ev_logistic_adoption,
    run_ev_policy_driven,
    run_ev_tco_parity,
)
from .core.charging import generate_all_scenarios, generate_charging_profiles
from .core.v2g import compute_v2g_potential
from .core.degradation import compute_battery_degradation
from .core.grid_impact import assess_grid_impact, compute_fleet_evolution_metrics

__all__ = [
    "__version__",
    # Config
    "TransportContext",
    "EVMacroData",
    "DEFAULT_CATEGORIES",
    "DEFAULT_CATEGORY_SHARES",
    "DEFAULT_ENERGY_CONSUMPTION",
    "DEFAULT_CONNECTED_PROFILE",
    # Results
    "EVAdoptionCurve",
    "EVValidationData",
    "ChargingProfile",
    "ChargingScenarioResult",
    "V2GPotential",
    "DegradationResult",
    "GridImpactResult",
    # Adoption
    "run_ev_logistic_adoption",
    "run_ev_bass_diffusion",
    "run_ev_tco_parity",
    "run_ev_policy_driven",
    # Charging
    "generate_charging_profiles",
    "generate_all_scenarios",
    # V2G
    "compute_v2g_potential",
    # Degradation
    "compute_battery_degradation",
    # Grid impact
    "assess_grid_impact",
    "compute_fleet_evolution_metrics",
]


def __getattr__(name):
    """Lazy import for heavy modules."""
    if name == "fit_adoption_to_ev_config":
        from .core.integration import fit_adoption_to_ev_config
        return fit_adoption_to_ev_config
    if name in ("IEA_EV_STOCK", "get_iea_ev_stock"):
        from .data import iea
        return getattr(iea, name)
    if name in ("BNEF_BATTERY_COSTS", "project_battery_costs"):
        from .data import battery_cost
        return getattr(battery_cost, name)
    if name in ("fetch_charging_stations", "fetch_road_density"):
        from .data import osm
        return getattr(osm, name)
    if name in ("fetch_world_bank_ev_data", "fetch_imf_ev_data"):
        from .data import world_bank
        return getattr(world_bank, name)
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
