#!/usr/bin/env python3
"""Delta-terminal v1.
Hämtar gratis makro/marknadsdata från FRED (ingen API-nyckel), hittar ovanliga
förändringar (z-score mot senaste året), upptäcker regimbyten sedan förra körningen
och skriver docs/index.html + docs/state.json.
Kör: pip install pandas && python delta.py
"""
import io, json, pathlib, datetime as dt, urllib.request
import pandas as pd

OUT = pathlib.Path("docs")
OUT.mkdir(exist_ok=True)

# FRED-id: (namn, grupp, typ)
# typ: pct = %-förändring | bp = räntepunkter (datan är i %) | pts = poäng
SERIES = {
    "SP500":        ("S&P 500", "Risk", "pct"),
    "VIXCLS":       ("VIX", "Risk", "pts"),
    "BAMLH0A0HYM2": ("High yield-spread", "Kredit", "bp"),
    "DGS2":         ("US 2-årsränta", "Räntor", "bp"),
    "DGS10":        ("US 10-årsränta", "Räntor", "bp"),
    "T10Y2Y":       ("Kurva 10y-2y", "Räntor", "bp"),
    "T10YIE":       ("Inflationsförväntan 10y", "Inflation", "bp"),
    "DTWEXBGS":     ("Dollarindex (bred)", "Valuta", "pct"),
    "DEXSIUS":      ("SEK per USD", "Valuta", "pct"),
    "DCOILWTICO":   ("Olja WTI", "Råvaror", "pct"),
}
HORIZONS = {"1d": 1, "5d": 5, "20d": 20}
LOOKBACK = 260  # ~1 handelsår
UNIT = {"pct": "%", "bp": " bp", "pts": " p"}


def fetch(sid):
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}"
    req = urllib.request.Request(url, headers={"User-Agent": "delta-terminal/0.1"})
    with urllib.request.urlopen(req, timeout=30) as r:
        df = pd.read_csv(io.BytesIO(r.read()), na_values=".")
    df.columns = ["date", "v"]
    df["date"] = pd.to_datetime(df["date"])
    return df.dropna().set_index("date")["v"].tail(900)


def change(s, n, kind):
    if kind == "pct":
        return s.pct_change(n) * 100
    return s.diff(n) * (100 if kind == "bp" else 1)


def analyse(sid, s):
    name, group, kind = SERIES[sid]
    best = None
    for h, n in HORIZONS.items():
        c = change(s, n, kind).dropna()
        hist = c.iloc[-LOOKBACK - 1:-1]
        if len(hist) < 100 or hist.std() == 0:
            continue
        z = float((c.iloc[-1] - hist.mean()) / hist.std())
        if best is None or abs(z) > abs(best["z"]):
            best = {"h": h, "chg": float(c.iloc[-1]), "z": z}
    if best is None:
        return None
    return {"id": sid, "name": name, "group": group, "kind": kind,
            "last": float(s.iloc[-1]), "asof": str(s.index[-1].date()), **best}


def regimes(d):
    def pctile(s):
        return float((s.iloc[-504:] < s.iloc[-1]).mean() * 100)
    out = {}
    if "T10Y2Y" in d:
        out["Räntekurvan är inverterad"] = bool(d["T10Y2Y"].iloc[-1] < 0)
    if "VIXCLS" in d:
        out["Volatiliteten är hög (VIX över 80:e percentilen)"] = pctile(d["VIXCLS"]) > 80
    if "BAMLH0A0HYM2" in d:
        out["Kreditstress (spreadar över 80:e percentilen)"] = pctile(d["BAMLH0A0HYM2"]) > 80
    if "SP500" in d:
        out["Aktier handlar under 200-dagarssnittet"] = bool(d["SP500"].iloc[-1] < d["SP500"].tail(200).mean())
    return out


def sentence(r):
    stor = "ovanligt stor rörelse" if abs(r["z"]) >= 2 else "normal rörelse"
    return f'{r["name"]}: {r["chg"]:+.1f}{UNIT[r["kind"]]} på {r["h"]} ({stor}, z={r["z"]:+.1f})'


PAGE = """<!doctype html><html lang="sv"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Delta-brief</title><style>
:root{--bg:#fff;--fg:#111;--mut:#666;--card:#f3f3f3;--up:#0a7d3b;--dn:#c0392b}
@media(prefers-color-scheme:dark){:root{--bg:#0f1115;--fg:#e8e8e8;--mut:#8b8f98;--card:#1a1d24}}
body{background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif;max-width:760px;margin:2rem auto;padding:0 1rem}
h1{font-size:1.3rem}h2{font-size:1rem;margin-top:2rem;color:var(--mut);text-transform:uppercase;letter-spacing:.05em}
.card{background:var(--card);padding:.6rem .9rem;border-radius:8px;margin:.4rem 0}
.up{color:var(--up)}.dn{color:var(--dn)}.mut{color:var(--mut)}
table{width:100%;border-collapse:collapse}td,th{padding:.3rem .4rem;text-align:left;border-bottom:1px solid var(--card)}
</style><h1>Delta-brief <span class="mut">%%ASOF%%</span></h1>
<h2>Regimbyten sedan senast</h2>%%FLIPS%%
<h2>Ovanliga rörelser</h2>%%MOVERS%%
<h2>Nuvarande regim</h2>%%REGIME%%
<h2>Alla serier</h2><table><tr><th>Serie</th><th>Senast</th><th>Rörelse</th><th>z</th></tr>%%TABLE%%</table>
<p class="mut">Källa: FRED. Data är fördröjd (föregående handelsdag) och duger för beslut på dagar till månader, inte intradag.</p></html>"""


def render(rows, reg, flips, asof):
    movers = [r for r in rows if abs(r["z"]) >= 2]
    f = "".join(f'<div class="card">{t}</div>' for t in flips) or '<div class="card mut">Inga byten.</div>'
    m = "".join(f'<div class="card {"up" if r["z"] > 0 else "dn"}">{sentence(r)}</div>' for r in movers) \
        or '<div class="card mut">Inget utanför det normala.</div>'
    g = "".join(f'<div class="card">{"🔴" if v else "🟢"} {k}: <b>{"ja" if v else "nej"}</b></div>' for k, v in reg.items())
    t = "".join(f'<tr><td>{r["name"]}</td><td>{r["last"]:.2f}</td>'
                f'<td>{r["chg"]:+.1f}{UNIT[r["kind"]]} / {r["h"]}</td><td>{r["z"]:+.1f}</td></tr>' for r in rows)
    return (PAGE.replace("%%ASOF%%", asof).replace("%%FLIPS%%", f).replace("%%MOVERS%%", m)
            .replace("%%REGIME%%", g).replace("%%TABLE%%", t))


def main(fetcher=fetch):
    data = {}
    for sid in SERIES:
        try:
            data[sid] = fetcher(sid)
        except Exception as e:  # en trasig serie ska inte fälla hela briefen
            print(f"Hoppar över {sid}: {e}")
    rows = [r for sid, s in data.items() if (r := analyse(sid, s))]
    rows.sort(key=lambda r: -abs(r["z"]))
    reg = regimes(data)

    state_file = OUT / "state.json"
    prev = json.loads(state_file.read_text()).get("regimes", {}) if state_file.exists() else {}
    flips = [f'{k}: {"nej → ja" if v else "ja → nej"}' for k, v in reg.items() if k in prev and prev[k] != v]

    asof = max((r["asof"] for r in rows), default=str(dt.date.today()))
    (OUT / "index.html").write_text(render(rows, reg, flips, asof), encoding="utf-8")
    state_file.write_text(json.dumps({"asof": asof, "regimes": reg, "rows": rows}, ensure_ascii=False, indent=1))
    print(f"Klar. {len(rows)} serier, {len(flips)} regimbyten, {sum(abs(r['z']) >= 2 for r in rows)} ovanliga rörelser.")


if __name__ == "__main__":
    main()
