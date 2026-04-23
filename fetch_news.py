import feedparser
import json
from datetime import datetime
import pytz
import re
import os
from urllib.request import urlopen, Request
from urllib.parse import quote
from collections import defaultdict

ET = pytz.timezone("America/New_York")
now_et = datetime.now(ET)
hour = now_et.hour
edition_es = "Edición matutina" if hour < 13 else "Edición vespertina"

# ── Translation ────────────────────────────────────────────────────────────
def translate_to_spanish(text):
    if not text:
        return text
    try:
        encoded = quote(text[:500])
        url = f"https://api.mymemory.translated.net/get?q={encoded}&langpair=en|es"
        req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(req, timeout=6) as r:
            data = json.loads(r.read().decode())
        t = data.get("responseData", {}).get("translatedText", "")
        if t and t.lower() != text.lower():
            return t
    except Exception as e:
        print(f"  Translation error: {e}")
    return text

# ── Deduplication helpers ──────────────────────────────────────────────────
def normalize(text):
    text = text.lower()
    text = re.sub(r'[^\w\s]', '', text)
    words = text.split()
    stopwords = {'the','a','an','in','on','at','to','of','and','or','for',
                 'is','are','was','were','has','have','had','be','been',
                 'el','la','los','las','de','en','un','una','y','o','que',
                 'se','su','por','con','del','al','es','son','ha','le'}
    return set(w for w in words if w not in stopwords and len(w) > 2)

def similarity(a, b):
    sa, sb = normalize(a), normalize(b)
    if not sa or not sb:
        return 0
    return len(sa & sb) / max(len(sa), len(sb))

def deduplicate(articles, threshold=0.45):
    """Merge articles that cover the same story. Keep newest, combine sources."""
    groups = []
    used = set()
    for i, a in enumerate(articles):
        if i in used:
            continue
        group = [a]
        for j, b in enumerate(articles):
            if j <= i or j in used:
                continue
            if similarity(a['title'], b['title']) >= threshold:
                group.append(b)
                used.add(j)
        used.add(i)
        groups.append(group)

    merged = []
    for group in groups:
        # Sort by published time desc (most recent first)
        group.sort(key=lambda x: x.get('pub_ts', 0), reverse=True)
        primary = group[0].copy()
        if len(group) > 1:
            all_sources = list(dict.fromkeys(g['source'] for g in group))
            primary['source'] = ' · '.join(all_sources[:3])
            primary['multi_source'] = True
        merged.append(primary)
    return merged

# ── RSS Feeds ──────────────────────────────────────────────────────────────
FEEDS = [
    # Internacional
    {"url": "https://feeds.bbci.co.uk/news/world/rss.xml",          "source": "BBC",            "lang": "en", "cat": "Internacional"},
    {"url": "https://feeds.reuters.com/reuters/worldNews",           "source": "Reuters",        "lang": "en", "cat": "Internacional"},
    {"url": "https://www.theguardian.com/world/rss",                 "source": "The Guardian",   "lang": "en", "cat": "Internacional"},
    {"url": "https://rss.dw.com/rdf/rss-es-world",                  "source": "DW Español",     "lang": "es", "cat": "Internacional"},
    {"url": "https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/section/internacional/portada",
                                                                     "source": "El País",        "lang": "es", "cat": "Internacional"},
    # Geopolítica
    {"url": "https://foreignpolicy.com/feed/",                       "source": "Foreign Policy", "lang": "en", "cat": "Geopolítica"},
    {"url": "https://www.cfr.org/rss.xml",                           "source": "CFR",            "lang": "en", "cat": "Geopolítica"},
    {"url": "https://euobserver.com/rss.xml",                        "source": "EUobserver",     "lang": "en", "cat": "Geopolítica"},
    {"url": "https://rss.dw.com/rdf/rss-es-eu",                     "source": "DW Europa",      "lang": "es", "cat": "Geopolítica"},
    # Mercados
    {"url": "https://feeds.marketwatch.com/marketwatch/topstories/", "source": "MarketWatch",    "lang": "en", "cat": "Mercados"},
    {"url": "https://feeds.reuters.com/reuters/businessNews",        "source": "Reuters Biz",    "lang": "en", "cat": "Mercados"},
    {"url": "https://www.theguardian.com/business/rss",              "source": "Guardian Biz",   "lang": "en", "cat": "Mercados"},
    {"url": "https://rss.dw.com/rdf/rss-es-eco",                    "source": "DW Economía",    "lang": "es", "cat": "Mercados"},
    {"url": "https://feeds.bbci.co.uk/news/business/rss.xml",       "source": "BBC Business",   "lang": "en", "cat": "Mercados"},
    # Política EE.UU.
    {"url": "https://feeds.bbci.co.uk/news/world/us_and_canada/rss.xml", "source": "BBC US",    "lang": "en", "cat": "Política EE.UU."},
    {"url": "https://feeds.reuters.com/Reuters/PoliticsNews",        "source": "Reuters Pol.",   "lang": "en", "cat": "Política EE.UU."},
    {"url": "https://www.theguardian.com/us-news/rss",               "source": "Guardian US",    "lang": "en", "cat": "Política EE.UU."},
    {"url": "https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/section/usa/portada",
                                                                     "source": "El País US",     "lang": "es", "cat": "Política EE.UU."},
    # Ciencia y Salud
    {"url": "https://feeds.bbci.co.uk/news/science_and_environment/rss.xml", "source": "BBC Science", "lang": "en", "cat": "Ciencia y Salud"},
    {"url": "https://www.theguardian.com/science/rss",               "source": "Guardian Sci.", "lang": "en", "cat": "Ciencia y Salud"},
    {"url": "https://feeds.reuters.com/reuters/scienceNews",         "source": "Reuters Sci.",  "lang": "en", "cat": "Ciencia y Salud"},
    # Deportes
    {"url": "https://feeds.bbci.co.uk/sport/rss.xml",                "source": "BBC Sport",      "lang": "en", "cat": "Deportes"},
    {"url": "https://www.theguardian.com/sport/rss",                  "source": "Guardian Sport", "lang": "en", "cat": "Deportes"},
    {"url": "https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/section/deportes/portada",
                                                                     "source": "El País Dep.",   "lang": "es", "cat": "Deportes"},
]

ITEMS_PER_FEED = 5
raw_articles = []
translation_count = 0
MAX_TRANSLATIONS = 850

def extract_image(entry):
    """Try to get a thumbnail from RSS entry."""
    # media:thumbnail
    if hasattr(entry, 'media_thumbnail') and entry.media_thumbnail:
        return entry.media_thumbnail[0].get('url', '')
    # media:content
    if hasattr(entry, 'media_content') and entry.media_content:
        for m in entry.media_content:
            if m.get('type','').startswith('image') or m.get('url','').endswith(('.jpg','.png','.webp')):
                return m.get('url','')
    # enclosures
    if hasattr(entry, 'enclosures') and entry.enclosures:
        for enc in entry.enclosures:
            if enc.get('type','').startswith('image'):
                return enc.get('href','')
    # parse from summary HTML
    if hasattr(entry, 'summary'):
        m = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', entry.summary or '')
        if m:
            return m.group(1)
    return ''

for feed_meta in FEEDS:
    try:
        feed = feedparser.parse(feed_meta["url"])
        for entry in feed.entries[:ITEMS_PER_FEED]:
            summary = getattr(entry, "summary", "") or ""
            summary = re.sub('<[^<]+?>', '', summary).strip()
            summary = summary[:240] + ("..." if len(summary) > 240 else "")

            title_es = entry.title
            summary_es = summary

            if feed_meta["lang"] == "en" and translation_count < MAX_TRANSLATIONS:
                title_es = translate_to_spanish(entry.title)
                translation_count += 1
                if summary and translation_count < MAX_TRANSLATIONS:
                    summary_es = translate_to_spanish(summary)
                    translation_count += 1

            pub = getattr(entry, "published_parsed", None)
            pub_ts = 0
            time_str = "—"
            if pub:
                dt = datetime(*pub[:6], tzinfo=pytz.utc).astimezone(ET)
                pub_ts = dt.timestamp()
                time_str = dt.strftime("%-I:%M %p ET")

            raw_articles.append({
                "title":      entry.title,
                "title_es":   title_es,
                "link":       entry.link,
                "summary":    summary,
                "summary_es": summary_es,
                "source":     feed_meta["source"],
                "lang":       feed_meta["lang"],
                "cat":        feed_meta["cat"],
                "time":       time_str,
                "pub_ts":     pub_ts,
                "image":      extract_image(entry),
                "multi_source": False,
            })
    except Exception as e:
        print(f"  Error {feed_meta['source']}: {e}")

print(f"Raw articles: {len(raw_articles)} | Translations: {translation_count}")

# ── Deduplicate per category ───────────────────────────────────────────────
by_cat_raw = defaultdict(list)
for a in raw_articles:
    by_cat_raw[a["cat"]].append(a)

by_cat = {}
total_deduped = 0
for cat, items in by_cat_raw.items():
    deduped = deduplicate(items)
    by_cat[cat] = deduped
    removed = len(items) - len(deduped)
    total_deduped += removed
    print(f"  {cat}: {len(items)} → {len(deduped)} articles ({removed} merged)")

print(f"Total after dedup: {sum(len(v) for v in by_cat.values())} (merged {total_deduped})")

# ── Design config ──────────────────────────────────────────────────────────
SECTIONS_ORDER = ["Internacional", "Geopolítica", "Mercados", "Política EE.UU.", "Ciencia y Salud", "Deportes"]

CAT_META = {
    "Internacional":   {"color": "#0a2540", "accent": "#2563eb", "light": "#dbeafe", "icon": "🌍", "gradient": "linear-gradient(135deg,#0a2540,#1e3a5f)"},
    "Geopolítica":     {"color": "#2d0a40", "accent": "#7c3aed", "light": "#ede9fe", "icon": "🗺️", "gradient": "linear-gradient(135deg,#2d0a40,#4c1d95)"},
    "Mercados":        {"color": "#052e16", "accent": "#16a34a", "light": "#dcfce7", "icon": "📈", "gradient": "linear-gradient(135deg,#052e16,#14532d)"},
    "Política EE.UU.": {"color": "#450a0a", "accent": "#dc2626", "light": "#fee2e2", "icon": "🏛️", "gradient": "linear-gradient(135deg,#450a0a,#7f1d1d)"},
    "Ciencia y Salud": {"color": "#083344", "accent": "#0891b2", "light": "#cffafe", "icon": "🔬", "gradient": "linear-gradient(135deg,#083344,#164e63)"},
    "Deportes":        {"color": "#431407", "accent": "#ea580c", "light": "#ffedd5", "icon": "⚽", "gradient": "linear-gradient(135deg,#431407,#7c2d12)"},
}

def flag(lang):
    return "🇬🇧" if lang == "en" else "🇪🇸"

def source_badge(a):
    multi = a.get("multi_source", False)
    prefix = "🔗 " if multi else ""
    return f"{prefix}{a['source']}"

def build_hero_card(a, cat):
    m = CAT_META[cat]
    img_html = ""
    if a.get("image"):
        img_html = f'<div class="hero-img" style="background-image:url(\'{a["image"]}\')"></div>'
    else:
        img_html = f'<div class="hero-img hero-img-placeholder" style="background:{m["gradient"]}"><span class="hero-icon">{m["icon"]}</span></div>'

    return f"""<a href="{a['link']}" target="_blank" rel="noopener" class="hero-card" style="--cat-accent:{m['accent']}">
      {img_html}
      <div class="hero-body">
        <div class="hero-meta">
          <span class="cat-tag" style="background:{m['light']};color:{m['color']}">{cat}</span>
          <span class="meta-time">{flag(a['lang'])} {source_badge(a)} · {a['time']}</span>
        </div>
        <h2 class="hero-title">{a['title_es']}</h2>
        {'<p class="hero-summary">' + a['summary_es'] + '</p>' if a.get('summary_es') else ''}
      </div>
    </a>"""

def build_list_card(a, cat):
    m = CAT_META[cat]
    img_html = ""
    if a.get("image"):
        img_html = f'<div class="list-thumb" style="background-image:url(\'{a["image"]}\')"></div>'
    else:
        img_html = f'<div class="list-thumb list-thumb-placeholder" style="background:{m["gradient"]}"><span style="font-size:18px">{m["icon"]}</span></div>'

    return f"""<a href="{a['link']}" target="_blank" rel="noopener" class="list-card" style="--cat-accent:{m['accent']}">
      <div class="list-body">
        <div class="list-meta">
          <span class="cat-tag cat-tag-sm" style="background:{m['light']};color:{m['color']}">{cat}</span>
          <span class="meta-time">{flag(a['lang'])} {source_badge(a)} · {a['time']}</span>
        </div>
        <h3 class="list-title">{a['title_es']}</h3>
      </div>
      {img_html}
    </a>"""

def build_section(cat, items):
    if not items:
        return ""
    m = CAT_META.get(cat, CAT_META["Internacional"])
    hero = items[0]
    rest = items[1:6]

    list_cards = "".join(build_list_card(a, cat) for a in rest)

    return f"""<section class="news-section" id="sec-{cat.lower().replace(' ','-').replace('.','')}" style="--cat-accent:{m['accent']}">
      <div class="section-header">
        <div class="section-label">
          <span class="section-icon">{m['icon']}</span>
          <h2 class="section-name">{cat}</h2>
        </div>
        <div class="section-line" style="background:{m['accent']}"></div>
      </div>
      {build_hero_card(hero, cat)}
      {'<div class="list-stack">' + list_cards + '</div>' if list_cards else ''}
    </section>"""

sections_html = "".join(build_section(cat, by_cat.get(cat, [])) for cat in SECTIONS_ORDER)

# ── Dates ──────────────────────────────────────────────────────────────────
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

# ── Audio ──────────────────────────────────────────────────────────────────
top = [by_cat[c][0] for c in SECTIONS_ORDER if by_cat.get(c)]
script_es = (f"Bienvenido a Mi Briefing. {edition_es}, {date_display}. "
             + " ".join(f"En {a['cat']}: {a['title_es']}. Fuente: {a['source']}." for a in top)
             + " Eso es todo. Visita Mi Briefing para leer los detalles completos.")
script_en = (f"Welcome to Mi Briefing. {edition_es}, {date_display}. "
             + " ".join(f"In {a['cat']}: {a['title']}. Source: {a['source']}." for a in top)
             + " That's all for now. Visit Mi Briefing for the full stories.")
audio_data = json.dumps({"es": script_es, "en": script_en})

all_sources = sorted(set(s for a in raw_articles for s in a['source'].split(' · ')))
sources_str = " · ".join(all_sources)

# ── HTML ──────────────────────────────────────────────────────────────────
HTML = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
<meta name="theme-color" content="#0f0e0c">
<meta property="og:title" content="Mi Briefing — {date_display}">
<meta property="og:description" content="Tu resumen de noticias internacionales · {edition_es}">
<title>Mi Briefing — {date_display}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Fraunces:ital,wght@0,600;0,700;1,600&family=DM+Sans:wght@400;500;600&display=swap" rel="stylesheet">
<style>
*, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
:root {{
  --bg: #f5f3ef;
  --surface: #ffffff;
  --surface2: #f0ede8;
  --border: #e0dbd3;
  --text: #0f0e0c;
  --muted: #5c5852;
  --faint: #a09a93;
  --radius: 12px;
  --cat-accent: #2563eb;
}}
html {{ scroll-behavior: smooth; }}
body {{
  font-family: 'DM Sans', sans-serif;
  background: var(--bg);
  color: var(--text);
  font-size: 15px;
  line-height: 1.6;
  -webkit-font-smoothing: antialiased;
}}
a {{ color: inherit; text-decoration: none; }}

/* ── MASTHEAD ── */
.masthead {{
  background: var(--text);
  color: white;
  padding: 1.25rem 1rem 1rem;
  text-align: center;
  position: relative;
  overflow: hidden;
}}
.masthead::before {{
  content: '';
  position: absolute;
  inset: 0;
  background: radial-gradient(ellipse at 50% -20%, rgba(255,255,255,0.07) 0%, transparent 70%);
  pointer-events: none;
}}
.masthead-eyebrow {{
  font-size: 10px;
  letter-spacing: 3px;
  text-transform: uppercase;
  color: rgba(255,255,255,0.5);
  margin-bottom: 0.4rem;
}}
.masthead-logo {{
  font-family: 'Fraunces', serif;
  font-size: clamp(2.2rem, 10vw, 3.2rem);
  font-weight: 700;
  letter-spacing: -1.5px;
  line-height: 1;
  color: white;
  margin-bottom: 0.75rem;
}}
.masthead-meta {{
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 10px;
  font-size: 11px;
  color: rgba(255,255,255,0.55);
  flex-wrap: wrap;
}}
.edition-badge {{
  background: rgba(255,255,255,0.15);
  color: white;
  font-size: 10px;
  font-weight: 600;
  padding: 3px 10px;
  border-radius: 20px;
  letter-spacing: 1px;
  text-transform: uppercase;
  border: 1px solid rgba(255,255,255,0.2);
}}
.masthead-sep {{ color: rgba(255,255,255,0.25); }}

/* ── TICKER ── */
.ticker-wrap {{
  background: #1a1814;
  color: rgba(255,255,255,0.85);
  font-size: 11px;
  font-weight: 500;
  overflow: hidden;
  white-space: nowrap;
  padding: 7px 0;
  border-bottom: 1px solid rgba(255,255,255,0.06);
}}
.ticker-inner {{ display: inline-block; animation: ticker 45s linear infinite; padding-left: 100%; }}
.ticker-item {{ margin: 0 1.5rem; }}
.ticker-dot {{ color: rgba(255,255,255,0.25); margin: 0 0.5rem; }}
@keyframes ticker {{ from {{ transform:translateX(0); }} to {{ transform:translateX(-100%); }} }}

/* ── SECTION NAV ── */
.sec-nav {{
  background: var(--surface);
  border-bottom: 1px solid var(--border);
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
  scrollbar-width: none;
}}
.sec-nav::-webkit-scrollbar {{ display: none; }}
.sec-nav-inner {{
  display: flex;
  gap: 4px;
  padding: 8px 12px;
  width: max-content;
  min-width: 100%;
}}
.nav-pill {{
  font-size: 12px;
  font-weight: 600;
  padding: 5px 14px;
  border-radius: 20px;
  border: 1.5px solid var(--border);
  color: var(--muted);
  white-space: nowrap;
  transition: all 0.18s;
  cursor: pointer;
}}
.nav-pill:hover {{
  border-color: var(--cat-accent);
  color: var(--cat-accent);
  background: color-mix(in srgb, var(--cat-accent) 8%, transparent);
}}

/* ── AUDIO BAR ── */
.audio-bar {{
  background: var(--surface);
  border-bottom: 1px solid var(--border);
  padding: 10px 12px;
}}
.audio-inner {{ display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }}
.audio-label {{ font-size: 13px; font-weight: 600; color: var(--text); }}
.lang-toggle {{ display: flex; border: 1.5px solid var(--border); border-radius: 6px; overflow: hidden; }}
.lang-btn {{ padding: 4px 12px; font-size: 12px; font-weight: 600; cursor: pointer; border: none; background: transparent; color: var(--muted); font-family: 'DM Sans', sans-serif; transition: all 0.15s; }}
.lang-btn.active {{ background: var(--text); color: white; }}
.play-btn {{ display: flex; align-items: center; gap: 6px; padding: 6px 16px; font-size: 13px; font-weight: 600; background: var(--text); color: white; border: none; border-radius: 8px; cursor: pointer; font-family: 'DM Sans', sans-serif; transition: opacity 0.15s; }}
.play-btn:hover {{ opacity: 0.85; }}
.audio-progress {{ flex: 1; min-width: 100px; font-size: 11px; color: var(--muted); display: none; }}
.audio-progress.visible {{ display: block; }}
.progress-bar-wrap {{ height: 3px; background: var(--border); border-radius: 2px; margin-top: 5px; }}
.progress-bar-fill {{ height: 3px; background: var(--text); border-radius: 2px; width: 0%; transition: width 0.5s linear; }}

/* ── LAYOUT ── */
.main {{ padding: 1.25rem 0 3rem; }}
.container {{ max-width: 680px; margin: 0 auto; padding: 0 12px; }}

/* ── SECTION ── */
.news-section {{ margin-bottom: 2.5rem; }}
.section-header {{
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 1rem;
}}
.section-label {{ display: flex; align-items: center; gap: 6px; flex-shrink: 0; }}
.section-icon {{ font-size: 16px; }}
.section-name {{
  font-family: 'Fraunces', serif;
  font-size: 1.05rem;
  font-weight: 600;
  color: var(--text);
  white-space: nowrap;
}}
.section-line {{
  flex: 1;
  height: 2px;
  border-radius: 1px;
  opacity: 0.25;
}}

/* ── HERO CARD ── */
.hero-card {{
  display: block;
  background: var(--surface);
  border-radius: var(--radius);
  overflow: hidden;
  border: 1px solid var(--border);
  margin-bottom: 10px;
  transition: transform 0.2s, box-shadow 0.2s;
  animation: fadeUp 0.4s ease both;
}}
.hero-card:hover {{
  transform: translateY(-2px);
  box-shadow: 0 8px 24px rgba(0,0,0,0.1);
}}
.hero-img {{
  width: 100%;
  height: 200px;
  background-size: cover;
  background-position: center;
  background-color: var(--surface2);
}}
.hero-img-placeholder {{
  display: flex;
  align-items: center;
  justify-content: center;
}}
.hero-icon {{ font-size: 48px; opacity: 0.6; }}
.hero-body {{ padding: 1rem 1.1rem 1.1rem; }}
.hero-meta {{ display: flex; align-items: center; justify-content: space-between; gap: 8px; margin-bottom: 0.5rem; flex-wrap: wrap; }}
.hero-title {{
  font-family: 'Fraunces', serif;
  font-size: 1.2rem;
  font-weight: 700;
  line-height: 1.3;
  color: var(--text);
  margin-bottom: 0.4rem;
}}
.hero-summary {{ font-size: 0.875rem; color: var(--muted); line-height: 1.55; }}
.hero-card:hover .hero-title {{ color: var(--cat-accent); }}

/* ── LIST CARDS ── */
.list-stack {{ display: flex; flex-direction: column; gap: 8px; }}
.list-card {{
  display: flex;
  align-items: stretch;
  background: var(--surface);
  border-radius: 10px;
  overflow: hidden;
  border: 1px solid var(--border);
  transition: transform 0.2s, box-shadow 0.2s;
  animation: fadeUp 0.4s ease both;
}}
.list-card:hover {{
  transform: translateY(-1px);
  box-shadow: 0 4px 16px rgba(0,0,0,0.08);
}}
.list-body {{ flex: 1; padding: 0.85rem 1rem; min-width: 0; }}
.list-meta {{ display: flex; align-items: center; gap: 6px; margin-bottom: 0.35rem; flex-wrap: wrap; }}
.list-title {{
  font-family: 'Fraunces', serif;
  font-size: 0.95rem;
  font-weight: 600;
  line-height: 1.35;
  color: var(--text);
}}
.list-card:hover .list-title {{ color: var(--cat-accent); }}
.list-thumb {{
  width: 90px;
  flex-shrink: 0;
  background-size: cover;
  background-position: center;
  background-color: var(--surface2);
}}
.list-thumb-placeholder {{ display: flex; align-items: center; justify-content: center; }}

/* ── TAGS & META ── */
.cat-tag {{
  font-size: 9px;
  font-weight: 700;
  letter-spacing: 1px;
  text-transform: uppercase;
  padding: 2px 8px;
  border-radius: 20px;
  flex-shrink: 0;
}}
.cat-tag-sm {{ font-size: 9px; padding: 2px 6px; }}
.meta-time {{ font-size: 11px; color: var(--faint); white-space: nowrap; }}

/* ── ANIMATIONS ── */
@keyframes fadeUp {{
  from {{ opacity: 0; transform: translateY(12px); }}
  to   {{ opacity: 1; transform: translateY(0); }}
}}
.news-section:nth-child(1) .hero-card {{ animation-delay: 0.05s; }}
.news-section:nth-child(2) .hero-card {{ animation-delay: 0.10s; }}
.news-section:nth-child(3) .hero-card {{ animation-delay: 0.15s; }}
.news-section:nth-child(4) .hero-card {{ animation-delay: 0.20s; }}
.news-section:nth-child(5) .hero-card {{ animation-delay: 0.25s; }}
.news-section:nth-child(6) .hero-card {{ animation-delay: 0.30s; }}
.list-card:nth-child(1) {{ animation-delay: 0.08s; }}
.list-card:nth-child(2) {{ animation-delay: 0.14s; }}
.list-card:nth-child(3) {{ animation-delay: 0.20s; }}
.list-card:nth-child(4) {{ animation-delay: 0.26s; }}

/* ── FOOTER ── */
.footer {{
  background: var(--text);
  color: rgba(255,255,255,0.6);
  padding: 1.5rem 1rem;
  text-align: center;
}}
.footer strong {{ color: white; }}
.footer p {{ font-size: 12px; margin-bottom: 4px; }}
.sources-list {{ font-size: 10px; color: rgba(255,255,255,0.35); margin-top: 8px; line-height: 1.9; }}

@media (min-width: 480px) {{
  .hero-img {{ height: 240px; }}
  .hero-title {{ font-size: 1.35rem; }}
  .list-thumb {{ width: 110px; }}
}}
</style>
</head>
<body>

<header class="masthead">
  <p class="masthead-eyebrow">Tu resumen · Your briefing</p>
  <h1 class="masthead-logo">Mi Briefing</h1>
  <div class="masthead-meta">
    <span>{date_display}</span>
    <span class="masthead-sep">·</span>
    <span class="edition-badge">{edition_es}</span>
    <span class="masthead-sep">·</span>
    <span>Actualizado {time_display}</span>
  </div>
</header>

<div class="ticker-wrap">
  <div class="ticker-inner">
    <span class="ticker-item">S&amp;P 500 — en seguimiento</span><span class="ticker-dot">·</span>
    <span class="ticker-item">Dow Jones — en seguimiento</span><span class="ticker-dot">·</span>
    <span class="ticker-item">Nasdaq — en seguimiento</span><span class="ticker-dot">·</span>
    <span class="ticker-item">EUR/USD — en seguimiento</span><span class="ticker-dot">·</span>
    <span class="ticker-item">Petróleo WTI — en seguimiento</span><span class="ticker-dot">·</span>
    <span class="ticker-item">Bitcoin — en seguimiento</span><span class="ticker-dot">·</span>
    <span class="ticker-item">Oro — en seguimiento</span><span class="ticker-dot">·</span>
    <span class="ticker-item">Bono 10Y EE.UU. — en seguimiento</span>
  </div>
</div>

<nav class="sec-nav">
  <div class="sec-nav-inner">
    <a class="nav-pill" href="#sec-internacional" style="--cat-accent:#2563eb">🌍 Internacional</a>
    <a class="nav-pill" href="#sec-geopolítica" style="--cat-accent:#7c3aed">🗺️ Geopolítica</a>
    <a class="nav-pill" href="#sec-mercados" style="--cat-accent:#16a34a">📈 Mercados</a>
    <a class="nav-pill" href="#sec-política-eeuu" style="--cat-accent:#dc2626">🏛️ Política EE.UU.</a>
    <a class="nav-pill" href="#sec-ciencia-y-salud" style="--cat-accent:#0891b2">🔬 Ciencia</a>
    <a class="nav-pill" href="#sec-deportes" style="--cat-accent:#ea580c">⚽ Deportes</a>
  </div>
</nav>

<div class="audio-bar">
  <div class="audio-inner">
    <div class="audio-label">🎧 Escuchar resumen</div>
    <div class="lang-toggle">
      <button class="lang-btn active" id="btn-es" onclick="setLang('es')">Español</button>
      <button class="lang-btn"        id="btn-en" onclick="setLang('en')">English</button>
    </div>
    <button class="play-btn" id="play-btn" onclick="toggleAudio()">
      <span id="play-icon">▶</span>
      <span id="play-label">Reproducir</span>
    </button>
    <div class="audio-progress" id="audio-progress">
      <div id="progress-text">Iniciando...</div>
      <div class="progress-bar-wrap"><div class="progress-bar-fill" id="progress-fill"></div></div>
    </div>
  </div>
</div>

<main class="main">
  <div class="container">
    {sections_html}
  </div>
</main>

<footer class="footer">
  <p><strong>Mi Briefing</strong> — Resumen para familia y amigos</p>
  <p>Actualizado automáticamente · 6:00 AM y 2:00 PM ET</p>
  <p class="sources-list">{sources_str}</p>
</footer>

<script>
const SCRIPTS = {audio_data};
let currentLang = 'es', speaking = false, utterance = null;
function setLang(l) {{
  currentLang = l;
  document.getElementById('btn-es').classList.toggle('active', l==='es');
  document.getElementById('btn-en').classList.toggle('active', l==='en');
  document.getElementById('play-label').textContent = l==='es' ? 'Reproducir' : 'Play';
  if (speaking) stopAudio();
}}
function toggleAudio() {{ speaking ? stopAudio() : startAudio(); }}
function startAudio() {{
  if (!window.speechSynthesis) {{ alert('Tu navegador no soporta síntesis de voz.'); return; }}
  utterance = new SpeechSynthesisUtterance(SCRIPTS[currentLang]);
  utterance.lang  = currentLang==='es' ? 'es-US' : 'en-US';
  utterance.rate  = 0.93;
  utterance.pitch = 1.0;
  const voices = speechSynthesis.getVoices();
  const pick = voices.find(v => currentLang==='es'
    ? v.lang.startsWith('es') && /Google|Paulina|Monica|Jorge/.test(v.name)
    : v.lang.startsWith('en') && /Google|Samantha|Alex/.test(v.name)
  ) || voices.find(v => currentLang==='es' ? v.lang.startsWith('es') : v.lang.startsWith('en'));
  if (pick) utterance.voice = pick;
  const total = SCRIPTS[currentLang].length;
  utterance.onboundary = e => {{
    if (e.name==='word') {{
      const pct = Math.min(100, Math.round(e.charIndex/total*100));
      document.getElementById('progress-fill').style.width = pct+'%';
      document.getElementById('progress-text').textContent = (currentLang==='es'?'Reproduciendo':'Playing')+'... '+pct+'%';
    }}
  }};
  utterance.onend = utterance.onerror = resetPlayer;
  speechSynthesis.speak(utterance);
  speaking = true;
  document.getElementById('play-icon').textContent  = '⏹';
  document.getElementById('play-label').textContent = currentLang==='es' ? 'Detener' : 'Stop';
  document.getElementById('audio-progress').classList.add('visible');
}}
function stopAudio() {{ speechSynthesis.cancel(); resetPlayer(); }}
function resetPlayer() {{
  speaking = false;
  document.getElementById('play-icon').textContent  = '▶';
  document.getElementById('play-label').textContent = currentLang==='es' ? 'Reproducir' : 'Play';
  document.getElementById('progress-fill').style.width = '0%';
  document.getElementById('audio-progress').classList.remove('visible');
}}
if (window.speechSynthesis) {{
  speechSynthesis.getVoices();
  speechSynthesis.onvoiceschanged = () => speechSynthesis.getVoices();
}}
</script>
</body>
</html>"""

os.makedirs("docs", exist_ok=True)
with open("docs/index.html", "w", encoding="utf-8") as f:
    f.write(HTML)

print(f"\n✅  docs/index.html listo — {edition_es} — {time_display}")
