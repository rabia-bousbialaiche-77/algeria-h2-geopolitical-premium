"""Headline numbers quoted in the article (version 2.1.0), recomputed with the full run."""
import pytest
from h2risk.simulation import run


@pytest.fixture(scope="module")
def res():
    return run(10_000, 20251113)


def _grp(res, country, mode, s, stat="p50"):
    return res["grp"][(country, mode, s)]["grp"][stat]


def test_algerian_baseline_cost(res):
    c = res["costs"][("Algeria", "pipeline", "S0")]["total"]
    assert (round(c["p50"], 2), round(c["p05"], 2), round(c["p95"], 2)) == (6.34, 5.18, 7.62)
    assert round(res["costs"][("Algeria", "ship", "S0")]["total"]["p50"], 2) == 9.10


def test_premiums(res):
    assert round(_grp(res, "Algeria", "pipeline", "S3"), 2) == 1.09
    assert round(_grp(res, "Algeria", "pipeline", "S3", "p05"), 2) == 0.83
    assert round(_grp(res, "Algeria", "pipeline", "S3", "p95"), 2) == 1.41
    assert round(_grp(res, "Algeria", "ship", "S3"), 2) == 1.11
    assert round(_grp(res, "Algeria", "pipeline", "H26"), 2) == 0.09
    assert round(100 * res["grp"][("Algeria", "pipeline", "S3")]["pct_of_S0_mean"], 1) == 17.3


def test_competitor_gaps(res):
    g = res["gaps"]
    assert round(g[("Chile", "pipeline")]["S0"]["gap"]["p50"], 2) == 1.26
    assert round(g[("Egypt", "pipeline")]["S0"]["gap"]["p50"], 2) == 4.10
    assert round(100 * g[("Chile", "pipeline")]["S3"]["share_algeria_cheaper"]) == 71
    assert round(res["grp"][("Oman", "ship", "S3")]["insurance"], 2) == 0.21


def test_central_decomposition(res):
    c = res["central"]
    assert round(c["wacc_8pct"]["total"], 2) == 5.74 and round(c["wacc_11pct"]["total"], 2) == 6.91
