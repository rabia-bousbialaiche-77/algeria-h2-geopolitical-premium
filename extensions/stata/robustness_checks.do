* ----------------------------------------------------------------------------
* Robustness checks (manuscript Table 7; Supplementary S7) - Stata 18
*   ssc install ivreg2, ranktest, weakivtest, xtbreak
* Run from the repository root:  do stata/robustness_checks.do
* ----------------------------------------------------------------------------
clear all
set more off
capture mkdir "outputs/econometrics"
log using "outputs/econometrics/robustness_checks.log", replace text
import delimited "data/processed/panel_monthly.csv", clear
gen mdate = monthly(substr(month,1,7), "YM")
format mdate %tm
tsset mdate

* Mediator regressions on observable market variables (preferred specification)
gen lgpr = ln(gpr)
gen lgpr_l12 = L12.lgpr
gen lgpr_l6  = L6.lgpr
gen lgpr_l3  = L3.lgpr

* IV: one-year lagged GPR as instrument for current GPR (exclusion restriction
* discussed in Supplementary S7; treated as a robustness check)
capture confirm variable spread_bp
if !_rc {
    ivreg2 spread_bp (lgpr = lgpr_l12), robust first
    weakivtest                                  // Montiel Olea & Pflueger (2013) effective F
    ivreg2 spread_bp (lgpr = lgpr_l6), robust
    ivreg2 spread_bp (lgpr = lgpr_l3), robust
}
ivreg2 ins_prem (lgpr = lgpr_l12), robust first
weakivtest

* Structural breaks (Bai-Perron) on the war-risk premium
xtbreak estimate ins_prem lgpr, breaks(4)

log close
