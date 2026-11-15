# Pricing geopolitical risk into delivered green hydrogen costs (Algeria–EU, Strait of Hormuz)

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.24182547.svg)](https://doi.org/10.5281/zenodo.24182547)

Replication code, data and Supplementary Material for:

> Bousbia Laiche, R., Letaim, F., & Cuce, E. *Pricing geopolitical risk into delivered green hydrogen costs: a route-explicit scenario framework for Algeria–EU supply tested on the 2026 Strait of Hormuz closure.* (manuscript submitted to the International Journal of Hydrogen Energy)

Version 2.0.0 replaces the econometric design of v1.0.0 with a calibrated scenario framework. The model is a deterministic, route-explicit delivered-cost model for hydrogen supplied to the EU from Algeria (pipeline and ammonia) and from Morocco, Egypt, Oman, Australia and Chile (ammonia). It prices two shock channels, project financing (C1) and war-risk insurance with rerouting (C2), propagates parameter uncertainty with a 10,000-draw Monte Carlo simulation (seed 20251113, common random numbers), and tests the ex-ante scenarios against the observed 2026 Strait of Hormuz closure.

**Version 2.1.0** (revision after review) corrects two accounting conventions and adds bounding variants; see `CHANGELOG.md`. Headline results: Algerian pipeline hydrogen costs 6.34 USD/kg in the baseline (5th-95th percentile 5.18-7.62); a full blockade (S3) adds 1.09 USD/kg (0.83-1.41), and the conditions observed in 2026 (H26) add 0.09 USD/kg.

## Quick start

```bash
pip install -r requirements.txt
python src/run_model.py --calibration 2023      # tables, figures, Sobol indices, run log
python src/run_model.py --calibration 2030      # 2030 electrolyser cost
pytest tests
```

Outputs are written to `outputs/calibration_<year>/`. A full 2023 run takes well under a minute.

## Repository structure

```
params/production.yaml        techno-economic parameters with distributions and sources (2023)
params/production_2030.yaml   same, with the 2030 electrolyser cost
params/countries.yaml         sites, PV yields, default spreads, CRPs, ports and routes
params/scenarios.yaml         S0, S1, S1a, S2, S3 (ex ante) and H26 (ex post, 2026)
data/raw/observed_2026.csv    observed 2026 war-risk premiums, spreads and prices, with URLs
src/h2risk/cost_model.py      delivered-cost model (manuscript Eqs. 1-6)
src/h2risk/simulation.py      WACC rule (Eq. 7), Monte Carlo, GRP (Eq. 8), Shapley split (Eq. 9), security premium (Eq. 10), break-even
src/h2risk/sensitivity.py     Sobol indices (SALib)
src/run_model.py              writes every table and figure of the article and the Supplementary Material
scripts/fetch_gsa.py          Global Solar Atlas PVOUT at the sites (provenance)
scripts/route_distances.py    sea distances with searoute (provenance)
scripts/make_supplementary.py writes docs/Supplementary_Material.md from the outputs
tests/                        unit tests of the cost model and the simulation
docs/Supplementary_Material.docx (and .md), docs/REFERENCES.md, docs/figures/
CHANGELOG.md                  changes between versions
extensions/                   v1.0.0 econometric code (DCC-MIDAS-X, TVP-VAR, mediation); not used in v2
```

## Map from the article to the outputs

| Article | Output |
|---|---|
| Table 3 (scenarios) | `params/scenarios.yaml` |
| Table 4, Fig. 2 | `table_algeria_scenarios.csv`, `fig2_cost_distributions` |
| Fig. 3 | `fig3_channel_decomposition` |
| Table 5, Fig. 4, Section 4.3 | `table_competitors.csv`, `table_baseline_gap_components.csv`, `table_breakeven.csv`, `fig4_competitor_differentials` |
| Table 6, Section 4.4 | `table_sobol.csv`, `table_variants.csv`, `convergence.csv` |
| Table 7, Fig. 5 | `table_validation_2026.csv`, `fig5_validation_2026` |
| Numbers quoted in the text | `results_full.json` (unrounded statistics), `summary.json` |
| Supplementary Tables S1-S12 | the files above, both calibrations (`scripts/make_supplementary.py`) |

## Data

All inputs are public and documented in `params/` and `docs/REFERENCES.md`; values without an external source are marked **AUTHOR ASSUMPTION**. Fig. 5 uses the Geopolitical Risk index of Caldara and Iacoviello (2022), which is not redistributed: download `data_gpr_export.xls` from https://www.matteoiacoviello.com/gpr.htm and save it as `data/raw/gpr_export.xls`. Without it the model runs and Fig. 5 omits the monthly GPR series. War-risk premiums for 2026 are broker and trade-press quotes, not transaction data.

## Modelling notes

* Algeria has no traded external sovereign bond; its default spread is the synthetic estimate of Damodaran (2026).
* The scenario WACC uplift is defined for Algeria and scaled to other exporters by the ratio of default spreads. This rule is decisive for the competitor results; `table_variants.csv` reports alternatives.
* In the ex-ante scenarios one war-risk premium applies to all listed areas; the 2026 test shows this was too uniform.
* Channels C3 (buyer preferences) and C4 (fossil-input prices) are not priced.
* The financing shock acts on PV and electrolysis only. The variant "midstream capital exposed to exporter WACC" in `table_variants.csv` is an upper bound on what this leaves out.
* The PV electricity cost is divided by the yield after clipping, and the 10,000 km reference voyage of the ammonia chain is valued at the baseline production cost (both changed in v2.1.0).
* The PV yield factor is one draw for all sites; `table_variants.csv` reports a variant with independent factors.

## Citation

Software archive (all versions): https://doi.org/10.5281/zenodo.24182547  
Version v2.1.0 (used in the revised article): DOI assigned by Zenodo when the v2.1.0 release is published  
Version v2.0.0: https://doi.org/10.5281/zenodo.24210196

## License

Code: MIT. Documentation, parameter files and figures: CC BY 4.0. See `LICENSE`.
