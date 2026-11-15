"""Write docs/Supplementary_Material.md from the model outputs.

Run after src/run_model.py for both calibrations:
    python scripts/make_supplementary.py
    pandoc docs/Supplementary_Material.md -o docs/Supplementary_Material.docx
"""
import json
from pathlib import Path

import pandas as pd
import yaml

R = str(Path(__file__).resolve().parents[1]) + '/'
BIB = {'zenodo2026': 'Bousbia Laiche R, Letaim F, Cuce E. Replication code and Supplementary Material: pricing geopolitical risk into delivered green hydrogen costs (Algeria–EU, 2026 Strait of Hormuz closure) (version v2.1.0) [software]. Zenodo; 2026. https://doi.org/10.5281/zenodo.24244835.', 'caldara2022': 'Caldara D, Iacoviello M. Measuring geopolitical risk. Am Econ Rev 2022;112:1194–225. https://doi.org/10.1257/aer.20191823.', 'damodaran2026': 'Damodaran A. Country default spreads and risk premiums, January 2026 update [dataset]. New York University Stern School of Business; 2026. https://pages.stern.nyu.edu/~adamodar/New_Home_Page/datafile/ctryprem.html.', 'esmap2020': 'ESMAP. Global photovoltaic power potential by country. Washington, DC: World Bank; 2020.', 'gsa2026': 'Solargis, World Bank (ESMAP). Global Solar Atlas 2.x, long-term PVOUT (data version 2.2.68) [dataset; accessed 14 November 2026]. https://globalsolaratlas.info.', 'halili2024': 'Halili G. searoute: a Python package for computing shortest sea routes (version 1.6.0) [software]. https://github.com/genthalili/searoute-py.', 'herman2017': 'Herman J, Usher W. SALib: an open-source Python library for sensitivity analysis. J Open Source Softw 2017;2:97. https://doi.org/10.21105/joss.00097.', 'iea2024': 'International Energy Agency. Global hydrogen review 2024. Paris: IEA; 2024. https://www.iea.org/reports/global-hydrogen-review-2024.', 'kharroubi2026': 'Kharroubi E. Maritime chokepoints and the global economy: evidence from the Strait of Hormuz. BIS Working Papers No. 1378. Basel: Bank for International Settlements; 2026.', 'saltelli2010': 'Saltelli A, Annoni P, Azzini I, Campolongo F, Ratto M, Tarantola S. Variance based sensitivity analysis of model output. Design and estimator for the total sensitivity index. Comput Phys Commun 2010;181:259–70. https://doi.org/10.1016/j.cpc.2009.09.018.', 'sobol2001': 'Sobol′ IM. Global sensitivity indices for nonlinear mathematical models and their Monte Carlo estimates. Math Comput Simul 2001;55:271–80. https://doi.org/10.1016/S0378-4754(00)00270-6.'}

O = R + 'outputs/calibration_2023/'
O30 = R + 'outputs/calibration_2030/'
L = []
def w(s=''): L.append(s)
def f2(x, d=2):
    try:
        if pd.isna(x): return '–'
        return f'{float(x):.{d}f}'
    except Exception: return str(x)
def table(df, cap):
    w(cap); w()
    w('| ' + ' | '.join(df.columns) + ' |'); w('|' + '---|' * len(df.columns))
    for _, r in df.iterrows(): w('| ' + ' | '.join(str(v) for v in r.values) + ' |')
    w()

log = json.load(open(O + 'run_log.json'))
log_central = json.load(open(O + 'summary.json'))['central']
w('**Supplementary Material**'); w()
w('**Pricing geopolitical risk into delivered green hydrogen costs: a route-explicit scenario framework for Algeria–EU supply tested on the 2026 Strait of Hormuz closure**'); w()
w('Rabia Bousbia Laiche, Fethi Letaim, Erdem Cuce'); w()
w('This Supplementary Material reports the full parameter set, the route inputs, the complete scenario and competitor results, the sensitivity analysis, the model variants, the 2030 calibration and the observed 2026 data used in the article. Every table is written by the code in the accompanying repository (Bousbia Laiche et al., 2026), and the numbering of the article\'s equations, tables and figures is used throughout.'); w()

w('# S1. Reproducibility'); w()
w(f'All results were produced with model version {log["model_version"]}, Python {log["python"]} and numpy {log["numpy"]}, with {log["n_draws"]:,} Monte Carlo draws and seed {log["seed"]}. Sobol indices use SALib 1.6.0 (Herman and Usher, 2017) and sea distances the searoute package 1.6.0 (Halili, 2024). The SHA-256 hash of the parameter files used for the 2023 calibration is {log["parameter_files_sha256"][:16]}… (full value in outputs/calibration_2023/run_log.json). The commands are:'); w()
w('`pip install -r requirements.txt`; `python src/run_model.py --calibration 2023`; `python src/run_model.py --calibration 2030`; `pytest tests`.'); w()
w('A full 2023 run, including the Sobol design (30,720 model evaluations) and the figures, takes well under one minute on a laptop. The Geopolitical Risk index workbook (Caldara and Iacoviello, 2022) is read from data/raw/gpr_export.xls, which users download from its authors because it is not redistributed with the repository.'); w()

w('# S2. Parameters'); w()
prod = yaml.safe_load(open(R + 'params/production.yaml'))
rows = []
for k, v in prod.items():
    if not isinstance(v, dict) or 'dist' not in v: continue
    if v['dist'] == 'triangular': val = f"Tri({v['low']:g}, {v['mode']:g}, {v['high']:g})"
    elif v['dist'] == 'fixed': val = f"{v['value']:g}"
    else: val = v['dist']
    rows.append([k, val, v.get('unit', ''), v.get('source', '')])
table(pd.DataFrame(rows, columns=['Parameter (code name)', 'Value', 'Unit', 'Source key']),
      'Table S1. Techno-economic parameters of the 2023 calibration (params/production.yaml). Tri(a, b, c): triangular with minimum a, mode b and maximum c. AUTHOR: author assumption. Source keys are resolved in docs/REFERENCES.md and in the reference list below.')
w('The 2030 calibration (params/production_2030.yaml) differs only in the electrolyser capital cost, Tri(950, 1 250, 1 450) USD/kW (IEA, 2024).'); w()

cty = yaml.safe_load(open(R + 'params/countries.yaml'))['countries']
ri = pd.read_csv(O + 'table_route_inputs.csv')
rows = []
for _, r in ri.iterrows():
    c = cty[r.country]
    rows.append([r.country, r.site, int(r.pvout_kwh_kwp), f2(100 * c['default_spread']), f2(100 * c['crp']), f2(r.wacc_pct_p50), f2(r.beta), r.port, r.route, int(r.distance_nm), f2(r.roundtrip_days_at_15kn, 1), r.canal, r.listed_areas])
table(pd.DataFrame(rows, columns=['Exporter', 'Site', 'PVOUT (kWh/kWp)', 'Default spread (%)', 'CRP (%)', 'WACC p50 (%)', 'Beta', 'Port', 'Route to Rotterdam', 'Distance (nm)', 'Round trip at 15 kn (days)', 'Canal', 'Listed areas']),
      'Table S2. Exporter sites, financing terms and routes. PVOUT: Global Solar Atlas long-term yield (ESMAP, 2020; Solargis and World Bank, 2026). Default spreads and country risk premiums (CRP): Damodaran (2026). Distances: searoute 1.6.0 (scripts/route_distances.py).')

w('# S3. Algerian results'); w()
a = pd.read_csv(O + 'table_algeria_scenarios.csv')
rows = []
for _, r in a.iterrows():
    rows.append([r['mode'], r.scenario, f2(r.cost_mean), f2(r.cost_p05), f2(r.cost_p50), f2(r.cost_p95), f2(r.cost_ES95), f2(r.grp_mean), f2(r.grp_p05), f2(r.grp_p50), f2(r.grp_p95), f2(r.grp_ES95), f2(r.grp_pct_of_S0_mean, 1), f2(r.grp_financing), f2(r.grp_insurance)])
table(pd.DataFrame(rows, columns=['Mode', 'Scenario', 'Cost mean', 'p05', 'p50', 'p95', 'ES95', 'GRP mean', 'p05', 'p50', 'p95', 'ES95', 'GRP % of S0 mean', 'Financing', 'Insurance and rerouting']),
      'Table S3. Algerian delivered cost and geopolitical risk premium by scenario and mode, 2023 calibration (USD/kg H2; empirical quantiles of 10 000 draws). Financing and insurance-and-rerouting are the Shapley shares of the GRP mean (Eq. 9).')

w('# S4. Competitor results'); w()
c = pd.read_csv(O + 'table_competitors.csv')
rows = []
for _, r in c.iterrows():
    rows.append([r.competitor, r.scenario, f2(r.cost_p50), r.route_shares, f2(r.gap_p50_vsDZpipe), f"{f2(r.gap_p05_vsDZpipe)} to {f2(r.gap_p95_vsDZpipe)}", f2(100 * r.share_DZ_cheaper_vsDZpipe, 0), f2(r.chg_financing_vsDZpipe), f2(r.chg_insurance_rerouting_vsDZpipe), f2(r.SP_ES95_vsDZpipe), f2(r.gap_p50_vsDZnh3), f2(r.SP_ES95_vsDZnh3)])
table(pd.DataFrame(rows, columns=['Competitor', 'Scenario', 'Cost p50', 'Route shares', 'Gap vs DZ pipeline p50', '90% interval', 'DZ cheaper (% draws)', 'Gap change: financing', 'Gap change: insurance and rerouting', 'Security premium ES95 vs DZ pipeline', 'Gap vs DZ ammonia p50', 'Security premium ES95 vs DZ ammonia']),
      'Table S4. Competitor delivered cost, route choice, gap with Algeria and security premium (USD/kg H2). Gap > 0: Algeria cheaper. Gap changes are relative to S0 and split by the Shapley rule. Security premium: ES95 of the competitor\'s cost change minus ES95 of Algeria\'s.')
g = pd.read_csv(O + 'table_baseline_gap_components.csv')
g = g.assign(**{k: g[k].map(f2) for k in ['resource', 'cost_of_capital', 'transport', 'insurance', 'total_gap_mean']})
g.columns = ['Competitor', 'Algeria mode', 'Resource', 'Cost of capital', 'Transport', 'Insurance', 'Total gap (mean)']
table(g, 'Table S5. Decomposition of the baseline (S0) mean gap between each competitor and Algeria (USD/kg H2; positive: Algeria cheaper). Resource: production cost difference at Algeria\'s WACC due to the PV yield; cost of capital: remaining production difference due to the WACC.')
b = pd.read_csv(O + 'table_breakeven.csv')
rows = []
for _, r in b.iterrows():
    rows.append([r.competitor, r.algeria_mode, f2(100 * r.share_DZ_cheaper_at_S0, 1), f2(100 * r.share_gain_S0_S3, 1), f2(100 * r.share_lose_S0_S3, 1),
                 '–' if pd.isna(r.lose_gpr_median) else f"{100 * r.lose_gpr_median:.0f} ({100 * r.lose_p05:.0f}–{100 * r.lose_p95:.0f})"])
table(pd.DataFrame(rows, columns=['Competitor', 'Algeria mode', 'Algeria cheaper at S0 (% draws)', 'Algeria becomes cheaper within S0–S3 (% draws)', 'Algeria loses its advantage within S0–S3 (% draws)', 'Break-even GPR, % above mean, median (5th–95th)']),
      'Table S6. Break-even analysis along the Hormuz path S0–S1–S2–S3 (grid step 0.02 of the GPR level; shocks interpolated linearly between scenarios).')

w('# S5. Sensitivity analysis and convergence'); w()
s = pd.read_csv(O + 'table_sobol.csv')
s = s.copy()
s = s.assign(S1=s.S1.map(lambda x: f2(x, 3)), S1_conf95=s.S1_conf95.map(lambda x: f2(x, 3)), ST=s.ST.map(lambda x: f2(x, 3)), ST_conf95=s.ST_conf95.map(lambda x: f2(x, 3)))
s.columns = ['Output', 'Input', 'S1', 'S1 ±95%', 'ST', 'ST ±95%', 'Status']
table(s, 'Table S7. Sobol first-order (S1) and total-order (ST) indices, Saltelli design with 2,048 base samples and D = 13 inputs (30,720 evaluations), Jansen estimator (Sobol\', 2001; Saltelli et al., 2010). All 13 inputs are listed for every output. u_w: quantile of the scenario WACC uplift; u_a: quantile of the war-risk premium (one quantile for both listed areas). Status: active; structurally inactive (the input does not enter the equations of the output, or cancels exactly in it); no effect on the sampled support (the input enters the equations but never changes the output over the sampled range).')
w('![](../outputs/calibration_2023/figS_sobol.png){width=16cm}'); w()
w('Figure S1. Total-order Sobol indices for the three outputs of Table S7.'); w()
cv = pd.read_csv(O + 'convergence.csv')
cv = cv[cv.n.isin([1000, 2000, 5000, 7500, 10000]) | (cv.n % 2500 == 0)].drop_duplicates('n')
cv = cv.assign(**{k: cv[k].map(lambda x: f2(x, 3)) for k in cv.columns if k != 'n'})
cv.columns = ['Draws', 'Running mean GRP S3', 'MCSE of mean', 'Running ES95', 'MCSE of ES95 (batch means)']
table(cv, 'Table S8. Convergence of the mean and ES95 of Algeria\'s pipeline GRP in S3 (USD/kg H2).')

w('# S6. Model variants'); w()
v = pd.read_csv(O + 'table_variants.csv')
v = v.assign(**{k: v[k].map(lambda x: f2(x)) for k in v.columns if k != 'variant'})
v.columns = ['Variant', 'DZ pipeline cost S0', 'DZ pipeline GRP S3', 'p05', 'p95', '% of S0', 'DZ pipeline GRP H26',
             'DZ ammonia cost S0', 'DZ ammonia GRP S3', '% of S0 (ammonia)', 'Oman − DZ ammonia gap S3',
             'Share of draws in which Algeria becomes cheaper than Oman', 'Conditional median break-even GPR (Oman)',
             'Australia − DZ ammonia gap S3', 'Share crossing (Australia)', 'Chile − DZ pipeline gap S3, p05', 'p50', 'p95',
             'Share DZ pipeline cheaper than Chile, S3', 'Oman cost S3', 'Egypt cost S3']
half = ['Variant'] + list(v.columns[1:11])
table(v[half], 'Table S9a. Variants changing one assumption at a time: Algerian results (USD/kg H2 unless stated).')
table(v[['Variant'] + list(v.columns[11:])], 'Table S9b. Variants changing one assumption at a time: competitor results (USD/kg H2; shares of draws).')
w('Author betas: Morocco 0.8, Egypt 1.1, Oman 1.2, Australia 0.3, Chile 0.3 (first version of the model). Sohar: Oman exports from Sohar inside the Gulf of Oman area (Hormuz and Red Sea, or Hormuz and the Cape). Midstream variant: 70% of the pipeline tariff and of the distance-independent ammonia cost F is treated as capital recovery over 30 years and moves with the exporter\'s WACC; it is an upper bound, because import-side cracking and the European pipeline sections are financed outside the exporting country. Fuel variant: the cargo used as fuel and lost as boil-off is valued at the production cost plus 1 USD/kg. Independent yield variant: one PV yield factor per site, drawn from a separate random stream, in place of one common factor. The three bounding parameters are author assumptions (params/production.yaml).'); w()

w('# S7. 2030 calibration'); w()
a3 = pd.read_csv(O30 + 'table_algeria_scenarios.csv')
rows = [[r['mode'], r.scenario, f2(r.cost_p50), f2(r.grp_p50), f"{f2(r.grp_p05)}–{f2(r.grp_p95)}", f2(r.grp_pct_of_S0_mean, 1)] for _, r in a3.iterrows()]
table(pd.DataFrame(rows, columns=['Mode', 'Scenario', 'Cost p50', 'GRP p50', 'GRP 90% interval', 'GRP % of S0 mean']),
      'Table S10. Algerian delivered cost and GRP with the 2030 electrolyser cost (USD/kg H2).')
c3 = pd.read_csv(O30 + 'table_competitors.csv')
c3 = c3[c3.scenario.isin(['S0', 'S3', 'H26'])]
rows = [[r.competitor, r.scenario, f2(r.cost_p50), f2(r.gap_p50_vsDZpipe), f2(100 * r.share_DZ_cheaper_vsDZpipe, 0), f2(r.gap_p50_vsDZnh3)] for _, r in c3.iterrows()]
table(pd.DataFrame(rows, columns=['Competitor', 'Scenario', 'Cost p50', 'Gap vs DZ pipeline p50', 'DZ cheaper (% draws)', 'Gap vs DZ ammonia p50']),
      'Table S11. Competitors in the 2030 calibration (USD/kg H2).')

w('# S8. Observed 2026 data'); w()
ob = pd.read_csv(R + 'data/raw/observed_2026.csv')
ob = ob[['date', 'variable', 'area', 'value_low', 'value_high', 'unit', 'source']]
ob.columns = ['Date', 'Variable', 'Area', 'Low', 'High', 'Unit', 'Source']
table(ob, 'Table S12. Observed values used to calibrate scenario H26 and to test the ex-ante scenarios (data/raw/observed_2026.csv, with URLs in the file). Quotes from brokers and the trade press are indicative, not transaction data.')

w('# S9. Changes in model version 2.1.0'); w()
c = log_central
w(f"Version 2.1.0 corrects two accounting conventions of version 2.0.0 and adds three bounding variants. (1) The annual cost of the PV plant is divided by the electricity that reaches the electrolyser, (1 − λ)Y, and no longer by the gross yield Y; the electrolyser full-load hours already used the clipped yield. At central parameters and a WACC of 8% the Algerian production cost is {c['wacc_8pct']['total']:.2f} USD/kg (electrolyser {c['wacc_8pct']['electrolyser']:.2f}, electricity {c['wacc_8pct']['electricity']:.2f}, water {c['wacc_8pct']['water']:.3f}); version 2.0.0 gave 5.67 USD/kg. (2) The 10,000 km reference voyage that is subtracted from the IRENA ammonia chain cost is valued at the exporter's baseline (S0) production cost, so the distance-independent conversion cost no longer moves with the scenario WACC. In version 2.0.0 this produced an Algerian ammonia premium slightly below the pipeline premium; it is now slightly above it, because the fuel burnt on the voyage is valued at the scenario production cost. (3) New variants: midstream capital exposed to the exporter's WACC, a higher value of the cargo used as fuel, and independent PV yield factors (Table S9). (4) The Sobol table reports whether an input is active, structurally inactive or without effect on the sampled support. (5) data/raw/observed_2026.csv adds dated war-risk quotes for the Red Sea and the Strait of Hormuz (30 March, 10-13 April, 18 June and 21-23 July 2026); the H26 scenario is unchanged. Equation numbers follow the revised article: (1) delivered cost, (2) production cost, (3) voyage cost, (4) ammonia transport, (5) route choice, (6) insurance, (7) WACC, (8) GRP, (9) Shapley split, (10) cost gap and security premium."); w()

w('# S10. Specifications proposed but not estimated'); w()
w('The earlier version of this work proposed three econometric models: a DCC-MIDAS-X model of the long-run correlation between the GPR index and hydrogen cost drivers, a TVP-VAR frequency-connectedness model, and a mediation model splitting the effect of GPR between financing, insurance, buyer-preference and fossil-input channels. None of them was estimated, and the article does not use them. They could not be estimated credibly on the available data: (1) Algeria has no traded external sovereign bond, so no market series exists for its financing channel; (2) war-risk premiums are available only as irregular broker quotes; (3) the monthly sample of the hydrogen-specific variables is short; and (4) a synthetic cost index built from the same drivers would make the dependent variable a function of its own regressors. The code of the earlier specifications is kept in the extensions/ folder of the repository for transparency.'); w()
w('The estimation that would most improve the framework is the elasticity of project financing costs to geopolitical shocks. A feasible design uses local projections of daily or weekly sovereign spreads (JPMorgan EMBI constituents) and project-finance pricing on standardised GPR shocks, in the spirit of Kharroubi (2026), with the 2024 Red Sea episode and the 2026 Hormuz closure as event windows. The estimated elasticities would replace the scenario uplifts and default-spread betas of Eq. (7). A second step would estimate per-transit war-risk premiums as a function of incidents and GPR from a panel of broker quotes, if such a panel can be obtained.'); w()

w('# S11. Repository and data availability'); w()
w('Code, parameters, observed 2026 data and outputs: https://github.com/rabia-bousbialaiche-77/algeria-h2-geopolitical-premium (archived on Zenodo, Bousbia Laiche et al., 2026). License: MIT for code, CC BY 4.0 for documentation and outputs. The GPR index is available from https://www.matteoiacoviello.com/gpr.htm.'); w()

w('# References'); w()
for k in ['zenodo2026', 'caldara2022', 'damodaran2026', 'esmap2020', 'gsa2026', 'halili2024', 'herman2017', 'iea2024', 'kharroubi2026', 'saltelli2010', 'sobol2001']:
    w(BIB[k]); w()
open(R + 'docs/Supplementary_Material.md', 'w', encoding='utf-8').write('\n'.join(L))
print('written docs/Supplementary_Material.md')
