#!/usr/bin/env python3
"""Delta-terminal v2.
26 gratisserier från FRED -> ovanliga förändringar (z-score) -> regelbaserad tolkning
-> regimbyten sedan senast -> docs/index.html (+ docs/state.json).
Kör: FRED_API_KEY=... python delta.py   (pip install pandas)
"""
import html, json, os, pathlib, time, datetime as dt, urllib.request
import pandas as pd
import ui

OUT = pathlib.Path("docs")
OUT.mkdir(exist_ok=True)
esc = html.escape

# FRED-id: (namn, grupp, typ, frekvens)  typ: pct=%-förändring | bp=räntepunkter (data i %) | pts=poäng
SERIES = {
    "SP500": ("S&P 500", "Risk", "pct", "d"),
    "NASDAQCOM": ("Nasdaq", "Risk", "pct", "d"),
    "VIXCLS": ("VIX", "Risk", "pts", "d"),
    "BAMLH0A0HYM2": ("High yield-spread", "Kredit", "bp", "d"),
    "BAMLC0A0CM": ("Investment grade-spread", "Kredit", "bp", "d"),
    "DFF": ("Styrränta (Fed funds)", "Räntor", "bp", "d"),
    "DTB3": ("US 3-månadersränta", "Räntor", "bp", "d"),
    "DGS2": ("US 2-årsränta", "Räntor", "bp", "d"),
    "DGS10": ("US 10-årsränta", "Räntor", "bp", "d"),
    "DGS30": ("US 30-årsränta", "Räntor", "bp", "d"),
    "T10Y2Y": ("Kurva 10y-2y", "Räntor", "bp", "d"),
    "T10Y3M": ("Kurva 10y-3m", "Räntor", "bp", "d"),
    "MORTGAGE30US": ("US bolåneränta 30 år", "Räntor", "bp", "w"),
    "DFII10": ("Realränta 10y (TIPS)", "Inflation", "bp", "d"),
    "T10YIE": ("Inflationsförväntan 10y", "Inflation", "bp", "d"),
    "T5YIFR": ("Inflationsförväntan 5y5y", "Inflation", "bp", "d"),
    "ICSA": ("Jobbansökningar (nya)", "Arbetsmarknad", "pct", "w"),
    "UNRATE": ("US arbetslöshet", "Arbetsmarknad", "pts", "m"),
    "NFCI": ("Finansiella villkor (NFCI)", "Likviditet", "pts", "w"),
    "WALCL": ("Fedens balansräkning", "Likviditet", "pct", "w"),
    "DTWEXBGS": ("Dollarindex (bred)", "Valuta", "pct", "d"),
    "DEXSIUS": ("SEK per USD", "Valuta", "pct", "d"),
    "DEXUSEU": ("USD per EUR", "Valuta", "pct", "d"),
    "DCOILWTICO": ("Olja WTI", "Råvaror", "pct", "d"),
    "DCOILBRENTEU": ("Olja Brent", "Råvaror", "pct", "d"),
    "DHHNGSP": ("Naturgas (Henry Hub)", "Råvaror", "pct", "d"),
}
GROUPS = ["Risk", "Kredit", "Räntor", "Inflation", "Arbetsmarknad", "Likviditet", "Valuta", "Råvaror"]
FREQ = {  # horisonter, lookback (obs), min historik, hämtningsfönster (dagar)
    "d": {"h": {"1d": 1, "5d": 5, "20d": 20}, "look": 260, "min": 100, "days": 1100},
    "w": {"h": {"1v": 1, "4v": 4, "13v": 13}, "look": 104, "min": 50, "days": 1800},
    "m": {"h": {"1m": 1, "3m": 3, "6m": 6}, "look": 60, "min": 30, "days": 3650},
}
UNIT = {"pct": "%", "bp": " bp", "pts": " p"}

# vad är det, vad händer när den går upp, vad händer när den går ner
INFO = {
    "SP500": ("Index över 500 stora amerikanska bolag, det vanligaste måttet på hur aktiemarknaden mår.",
              "Bra för aktieägare. Speglar ofta förväntad vinsttillväxt och lägre risk. Snabba uppgångar utan stöd från kredit kan vara sköra.",
              "Dåligt för aktieägare. Faller ofta när tillväxtoro, högre räntor eller ökad risk slår igenom. Stora fall kan smitta av sig på konsumtion och finansiering."),
    "NASDAQCOM": ("Teknik- och tillväxttungt index, känsligare för räntor än S&P 500.",
                  "Ökad riskaptit och tillväxttro, ofta när räntorna faller.",
                  "Ofta ränteuppgång eller minskad riskvilja. Tillväxtbolag drabbas hårdare än breda index."),
    "VIXCLS": ("Förväntad volatilitet i S&P 500 de närmaste 30 dagarna, ofta kallat rädslomåttet.",
               "Oro på marknaden, dåligt för aktier på kort sikt. VIX och aktiefall följs ofta åt.",
               "Lugn och lägre riskpremie, bra för aktier. Mycket låg VIX kan dock tyda på självbelåtenhet."),
    "BAMLH0A0HYM2": ("Extra ränta som företag med låg kreditvärdighet måste betala över statsräntan.",
                     "Investerare kräver mer betalt för risk. Varnar för sämre konjunktur och fler konkurser. Dåligt för riskfyllda tillgångar och för bolag som behöver refinansiera.",
                     "Ökat förtroende och billigare finansiering, bra för risktillgångar. Mycket låga spreadar ger litet utrymme för felsteg."),
    "BAMLC0A0CM": ("Samma sak som high yield, fast för företag med hög kreditvärdighet.",
                   "Oron når även de säkra bolagen, vilket tyder på bredare finansiell stress.",
                   "Gynnsamma finansieringsvillkor för stora företag."),
    "DFF": ("Federal Reserves styrränta, priset på kortfristiga pengar.",
            "Dyrare lån och åtstramning. Bromsar ekonomi och inflation, pressar ofta tillväxtaktier och bostäder, gynnar sparare.",
            "Billigare lån och stimulans, ofta bra för aktier och bostäder. Kan också betyda att ekonomin har försvagats."),
    "DTB3": ("Ränta på 3 månaders statsskuldväxlar, följer marknadens syn på styrräntan.",
             "Marknaden räknar med högre styrränta.",
             "Marknaden räknar med sänkningar, eller flyr till säkerhet."),
    "DGS2": ("Ränta på 2-åriga statsobligationer, den som känner av Feds förväntade bana mest.",
             "Marknaden prisar in högre eller längre kvarvarande styrränta, ofta efter stark data eller hög inflation.",
             "Marknaden prisar in sänkningar, ofta för att tillväxten ser svagare ut."),
    "DGS10": ("Riktränta för lån och för hur långsiktiga tillgångar värderas. Styr bland annat bolåneräntor.",
              "Dyrare finansiering och lägre värdering av framtida vinster, särskilt för tillväxtbolag. Pressar ofta både aktier och obligationspriser. Bra för den som köper nya obligationer.",
              "Lättare villkor och stöd för värdering och bostäder. Om fallet beror på oro är det i stället en varningssignal."),
    "DGS30": ("Den långa räntan, speglar långsiktig inflation och statsfinanser.",
              "Oro för inflation eller statsskuld (högre term premium). Tryck på långa tillgångar.",
              "Lägre långsiktiga förväntningar på inflation och tillväxt, eller flykt till säkerhet."),
    "T10Y2Y": ("Skillnaden mellan 10- och 2-årsränta, en klassisk konjunkturindikator.",
               "Kurvan brantar. Efter en inversion kommer det ofta när marknaden prisar in sänkningar eller när lågkonjunkturen närmar sig.",
               "Kurvan planar ut eller inverteras: marknaden prisar in tight politik och svagare tillväxt. Inversion har historiskt föregått de flesta amerikanska lågkonjunkturer, men med lång och osäker fördröjning."),
    "T10Y3M": ("Skillnaden mellan 10-årsränta och 3-månadersränta, den kurva som oftast används för recessionsrisk.",
               "Kurvan brantar. Nära en lågkonjunktur kan det betyda att marknaden väntar sig snabba sänkningar.",
               "Planare eller inverterad kurva: tight penningpolitik och ökad recessionsrisk framåt."),
    "MORTGAGE30US": ("Genomsnittlig 30-årig bolåneränta i USA (Freddie Mac), veckodata.",
                     "Dyrare att köpa bostad. Dämpar bostadsmarknad och byggande. Bra för sparare.",
                     "Stimulerar bostadsmarknad och omfinansiering."),
    "DFII10": ("Realränta: 10-årsräntan justerad för inflation, det verkliga priset på pengar.",
               "Tightare finansiella villkor. Pressar värdering av aktier (särskilt tillväxt) och guld.",
               "Lättare villkor och stöd för riskfyllda tillgångar."),
    "T10YIE": ("Break-even-inflation: vad marknaden förväntar sig för inflation de närmaste 10 åren.",
               "Högre förväntad inflation. Ökar trycket på centralbanken att strama åt, följer ofta oljepriset. Gynnar realtillgångar, drabbar nominella obligationer.",
               "Lägre inflations- eller tillväxtförväntningar. Gynnar obligationer men kan tyda på svag efterfrågan."),
    "T5YIFR": ("Förväntad inflation 5 år framåt, räknat från om 5 år. Ett mått på hur väl inflationsförväntningarna är förankrade.",
               "Förväntningarna lossnar från målet (cirka 2 %). Ett problem för centralbanken.",
               "Förväntningar under målet, kan tyda på deflationsoro."),
    "ICSA": ("Antal nya ansökningar om arbetslöshetsersättning i USA per vecka, en snabb indikator på arbetsmarknaden.",
             "Fler uppsägningar, en tidig varning för svagare konjunktur. Enstaka veckor kan vara brus, till exempel kring högtider.",
             "Stark arbetsmarknad, bra för konsumtion. Kan samtidigt hålla räntorna uppe."),
    "UNRATE": ("Andelen arbetslösa i USA, månadsdata.",
               "Svagare ekonomi. En snabb ökning (cirka 0,5 procentenheter) har historiskt sammanfallit med lågkonjunktur. Kan leda till räntesänkningar.",
               "Starkare arbetsmarknad, bra för konsumtion men kan driva på löneinflation."),
    "NFCI": ("Chicago Feds index för finansiella villkor (kredit, risk, hävstång). Noll är genomsnitt.",
             "Strammare villkor (över 0): dyrare och svårare att få finansiering, dåligt för tillväxt.",
             "Lättare villkor (under 0): gynnsamt för risktillgångar och tillväxt."),
    "WALCL": ("Totala tillgångar på Federal Reserves balansräkning, ett mått på hur mycket likviditet centralbanken tillför.",
              "Fed köper tillgångar (QE) och tillför likviditet, vilket stödjer tillgångspriser.",
              "Fed krymper balansräkningen (QT) och drar undan likviditet, vilket kan pressa risktillgångar."),
    "DTWEXBGS": ("Dollarn mot en bred korg av USA:s handelspartners valutor.",
                 "Åtstramar globala finansiella villkor. Dåligt för råvaror, tillväxtmarknader och dollarskuldsatta utanför USA. Pressar amerikanska exportbolags utlandsvinster.",
                 "Lättare globala villkor. Stöd för råvaror och tillväxtmarknader."),
    "DEXSIUS": ("Hur många svenska kronor en dollar kostar.",
                "Kronan försvagas. Dyrare import och dyrare att köpa dollartillgångar (till exempel amerikanska aktier), ökat inflationstryck i Sverige. Gynnar exportbolag och dig som redan äger dollartillgångar.",
                "Kronan stärks. Billigare import och lägre inflation, men dollartillgångar tappar värde i kronor och exportörer pressas."),
    "DEXUSEU": ("Hur många dollar en euro kostar.",
                "Euron stärks och dollarn försvagas. Lättare globala villkor, men pressar europeiska exportörer.",
                "Euron försvagas och dollarn stärks. Motsatt effekt: strängare globala villkor, stöd för europeisk export."),
    "DCOILWTICO": ("Priset på amerikansk råolja (WTI).",
                   "Dyrare energi: högre inflation och svagare konsumtion. Bra för oljebolag och producentländer, dåligt för transport, industri och konsumenter.",
                   "Lättar inflationen och gynnar konsumenter, men drabbar oljebolag. Om fallet beror på svag efterfrågan är det en varningssignal."),
    "DCOILBRENTEU": ("Internationell oljeprisreferens (Nordsjön), används för det mesta av världens olja.",
                     "Dyrare energi, högre inflation, bra för producenter.",
                     "Billigare energi och lägre inflation, men sämre för producenter."),
    "DHHNGSP": ("Priset på naturgas i USA (Henry Hub).",
                "Dyrare uppvärmning, el och industriinsatser. Bra för gasproducenter.",
                "Billigare energi och lägre kostnader. Sämre för gasproducenter."),
}



def fetch(sid):
    key = os.environ.get("FRED_API_KEY")
    if not key:
        raise SystemExit("FRED_API_KEY saknas. Lägg den som GitHub-secret.")
    since = dt.date.today() - dt.timedelta(days=FREQ[SERIES[sid][3]]["days"])
    url = ("https://api.stlouisfed.org/fred/series/observations"
           f"?series_id={sid}&api_key={key}&file_type=json&observation_start={since}")
    last = None
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "delta-terminal/0.3"})
            with urllib.request.urlopen(req, timeout=15) as r:
                obs = json.loads(r.read())["observations"]
            s = pd.Series({pd.Timestamp(o["date"]): float(o["value"]) for o in obs if o["value"] != "."})
            return s.sort_index().tail(900)
        except Exception as e:
            last = e
            time.sleep(2 * (attempt + 1))
    raise last


def change(s, n, kind):
    if kind == "pct":
        return s.pct_change(n) * 100
    return s.diff(n) * (100 if kind == "bp" else 1)


def analyse(sid, s):
    name, group, kind, freq = SERIES[sid]
    cfg = FREQ[freq]
    hz = {}
    for h, n in cfg["h"].items():
        c = change(s, n, kind).dropna()
        hist = c.iloc[-cfg["look"] - 1:-1]
        if len(hist) < cfg["min"] or hist.std() == 0:
            continue
        hz[h] = {"chg": float(c.iloc[-1]), "z": float((c.iloc[-1] - hist.mean()) / hist.std())}
    if not hz:
        return None
    best = max(hz, key=lambda h: abs(hz[h]["z"]))
    spark = s.tail({"d": 120, "w": 52, "m": 36}[freq]).round(4).tolist()
    return {"id": sid, "name": name, "group": group, "kind": kind, "freq": freq,
            "mid": list(cfg["h"])[1], "last": float(s.iloc[-1]), "asof": str(s.index[-1].date()),
            "hz": hz, "h": best, "chg": hz[best]["chg"], "z": hz[best]["z"], "spark": spark}


def regimes(d):
    def pct(s):
        return float((s.iloc[-504:] < s.iloc[-1]).mean() * 100)
    r = {}
    if "T10Y2Y" in d: r["Räntekurvan är inverterad (10y-2y)"] = bool(d["T10Y2Y"].iloc[-1] < 0)
    if "VIXCLS" in d: r["Hög volatilitet (VIX över 80:e percentilen)"] = pct(d["VIXCLS"]) > 80
    if "BAMLH0A0HYM2" in d: r["Kreditstress (spreadar över 80:e percentilen)"] = pct(d["BAMLH0A0HYM2"]) > 80
    if "SP500" in d: r["Aktier under 200-dagarssnittet"] = bool(d["SP500"].iloc[-1] < d["SP500"].tail(200).mean())
    if "NFCI" in d: r["Finansiella villkor åtstramade (NFCI över 0)"] = bool(d["NFCI"].iloc[-1] > 0)
    if "DFII10" in d: r["Hög realränta (över 2 %)"] = bool(d["DFII10"].iloc[-1] > 2)
    return r


def build_reads(R):
    out = []

    def add(tone, title, detail):
        out.append({"tone": tone, "title": title, "detail": detail})

    def hz(sid, h=None):
        r = R.get(sid)
        return (r["hz"].get(h or r["mid"]), r["mid"]) if r else (None, None)

    def big(x, t=1.5):
        return x is not None and abs(x["z"]) >= t

    spx, m = hz("SP500"); vix, _ = hz("VIXCLS"); hy, _ = hz("BAMLH0A0HYM2")
    if big(spx) and big(vix) and spx["chg"] < 0 < vix["chg"]:
        add("off", "Risk-off: aktier ner, volatilitet upp", f"S&P 500 {spx['chg']:+.1f}% och VIX {vix['chg']:+.1f} p ({m}).")
    elif big(spx) and big(vix) and vix["chg"] < 0 < spx["chg"]:
        add("on", "Risk-on: aktier upp, volatilitet ner", f"S&P 500 {spx['chg']:+.1f}% och VIX {vix['chg']:+.1f} p ({m}).")
    elif big(vix) and vix["chg"] > 0:
        add("off", "Volatiliteten stiger ovanligt", f"VIX {vix['chg']:+.1f} p ({m}).")
    elif big(spx):
        add("off" if spx["chg"] < 0 else "on", "Aktier rör sig ovanligt " + ("ner" if spx["chg"] < 0 else "upp"), f"S&P 500 {spx['chg']:+.1f}% ({m}).")
    if big(hy) and hy["chg"] > 0:
        add("off", "Kreditspreadar vidgas", f"High yield-spread {hy['chg']:+.0f} bp ({m}). Kreditmarknaden bekräftar stress, vilket ofta väger tyngre än enbart VIX.")
    if hy and spx and spx["z"] >= 1 and hy["z"] >= 1:
        add("neutral", "Divergens: aktier upp men kreditspreadar vidgas", "Aktier och kredit säger olika saker. Kredit anses ofta reagera tidigare på försämrade förutsättningar.")

    y10, m = hz("DGS10"); ry, _ = hz("DFII10"); be, _ = hz("T10YIE"); y2, _ = hz("DGS2"); cv, _ = hz("T10Y2Y")
    if big(y10):
        det = f"US 10y {y10['chg']:+.0f} bp ({m})"
        if ry and be:
            drv = "realräntor (tightare finansiella villkor)" if abs(ry["chg"]) >= abs(be["chg"]) else "inflationsförväntningar"
            det += f", realränta {ry['chg']:+.0f} bp, inflationsförväntan {be['chg']:+.0f} bp. Rörelsen drivs mest av {drv}."
        up = y10["chg"] > 0
        add("off" if up else "neutral", "Långräntorna " + ("stiger" if up else "faller") + " ovanligt snabbt", det)
    if big(cv):
        if cv["chg"] > 0:
            txt = ("Kort ränta faller mer: marknaden prisar in lägre styrränta eller svagare tillväxt."
                   if y2 and y2["chg"] < 0 else
                   "Långa räntor stiger mer: ofta oro för inflation eller statsfinanser (term premium).")
            add("neutral", "Räntekurvan brantar", f"10y-2y {cv['chg']:+.0f} bp ({m}). {txt}")
        else:
            add("neutral", "Räntekurvan planar ut", f"10y-2y {cv['chg']:+.0f} bp ({m}). Marknaden prisar in tightare politik eller svagare tillväxt längre fram.")

    usd, m = hz("DTWEXBGS"); sek, _ = hz("DEXSIUS")
    if big(usd):
        up = usd["chg"] > 0
        add("off" if up else "on", "Dollarn " + ("stärks" if up else "försvagas") + " ovanligt snabbt",
            f"Bred dollarindex {usd['chg']:+.1f}% ({m}). " + ("Starkare dollar åtstramar globala finansiella villkor och är motvind för råvaror och tillväxtmarknader." if up else "Svagare dollar lättar globala finansiella villkor."))
    if big(sek):
        add("neutral", "Kronan " + ("försvagas" if sek["chg"] > 0 else "stärks") + " mot dollarn", f"SEK per USD {sek['chg']:+.1f}% ({m}).")

    oil, m = hz("DCOILWTICO")
    if big(oil):
        up = oil["chg"] > 0
        add("neutral", "Oljan " + ("stiger" if up else "faller") + " ovanligt mycket",
            f"WTI {oil['chg']:+.1f}% ({m}). " + ("Uppåtrisk för inflationen." if up else "Lättar inflationstrycket men kan signalera svagare efterfrågan."))

    ic, m = hz("ICSA"); un, mu = hz("UNRATE")
    if big(ic) and ic["chg"] > 0:
        add("off", "Jobbansökningar ökar ovanligt snabbt", f"Nya ansökningar om arbetslöshetsersättning {ic['chg']:+.1f}% ({m}). Tidig varningssignal för arbetsmarknaden.")
    if un and mu == "3m" and un["chg"] >= 0.3:
        add("off", "Arbetslösheten stiger", f"US arbetslöshet {un['chg']:+.1f} procentenheter på 3 månader.")

    nf, m = hz("NFCI"); fed, m2 = hz("WALCL"); mg, m3 = hz("MORTGAGE30US")
    if big(nf):
        add("off" if nf["chg"] > 0 else "on", "Finansiella villkor " + ("åtstramas" if nf["chg"] > 0 else "lättas") + " snabbt", f"NFCI {nf['chg']:+.2f} p ({m}).")
    if big(fed):
        add("on" if fed["chg"] > 0 else "off", "Fedens balansräkning " + ("växer" if fed["chg"] > 0 else "krymper") + " ovanligt snabbt", f"{fed['chg']:+.1f}% ({m2}). Påverkar likviditeten i systemet.")
    if big(mg) and mg["chg"] > 0:
        add("neutral", "Bolåneräntorna i USA stiger snabbt", f"{mg['chg']:+.0f} bp ({m3}).")
    return out


def headline(reads):
    if not reads:
        return "neutral", "Lugn dag", "Inget ligger över tröskeln (z ≥ 1,5)."
    off = sum(r["tone"] == "off" for r in reads)
    on = sum(r["tone"] == "on" for r in reads)
    tone, title = ("off", "Risk-off-lutning") if off - on >= 2 else ("on", "Risk-on-lutning") if on - off >= 2 else ("neutral", "Blandat läge")
    return tone, title, f"{len(reads)} signaler över tröskeln: " + " · ".join(r["title"] for r in reads[:3])


SPECIAL = {"WALCL": lambda v: f"{v / 1e6:.2f} tn $", "ICSA": lambda v: f"{v / 1000:.0f} k"}


def fmt(r):
    if r["id"] in SPECIAL: return SPECIAL[r["id"]](r["last"])
    v = r["last"]
    if r["kind"] == "bp": return f"{v:.2f}%"
    return f"{v:,.0f}".replace(",", " ") if abs(v) >= 1000 else f"{v:.2f}"


def spark(vals, w=96, h=26):
    if len(vals) < 2: return ""
    lo, hi = min(vals), max(vals)
    rng = (hi - lo) or 1
    pts = " ".join(f"{i * (w - 2) / (len(vals) - 1) + 1:.1f},{h - 2 - (v - lo) / rng * (h - 4):.1f}" for i, v in enumerate(vals))
    cls = "u" if vals[-1] >= vals[0] else "d"
    return f'<svg class="sp {cls}" viewBox="0 0 {w} {h}" width="{w}" height="{h}"><polyline points="{pts}" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/></svg>'


def zbar(z):
    w = min(abs(z), 4) / 4 * 50
    pos = "left:50%" if z > 0 else "right:50%"
    return f'<div class="zb"><i class="{"hot" if abs(z) >= 2 else ""}" style="width:{w:.0f}%;{pos}"></i></div>'


def info_panel(r):
    what, up, dn = INFO.get(r["id"], ("", "", ""))
    now = " · ".join(f'{h} {v["chg"]:+.1f}{UNIT[r["kind"]]} (z {v["z"]:+.1f})' for h, v in r["hz"].items())
    return (f'<div class="info"><p>{esc(what)}</p>'
            f'<div class="ud"><div><b class="up">▲ Går upp</b><span>{esc(up)}</span></div>'
            f'<div><b class="dn">▼ Går ner</b><span>{esc(dn)}</span></div></div>'
            f'<p class="mut">Just nu: {esc(now)}. z är hur många standardavvikelser rörelsen ligger från det normala senaste tiden. '
            f'Vad som är bra eller dåligt beror på sammanhanget, så läs det som tumregler.</p></div>')


def row(r):
    arrow = "▲" if r["chg"] > 0 else "▼" if r["chg"] < 0 else "–"
    cls = "up" if r["chg"] > 0 else "dn"
    fq = {"d": "dagsdata", "w": "veckodata", "m": "månadsdata"}[r["freq"]]
    return (f'<details class="sr"><summary class="row"><div class="nm" title="{fq}, senast {r["asof"]}">{esc(r["name"])}'
            f'{"" if r["freq"] == "d" else f" <small>{fq}</small>"}</div>'
            f'<div class="vl">{fmt(r)}</div>'
            f'<div class="ch {cls}">{arrow} {r["chg"]:+.1f}{UNIT[r["kind"]]} <small>/{r["h"]}</small></div>'
            f'{spark(r["spark"])}{zbar(r["z"])}</summary>{info_panel(r)}</details>')


PAGE = """<div class="hl %%TONE%%"><b>%%TITLE%%</b><span class="mut">%%SUB%%</span></div>
%%FLIPS%%
<h2>Läget i klartext</h2><div class="reads">%%READS%%</div>
<h2>Regim</h2><div class="pills">%%REGIME%%</div>
<h2>Alla serier <small>(klicka på en rad för förklaring. Stapeln visar hur ovanlig rörelsen är: fylld mot höger = upp, mot vänster = ner, gul = över 2 standardavvikelser)</small></h2>
<div class="grid">%%GROUPS%%</div>"""


def render(rows, reg, flips, asof):
    R = {r["id"]: r for r in rows}
    reads = build_reads(R)
    tone, title, sub = headline(reads)
    rd = "".join(f'<div class="rd {x["tone"]}"><b>{esc(x["title"])}</b><span class="mut">{esc(x["detail"])}</span></div>' for x in reads) \
        or '<div class="rd"><span class="mut">Inget ovanligt just nu.</span></div>'
    fl = "".join(f'<div class="flip">Regimbyte: {esc(t)}</div>' for t in flips)
    pills = "".join(f'<span class="pill {"yes" if v else ""}"><i></i>{esc(k)}</span>' for k, v in reg.items())
    groups = ""
    for g in GROUPS:
        items = [R[s] for s in SERIES if s in R and SERIES[s][1] == g]
        if items:
            groups += f'<div class="card"><h3>{g}</h3>{"".join(row(r) for r in items)}</div>'
    body = (PAGE.replace("%%TONE%%", tone).replace("%%TITLE%%", esc(title))
            .replace("%%SUB%%", esc(sub)).replace("%%FLIPS%%", fl).replace("%%READS%%", rd)
            .replace("%%REGIME%%", pills).replace("%%GROUPS%%", groups))
    return ui.wrap("makro", "Makro", f"Data t.o.m. {asof}", body)


def main(fetcher=fetch):
    data = {}
    for sid in SERIES:
        try:
            data[sid] = fetcher(sid)
        except Exception as e:
            print(f"Hoppar över {sid}: {e}")
    if len(data) < max(6, len(SERIES) // 2):
        raise SystemExit(f"Bara {len(data)} av {len(SERIES)} serier hämtades, avbryter.")
    rows = [r for sid, s in data.items() if (r := analyse(sid, s))]
    reg = regimes(data)
    state_file = OUT / "state.json"
    prev = json.loads(state_file.read_text()).get("regimes", {}) if state_file.exists() else {}
    flips = [f'{k}: {"nej → ja" if v else "ja → nej"}' for k, v in reg.items() if k in prev and prev[k] != v]
    asof = max((r["asof"] for r in rows), default=str(dt.date.today()))
    (OUT / "makro.html").write_text(render(rows, reg, flips, asof), encoding="utf-8")
    state_file.write_text(json.dumps({"asof": asof, "regimes": reg, "flips": flips,
                                      "rows": [{k: v for k, v in r.items() if k != "spark"} for r in rows]},
                                     ensure_ascii=False, indent=1))
    print(f"Klar. {len(rows)} serier, {len(flips)} regimbyten, {sum(abs(r['z']) >= 2 for r in rows)} ovanliga rörelser.")


if __name__ == "__main__":
    main()
