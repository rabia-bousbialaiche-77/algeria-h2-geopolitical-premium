import numpy as np
from h2risk import cost_model as cm
from h2risk.params import central_production


def test_crf_matches_annuity_formula():
    assert abs(float(cm.crf(0.08, 20)) - 0.10185) < 1e-4


def test_shipping_cost_increases_with_distance():
    p = central_production()
    v = np.array([5.0])
    assert cm.shipping_cost(p, 1000, v)[0] < cm.shipping_cost(p, 5000, v)[0] < cm.shipping_cost(p, 10000, v)[0]


def test_nh3_chain_reproduces_irena_at_10000_km():
    p = central_production()
    v = np.array([5.0])
    fixed = cm.nh3_fixed_cost(p, v)
    total = fixed + cm.shipping_cost(p, 10000 / cm.NM_TO_KM, v)
    assert abs(total[0] - p["nh3_chain_10k_usd_per_kg"][0]) < 1e-9


def test_insurance_linear_in_premium():
    p = central_production()
    i1 = cm.insurance_cost(p, {"red_sea": 0.01}, ["red_sea"])
    i2 = cm.insurance_cost(p, {"red_sea": 0.02}, ["red_sea"])
    assert np.allclose(i2, 2 * i1)


def test_rerouting_picks_cheaper_route():
    p = central_production()
    routes = [{"name": "Suez", "nm": 5623, "canal": "suez", "areas": ["red_sea"]},
              {"name": "Cape", "nm": 10406, "canal": "none", "areas": []}]
    low = cm.delivered_cost(p, np.array([0.06]), np.array([1900.0]), "ship", {"red_sea": np.array([0.0005])}, routes)
    high = cm.delivered_cost(p, np.array([0.06]), np.array([1900.0]), "ship", {"red_sea": np.array([0.05])}, routes)
    assert low["route"][0] == 0 and high["route"][0] == 1


def test_electricity_cost_uses_the_clipped_yield():
    """The PV cost is spread over the energy that reaches the electrolyser (v2.1.0)."""
    p = central_production()
    y = np.array([1901.0])
    annual = p["pv_capex_usd_per_kw"] * cm.crf(0.08, p["pv_lifetime_yr"]) + p["pv_fixed_om_usd_per_kw_yr"]
    assert np.allclose(cm.pv_lcoe(p, np.array([0.08]), y), annual / (1901.0 * 0.97))
    assert np.allclose(cm.full_load_hours(p, y), 1901.0 * 0.97 / 0.7)
    total, parts = cm.lcoh_production(p, np.array([0.08]), y, detail=True)
    assert abs(parts["electrolyser"][0] - 3.318) < 5e-3 and abs(parts["electricity"][0] - 2.386) < 5e-3
    assert abs(total[0] - 5.739) < 5e-3


def test_conversion_cost_does_not_move_with_the_scenario_wacc():
    """The 10,000 km reference voyage is valued at the baseline production cost (v2.1.0), so the
    ammonia premium of a route without war risk is the production premium times (1 + fuel share)."""
    p = central_production()
    y = np.array([1901.0])
    route = [{"name": "Arzew", "nm": 1640, "canal": "none", "areas": []}]
    base = cm.delivered_cost(p, np.array([0.08]), y, "ship", {}, route, wacc_base=np.array([0.08]))
    shock = cm.delivered_cost(p, np.array([0.108]), y, "ship", {}, route, wacc_base=np.array([0.08]))
    d_prod = shock["production"][0] - base["production"][0]
    fuel_share = 2 * 0.01 * 1640 * cm.NM_TO_KM / 5000.0
    assert abs((shock["total"][0] - base["total"][0]) - d_prod * (1 + fuel_share)) < 1e-9


def test_midstream_variant_only_changes_scenario_costs():
    p = central_production()
    y = np.array([1901.0])
    w0, w1 = np.array([0.08]), np.array([0.108])
    assert np.allclose(cm.delivered_cost(p, w0, y, "pipeline", {}, wacc_base=w0, midstream=True)["total"],
                       cm.delivered_cost(p, w0, y, "pipeline", {}, wacc_base=w0)["total"])
    assert (cm.delivered_cost(p, w1, y, "pipeline", {}, wacc_base=w0, midstream=True)["total"]
            > cm.delivered_cost(p, w1, y, "pipeline", {}, wacc_base=w0)["total"])
