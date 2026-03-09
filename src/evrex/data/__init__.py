"""
Data fetchers for EV fleet assessment.

- osm: Charging station and road network data from OpenStreetMap
- world_bank: GDP, urbanization, population from World Bank and IMF
- iea: Bundled IEA Global EV Data Explorer (2010-2024)
- battery_cost: Bundled BNEF battery pack cost trajectory
"""

from .battery_cost import BNEF_BATTERY_COSTS, project_battery_costs
from .iea import IEA_EV_STOCK, get_iea_ev_stock

__all__ = [
    "BNEF_BATTERY_COSTS",
    "project_battery_costs",
    "IEA_EV_STOCK",
    "get_iea_ev_stock",
]
