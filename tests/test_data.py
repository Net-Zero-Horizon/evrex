"""
Tests for evrex data modules (bundled IEA, BNEF data).
"""

import pytest

from evrex.data.iea import IEA_EV_STOCK, get_iea_ev_stock
from evrex.data.battery_cost import BNEF_BATTERY_COSTS, project_battery_costs


class TestIEAData:
    def test_has_countries(self):
        assert len(IEA_EV_STOCK) >= 15

    def test_china_data_exists(self):
        assert "CHN" in IEA_EV_STOCK
        assert 2024 in IEA_EV_STOCK["CHN"]

    def test_get_iea_ev_stock_valid(self):
        data = get_iea_ev_stock("USA")
        assert data.source == "iea"
        assert len(data.years) > 0
        assert len(data.ev_stock) == len(data.years)
        # Values in units (not thousands)
        assert data.ev_stock[-1] > 1000

    def test_get_iea_ev_stock_unknown_country(self):
        data = get_iea_ev_stock("XYZ")
        assert data.years == []
        assert data.ev_stock == []

    def test_stock_monotonically_increasing(self):
        for country, data in IEA_EV_STOCK.items():
            years = sorted(data.keys())
            values = [data[y] for y in years]
            for i in range(1, len(values)):
                assert values[i] >= values[i - 1], f"{country} not monotonic at {years[i]}"


class TestBNEFData:
    def test_has_historical_data(self):
        assert 2013 in BNEF_BATTERY_COSTS
        assert 2024 in BNEF_BATTERY_COSTS

    def test_costs_declining_trend(self):
        assert BNEF_BATTERY_COSTS[2024] < BNEF_BATTERY_COSTS[2013]

    def test_project_battery_costs_includes_historical(self):
        traj = project_battery_costs()
        assert 2013 in traj
        assert 2024 in traj

    def test_project_battery_costs_projects_forward(self):
        traj = project_battery_costs(target_year=2040)
        assert 2040 in traj
        assert traj[2040] < traj[2024]

    def test_project_battery_costs_floor(self):
        traj = project_battery_costs(annual_decline_rate=0.20, target_year=2060, floor_cost=50.0)
        assert traj[2060] >= 50.0

    def test_project_battery_costs_custom_decline(self):
        traj_slow = project_battery_costs(annual_decline_rate=0.03, target_year=2040)
        traj_fast = project_battery_costs(annual_decline_rate=0.10, target_year=2040)
        assert traj_fast[2040] < traj_slow[2040]
