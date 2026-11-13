# ----------------------------------------------------------------------------
# Model III: mediation with sensitivity analysis (Imai, Keele & Tingley, 2010)
# Treatment: GPR (standardised); mediator: Ins_Prem or Spread_bp; outcome: the
# delivered-cost series. Because LCOH_Export is built from the mediators
# (Supplementary S2.3), results are reported as model-implied channel
# contributions; medsens() shows how strong unobserved confounding (rho) must be
# to remove the indirect effect.
# ----------------------------------------------------------------------------
suppressPackageStartupMessages(library(mediation))
d <- read.csv("data/processed/panel_monthly.csv")
need <- c("GPR", "Ins_Prem", "LCOH_ship")
stopifnot(all(need %in% names(d)))
d <- na.omit(d[, c(need, intersect(c("Oil_Vol", "EU_ETS"), names(d)))])
d$GPR <- as.numeric(scale(d$GPR))
ctrl <- setdiff(names(d), need)
f_m <- as.formula(paste("Ins_Prem ~ GPR", if (length(ctrl)) paste("+", paste(ctrl, collapse = "+"))))
f_y <- as.formula(paste("LCOH_ship ~ GPR + Ins_Prem", if (length(ctrl)) paste("+", paste(ctrl, collapse = "+"))))
m_med <- lm(f_m, data = d)
m_out <- lm(f_y, data = d)
med <- mediate(m_med, m_out, treat = "GPR", mediator = "Ins_Prem",
               treat.value = 1, control.value = 0, sims = 1000, boot = TRUE)
sens <- medsens(med, rho.by = 0.05, sims = 1000)
dir.create("outputs/econometrics", showWarnings = FALSE, recursive = TRUE)
capture.output(summary(med), summary(sens), file = "outputs/econometrics/mediation_sensitivity.txt")
