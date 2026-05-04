"""
Mi Briefing — fetch_news.py
Lee config.json, descarga RSS, deduplica con algoritmo mejorado,
traduce titulares al español y genera docs/index.html
"""

import feedparser
import json
import re
import os
from datetime import datetime, timezone, timedelta
from urllib.request import urlopen, Request
from urllib.parse import quote
from collections import defaultdict
import pytz

# ── Config ─────────────────────────────────────────────────────────────────
with open("config.json", encoding="utf-8") as f:
    CFG = json.load(f)

ET      = pytz.timezone("America/New_York")
now_et  = datetime.now(ET)
hour    = now_et.hour
edition_es = "Edición matutina" if hour < 13 else "Edición vespertina"

DEDUP   = CFG["deduplicacion"]
UMBRAL  = DEDUP["umbral_similitud"]
VENTANA = DEDUP["ventana_horas"]

# ── Translation ────────────────────────────────────────────────────────────
_translation_count = 0
MAX_TRANSLATIONS   = 850

def translate(text):
    global _translation_count
    if not text or _translation_count >= MAX_TRANSLATIONS:
        return text
    try:
        encoded = quote(text[:500])
        url = f"https://api.mymemory.translated.net/get?q={encoded}&langpair=en|es"
        req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(req, timeout=6) as r:
            data = json.loads(r.read().decode())
        t = data.get("responseData", {}).get("translatedText", "")
        if t and t.lower() != text.lower():
            _translation_count += 1
            return t
    except Exception as e:
        print(f"  ⚠ Translation error: {e}")
    return text

# ── Deduplication ──────────────────────────────────────────────────────────
STOPWORDS = {
    'the','a','an','in','on','at','to','of','and','or','for','is','are',
    'was','were','has','have','had','be','been','as','by','its','it',
    'el','la','los','las','de','en','un','una','y','o','que','se','su',
    'por','con','del','al','es','son','ha','le','lo','más','no','si',
    'this','that','with','from','after','over','will','who','says','said',
    'new','first','after','amid','over','says','amid'
}

def keywords(text):
    """Extract meaningful keywords from a title."""
    text = text.lower()
    text = re.sub(r'[^\w\s]', ' ', text)
    words = text.split()
    # Keep words >3 chars and not stopwords — gives better signal
    return set(w for w in words if len(w) > 3 and w not in STOPWORDS)

def jaccard(a, b):
    sa, sb = keywords(a), keywords(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)

def ngrams(text, n=3):
    """Character n-grams for fuzzy matching when word overlap fails."""
    text = re.sub(r'[^\w]', '', text.lower())
    return set(text[i:i+n] for i in range(len(text) - n + 1))

def ngram_sim(a, b, n=3):
    ga, gb = ngrams(a, n), ngrams(b, n)
    if not ga or not gb:
        return 0.0
    return len(ga & gb) / len(ga | gb)

def similarity(title_a, title_b):
    """
    Combined similarity: Jaccard on keywords + character n-grams.
    Jaccard alone misses when outlets phrase the same story differently
    (e.g. 'Fed holds rates' vs 'Federal Reserve keeps interest rates unchanged').
    N-grams catch shared proper nouns and named entities even when phrasing differs.
    """
    j = jaccard(title_a, title_b)
    n = ngram_sim(title_a, title_b, n=4)
    # Weighted blend — keyword overlap matters more
    return j * 0.65 + n * 0.35

def within_time_window(ts_a, ts_b, hours):
    """Return True if both timestamps are within `hours` of each other."""
    if ts_a == 0 or ts_b == 0:
        return True  # unknown time → assume same window
    return abs(ts_a - ts_b) < hours * 3600

def deduplicate(articles):
    """
    Merge articles covering the same story.
    - Uses combined keyword + n-gram similarity
    - Only merges if published within VENTANA hours of each other
    - Higher-priority source (lower prioridad number) wins when merging
    - Keeps at most max_fuentes_combinadas source names
    """
    max_src = DEDUP["max_fuentes_combinadas"]
    groups  = []
    used    = set()

    for i, a in enumerate(articles):
        if i in used:
            continue
        group = [a]
        for j, b in enumerate(articles):
            if j <= i or j in used:
                continue
            sim = similarity(a["title"], b["title"])
            if sim >= UMBRAL and within_time_window(a["pub_ts"], b["pub_ts"], VENTANA):
                group.append(b)
                used.add(j)
        used.add(i)
        groups.append(group)

    merged = []
    for group in groups:
        # Sort: higher priority (lower number) first, then most recent
        group.sort(key=lambda x: (x.get("prioridad", 9), -x.get("pub_ts", 0)))
        primary = group[0].copy()
        if len(group) > 1:
            # Collect unique source names
            seen_src = []
            for g in group:
                for s in g["source"].split(" · "):
                    if s not in seen_src:
                        seen_src.append(s)
            primary["source"]       = " · ".join(seen_src[:max_src])
            primary["multi_source"] = len(seen_src) > 1
            # Prefer the richest summary among duplicates
            if not primary.get("summary_es"):
                for g in group[1:]:
                    if g.get("summary_es"):
                        primary["summary_es"] = g["summary_es"]
                        break
        else:
            primary["multi_source"] = False
        merged.append(primary)

    return merged

# ── Image extraction ───────────────────────────────────────────────────────
def extract_image(entry):
    if hasattr(entry, "media_thumbnail") and entry.media_thumbnail:
        return entry.media_thumbnail[0].get("url", "")
    if hasattr(entry, "media_content") and entry.media_content:
        for m in entry.media_content:
            url = m.get("url", "")
            if m.get("type", "").startswith("image") or url.lower().endswith((".jpg",".jpeg",".png",".webp")):
                return url
    if hasattr(entry, "enclosures") and entry.enclosures:
        for enc in entry.enclosures:
            if enc.get("type", "").startswith("image"):
                return enc.get("href", "")
    if hasattr(entry, "summary"):
        m = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', entry.summary or "")
        if m:
            return m.group(1)
    return ""

# ── Fetch feeds ────────────────────────────────────────────────────────────
active_feeds = [f for f in CFG["fuentes"] if f.get("activa", True)]
active_secs  = {k for k, v in CFG["secciones"].items() if v.get("activa", True)}

raw_articles = []
feed_stats   = defaultdict(lambda: {"fetched": 0, "error": None})

print(f"\n📡  Fetching {len(active_feeds)} active feeds...\n")

for feed_meta in active_feeds:
    sec = feed_meta["seccion"]
    if sec not in active_secs:
        print(f"  ⏭  Skipping {feed_meta['nombre']} (section '{sec}' disabled)")
        continue

    try:
        feed = feedparser.parse(feed_meta["url"])
        count = 0
        for entry in feed.entries[:feed_meta.get("max_items", 4)]:
            title = entry.get("title", "").strip()
            if not title:
                continue

            summary = getattr(entry, "summary", "") or ""
            summary = re.sub(r"<[^<]+?>", "", summary).strip()
            summary = summary[:240] + ("..." if len(summary) > 240 else "")

            # Translate if English
            title_es   = title
            summary_es = summary
            if feed_meta["idioma"] == "en":
                title_es   = translate(title)
                if summary:
                    summary_es = translate(summary)

            # Parse publish time
            pub = getattr(entry, "published_parsed", None)
            pub_ts   = 0
            time_str = "—"
            if pub:
                try:
                    dt = datetime(*pub[:6], tzinfo=timezone.utc).astimezone(ET)
                    pub_ts   = dt.timestamp()
                    time_str = dt.strftime("%-I:%M %p ET")
                except Exception:
                    pass

            raw_articles.append({
                "title":        title,
                "title_es":     title_es,
                "link":         entry.get("link", "#"),
                "summary":      summary,
                "summary_es":   summary_es,
                "source":       feed_meta["nombre"],
                "idioma":       feed_meta["idioma"],
                "seccion":      sec,
                "time":         time_str,
                "pub_ts":       pub_ts,
                "prioridad":    feed_meta.get("prioridad", 5),
                "image":        extract_image(entry),
                "multi_source": False,
            })
            count += 1

        feed_stats[feed_meta["nombre"]]["fetched"] = count
        print(f"  ✓  {feed_meta['nombre']:30s} → {count} articles")

    except Exception as e:
        feed_stats[feed_meta["nombre"]]["error"] = str(e)
        print(f"  ✗  {feed_meta['nombre']:30s} → ERROR: {e}")

print(f"\n📰  Raw total: {len(raw_articles)} articles | Translations: {_translation_count}")

# ── Group & deduplicate per section ───────────────────────────────────────
by_sec_raw = defaultdict(list)
for a in raw_articles:
    by_sec_raw[a["seccion"]].append(a)

by_sec = {}
total_merged = 0
print("\n🔍  Deduplication:")
for sec, items in by_sec_raw.items():
    deduped = deduplicate(items)
    removed = len(items) - len(deduped)
    total_merged += removed
    max_art = CFG["secciones"].get(sec, {}).get("max_articulos", 6)
    by_sec[sec] = deduped[:max_art]
    print(f"  {sec:20s} {len(items):3d} → {len(deduped):3d}  (merged {removed:2d})")

print(f"\n  Total merged: {total_merged} duplicates removed")

# ── Section order ──────────────────────────────────────────────────────────
SECTIONS_ORDER = sorted(
    [s for s in CFG["secciones"] if CFG["secciones"][s].get("activa", True)],
    key=lambda s: CFG["secciones"][s].get("orden", 99)
)

# ── Design tokens per section ──────────────────────────────────────────────
CAT_META = {
    "Internacional":   {"accent": "#2563eb", "light": "#dbeafe", "dark": "#0a2540", "icon": "🌍",  "grad": "135deg,#0a2540,#1e3a5f"},
    "Geopolítica":     {"accent": "#7c3aed", "light": "#ede9fe", "dark": "#2d0a40", "icon": "🗺️", "grad": "135deg,#2d0a40,#4c1d95"},
    "Ecuador":         {"accent": "#059669", "light": "#d1fae5", "dark": "#064e3b", "icon": "🇪🇨", "grad": "135deg,#064e3b,#065f46"},
    "Mercados":        {"accent": "#16a34a", "light": "#dcfce7", "dark": "#052e16", "icon": "📈",  "grad": "135deg,#052e16,#14532d"},
    "Política EE.UU.": {"accent": "#dc2626", "light": "#fee2e2", "dark": "#450a0a", "icon": "🏛️", "grad": "135deg,#450a0a,#7f1d1d"},
    "Ciencia y Salud": {"accent": "#0891b2", "light": "#cffafe", "dark": "#083344", "icon": "🔬",  "grad": "135deg,#083344,#164e63"},
    "Deportes":        {"accent": "#ea580c", "light": "#ffedd5", "dark": "#431407", "icon": "⚽",  "grad": "135deg,#431407,#7c2d12"},
}
DEFAULT_META = {"accent": "#64748b", "light": "#f1f5f9", "dark": "#1e293b", "icon": "📰", "grad": "135deg,#1e293b,#334155"}

def flag(lang):
    return "🇬🇧" if lang == "en" else "🇪🇸"

def hero_card(a, sec):
    m = CAT_META.get(sec, DEFAULT_META)
    img = f'<div class="hero-img" style="background-image:url(\'{a["image"]}\')"></div>' \
          if a.get("image") else \
          f'<div class="hero-img hero-ph" style="background:linear-gradient({m["grad"]})"><span class="ph-icon">{m["icon"]}</span></div>'
    src_badge = ("🔗 " if a.get("multi_source") else "") + a["source"]
    return f"""<a href="{a['link']}" target="_blank" rel="noopener" class="hero-card" style="--acc:{m['accent']}">
      {img}
      <div class="hero-body">
        <div class="card-meta-row">
          <span class="ctag" style="background:{m['light']};color:{m['dark']}">{sec}</span>
          <span class="mtime">{flag(a['idioma'])} {src_badge} · {a['time']}</span>
        </div>
        <h2 class="hero-title">{a['title_es']}</h2>
        {'<p class="hero-sum">' + a['summary_es'] + '</p>' if a.get('summary_es') else ''}
      </div>
    </a>"""

def list_card(a, sec):
    m = CAT_META.get(sec, DEFAULT_META)
    thumb = f'<div class="lthumb" style="background-image:url(\'{a["image"]}\')"></div>' \
            if a.get("image") else \
            f'<div class="lthumb lph" style="background:linear-gradient({m["grad"]})"><span style="font-size:18px">{m["icon"]}</span></div>'
    src_badge = ("🔗 " if a.get("multi_source") else "") + a["source"]
    return f"""<a href="{a['link']}" target="_blank" rel="noopener" class="lcard" style="--acc:{m['accent']}">
      <div class="lbody">
        <div class="card-meta-row">
          <span class="ctag ctag-sm" style="background:{m['light']};color:{m['dark']}">{sec}</span>
          <span class="mtime">{flag(a['idioma'])} {src_badge} · {a['time']}</span>
        </div>
        <h3 class="ltitle">{a['title_es']}</h3>
      </div>
      {thumb}
    </a>"""

def build_section(sec, items):
    if not items:
        return ""
    m   = CAT_META.get(sec, DEFAULT_META)
    sec_id = re.sub(r'[^a-z0-9]', '-', sec.lower())
    hero   = hero_card(items[0], sec)
    rest   = "".join(list_card(a, sec) for a in items[1:])
    return f"""<section class="nsec" id="s-{sec_id}" style="--acc:{m['accent']}">
      <div class="sec-hd">
        <div class="sec-lbl"><span>{m['icon']}</span><h2 class="sec-name">{sec}</h2></div>
        <div class="sec-line"></div>
      </div>
      {hero}
      {'<div class="lstack">' + rest + '</div>' if rest else ''}
    </section>"""

sections_html = "".join(build_section(s, by_sec.get(s, [])) for s in SECTIONS_ORDER)

# ── Nav pills ──────────────────────────────────────────────────────────────
nav_pills = "".join(
    f'<a class="npill" href="#s-{re.sub(r"[^a-z0-9]", "-", s.lower())}" '
    f'style="--acc:{CAT_META.get(s, DEFAULT_META)["accent"]}">'
    f'{CAT_META.get(s, DEFAULT_META)["icon"]} {s}</a>'
    for s in SECTIONS_ORDER if by_sec.get(s)
)

# ── Audio scripts ──────────────────────────────────────────────────────────
top = [by_sec[s][0] for s in SECTIONS_ORDER if by_sec.get(s)]
months_en_es = {"January":"enero","February":"febrero","March":"marzo","April":"abril",
    "May":"mayo","June":"junio","July":"julio","August":"agosto",
    "September":"septiembre","October":"octubre","November":"noviembre","December":"diciembre"}
days_en_es = {"Monday":"Lunes","Tuesday":"Martes","Wednesday":"Miércoles","Thursday":"Jueves",
    "Friday":"Viernes","Saturday":"Sábado","Sunday":"Domingo"}
date_es = now_et.strftime("%-d de %B de %Y")
for en, es in months_en_es.items():
    date_es = date_es.replace(en, es)
date_display = f"{days_en_es.get(now_et.strftime('%A'), now_et.strftime('%A'))}, {date_es}"
time_display = now_et.strftime("%-I:%M %p ET")

script_es = (f"Bienvenido a Mi Briefing. {edition_es}, {date_display}. "
             + " ".join(f"En {a['seccion']}: {a['title_es']}. Fuente: {a['source']}." for a in top)
             + " Eso es todo por ahora. Visita Mi Briefing para leer todos los detalles.")
script_en = (f"Welcome to Mi Briefing. {edition_es}, {date_display}. "
             + " ".join(f"In {a['seccion']}: {a['title']}. Source: {a['source']}." for a in top)
             + " That's all for now. Visit Mi Briefing for the full stories.")
audio_data = json.dumps({"es": script_es, "en": script_en})

all_sources = sorted(set(
    s.strip() for a in raw_articles for s in a["source"].split("·")
))
sources_str = " · ".join(all_sources)

# ── HTML ──────────────────────────────────────────────────────────────────
site = CFG["site"]
HTML = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="theme-color" content="#0f0e0c">
<meta property="og:title" content="{site['nombre']} — {date_display}">
<meta property="og:description" content="{site['subtitulo']} · {edition_es}">
<title>{site['nombre']} — {date_display}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Fraunces:ital,wght@0,600;0,700;1,600&family=DM+Sans:wght@400;500;600&display=swap" rel="stylesheet">
<style>
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0;}}
:root{{--bg:#f5f3ef;--sur:#fff;--bdr:#e0dbd3;--txt:#0f0e0c;--mut:#5c5852;--fnt:#a09a93;--r:12px;--acc:#2563eb;}}
html{{scroll-behavior:smooth;}}
body{{font-family:'DM Sans',sans-serif;background:var(--bg);color:var(--txt);font-size:15px;line-height:1.6;-webkit-font-smoothing:antialiased;}}
a{{color:inherit;text-decoration:none;}}

.masthead{{background:var(--txt);color:#fff;padding:1.25rem 1rem 1rem;text-align:center;position:relative;overflow:hidden;}}
.masthead::before{{content:'';position:absolute;inset:0;background:radial-gradient(ellipse at 50% -20%,rgba(255,255,255,.07) 0%,transparent 70%);pointer-events:none;}}
.eyebrow{{font-size:10px;letter-spacing:3px;text-transform:uppercase;color:rgba(255,255,255,.5);margin-bottom:.4rem;}}
.logo{{font-family:'Fraunces',serif;font-size:clamp(2.2rem,10vw,3.2rem);font-weight:700;letter-spacing:-1.5px;line-height:1;margin-bottom:.75rem;}}
.mastmeta{{display:flex;justify-content:center;align-items:center;gap:10px;font-size:11px;color:rgba(255,255,255,.55);flex-wrap:wrap;}}
.edbadge{{background:rgba(255,255,255,.15);color:#fff;font-size:10px;font-weight:600;padding:3px 10px;border-radius:20px;border:1px solid rgba(255,255,255,.2);letter-spacing:1px;text-transform:uppercase;}}

.ticker{{background:#1a1814;color:rgba(255,255,255,.85);font-size:11px;font-weight:500;overflow:hidden;white-space:nowrap;padding:7px 0;}}
.tick-in{{display:inline-block;animation:tick 45s linear infinite;padding-left:100%;}}
.tick-in span{{margin:0 1.5rem;}}
@keyframes tick{{from{{transform:translateX(0);}}to{{transform:translateX(-100%);}}}}

.sec-nav{{background:var(--sur);border-bottom:1px solid var(--bdr);overflow-x:auto;-webkit-overflow-scrolling:touch;scrollbar-width:none;}}
.sec-nav::-webkit-scrollbar{{display:none;}}
.nav-row{{display:flex;gap:4px;padding:8px 12px;width:max-content;min-width:100%;}}
.npill{{font-size:12px;font-weight:600;padding:5px 14px;border-radius:20px;border:1.5px solid var(--bdr);color:var(--mut);white-space:nowrap;transition:all .18s;}}
.npill:hover{{border-color:var(--acc);color:var(--acc);background:color-mix(in srgb,var(--acc) 8%,transparent);}}

.audio-bar{{background:var(--sur);border-bottom:1px solid var(--bdr);padding:10px 12px;}}
.audio-in{{display:flex;align-items:center;gap:10px;flex-wrap:wrap;}}
.albl{{font-size:13px;font-weight:600;}}
.ltog{{display:flex;border:1.5px solid var(--bdr);border-radius:6px;overflow:hidden;}}
.lbtn{{padding:4px 12px;font-size:12px;font-weight:600;cursor:pointer;border:none;background:transparent;color:var(--mut);font-family:'DM Sans',sans-serif;transition:all .15s;}}
.lbtn.on{{background:var(--txt);color:#fff;}}
.pbtn{{display:flex;align-items:center;gap:6px;padding:6px 16px;font-size:13px;font-weight:600;background:var(--txt);color:#fff;border:none;border-radius:8px;cursor:pointer;font-family:'DM Sans',sans-serif;transition:opacity .15s;}}
.pbtn:hover{{opacity:.85;}}
.aprg{{flex:1;min-width:100px;font-size:11px;color:var(--mut);display:none;}}
.aprg.on{{display:block;}}
.prg-wrap{{height:3px;background:var(--bdr);border-radius:2px;margin-top:5px;}}
.prg-fill{{height:3px;background:var(--txt);border-radius:2px;width:0%;transition:width .5s linear;}}

.main{{padding:1.25rem 0 3rem;}}
.wrap{{max-width:680px;margin:0 auto;padding:0 12px;}}

.nsec{{margin-bottom:2.5rem;scroll-margin-top:80px;}}
.sec-hd{{display:flex;align-items:center;gap:10px;margin-bottom:1rem;}}
.sec-lbl{{display:flex;align-items:center;gap:6px;flex-shrink:0;}}
.sec-name{{font-family:'Fraunces',serif;font-size:1.05rem;font-weight:600;white-space:nowrap;}}
.sec-line{{flex:1;height:2px;border-radius:1px;background:var(--acc);opacity:.25;}}

.hero-card{{display:block;background:var(--sur);border-radius:var(--r);overflow:hidden;border:1px solid var(--bdr);margin-bottom:10px;transition:transform .2s,box-shadow .2s;animation:up .4s ease both;}}
.hero-card:hover{{transform:translateY(-2px);box-shadow:0 8px 24px rgba(0,0,0,.1);}}
.hero-img{{width:100%;height:200px;background-size:cover;background-position:center;}}
.hero-ph{{display:flex;align-items:center;justify-content:center;}}
.ph-icon{{font-size:48px;opacity:.6;}}
.hero-body{{padding:1rem 1.1rem 1.1rem;}}
.hero-title{{font-family:'Fraunces',serif;font-size:1.2rem;font-weight:700;line-height:1.3;margin-bottom:.4rem;}}
.hero-sum{{font-size:.875rem;color:var(--mut);line-height:1.55;}}
.hero-card:hover .hero-title{{color:var(--acc);}}

.lstack{{display:flex;flex-direction:column;gap:8px;}}
.lcard{{display:flex;align-items:stretch;background:var(--sur);border-radius:10px;overflow:hidden;border:1px solid var(--bdr);transition:transform .2s,box-shadow .2s;animation:up .4s ease both;}}
.lcard:hover{{transform:translateY(-1px);box-shadow:0 4px 16px rgba(0,0,0,.08);}}
.lbody{{flex:1;padding:.85rem 1rem;min-width:0;}}
.ltitle{{font-family:'Fraunces',serif;font-size:.95rem;font-weight:600;line-height:1.35;}}
.lcard:hover .ltitle{{color:var(--acc);}}
.lthumb{{width:90px;flex-shrink:0;background-size:cover;background-position:center;}}
.lph{{display:flex;align-items:center;justify-content:center;}}

.card-meta-row{{display:flex;align-items:center;justify-content:space-between;gap:8px;margin-bottom:.5rem;flex-wrap:wrap;}}
.ctag{{font-size:9px;font-weight:700;letter-spacing:1px;text-transform:uppercase;padding:2px 8px;border-radius:20px;flex-shrink:0;}}
.ctag-sm{{font-size:9px;padding:2px 6px;}}
.mtime{{font-size:11px;color:var(--fnt);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:200px;}}

.footer{{background:var(--txt);color:rgba(255,255,255,.6);padding:1.5rem 1rem;text-align:center;}}
.footer strong{{color:#fff;}}
.footer p{{font-size:12px;margin-bottom:4px;}}
.src-list{{font-size:10px;color:rgba(255,255,255,.3);margin-top:8px;line-height:1.9;}}

@keyframes up{{from{{opacity:0;transform:translateY(12px);}}to{{opacity:1;transform:translateY(0);}}}}
@media(min-width:480px){{.hero-img{{height:240px;}}.hero-title{{font-size:1.35rem;}}.lthumb{{width:110px;}}}}
</style>
</head>
<body>

<header class="masthead">
  <div class="wrap">
    <p class="eyebrow">{site['subtitulo']}</p>
    <h1 class="logo">{site['nombre']}</h1>
    <div class="mastmeta">
      <span>{date_display}</span>
      <span>·</span>
      <span class="edbadge">{edition_es}</span>
      <span>·</span>
      <span>Actualizado {time_display}</span>
    </div>
  </div>
</header>

<div class="ticker">
  <div class="tick-in">
    <span>S&amp;P 500 — en seguimiento</span><span>·</span>
    <span>Dow Jones — en seguimiento</span><span>·</span>
    <span>Nasdaq — en seguimiento</span><span>·</span>
    <span>EUR/USD — en seguimiento</span><span>·</span>
    <span>Petróleo WTI — en seguimiento</span><span>·</span>
    <span>Bitcoin — en seguimiento</span><span>·</span>
    <span>Oro — en seguimiento</span>
  </div>
</div>

<nav class="sec-nav"><div class="nav-row">{nav_pills}</div></nav>

<div class="audio-bar">
  <div class="audio-in">
    <div class="albl">🎧 Escuchar resumen</div>
    <div class="ltog">
      <button class="lbtn on" id="bes" onclick="setLang('es')">Español</button>
      <button class="lbtn"    id="ben" onclick="setLang('en')">English</button>
    </div>
    <button class="pbtn" onclick="toggleAudio()">
      <span id="pico">▶</span><span id="plbl">Reproducir</span>
    </button>
    <div class="aprg" id="aprg">
      <div id="ptxt">Iniciando...</div>
      <div class="prg-wrap"><div class="prg-fill" id="pfill"></div></div>
    </div>
  </div>
</div>

<main class="main"><div class="wrap">{sections_html}</div></main>

<footer class="footer">
  <div class="wrap">
    <p><strong>{site['nombre']}</strong> — Resumen para familia y amigos</p>
    <p>Actualizado automáticamente · {site['hora_manana']} AM y {site['hora_tarde'].replace('14','02')} PM ET</p>
    <p class="src-list">{sources_str}</p>
  </div>
</footer>

<script>
const SC={audio_data};
let lang='es',speaking=false,utt=null;
function setLang(l){{
  lang=l;
  document.getElementById('bes').classList.toggle('on',l==='es');
  document.getElementById('ben').classList.toggle('on',l==='en');
  document.getElementById('plbl').textContent=l==='es'?'Reproducir':'Play';
  if(speaking)stop();
}}
function toggleAudio(){{speaking?stop():play();}}
function play(){{
  if(!window.speechSynthesis){{alert('Tu navegador no soporta síntesis de voz.');return;}}
  utt=new SpeechSynthesisUtterance(SC[lang]);
  utt.lang=lang==='es'?'es-US':'en-US';
  utt.rate=0.93;utt.pitch=1;
  const vs=speechSynthesis.getVoices();
  const pick=vs.find(v=>lang==='es'
    ?v.lang.startsWith('es')&&/Google|Paulina|Monica|Jorge/.test(v.name)
    :v.lang.startsWith('en')&&/Google|Samantha|Alex/.test(v.name)
  )||vs.find(v=>lang==='es'?v.lang.startsWith('es'):v.lang.startsWith('en'));
  if(pick)utt.voice=pick;
  const tot=SC[lang].length;
  utt.onboundary=e=>{{
    if(e.name==='word'){{
      const p=Math.min(100,Math.round(e.charIndex/tot*100));
      document.getElementById('pfill').style.width=p+'%';
      document.getElementById('ptxt').textContent=(lang==='es'?'Reproduciendo':'Playing')+'... '+p+'%';
    }}
  }};
  utt.onend=utt.onerror=reset;
  speechSynthesis.speak(utt);speaking=true;
  document.getElementById('pico').textContent='⏹';
  document.getElementById('plbl').textContent=lang==='es'?'Detener':'Stop';
  document.getElementById('aprg').classList.add('on');
}}
function stop(){{speechSynthesis.cancel();reset();}}
function reset(){{
  speaking=false;
  document.getElementById('pico').textContent='▶';
  document.getElementById('plbl').textContent=lang==='es'?'Reproducir':'Play';
  document.getElementById('pfill').style.width='0%';
  document.getElementById('aprg').classList.remove('on');
}}
if(window.speechSynthesis){{speechSynthesis.getVoices();speechSynthesis.onvoiceschanged=()=>speechSynthesis.getVoices();}}
</script>
</body>
</html>"""

os.makedirs("docs", exist_ok=True)
with open("docs/index.html", "w", encoding="utf-8") as f:
    f.write(HTML)

total_shown = sum(len(v) for v in by_sec.values())
print(f"\n✅  docs/index.html generado")
print(f"    Secciones: {len(by_sec)} | Artículos mostrados: {total_shown} | Duplicados eliminados: {total_merged}")
print(f"    Edición: {edition_es} · {time_display}")
