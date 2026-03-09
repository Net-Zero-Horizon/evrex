# EVreX - EV Resource eXchange

[![Tests](https://github.com/msotocalvo/evrex/actions/workflows/tests.yml/badge.svg)](https://github.com/msotocalvo/evrex/actions/workflows/tests.yml)
[![DOI](https://zenodo.org/badge/1176473313.svg)](https://doi.org/10.5281/zenodo.18918073)

A Python library for electric vehicle fleet electrification assessment,
adoption modeling, V2G potential analysis, battery degradation modeling,
and grid impact assessment.

## Installation

```bash
pip install evrex
```

With optional dependencies:

```bash
pip install evrex[fetch]   # OSM, World Bank, IMF data fetchers
pip install evrex[viz]     # Matplotlib visualization
pip install evrex[all]     # Everything
```

## Quick Start

```python
from evrex import (
    TransportContext,
    EVMacroData,
    run_ev_bass_diffusion,
    run_ev_tco_parity,
    generate_charging_profiles,
    compute_v2g_potential,
    compute_battery_degradation,
    assess_grid_impact,
)

# Define transport context
transport = TransportContext(
    fleet_by_category={"light": 5000, "medium": 800, "heavy": 200, "buses": 100},
    charging_stations=120,
    population=500_000,
)

# Run Bass diffusion adoption model
curve = run_ev_bass_diffusion(transport, base_year=2025, target_year=2050)
print(f"EV penetration by 2050: {curve.penetration[-1]:.1%}")
print(f"Peak charging demand: {curve.peak_charging_mw[-1]:.1f} MW")

# Battery degradation analysis
deg = compute_battery_degradation(v2g_cycles_per_day=0.5, chemistry="LFP")
print(f"Degradation: {deg.total_degradation_pct_per_year:.2f}%/year")
print(f"Break-even V2G rate: ${deg.breakeven_compensation:.0f}/MWh")
```

## Adoption Models

Four methods for projecting EV fleet evolution:

| Method | Function | Key Drivers |
|--------|----------|-------------|
| Logistic | `run_ev_logistic_adoption()` | GDP, fuel price, EV cost, infrastructure |
| Bass Diffusion | `run_ev_bass_diffusion()` | Innovation (p) and imitation (q) |
| TCO-Parity | `run_ev_tco_parity()` | Total cost of ownership comparison |
| Policy-Driven | `run_ev_policy_driven()` | ICE bans, emission targets, scrappage |

## Modules

- `evrex.core` - Adoption models, charging profiles, V2G, degradation, grid impact
- `evrex.data` - OSM, World Bank, IMF, IEA (bundled), BNEF (bundled) data

## License

MIT
