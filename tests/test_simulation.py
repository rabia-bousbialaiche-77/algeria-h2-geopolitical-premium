import numpy as np

from h2risk.simulation import run


def test_reproducible_with_seed():
    a = run(2000, seed=1)
    b = run(2000, seed=1)
    assert a["scenarios"][("pipeline", "S3")]["grp"]["mean"] == b["scenarios"][("pipeline", "S3")]["grp"]["mean"]


def test_decomposition_adds_up():
    r = run(2000, seed=2)
    for key, d in r["scenarios"].items():
        total = d["grp"]["mean"]
        assert np.isclose(d["financing_contrib"] + d["insurance_contrib"], total, atol=1e-9)


def test_grp_increases_with_escalation():
    r = run(2000, seed=3)
    g = [r["scenarios"][("pipeline", s)]["grp"]["mean"] for s in ("S0", "S1", "S2", "S3")]
    assert all(x < y for x, y in zip(g, g[1:]))


def test_baseline_grp_is_zero():
    r = run(500, seed=4)
    assert r["scenarios"][("pipeline", "S0")]["grp"]["mean"] == 0.0
