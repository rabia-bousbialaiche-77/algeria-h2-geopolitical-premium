"""Retrieve long-term PVOUT (c-Si, optimum tilt) at the export sites from the
Global Solar Atlas API (Solargis / World Bank ESMAP). Values are copied by hand
into params/countries.yaml; this script documents and re-checks them."""
import json
import urllib.request

SITES = {"Algeria": (32.93, 3.27), "Morocco": (28.98, -10.06), "Egypt": (29.60, 32.30), "Oman": (19.70, 57.60),
         "Australia": (-20.40, 118.70), "Chile": (-23.30, -70.10)}
for k, (lat, lon) in SITES.items():
    d = json.load(urllib.request.urlopen(f"https://api.globalsolaratlas.info/data/lta?loc={lat},{lon}", timeout=60))
    print(k, round(d["annual"]["data"]["PVOUT_csi"]), "kWh/kWp/yr; layer version",
          d["annual"]["metadata"]["layers"]["PVOUT_csi"]["version"])
