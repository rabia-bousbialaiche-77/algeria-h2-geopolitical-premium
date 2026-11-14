# ----------------------------------------------------------------------------
# Model II: TVP-VAR frequency connectedness (manuscript Section 3.5.2, Supplementary S6)
# Antonakakis, Chatziantoniou & Gabauer (2020) TVP-VAR with the Barunik & Krehlik
# (2018) frequency decomposition, as implemented in the ConnectednessApproach package.
#
# Monthly data: the shortest resolvable period is 2 months (Nyquist). Bands:
#   short  : 2-3 months    omega in (2*pi/3, pi]
#   medium : 3-12 months   omega in (pi/6, 2*pi/3]
#   long   : > 12 months   omega in [0, pi/6]
# Run from the repository root:  Rscript R/tvp_var_frequency.R
# NOTE: written against ConnectednessApproach >= 1.0; check argument names against
# the installed version (help(ConnectednessApproach)) and record sessionInfo().
# ----------------------------------------------------------------------------
suppressPackageStartupMessages({library(ConnectednessApproach); library(zoo)})

panel <- read.csv("data/processed/panel_monthly.csv")
vars  <- c("GPR", "Ins_Prem", "Oil_Vol", "EU_ETS", "Spread_bp")
missing <- setdiff(vars, names(panel))
if (length(missing)) stop("missing inputs: ", paste(missing, collapse = ", "),
                          " - see params/data_dictionary.csv")
x <- zoo(panel[, vars], order.by = as.Date(panel$month))
x <- na.omit(diff(log(x + 1e-6)))          # stationary transformation (log-differences)

dca <- ConnectednessApproach(
  x,
  nlag = 1,                                 # lag order: select by BIC and report
  nfore = 100,                              # spectral horizon H = 100 (Barunik & Krehlik, 2018)
  model = "TVP-VAR",
  connectedness = "Frequency",
  VAR_config = list(TVPVAR = list(kappa1 = 0.99, kappa2 = 0.99, prior = "BayesPrior")),
  Connectedness_config = list(FrequencyConnectedness = list(
    partition = c(pi + 0.00001, 2 * pi / 3, pi / 6, 0),
    generalized = TRUE, scenario = "ABS"))
)
dir.create("outputs/econometrics", showWarnings = FALSE, recursive = TRUE)
saveRDS(dca, "outputs/econometrics/tvp_var_frequency.rds")
write.csv(as.data.frame(dca$TCI), "outputs/econometrics/tci_by_band.csv")
capture.output(sessionInfo(), file = "outputs/econometrics/sessionInfo_tvpvar.txt")
