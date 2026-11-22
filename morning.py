#!/usr/bin/env python3
"""Morgonuppdatering -> docs/index.html. Regelbaserad och gratis.
Läser docs/state.json (från delta.py), docs/portfolio_state.json (från watchlist.py) och positions.json,
hämtar dagens kalender från FRED och nattens rörelser från Yahoo."""
import html, json, os, pathlib, time, datetime as dt, urllib.parse, urllib.request
import pandas as pd
import delta, ui

OUT = pathlib.Path("docs")
OUT.mkdir(exist_ok=True)
esc = html.escape
DAYS = ["måndag", "tisdag", "onsdag", "torsdag", "fredag", "lördag", "söndag"]
MONTHS = ["januari", "februari", "mars", "april", "maj", "juni", "juli", "augusti", "september", "oktober", "november", "december"]
# (nyckelord i FRED:s releasenamn, etikett, vikt 1-3)
EVENTS = [
    ("Consumer Price Index", "Inflation (KPI)", 3), ("Employment Situation", "Jobbrapport (sysselsättning)", 3),
    ("Gross Domestic Product", "BNP", 3), ("Personal Income and Outlays", "PCE-inflation (Feds favoritmått)", 3),
    ("FOMC", "Fed (FOMC)", 3), ("Producer Price Index", "Producentpriser", 2),
    ("Advance Monthly Sales for Retail", "Detaljhandelsförsäljning", 2),
    ("Unemployment Insurance Weekly Claims", "Jobbansökningar (veckovis)", 2),
    ("Job Openings and Labor Turnover", "Lediga jobb (JOLTS)", 2),
    ("Industrial Production", "Industriproduktion", 1), ("New Residential Construction", "Bostadsbyggande", 1),
]
MARKETS = [("ES=F", "S&P 500-futures"), ("NQ=F", "Nasdaq-futures"), ("^N225", "Nikkei (Japan)"), ("^HSI", "Hang Seng")]
UA = {"User-Agent": "Mozilla/5.0"}


def fetch_calendar(today, days=7):
    key = os.environ.get("FRED_API_KEY")
    if not key:
        raise RuntimeError("FRED_API_KEY saknas")
    q = {"api_key": key, "file_type": "json", "realtime_start": today.isoformat(),
         "realtime_end": (today + dt.timedelta(days=days)).isoformat(),
         "include_release_dates_with_no_data": "true", "order_by": "release_date", "sort_order": "asc", "limit": 1000}
    req = urllib.request.Request("https://api.stlouisfed.org/fred/releases/dates?" + urllib.parse.urlencode(q), headers=UA)
    with urllib.request.urlopen(req, timeout=20) as r:
        j = json.loads(r.read())
    seen, out = set(), []
    for d in j.get("release_dates", []):
        for kw, label, w in EVENTS:
            if kw.lower() in d["release_name"].lower() and (d["date"], label) not in seen:
                seen.add((d["date"], label))
                out.append({"date": d["date"], "label": label, "w": w})
                break
    return out


def fetch_change(sym):
    """Senaste förändringen i % mellan de två sista stängningarna (för futures: pågående kurs)."""
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(sym)}?range=5d&interval=1d"
    last = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=15) as r:
                res = json.loads(r.read())["chart"]["result"][0]
            s = pd.Series(res["indicators"]["quote"][0]["close"]).dropna()
            return float((s.iloc[-1] / s.iloc[-2] - 1) * 100)
        except Exception as e:
            last = e
            time.sleep(2 * (attempt + 1))
    raise last


def load(name, default):
    f = OUT / name
    return json.loads(f.read_text()) if f.exists() else default


def build_items(today, R, state, events, mk, se_share, trips):
    items = []

    def add(tone, title, detail):
        items.append({"tone": tone, "title": title, "detail": detail})
    for r in [x for x in delta.build_reads(R) if x["tone"] == "off"][:3]:
        add("off", "Pågår: " + r["title"], r["detail"])
    for f in state.get("flips", []):
        add("neutral", "Regimbyte: " + f, "Ändring sedan förra körningen.")
    hi = [e for e in (events or []) if e["date"] == today.isoformat() and e["w"] == 3]
    if hi:
        add("neutral", "Hög eventrisk idag: " + ", ".join(e["label"] for e in hi),
            "Siffran kan flytta räntor och aktier snabbt. Mest känsligt i din portfölj: banker (SEB, Swedbank, Nordea, JPM) och Investor.")
    es = mk.get("ES=F")
    if es is not None and abs(es) >= 1:
        add("off" if es < 0 else "on", f"S&P-futures {es:+.1f} %",
            f"Svenska marknaden brukar följa med vid öppning. {se_share:.0f} % av din portfölj är svenska innehav (aktier och OMXS30-fonden).")
    asia = [f"{n} {mk[s]:+.1f} %" for s, n in MARKETS[2:] if s in mk and abs(mk[s]) >= 2]
    if asia:
        add("neutral", "Asien rör sig kraftigt", ", ".join(asia))
    trig = [k for k, v in trips.items() if v]
    if trig:
        add("off", f"{len(trig)} tripwire{'s' if len(trig) != 1 else ''} utlöst{'a' if len(trig) != 1 else ''} i portföljen", " · ".join(trig[:4]))
    if not items:
        add("neutral", "Inget utöver det vanliga", "Inga signaler över tröskeln just nu.")
    items.sort(key=lambda x: {"off": 0, "neutral": 1, "on": 2}[x["tone"]])
    return items[:7]


def headline(items, events, today, mk):
    off = sum(i["tone"] == "off" for i in items)
    on = sum(i["tone"] == "on" for i in items)
    tone, title = ("off", "Försiktigt läge") if off - on >= 2 else ("on", "Positivt läge") if on - off >= 2 else ("neutral", "Blandat läge")
    if items[0]["title"].startswith("Inget utöver"):
        tone, title = "neutral", "Lugnt läge"
    parts = []
    todays = [e for e in (events or []) if e["date"] == today.isoformat() and e["w"] >= 2]
    if todays:
        parts.append(f"{len(todays)} publicering{'ar' if len(todays) != 1 else ''} idag: " + ", ".join(e["label"] for e in todays[:3]))
    if mk.get("ES=F") is not None:
        parts.append(f"S&P-futures {mk['ES=F']:+.1f} %")
    parts.append("Regelbaserad sammanfattning, ingen prognos.")
    return tone, title, " · ".join(parts)


def schedule(events, today):
    if events is None:
        return '<div class="rd"><span class="mut">Kalendern kunde inte hämtas just nu.</span></div>'
    if not events:
        return '<div class="rd"><span class="mut">Inga större publiceringar de närmaste dagarna.</span></div>'
    out = []
    for e in sorted(events, key=lambda e: (e["date"], -e["w"])):
        d = dt.date.fromisoformat(e["date"])
        when = "Idag" if d == today else f"{DAYS[d.weekday()][:3].capitalize()} {d.day}/{d.month}"
        out.append(f'<div class="ev w{e["w"]}"><span class="when">{when}</span><b>{esc(e["label"])}</b>'
                   f'<span class="imp">{["", "låg", "medel", "hög"][e["w"]]} vikt</span></div>')
    return "".join(out)


def main(fcal=fetch_calendar, fchg=fetch_change, today=None):
    today = today or dt.date.today()
    state = load("state.json", {})
    R = {r["id"]: r for r in state.get("rows", [])}
    trips = load("portfolio_state.json", {}).get("trips", {})
    pos = json.loads(pathlib.Path("positions.json").read_text())["positions"] if pathlib.Path("positions.json").exists() else []
    se_share = sum(p["weight"] for p in pos if p["country"] == "SE" and (p["type"] == "STOCK" or p["symbol"] == "^OMX"))
    try:
        events = fcal(today)
    except Exception as e:
        print("Kalender-fel:", e)
        events = None
    mk = {}
    for sym, _ in MARKETS:
        try:
            mk[sym] = fchg(sym)
        except Exception as e:
            print(f"Yahoo hoppar över {sym}: {e}")
    items = build_items(today, R, state, events, mk, se_share, trips)
    tone, title, sub = headline(items, events, today, mk)
    cards = "".join(f'<div class="rd {i["tone"]}"><b>{esc(i["title"])}</b><span class="mut">{esc(i["detail"])}</span></div>' for i in items)
    tiles = "".join(
        f'<div class="tile"><small>{n}</small><b class="{"up" if mk.get(s, 0) > 0 else "dn"}">{mk[s]:+.1f}%</b></div>' if s in mk
        else f'<div class="tile"><small>{n}</small><b class="mut">–</b></div>' for s, n in MARKETS)
    pills = "".join(f'<span class="pill {"yes" if v else ""}"><i></i>{esc(k)}</span>' for k, v in state.get("regimes", {}).items())
    body = (f'<div class="hl {tone}"><b>{esc(title)}</b><span class="mut">{esc(sub)}</span></div>'
            f'<h2>Att hålla ögonen på</h2><div class="reads">{cards}</div>'
            f'<h2>Dagens schema <small>(och kommande dagar)</small></h2>{schedule(events, today)}'
            f'<h2>Över natten</h2><div class="tiles">{tiles}</div>'
            f'<h2>Regim</h2><div class="pills">{pills or "<span class=mut>Ingen regimdata ännu.</span>"}</div>'
            f'<p class="mut" style="margin-top:1.5rem">Schemat visar vilka datapublikationer som kommer. Förväntningar (konsensus) finns inte gratis, så du ser att siffran kommer men inte vad marknaden räknar med.</p>')
    sub_top = f"{DAYS[today.weekday()].capitalize()} {today.day} {MONTHS[today.month - 1]} {today.year}"
    (OUT / "index.html").write_text(ui.wrap("index", "Idag", sub_top, body), encoding="utf-8")
    print(f"Klar. {len(items)} punkter, {len(events or [])} händelser, {len(mk)}/{len(MARKETS)} marknader.")


if __name__ == "__main__":
    main()
