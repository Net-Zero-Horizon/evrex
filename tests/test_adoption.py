"""
Tests for evrex adoption models.

Covers: TransportContext, EVMacroData, EVAdoptionCurve, EVValidationData,
run_ev_logistic_adoption, run_ev_bass_diffusion, run_ev_tco_parity,
run_ev_policy_driven, fit_adoption_to_ev_config.
"""

import pytest

from evrex import (
    DEFAULT_CATEGORIES,
    DEFAULT_ENERGY_CONSUMPTION,
    EVAdoptionCurve,
    EVMacroData,
    EVValidationData,
    TransportContext,
    run_ev_bass_diffusion,
    run_ev_logistic_adoption,
    run_ev_policy_driven,
    run_ev_tco_parity,
)
from evrex.core.integration import fit_adoption_to_ev_config


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def transport():
    return TransportContext(
        fleet_by_category={"light": 1000, "medium": 200, "heavy": 50, "buses": 30},
        avg_daily_km={"light": 40, "medium": 80, "heavy": 150, "buses": 200},
        energy_consumption={"light": 18, "medium": 25, "heavy": 55, "buses": 80},
        charging_stations=50,
        road_density_km2=3.5,
        population=500_000,
    )


@pytest.fixture
def macro():
    return EVMacroData(
        country_iso="CUB",
        gdp_per_capita=10000,
        urbanization_pct=75,
        population=500_000,
        battery_cost_per_kwh=140,
        battery_cost_decline_rate=0.08,
        fuel_price_gasoline=1.20,
        fuel_price_diesel=1.10,
        electricity_tariff=0.15,
        maintenance_diff_annual=500,
    )


def _assert_valid_curve(curve, base_year, target_year):
    assert isinstance(curve, EVAdoptionCurve)
    assert curve.years[0] == base_year
    assert curve.years[-1] == target_year
    n = len(curve.years)
    assert len(curve.penetration) == n
    assert len(curve.total_fleet_ev) == n
    assert len(curve.energy_demand_gwh) == n
    assert len(curve.peak_charging_mw) == n
    assert all(0 <= p <= 1.0 for p in curve.penetration)
    assert all(f >= 0 for f in curve.total_fleet_ev)
    assert all(e >= 0 for e in curve.energy_demand_gwh)
    for cat, counts in curve.fleet_by_category.items():
        assert len(counts) == n
        assert all(c >= 0 for c in counts)


# ---------------------------------------------------------------------------
# Dataclass defaults
# ---------------------------------------------------------------------------


class TestDataclasses:
    def test_transport_context_defaults(self):
        ctx = TransportContext()
        assert "light" in ctx.fleet_by_category
        assert ctx.charging_stations == 0
        assert ctx.population == 1_000_000

    def test_ev_macro_data_defaults(self):
        m = EVMacroData()
        assert m.gdp_per_capita == 5000.0
        assert m.battery_cost_per_kwh == 140.0
        assert m.ice_phaseout_year == 0

    def test_ev_adoption_curve_has_method(self):
        c = EVAdoptionCurve(method="test", years=[2025], penetration=[0.1])
        assert c.method == "test"

    def test_ev_validation_data(self):
        vd = EVValidationData(label="IEA", years=[2020], ev_stock=[500], source="iea")
        assert vd.source == "iea"

    def test_default_categories_exist(self):
        assert "light" in DEFAULT_CATEGORIES
        assert "buses" in DEFAULT_CATEGORIES
        assert len(DEFAULT_CATEGORIES) == 4

    def test_default_energy_consumption(self):
        assert DEFAULT_ENERGY_CONSUMPTION["light"] < DEFAULT_ENERGY_CONSUMPTION["buses"]


# ---------------------------------------------------------------------------
# Logistic adoption
# ---------------------------------------------------------------------------


class TestLogisticAdoption:
    def test_returns_valid_curve(self, macro, transport):
        curve = run_ev_logistic_adoption(macro, transport, 2025, 2050)
        _assert_valid_curve(curve, 2025, 2050)
        assert curve.method == "logistic"

    def test_penetration_increases_with_gdp(self, transport):
        m_low = EVMacroData(gdp_per_capita=3000)
        m_high = EVMacroData(gdp_per_capita=30000)
        c_low = run_ev_logistic_adoption(m_low, transport, 2025, 2040)
        c_high = run_ev_logistic_adoption(m_high, transport, 2025, 2040)
        assert c_high.penetration[-1] >= c_low.penetration[-1]

    def test_penetration_increases_with_fuel_price(self, transport):
        m_low = EVMacroData(fuel_price_gasoline=0.50)
        m_high = EVMacroData(fuel_price_gasoline=3.00)
        c_low = run_ev_logistic_adoption(m_low, transport, 2025, 2040)
        c_high = run_ev_logistic_adoption(m_high, transport, 2025, 2040)
        assert c_high.penetration[-1] >= c_low.penetration[-1]

    def test_number_of_years(self, macro, transport):
        curve = run_ev_logistic_adoption(macro, transport, 2025, 2035)
        assert len(curve.years) == 11

    def test_custom_coefficients(self, macro, transport):
        coeffs = {"beta_0": -5.0, "beta_fuel_savings": 1.0}
        curve = run_ev_logistic_adoption(macro, transport, 2025, 2040, coefficients=coeffs)
        _assert_valid_curve(curve, 2025, 2040)

    def test_parameters_stored(self, macro, transport):
        curve = run_ev_logistic_adoption(macro, transport, 2025, 2040)
        assert "beta_0" in curve.parameters


# ---------------------------------------------------------------------------
# Bass diffusion
# ---------------------------------------------------------------------------


class TestBassDiffusion:
    def test_returns_valid_curve(self, transport):
        curve = run_ev_bass_diffusion(transport, 2025, 2050)
        _assert_valid_curve(curve, 2025, 2050)
        assert curve.method == "bass"

    def test_higher_q_faster_adoption(self, transport):
        c_low = run_ev_bass_diffusion(transport, 2025, 2050, q=0.20)
        c_high = run_ev_bass_diffusion(transport, 2025, 2050, q=0.60)
        assert c_high.penetration[-1] >= c_low.penetration[-1]

    def test_higher_p_faster_initial(self, transport):
        c_low = run_ev_bass_diffusion(transport, 2025, 2050, p=0.005)
        c_high = run_ev_bass_diffusion(transport, 2025, 2050, p=0.05)
        assert c_high.penetration[3] >= c_low.penetration[3]

    def test_monotonically_increasing(self, transport):
        curve = run_ev_bass_diffusion(transport, 2025, 2050)
        for i in range(1, len(curve.penetration)):
            assert curve.penetration[i] >= curve.penetration[i - 1]

    def test_initial_penetration_respected(self, transport):
        curve = run_ev_bass_diffusion(transport, 2025, 2050, initial_penetration=0.10)
        assert curve.penetration[0] >= 0.09

    def test_parameters_stored(self, transport):
        curve = run_ev_bass_diffusion(transport, 2025, 2050, p=0.03, q=0.45)
        assert curve.parameters["p"] == 0.03
        assert curve.parameters["q"] == 0.45

    def test_approaches_one(self, transport):
        curve = run_ev_bass_diffusion(transport, 2025, 2070, p=0.03, q=0.50)
        assert curve.penetration[-1] > 0.90


# ---------------------------------------------------------------------------
# TCO-parity
# ---------------------------------------------------------------------------


class TestTCOParity:
    def test_returns_valid_curve(self, macro, transport):
        curve = run_ev_tco_parity(macro, transport, 2025, 2050)
        _assert_valid_curve(curve, 2025, 2050)
        assert curve.method == "tco_parity"

    def test_cheaper_ev_higher_adoption(self, transport):
        m_expensive = EVMacroData(
            ev_price={"light": 60000, "medium": 80000, "heavy": 200000, "buses": 500000},
        )
        m_cheap = EVMacroData(
            ev_price={"light": 20000, "medium": 30000, "heavy": 70000, "buses": 180000},
        )
        c_exp = run_ev_tco_parity(m_expensive, transport, 2025, 2040)
        c_cheap = run_ev_tco_parity(m_cheap, transport, 2025, 2040)
        assert c_cheap.penetration[-1] > c_exp.penetration[-1]

    def test_battery_decline_helps(self, transport):
        m_no = EVMacroData(battery_cost_decline_rate=0.0)
        m_yes = EVMacroData(battery_cost_decline_rate=0.12)
        c_no = run_ev_tco_parity(m_no, transport, 2025, 2050)
        c_yes = run_ev_tco_parity(m_yes, transport, 2025, 2050)
        assert c_yes.penetration[-1] >= c_no.penetration[-1]

    def test_subsidy_increases_adoption(self, transport):
        m_no = EVMacroData(ev_subsidy_pct=0.0)
        m_sub = EVMacroData(ev_subsidy_pct=0.30)
        c_no = run_ev_tco_parity(m_no, transport, 2025, 2040)
        c_sub = run_ev_tco_parity(m_sub, transport, 2025, 2040)
        assert c_sub.penetration[-1] >= c_no.penetration[-1]


# ---------------------------------------------------------------------------
# Policy-driven
# ---------------------------------------------------------------------------


class TestPolicyDriven:
    def test_returns_valid_curve(self, macro, transport):
        curve = run_ev_policy_driven(macro, transport, 2025, 2050)
        _assert_valid_curve(curve, 2025, 2050)
        assert curve.method == "policy_driven"

    def test_ice_ban_reaches_high_penetration(self, transport):
        m = EVMacroData(ice_phaseout_year=2035)
        curve = run_ev_policy_driven(m, transport, 2025, 2060)
        assert curve.penetration[-1] > 0.70

    def test_no_ban_slow_adoption(self, transport):
        m = EVMacroData(ice_phaseout_year=0, emission_target_pct=0)
        curve = run_ev_policy_driven(m, transport, 2025, 2050)
        assert curve.penetration[-1] < 0.50

    def test_emission_target_drives_adoption(self, transport):
        m_low = EVMacroData(ice_phaseout_year=0, emission_target_pct=20)
        m_high = EVMacroData(ice_phaseout_year=0, emission_target_pct=80)
        c_low = run_ev_policy_driven(m_low, transport, 2025, 2050)
        c_high = run_ev_policy_driven(m_high, transport, 2025, 2050)
        assert c_high.penetration[-1] > c_low.penetration[-1]

    def test_scrappage_model_lag(self, transport):
        m = EVMacroData(ice_phaseout_year=2035)
        curve = run_ev_policy_driven(m, transport, 2025, 2060)
        ban_idx = curve.years.index(2035)
        assert curve.penetration[ban_idx] < 1.0

    def test_parameters_contain_sales_share(self, macro, transport):
        curve = run_ev_policy_driven(macro, transport, 2025, 2040)
        assert "sales_share_trajectory" in curve.parameters


# ---------------------------------------------------------------------------
# Fleet breakdown
# ---------------------------------------------------------------------------


class TestFleetBreakdown:
    def test_fleet_sum_close_to_total(self, transport):
        curve = run_ev_bass_diffusion(transport, 2025, 2040)
        for i in range(len(curve.years)):
            cat_sum = sum(
                curve.fleet_by_category[cat][i] for cat in curve.fleet_by_category
            )
            assert abs(cat_sum - curve.total_fleet_ev[i]) <= len(curve.fleet_by_category)

    def test_energy_demand_positive_when_fleet_positive(self, transport):
        curve = run_ev_bass_diffusion(transport, 2025, 2040)
        for i in range(len(curve.years)):
            if curve.total_fleet_ev[i] > 0:
                assert curve.energy_demand_gwh[i] > 0

    def test_peak_charging_scales_with_fleet(self, transport):
        c = run_ev_bass_diffusion(transport, 2025, 2035)
        assert c.peak_charging_mw[-1] >= c.peak_charging_mw[0]

    def test_all_categories_present(self, transport):
        curve = run_ev_bass_diffusion(transport, 2025, 2040)
        for cat in DEFAULT_CATEGORIES:
            assert cat in curve.fleet_by_category


# ---------------------------------------------------------------------------
# fit_adoption_to_ev_config
# ---------------------------------------------------------------------------


class TestFitAdoptionToConfig:
    def test_returns_dict(self, transport):
        curve = run_ev_bass_diffusion(transport, 2025, 2050)
        config = fit_adoption_to_ev_config(curve, transport, num_nodes=2)
        assert isinstance(config, dict)

    def test_has_required_keys(self, transport):
        curve = run_ev_bass_diffusion(transport, 2025, 2050)
        config = fit_adoption_to_ev_config(curve, transport, num_nodes=2)
        for key in ("base_year", "target_year", "categories", "initial_soc", "fitted_s_curve", "method"):
            assert key in config

    def test_categories_count(self, transport):
        curve = run_ev_bass_diffusion(transport, 2025, 2050)
        config = fit_adoption_to_ev_config(curve, transport, num_nodes=2)
        assert len(config["categories"]) == 4

    def test_initial_soc_per_node(self, transport):
        curve = run_ev_bass_diffusion(transport, 2025, 2050)
        config = fit_adoption_to_ev_config(curve, transport, num_nodes=3)
        assert len(config["initial_soc"]) == 3
        assert all(soc >= 0 for soc in config["initial_soc"])

    def test_fitted_s_curve_reasonable(self, transport):
        curve = run_ev_bass_diffusion(transport, 2025, 2050)
        config = fit_adoption_to_ev_config(curve, transport, num_nodes=1)
        sc = config["fitted_s_curve"]
        assert sc["max_adoption"] > 0
        assert 0 < sc["growth_rate"] < 1
        assert 0.1 <= sc["mid_point_fraction"] <= 0.9

    def test_node_demand_fractions_applied(self, transport):
        curve = run_ev_bass_diffusion(transport, 2025, 2050)
        config = fit_adoption_to_ev_config(
            curve, transport, num_nodes=3, node_demand_fractions=[0.6, 0.3, 0.1],
        )
        light = config["categories"]["light"]
        assert light["quantity"][0] > light["quantity"][2]

    def test_v2g_params_applied(self, transport):
        curve = run_ev_bass_diffusion(transport, 2025, 2050)
        config = fit_adoption_to_ev_config(
            curve, transport, num_nodes=1,
            v2g_params={"light": {"v2g_power": 10.0, "v2g_participation": 0.5}},
        )
        assert config["categories"]["light"]["v2g_power"] == 10.0

    def test_empty_curve_returns_empty(self, transport):
        curve = EVAdoptionCurve(method="test", years=[], penetration=[])
        config = fit_adoption_to_ev_config(curve, transport, num_nodes=1)
        assert config == {}


# ---------------------------------------------------------------------------
# Cross-method comparison
# ---------------------------------------------------------------------------


class TestCrossMethodComparison:
    def test_all_methods_produce_valid_curves(self, macro, transport):
        curves = [
            run_ev_logistic_adoption(macro, transport, 2025, 2040),
            run_ev_bass_diffusion(transport, 2025, 2040),
            run_ev_tco_parity(macro, transport, 2025, 2040),
            run_ev_policy_driven(macro, transport, 2025, 2040),
        ]
        for curve in curves:
            _assert_valid_curve(curve, 2025, 2040)

    def test_all_methods_have_distinct_names(self, macro, transport):
        methods = {
            run_ev_logistic_adoption(macro, transport, 2025, 2040).method,
            run_ev_bass_diffusion(transport, 2025, 2040).method,
            run_ev_tco_parity(macro, transport, 2025, 2040).method,
            run_ev_policy_driven(macro, transport, 2025, 2040).method,
        }
        assert len(methods) == 4
