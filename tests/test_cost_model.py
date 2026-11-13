import numpy as np
import pytest

from h2risk import cost_model as cm
from h2risk.params import central_production


def test_crf_known_value():
    # 8% over 20 years -> 0.101852...
    assert cm.crf(0.08, 20) == pytest.approx(0.1018522, rel=1e-6)


def test_pipeline_unit_conversion():
    p = central_production()
    # 14 EUR/MWh * 33.33 kWh/kg / 1000 * 1.08
    assert cm.transport_pipeline(p)[0] == pytest.approx(14 * 33.33 / 1000 * 1.08)


def test_h2_cargo_from_ammonia_carrier():
    p = central_production()
    kg = cm.h2_cargo_kg(p)[0]
    assert 10.5e6 < kg < 11.5e6          # about 11,000 t H2-equivalent per 93,000 m3 voyage


def test_war_risk_conversion_one_percent():
    p = central_production()
    usd_per_kg = cm.war_risk_cost(p, np.array([0.01]), periods=1, spillover=0)[0]
    assert usd_per_kg == pytest.approx(0.01 * 125e6 / cm.h2_cargo_kg(p)[0])


def test_wacc_increases_cost():
    p = central_production()
    lo = cm.lcoh_production(p, p["wacc_base"])[0]
    hi = cm.lcoh_production(p, p["wacc_base"] + 0.02)[0]
    assert hi > lo


def test_pipeline_has_no_war_risk_cost():
    p = central_production()
    out = cm.delivered_cost(p, "pipeline", np.array([0.0]), np.array([0.05]))
    assert out["insurance"][0] == 0.0
