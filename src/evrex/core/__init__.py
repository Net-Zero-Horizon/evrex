"""
Core computation modules for EV fleet assessment.

- adoption: Four EV adoption modeling methods
- charging: Charging demand profile generation
- v2g: Vehicle-to-Grid potential assessment
- degradation: Battery degradation modeling
- grid_impact: Grid impact assessment
- integration: Adoption curve to config conversion
"""

from .adoption import (
    run_ev_bass_diffusion,
    run_ev_logistic_adoption,
    run_ev_policy_driven,
    run_ev_tco_parity,
)
from .charging import generate_all_scenarios, generate_charging_profiles
from .degradation import compute_battery_degradation
from .grid_impact import assess_grid_impact, compute_fleet_evolution_metrics
from .integration import fit_adoption_to_ev_config
from .v2g import compute_v2g_potential

__all__ = [
    "run_ev_logistic_adoption",
    "run_ev_bass_diffusion",
    "run_ev_tco_parity",
    "run_ev_policy_driven",
    "generate_charging_profiles",
    "generate_all_scenarios",
    "compute_v2g_potential",
    "compute_battery_degradation",
    "assess_grid_impact",
    "compute_fleet_evolution_metrics",
    "fit_adoption_to_ev_config",
]
