"""Download the publicly available input series into data/raw/.

    python scripts/download_data.py

Automatic: GPR (Caldara & Iacoviello), global EPU and Brent (FRED).
Manual (licensed or author-specified, see params/data_dictionary.csv):
    data/raw/eu_ets.csv            date,price_eur
    data/raw/financing_proxy.csv   date,spread_bp
    data/raw/cri.csv               date,cri
Record the download date: the GPR page asks users to cite it.
"""
from __future__ import annotations

import datetime as dt
import json
import urllib.request
from pathlib import Path

RAW = Path(__file__).resolve().parents[1] / "data" / "raw"
SOURCES = {
    "gpr_export.xls": "https://www.matteoiacoviello.com/gpr_files/data_gpr_export.xls",
    "fred_GEPUCURRENT.csv": "https://fred.stlouisfed.org/graph/fredgraph.csv?id=GEPUCURRENT",
    "fred_DCOILBRENTEU.csv": "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DCOILBRENTEU",
}


def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    log = {}
    for name, url in SOURCES.items():
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (research replication)"})
            data = urllib.request.urlopen(req, timeout=60).read()
            (RAW / name).write_bytes(data)
            log[name] = {"url": url, "bytes": len(data), "downloaded": dt.date.today().isoformat()}
            print(f"ok   {name} ({len(data):,} bytes)")
        except Exception as exc:  # network or URL change: report and continue
            log[name] = {"url": url, "error": str(exc)}
            print(f"FAIL {name}: {exc} -> download manually from {url}")
    (RAW / "download_log.json").write_text(json.dumps(log, indent=2))
    for f in ("eu_ets.csv", "financing_proxy.csv", "cri.csv"):
        if not (RAW / f).exists():
            print(f"MANUAL {f} missing - see params/data_dictionary.csv")


if __name__ == "__main__":
    main()
