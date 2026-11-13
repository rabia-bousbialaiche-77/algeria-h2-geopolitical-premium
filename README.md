# Algerian green hydrogen: export costs and security premiums under Strait of Hormuz disruptions

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.24182547.svg)](https://doi.org/10.5281/zenodo.24182547)

Replication code and Supplementary Material for:

> Bousbia Laiche, R., Letaim, F., & Cuce, E. *Demand for Algerian green hydrogen in the context of geopolitical supply chain challenges: A case study on modelling export costs and security premiums under supply disruptions through the Strait of Hormuz.* (manuscript under review)

The repository contains a transparent bottom-up model of the delivered cost of Algerian green hydrogen, the scenario Monte Carlo simulation, the competitor break-even analysis, and the econometric scripts (DCC-MIDAS-X, TVP-VAR frequency connectedness, mediation with sensitivity analysis, IV robustness checks). Every numerical input is stored in `params/` together with its source; inputs without an external source are explicitly marked **AUTHOR ASSUMPTION**.

## Quick start

```bash
pip install -r requirements.txt
python src/mcc_simulation.py --calibration 2023      # current (2023) sourced costs
python src/mcc_simulation.py --calibration 2030      # 2030 electrolyser-cost projection
python -m pytest -q                                   # 12 unit tests
```

A full run (10,000 draws, five scenarios, two routes, five competitors) takes about one second. Each run writes `outputs/calibration_<year>/run_log.json` with the seed, the number of draws, software versions and the SHA-256 hash of all parameter files.

## Repository structure

```
params/
  production.yaml          techno-economic, transport and vessel parameters (2023 costs)
  production_2030.yaml     same, with the 2030 electrolyser-cost projection
  scenarios.yaml           S0, S1, S1a, S2, S3 (manuscript Table 6) and route exposure
  competitors.csv          competitor cost gaps, WACC betas and route exposure
  data_dictionary.csv      every variable: definition, unit, frequency, source, status
src/
  h2risk/cost_model.py     Eqs. S1–S9 (delivered cost by route)
  h2risk/simulation.py     Monte Carlo, GRP decomposition, break-even GPR
  mcc_simulation.py        entry point; writes all tables and figures
  build_panel.py           monthly panel and quarterly synthetic cost index
  econometrics/dcc_midas_x.py   two-step QML DCC-MIDAS-X estimator
R/                         TVP-VAR frequency connectedness; mediation sensitivity
stata/robustness_checks.do IV (ivreg2, weakivtest), Bai–Perron breaks
notebooks/data_cleaning.ipynb
scripts/download_data.py   public inputs (GPR, FRED series)
data/raw/war_risk_quotes.csv          hand-collected war-risk premium quotes with sources
tests/                     unit tests (cost model, simulation, estimator)
docs/                      Supplementary Material (docx), manuscript Figures 1–5, references
```

## Map from the manuscript to the code

| Manuscript | Produced by | Output |
|---|---|---|
| Eqs. (1)–(2), Table 5 | `src/h2risk/cost_model.py` | — |
| Table 6 (scenarios) | `params/scenarios.yaml` | — |
| Table 11 (decomposition) | `src/mcc_simulation.py` | `table_S6_grp_decomposition.csv` |
| Table 12 (distribution) | `src/mcc_simulation.py` | `table_S5_lcoh_by_scenario.csv` |
| Table 13 (competitors, thresholds) | `src/mcc_simulation.py` | `table_S7_competitors.csv`, `table_S9_breakeven_sensitivity.csv` |
| Table 14 (security value) | `src/mcc_simulation.py` | `table_S8_security_value.csv` |
| Eqs. (3)–(4), Model I | `src/econometrics/dcc_midas_x.py` | — |
| Eqs. (5)–(6), Model II | `R/tvp_var_frequency.R` | `outputs/econometrics/` |
| Eqs. (7)–(9), Model III; Table 7 | `R/mediation_sensitivity.R`, `stata/robustness_checks.do` | `outputs/econometrics/` |
| Figures 1–5 | authors' figures of Tables 3 and 11–14 | `docs/figures/` |
| Supplementary Material | generated from `outputs/calibration_2023/` and `params/` | `docs/Supplementary_Material.docx` |

## Data availability

Public series are downloaded by `scripts/download_data.py` (GPR: Caldara & Iacoviello; global EPU and Brent: FRED). Licensed or author-specified series (EU ETS futures, a financing-cost proxy, the climate risk index) must be placed in `data/raw/` as described in `params/data_dictionary.csv`; they are not redistributed. Algeria has no actively traded external sovereign bond, so the financing channel requires a documented proxy. War-risk premiums are sparse market quotes (`data/raw/war_risk_quotes.csv`) with their sources.

## Important modelling notes

* The synthetic `LCOH_Export` index is computed with the cost model, so it moves mechanically with the financing proxy and the war-risk premium. Channel shares obtained from it are accounting contributions, not causal effects (Supplementary S2.3 and S7).
* Route exposure is explicit: Algerian pipeline and Mediterranean shipping routes carry no listed-area war-risk premium by default; `spillover_share` in `scenarios.yaml` tests regional repricing.
* Competitor results depend on the WACC betas and S0 gaps in `competitors.csv`, which are author assumptions; `table_S9_breakeven_sensitivity.csv` reports the break-evens for two values of the Algerian WACC beta.
* The R and Stata scripts could not be executed in the build environment; record `sessionInfo()` / Stata version when running them.

## Citation

Software archive (all versions, resolves to the latest): https://doi.org/10.5281/zenodo.24182547  
Version v1.0.0: https://doi.org/10.5281/zenodo.24182548

> Bousbia Laiche, R., Letaim, F., & Cuce, E. (2026). *Replication code and Supplementary Material: Algerian green hydrogen export costs and security premiums under Strait of Hormuz disruptions* (Version v1.0.0) [Computer software]. Zenodo. https://doi.org/10.5281/zenodo.24182548

New GitHub releases are archived automatically by Zenodo as new versions under the same concept DOI.

## License

Code: MIT. Documentation, parameter files and figures: CC BY 4.0. See `LICENSE`.
