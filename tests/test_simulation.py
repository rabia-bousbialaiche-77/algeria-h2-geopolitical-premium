import numpy as np
from h2risk.simulation import run


def test_grp_is_zero_in_baseline_and_monotone_on_path():
    r = run(2000, 3)
    g = [r["grp"][("Algeria", "pipeline", s)]["grp"]["mean"] for s in ("S0", "S1", "S2", "S3")]
    assert g[0] == 0.0 and g[1] < g[2] < g[3]


def test_shapley_parts_add_up():
    r = run(2000, 3)
    for k, v in r["grp"].items():
        assert abs(v["financing"] + v["insurance"] - v["grp"]["mean"]) < 1e-9


def test_algeria_routes_have_no_insurance_exposure():
    r = run(2000, 3)
    assert abs(r["grp"][("Algeria", "pipeline", "S3")]["insurance"]) < 1e-12
    assert abs(r["grp"][("Algeria", "ship", "S3")]["insurance"]) < 1e-12


def test_reproducible_with_seed():
    a, b = run(1000, 11), run(1000, 11)
    assert a["costs"][("Oman", "ship", "S3")]["total"]["p50"] == b["costs"][("Oman", "ship", "S3")]["total"]["p50"]


def test_algerian_ammonia_premium_is_not_below_the_pipeline_premium():
    """With the reference voyage valued at the baseline cost, shipping adds fuel to the premium."""
    r = run(2000, 3)
    for s in ("S1", "S2", "S3", "H26"):
        assert r["grp"][("Algeria", "ship", s)]["grp"]["p50"] >= r["grp"][("Algeria", "pipeline", s)]["grp"]["p50"]


def test_shapley_interaction_is_zero_without_rerouting():
    r = run(2000, 3)
    assert abs(r["grp"][("Chile", "ship", "S3")]["interaction"]) < 1e-12
    assert r["grp"][("Oman", "ship", "S3")]["interaction"] > 0
