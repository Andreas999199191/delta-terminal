#!/usr/bin/env python3
"""Portföljbevakning v1 -> docs/portfolio.html
Läser positions.json (bara vikter och GAV, inga kontonummer), hämtar kurser
(Alpaca för USA-aktier/ETF-proxys, Yahoo för svenska aktier), räknar delta, relativ styrka,
tripwires och en makrokoppling från docs/state.json (skapas av delta.py).
"""
import html, json, os, pathlib, re, time, datetime as dt, urllib.parse, urllib.request
import pandas as pd
import delta  # återanvänder CSS

OUT = pathlib.Path("docs")
OUT.mkdir(exist_ok=True)
esc = html.escape
DEFAULT_TRIPS = [{"type": "below_sma", "n": 200}, {"type": "drop", "pct": 8, "days": 5}, {"type": "volspike", "x": 2.0}]


def fetch_alpaca(symbols):
    kid, sec = os.environ.get("ALPACA_KEY_ID"), os.environ.get("ALPACA_SECRET")
    if not (kid and sec):
        raise RuntimeError("ALPACA_KEY_ID/ALPACA_SECRET saknas")
    start = (dt.date.today() - dt.timedelta(days=900)).isoformat()
    rows, token = {}, None
    while True:
        q = {"symbols": ",".join(symbols), "timeframe": "1Day", "start": start, "limit": 10000,
             "feed": "iex", "adjustment": "split"}
        if token:
            q["page_token"] = token
        req = urllib.request.Request("https://data.alpaca.markets/v2/stocks/bars?" + urllib.parse.urlencode(q),
                                     headers={"APCA-API-KEY-ID": kid, "APCA-API-SECRET-KEY": sec})
        with urllib.request.urlopen(req, timeout=20) as r:
            j = json.loads(r.read())
        for sym, bars in (j.get("bars") or {}).items():
            rows.setdefault(sym, []).extend((b["t"][:10], b["c"]) for b in bars)
        token = j.get("next_page_token")
        if not token:
            break
    return {s: pd.Series({pd.Timestamp(d): c for d, c in v}).sort_index() for s, v in rows.items()}


def fetch_yahoo(sym):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(sym)}?range=3y&interval=1d"
    last = None
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=15) as r:
                res = json.loads(r.read())["chart"]["result"][0]
            s = pd.Series(res["indicators"]["quote"][0]["close"], index=pd.to_datetime(res["timestamp"], unit="s").normalize()).dropna()
            return s[~s.index.duplicated(keep="last")].sort_index()
        except Exception as e:
            last = e
            time.sleep(2 * (attempt + 1))
    raise last


def eval_trip(t, s, m):
    ty = t["type"]
    if ty == "below_sma":
        return f"Under {t['n']}-dagarssnittet", bool(len(s) >= t["n"] and s.iloc[-1] < s.tail(t["n"]).mean())
    if ty == "drop":
        d = t["days"]
        return f"Faller mer än {t['pct']:g} % på {d} dagar", bool(len(s) > d and (s.iloc[-1] / s.iloc[-1 - d] - 1) * 100 <= -t["pct"])
    if ty == "below_price":
        return f"Under {t['price']:g}", bool(s.iloc[-1] < t["price"])
    if ty == "above_price":
        return f"Över {t['price']:g}", bool(s.iloc[-1] > t["price"])
    if ty == "drawdown":
        return f"{t['pct']:g} % under 52-veckorshögsta", bool(m["dd"] <= -t["pct"])
    if ty == "volspike":
        return f"Volatiliteten {t['x']:g}x normalt", bool(m["volx"] and m["volx"] >= t["x"])
    return str(t), False


def metrics(p, s, bench):
    s = s.dropna()
    if len(s) < 60:
        return None
    ret = s.pct_change()
    m = {"last": float(s.iloc[-1]), "asof": str(s.index[-1].date()), "hz": {}}
    for h, n in (("1d", 1), ("5d", 5), ("20d", 20)):
        c = (s.pct_change(n) * 100).dropna()
        hist = c.iloc[-261:-1]
        z = float((c.iloc[-1] - hist.mean()) / hist.std()) if len(hist) >= 100 and hist.std() > 0 else 0.0
        m["hz"][h] = {"chg": float(c.iloc[-1]), "z": z}
    m["vs200"] = float((s.iloc[-1] / s.tail(200).mean() - 1) * 100) if len(s) >= 200 else None
    m["dd"] = float((s.iloc[-1] / s.tail(252).max() - 1) * 100)
    v10, v60 = ret.tail(10).std(), ret.tail(60).std()
    m["volx"] = float(v10 / v60) if v60 else None
    if bench is not None and len(bench) > 21:
        m["rel20"] = m["hz"]["20d"]["chg"] - float((bench.iloc[-1] / bench.iloc[-21] - 1) * 100)
    if p.get("gav") and not p["proxy"]:
        m["pl"] = float((m["last"] / p["gav"] - 1) * 100)
    m["spark"] = s.tail(120).round(4).tolist()
    m["trips"] = [dict(zip(("label", "hit"), eval_trip(t, s, m))) for t in (p.get("tripwires") or DEFAULT_TRIPS)]
    return m


def macro_notes(tags, R):
    def z(sid):
        r = R.get(sid)
        return r["hz"].get(r["mid"]) if r else None

    def big(x):
        return x is not None and abs(x["z"]) >= 1.5
    hy, cv, vix, spx, sek = z("BAMLH0A0HYM2"), z("T10Y2Y"), z("VIXCLS"), z("SP500"), z("DEXSIUS")
    out = []
    if "Bank" in tags and big(hy) and hy["chg"] > 0:
        out.append(("off", "Kreditspreadar vidgas", "Negativt för dina banker (SEB, Swedbank, Nordea, JPM): kreditoro slår mot kreditförluster och finansieringskostnader."))
    if "Bank" in tags and big(cv) and cv["chg"] > 0:
        out.append(("on", "Räntekurvan brantar", "Normalt positivt för bankernas räntenetto, så länge det inte drivs av kreditoro."))
    if big(vix) and big(spx) and spx["chg"] < 0 < vix["chg"] and tags & {"Holding", "Industri"}:
        out.append(("off", "Risk-off på marknaden", "Investor och Atlas Copco är cykliska och brukar följa med ner när riskviljan sjunker."))
    if big(sek):
        if sek["chg"] > 0:
            out.append(("neutral", "Kronan försvagas", "Dollarinnehav (JPM, Visa, BRK.B, AXP) blir mer värda i kronor, och exportbolag som Atlas Copco gynnas."))
        else:
            out.append(("neutral", "Kronan stärks", "Dollarinnehav tappar värde i kronor även om kursen i dollar är oförändrad."))
    return out


def chip(h):
    cls = "up" if h["chg"] > 0 else "dn"
    return f'<div class="c {cls}{" hot" if abs(h["z"]) >= 2 else ""}">{h["chg"]:+.1f}%</div>'


def card(p, m):
    head = f'<div class="nm">{esc(p["name"])} <small>{esc(p["ticker"])}{" · proxy " + esc(p["symbol"]) if p["proxy"] else ""}</small></div><div class="vl">{p["weight"]:.1f}%</div>'
    if not m:
        return f'<details class="sr"><summary class="hr">{head}<div class="nodata">ingen kursdata</div></summary></details>'
    hit = [t for t in m["trips"] if t["hit"]]
    rel = f'{m["rel20"]:+.1f} pp' if "rel20" in m else "–"
    v200 = f'{m["vs200"]:+.1f}%' if m["vs200"] is not None else "–"
    pl = f'{m["pl"]:+.1f}%' if "pl" in m else "–"
    flag = f'<span class="tw">{len(hit)}</span>' if hit else ""
    trips = "".join(f'<span class="pill {"yes" if t["hit"] else ""}"><i></i>{esc(t["label"])}</span>' for t in m["trips"])
    thesis = esc(p["thesis"]) if p["thesis"] else "Ingen tes inskriven ännu. Lägg en rad i positions.json."
    return (f'<details class="sr"><summary class="hr">{head}{chip(m["hz"]["1d"])}{chip(m["hz"]["5d"])}{chip(m["hz"]["20d"])}'
            f'<div class="c">{rel}</div><div class="c">{v200}</div>{delta.spark(m["spark"])}{flag}</summary>'
            f'<div class="info"><p><b>Varför:</b> {thesis}</p><div class="pills">{trips}</div>'
            f'<p class="mut">P/L mot GAV: {pl} · Från 52v-topp: {m["dd"]:+.1f}% · Volatilitet vs normalt: {m["volx"]:.1f}x · '
            f'Relativt {esc(p["bench"] or "marknaden")} 20d: {rel} · Senast {m["asof"]}'
            f'{" · Fond: kursen är en proxy, inte fondens egen" if p["proxy"] else ""}</p></div></details>')


EXTRA_CSS = """
.hr{display:grid;grid-template-columns:minmax(0,1.8fr) 52px 60px 60px 60px 66px 66px 96px 26px;gap:.5rem;align-items:center;padding:.4rem 0;border-top:1px solid var(--line)}
.hr .c{text-align:right;font-variant-numeric:tabular-nums}.hr .c.hot{font-weight:700}.nodata{grid-column:span 7;color:var(--mut)}
.hh{display:grid;grid-template-columns:minmax(0,1.8fr) 52px 60px 60px 60px 66px 66px 96px 26px;gap:.5rem;color:var(--mut);font-size:.72rem;text-transform:uppercase;padding:.2rem 0}
.hh div:nth-child(n+2){text-align:right}.tw{background:var(--off);color:#fff;border-radius:99px;font-size:.72rem;text-align:center}
@media(max-width:700px){.hr,.hh{grid-template-columns:minmax(0,1fr) 46px 58px 58px 26px}.hr .c:nth-of-type(1),.hr .c:nth-of-type(4),.hr .c:nth-of-type(5),.sp,.hh div:nth-child(3),.hh div:nth-child(6),.hh div:nth-child(7),.hh div:nth-child(8){display:none}}
"""
CSS = re.search(r"<style>(.*?)</style>", delta.PAGE, re.S).group(1) + EXTRA_CSS
PAGE = ('<!doctype html><html lang="sv"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        "<title>Portfölj</title><style>" + CSS + "</style><main>"
        '<header><h1>Portfölj</h1><a class="mut" href="index.html">← Makro</a></header>'
        '<div class="hl %%TONE%%"><b>%%TITLE%%</b><span class="mut">%%SUB%%</span></div>%%FLIPS%%'
        "<h2>Makro och dina innehav</h2><div class=\"reads\">%%NOTES%%</div>"
        '<h2>Innehav <small>(klicka för tes, tripwires och detaljer. Vikter från %%SNAP%%)</small></h2>'
        '<div class="card"><div class="hh"><div>Innehav</div><div>Vikt</div><div>1d</div><div>5d</div><div>20d</div><div>vs index 20d</div><div>vs 200d</div><div></div><div></div></div>%%ROWS%%</div>'
        '<footer>Kurser: Alpaca (USA) och Yahoo (Sverige), fördröjda och inofficiella i vissa fall. Fonder visas med en proxy. Inte rådgivning.</footer></main></html>')


def main(fa=fetch_alpaca, fy=fetch_yahoo):
    cfg = json.loads(pathlib.Path("positions.json").read_text())
    pos = cfg["positions"]
    series = {}
    a_syms = sorted({p["symbol"] for p in pos if p["src"] == "alpaca"} | {p["bench"] for p in pos if p["bench"] == "SPY"})
    try:
        series.update(fa(a_syms))
    except Exception as e:
        print("Alpaca-fel:", e)
    for sym in sorted({p["symbol"] for p in pos if p["src"] == "yahoo"} | {p["bench"] for p in pos if p["bench"] == "^OMX"}):
        try:
            series[sym] = fy(sym)
        except Exception as e:
            print(f"Yahoo hoppar över {sym}: {e}")
    res = [(p, metrics(p, series[p["symbol"]], series.get(p["bench"])) if p["symbol"] in series else None) for p in pos]
    if not any(m for _, m in res):
        raise SystemExit("Ingen kursdata alls, avbryter.")
    hits = {f'{p["ticker"]}: {t["label"]}': t["hit"] for p, m in res if m for t in m["trips"]}
    sf = OUT / "portfolio_state.json"
    prev = json.loads(sf.read_text()).get("trips", {}) if sf.exists() else {}
    flips = [f'{k} ({"utlöst" if v else "ej längre utlöst"})' for k, v in hits.items() if k in prev and prev[k] != v]
    sf.write_text(json.dumps({"trips": hits}, ensure_ascii=False, indent=1))
    trig = [k for k, v in hits.items() if v]
    tone, title = ("off", f"{len(trig)} tripwire{'s' if len(trig) != 1 else ''} utlöst{'a' if len(trig) != 1 else ''}") if trig else ("neutral", "Inga tripwires utlösta")
    sub = " · ".join(trig[:4]) + (" …" if len(trig) > 4 else "") if trig else "Inget av dina innehav bryter sina regler just nu."
    st = OUT / "state.json"
    R = {r["id"]: r for r in json.loads(st.read_text()).get("rows", [])} if st.exists() else {}
    notes = macro_notes({p["sector"] for p in pos}, R)
    nh = "".join(f'<div class="rd {t}"><b>{esc(a)}</b><span class="mut">{esc(b)}</span></div>' for t, a, b in notes) \
        or '<div class="rd"><span class="mut">Inget i makrot sticker ut för dina innehav just nu.</span></div>'
    rows_html = ""
    for title_, flt in (("Svenska aktier", lambda p: p["type"] == "STOCK" and p["country"] == "SE"),
                        ("Amerikanska aktier", lambda p: p["type"] == "STOCK" and p["country"] == "US"),
                        ("Fonder", lambda p: p["type"] == "FUND")):
        sel = [(p, m) for p, m in res if flt(p)]
        if sel:
            rows_html += f'<h3 style="margin:.9rem 0 .2rem;font-size:.8rem;color:var(--mut)">{title_}</h3>' + "".join(card(p, m) for p, m in sel)
    page = (PAGE.replace("%%TONE%%", tone).replace("%%TITLE%%", esc(title)).replace("%%SUB%%", esc(sub))
            .replace("%%FLIPS%%", "".join(f'<div class="flip">Förändring: {esc(f)}</div>' for f in flips))
            .replace("%%NOTES%%", nh).replace("%%ROWS%%", rows_html).replace("%%SNAP%%", cfg["snapshot"]))
    (OUT / "portfolio.html").write_text(page, encoding="utf-8")
    print(f"Klar. {sum(1 for _, m in res if m)}/{len(pos)} innehav med data, {len(trig)} tripwires utlösta.")


if __name__ == "__main__":
    main()
