"""Sea distances (nautical miles) from export ports to Rotterdam with searoute
(Halili, v1.6.0). Restricting a passage gives the alternative route."""
import searoute as sr

R = (4.05, 51.95)
PORTS = {"Algeria (Arzew)": (-0.30, 35.85), "Morocco (Jorf Lasfar)": (-8.64, 33.12), "Egypt (Ain Sokhna)": (32.35, 29.60),
         "Oman (Duqm)": (57.70, 19.67), "Oman (Sohar)": (56.73, 24.36), "Australia (Port Hedland)": (118.58, -20.31),
         "Chile (Mejillones)": (-70.45, -23.10)}
for k, o in PORTS.items():
    base = sr.searoute(o, R, units="naut")["properties"]["length"]
    alt = {}
    for r in ("suez", "panama"):
        try:
            alt[r] = round(sr.searoute(o, R, units="naut", restrictions=[r])["properties"]["length"])
        except Exception:
            alt[r] = None
    print(k, round(base), "nm; without", alt)
