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
