# R packages used by the replication scripts (tested versions to be recorded in R/sessionInfo.txt)
pkgs <- c("ConnectednessApproach", "mediation", "strucchange", "midasr", "readr", "dplyr", "zoo")
install.packages(setdiff(pkgs, rownames(installed.packages())), repos = "https://cloud.r-project.org")
