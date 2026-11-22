"""Gemensam layout för hela sidan: topp-navigering med flikar + CSS."""
NAV = [("index", "Idag", "index.html"), ("makro", "Makro", "makro.html"), ("portfolio", "Portfölj", "portfolio.html")]

CSS = """
:root{--bg:#0b0e13;--card:#141922;--line:#232a36;--fg:#e6e9ef;--mut:#8a93a3;--up:#4da3ff;--dn:#ff9a4d;--hot:#ffc233;--off:#ff5c5c;--on:#3ddc97}
@media(prefers-color-scheme:light){:root{--bg:#f5f6f8;--card:#fff;--line:#e3e6ec;--fg:#14171c;--mut:#667085;--up:#1a6fd6;--dn:#d9660f;--hot:#e0a100;--off:#d93636;--on:#14a06a}}
*{box-sizing:border-box}html{scroll-behavior:smooth}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.55 system-ui,-apple-system,"Segoe UI",sans-serif}
nav{position:sticky;top:0;z-index:10;background:color-mix(in srgb,var(--bg) 88%,transparent);backdrop-filter:blur(10px);border-bottom:1px solid var(--line)}
.nv{max-width:1100px;margin:0 auto;padding:0 1rem;display:flex;align-items:center;gap:1.5rem;height:54px}
.nv>b{letter-spacing:.06em;font-size:.95rem}
.tabs{display:flex;gap:.3rem}.tabs a{padding:.45rem .9rem;border-radius:8px;color:var(--mut);text-decoration:none;font-weight:600;font-size:.92rem}
.tabs a:hover{background:var(--card);color:var(--fg)}.tabs a.act{background:var(--card);color:var(--fg);box-shadow:inset 0 -2px 0 var(--up)}
main{max-width:1100px;margin:0 auto;padding:1.6rem 1rem 3.5rem}
.ph{display:flex;justify-content:space-between;align-items:baseline;gap:1rem;flex-wrap:wrap;margin-bottom:1rem}
h1{font-size:1.6rem;margin:0;letter-spacing:-.01em}.mut,small{color:var(--mut)}
h2{font-size:.78rem;color:var(--mut);text-transform:uppercase;letter-spacing:.09em;margin:2.2rem 0 .7rem;font-weight:700}
.hl{background:var(--card);border:1px solid var(--line);border-left:5px solid var(--mut);border-radius:12px;padding:1.1rem 1.3rem}
.hl.off{border-left-color:var(--off)}.hl.on{border-left-color:var(--on)}.hl b{font-size:1.45rem;display:block;margin-bottom:.15rem}
.reads{display:grid;gap:.55rem}.rd{background:var(--card);border:1px solid var(--line);border-left:4px solid var(--mut);border-radius:10px;padding:.7rem 1rem}
.rd.off{border-left-color:var(--off)}.rd.on{border-left-color:var(--on)}.rd b{display:block}
.pills{display:flex;flex-wrap:wrap;gap:.4rem}.pill{background:var(--card);border:1px solid var(--line);border-radius:99px;padding:.22rem .75rem;font-size:.82rem}
.pill i{display:inline-block;width:.55rem;height:.55rem;border-radius:50%;margin-right:.45rem;background:var(--on)}.pill.yes i{background:var(--off)}
.flip{background:var(--card);border:1px solid var(--hot);border-radius:10px;padding:.55rem 1rem;margin:.5rem 0}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:.7rem}
.tile{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:.8rem 1rem}.tile small{display:block;font-size:.76rem}.tile b{font-size:1.4rem;font-variant-numeric:tabular-nums}
.ev{display:grid;grid-template-columns:70px 1fr auto;gap:.8rem;align-items:center;padding:.55rem 1rem;background:var(--card);border:1px solid var(--line);border-radius:10px;margin-bottom:.4rem}
.ev .when{color:var(--mut);font-weight:600}.ev .imp{font-size:.75rem;color:var(--mut)}.ev.w3{border-left:4px solid var(--hot)}.ev.w3 .imp{color:var(--hot);font-weight:700}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(480px,1fr));gap:1rem}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:.4rem 1rem .6rem}
.card h3{font-size:.8rem;margin:.7rem 0 .3rem;color:var(--mut);text-transform:uppercase;letter-spacing:.06em}
.row{display:grid;grid-template-columns:minmax(0,1fr) 70px 112px 96px 70px;gap:.6rem;align-items:center;padding:.4rem 0;border-top:1px solid var(--line)}
.vl{text-align:right;font-variant-numeric:tabular-nums}.ch{font-variant-numeric:tabular-nums;white-space:nowrap}
.up{color:var(--up)}.dn{color:var(--dn)}.sp.u{color:var(--up)}.sp.d{color:var(--dn)}
.zb{position:relative;height:6px;background:var(--line);border-radius:3px}.zb::after{content:"";position:absolute;left:50%;top:-2px;bottom:-2px;width:1px;background:var(--mut)}
.zb i{position:absolute;top:0;bottom:0;border-radius:3px;background:var(--mut)}.zb i.hot{background:var(--hot)}
.sr>summary{list-style:none;cursor:pointer}.sr>summary::-webkit-details-marker{display:none}
.sr>summary:hover{background:var(--line)}.sr .nm::before{content:"▸";margin-right:.45rem;color:var(--mut)}.sr[open] .nm::before{content:"▾"}
.info{padding:.2rem 0 .8rem 1.1rem;font-size:.86rem}.info p{margin:.35rem 0}
.ud{display:grid;grid-template-columns:1fr 1fr;gap:.8rem;margin:.5rem 0}.ud b{display:block;margin-bottom:.15rem}
.alloc{display:flex;height:16px;border-radius:8px;overflow:hidden;margin:.3rem 0 .6rem}.alloc i{display:block}
.lg{display:flex;flex-wrap:wrap;gap:.4rem 1.1rem;font-size:.82rem;color:var(--mut)}.lg i{display:inline-block;width:.6rem;height:.6rem;border-radius:3px;margin-right:.4rem}
.pg{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:.8rem}
.pc{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:.85rem 1rem}
.pc>summary{list-style:none;cursor:pointer}.pc>summary::-webkit-details-marker{display:none}.pc:hover{border-color:var(--mut)}
.pt{display:flex;justify-content:space-between;gap:.5rem;align-items:flex-start}.pt b{display:block;line-height:1.25}.pt small{font-size:.78rem}
.wp{background:var(--line);border-radius:99px;padding:.1rem .6rem;font-size:.78rem;font-weight:700;white-space:nowrap}
.pm{display:flex;align-items:baseline;gap:.5rem;margin:.55rem 0 .15rem}.px{font-size:1.15rem;font-weight:700;font-variant-numeric:tabular-nums}
.c{font-variant-numeric:tabular-nums}.c.hot{font-weight:800}
.pk{display:flex;gap:.9rem;font-size:.8rem;color:var(--mut);margin:.2rem 0 .4rem;flex-wrap:wrap}.pk b{font-weight:600}
.tw{background:var(--off);color:#fff;border-radius:99px;font-size:.72rem;padding:.05rem .5rem;margin-left:.3rem;font-weight:700}
.pc .info{padding-left:0;border-top:1px solid var(--line);margin-top:.6rem;padding-top:.5rem}
footer{margin-top:2.5rem;color:var(--mut);font-size:.8rem}
@media(max-width:560px){.grid{grid-template-columns:1fr}.row{grid-template-columns:minmax(0,1fr) 64px 100px 60px}.sp{display:none}.ud{grid-template-columns:1fr}.ev{grid-template-columns:60px 1fr auto}h1{font-size:1.35rem}}
"""


def wrap(active, title, sub, body):
    tabs = "".join(f'<a href="{h}" class="{"act" if k == active else ""}">{n}</a>' for k, n, h in NAV)
    return ('<!doctype html><html lang="sv"><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            f"<title>{title} · Delta</title><style>{CSS}</style>"
            f'<nav><div class="nv"><b>Δ DELTA</b><div class="tabs">{tabs}</div></div></nav>'
            f'<main><div class="ph"><h1>{title}</h1><span class="mut">{sub}</span></div>{body}'
            '<footer>Källor: FRED, Alpaca, Yahoo Finance. Fördröjd data. Regelbaserade tumregler, inte rådgivning.</footer></main></html>')
