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

# ── Translation via MyMemory (free, no key, 1000 req/day) ──────────────────
def translate_to_spanish(text):
    if not text or len(text.strip()) == 0:
        return text
    try:
        encoded = quote(text[:500])
        url = f"https://api.mymemory.translated.net/get?q={encoded}&langpair=en|es"
        req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(req, timeout=6) as r:
            data = json.loads(r.read().decode())
        translated = data.get("responseData", {}).get("translatedText", "")
        if translated and translated.lower() != text.lower():
            return translated
    except Exception as e:
        print(f"  Translation error: {e}")
    return text

# ── RSS Feeds by section ───────────────────────────────────────────────────
# Equivalencias:
#   NYT World/Business  → The Guardian World + AP + Vox
#   Financial Times     → The Guardian Business + MarketWatch + Seeking Alpha
#   Le Grand Continent  → Foreign Policy + Council on Foreign Relations + EUobserver
FEEDS = [
    # ── Internacional ──────────────────────────────────────────────────────
    {"url": "https://feeds.bbci.co.uk/news/world/rss.xml",                         "source": "BBC World",      "lang": "en", "cat": "Internacional"},
    {"url": "https://feeds.reuters.com/reuters/worldNews",                          "source": "Reuters",        "lang": "en", "cat": "Internacional"},
    {"url": "https://www.theguardian.com/world/rss",                                "source": "The Guardian",   "lang": "en", "cat": "Internacional"},
    {"url": "https://rsshub.app/apnews/topics/apf-topnews",                         "source": "AP News",        "lang": "en", "cat": "Internacional"},
    {"url": "https://rss.dw.com/rdf/rss-es-world",                                 "source": "DW Español",     "lang": "es", "cat": "Internacional"},
    {"url": "https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/section/internacional/portada",
                                                                                    "source": "El País",        "lang": "es", "cat": "Internacional"},

    # ── Geopolítica europea ────────────────────────────────────────────────
    {"url": "https://foreignpolicy.com/feed/",                                      "source": "Foreign Policy", "lang": "en", "cat": "Geopolítica"},
    {"url": "https://www.cfr.org/rss.xml",                                          "source": "CFR",            "lang": "en", "cat": "Geopolítica"},
    {"url": "https://euobserver.com/rss.xml",                                       "source": "EUobserver",     "lang": "en", "cat": "Geopolítica"},
    {"url": "https://www.chathamhouse.org/rss.xml",                                 "source": "Chatham House",  "lang": "en", "cat": "Geopolítica"},
    {"url": "https://rss.dw.com/rdf/rss-es-eu",                                    "source": "DW Europa",      "lang": "es", "cat": "Geopolítica"},

    # ── Mercados y Wall Street ─────────────────────────────────────────────
    {"url": "https://feeds.marketwatch.com/marketwatch/topstories/",                "source": "MarketWatch",    "lang": "en", "cat": "Mercados"},
    {"url": "https://www.theguardian.com/business/rss",                             "source": "Guardian Biz",   "lang": "en", "cat": "Mercados"},
    {"url": "https://feeds.reuters.com/reuters/businessNews",                       "source": "Reuters Biz",    "lang": "en", "cat": "Mercados"},
    {"url": "https://rss.dw.com/rdf/rss-es-eco",                                   "source": "DW Economía",    "lang": "es", "cat": "Mercados"},
    {"url": "https://feeds.bbci.co.uk/news/business/rss.xml",                      "source": "BBC Business",   "lang": "en", "cat": "Mercados"},

    # ── Política EE.UU. ────────────────────────────────────────────────────
    {"url": "https://feeds.bbci.co.uk/news/world/us_and_canada/rss.xml",           "source": "BBC US",         "lang": "en", "cat": "Política EE.UU."},
    {"url": "https://feeds.reuters.com/Reuters/PoliticsNews",                       "source": "Reuters Pol.",   "lang": "en", "cat": "Política EE.UU."},
    {"url": "https://www.theguardian.com/us-news/rss",                              "source": "Guardian US",    "lang": "en", "cat": "Política EE.UU."},
    {"url": "https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/section/usa/portada",
                                                                                    "source": "El País US",     "lang": "es", "cat": "Política EE.UU."},

    # ── Ciencia y Salud ────────────────────────────────────────────────────
    {"url": "https://feeds.bbci.co.uk/news/science_and_environment/rss.xml",       "source": "BBC Science",    "lang": "en", "cat": "Ciencia y Salud"},
    {"url": "https://www.theguardian.com/science/rss",                              "source": "Guardian Sci.",  "lang": "en", "cat": "Ciencia y Salud"},
    {"url": "https://feeds.reuters.com/reuters/scienceNews",                        "source": "Reuters Sci.",   "lang": "en", "cat": "Ciencia y Salud"},
    {"url": "https://rss.dw.com/rdf/rss-es-ciencia",                               "source": "DW Ciencia",     "lang": "es", "cat": "Ciencia y Salud"},

    # ── Deportes ───────────────────────────────────────────────────────────
    {"url": "https://feeds.bbci.co.uk/sport/rss.xml",                              "source": "BBC Sport",      "lang": "en", "cat": "Deportes"},
    {"url": "https://www.theguardian.com/sport/rss",                                "source": "Guardian Sport", "lang": "en", "cat": "Deportes"},
    {"url": "https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/section/deportes/portada",
                                                                                    "source": "El País Dep.",   "lang": "es", "cat": "Deportes"},
    {"url": "https://rss.dw.com/rdf/rss-es-deportes",                              "source": "DW Deportes",    "lang": "es", "cat": "Deportes"},
]

ITEMS_PER_FEED = 3
articles = []
translation_count = 0
MAX_TRANSLATIONS = 900  # stay under MyMemory's 1000/day limit

for feed_meta in FEEDS:
    try:
        feed = feedparser.parse(feed_meta["url"])
        for entry in feed.entries[:ITEMS_PER_FEED]:
            summary = getattr(entry, "summary", "") or ""
            summary = re.sub('<[^<]+?>', '', summary).strip()
            summary = summary[:220] + ("..." if len(summary) > 220 else "")

            title_es   = entry.title
            summary_es = summary

            if feed_meta["lang"] == "en" and translation_count < MAX_TRANSLATIONS:
                print(f"  [{feed_meta['cat']}] Translating: {entry.title[:55]}...")
                title_es = translate_to_spanish(entry.title)
                translation_count += 1
                if summary and translation_count < MAX_TRANSLATIONS:
                    summary_es = translate_to_spanish(summary)
                    translation_count += 1

            pub = getattr(entry, "published_parsed", None)
            if pub:
                dt = datetime(*pub[:6], tzinfo=pytz.utc).astimezone(ET)
                time_str = dt.strftime("%-I:%M %p ET")
            else:
                time_str = "—"

            articles.append({
                "title":      entry.title,
                "title_es":   title_es,
                "link":       entry.link,
                "summary":    summary,
                "summary_es": summary_es,
                "source":     feed_meta["source"],
                "lang":       feed_meta["lang"],
                "cat":        feed_meta["cat"],
                "time":       time_str,
            })
    except Exception as e:
        print(f"  Error fetching {feed_meta['source']}: {e}")

print(f"\nTotal articles: {len(articles)} | Translations used: {translation_count}")

# ── Group by category ──────────────────────────────────────────────────────
by_cat = defaultdict(list)
for a in articles:
    by_cat[a["cat"]].append(a)

SECTIONS_ORDER = ["Internacional", "Geopolítica", "Mercados", "Política EE.UU.", "Ciencia y Salud", "Deportes"]

CAT_META = {
    "Internacional":   {"color": "#1a3a5c", "bg": "#e8f0fa", "dot": "#1a3a5c", "icon": "🌍"},
    "Geopolítica":     {"color": "#2d1a5c", "bg": "#ede8fa", "dot": "#2d1a5c", "icon": "🗺️"},
    "Mercados":        {"color": "#1a4a2e", "bg": "#e8f5ee", "dot": "#1a4a2e", "icon": "📈"},
    "Política EE.UU.": {"color": "#5c2a1a", "bg": "#faeee8", "dot": "#5c2a1a", "icon": "🏛️"},
    "Ciencia y Salud": {"color": "#1a3a3a", "bg": "#e8f5f5", "dot": "#1a3a3a", "icon": "🔬"},
    "Deportes":        {"color": "#3a2a00", "bg": "#faf3e8", "dot": "#3a2a00", "icon": "⚽"},
}

def flag(lang):
    return "🇬🇧" if lang == "en" else "🇪🇸"

def build_card(a, featured=False):
    m = CAT_META.get(a["cat"], {"color":"#333","bg":"#f5f5f5"})
    return f"""<a href="{a['link']}" target="_blank" rel="noopener" class="card {'card-featured' if featured else ''}">
      <div class="card-top">
        <span class="tag" style="background:{m['bg']};color:{m['color']}">{a['cat']}</span>
        <span class="card-meta">{flag(a['lang'])} {a['source']} · {a['time']}</span>
      </div>
      <h3 class="card-title {'card-title-big' if featured else ''}">{a['title_es']}</h3>
      {'<p class="card-summary">' + a['summary_es'] + '</p>' if featured and a.get('summary_es') else ''}
    </a>"""

def build_section(cat, items):
    if not items:
        return ""
    m = CAT_META.get(cat, {"color":"#333","bg":"#f5f5f5","dot":"#333","icon":""})
    featured   = items[0]
    secondary  = items[1:4]   # up to 3 in grid
    extra      = items[4:7]   # up to 3 more smaller

    html = f"""<section class="news-section">
      <div class="section-header">
        <span class="section-dot" style="background:{m['dot']}"></span>
        <h2 class="section-title">{m['icon']} {cat}</h2>
      </div>
      {build_card(featured, featured=True)}"""

    if secondary:
        html += '<div class="card-grid">' + "".join(build_card(a) for a in secondary) + '</div>'
    if extra:
        html += '<div class="card-grid card-grid-sm">' + "".join(build_card(a) for a in extra) + '</div>'

    html += "</section>"
    return html

sections_html = "".join(build_section(cat, by_cat.get(cat, [])) for cat in SECTIONS_ORDER)

# ── Audio scripts ──────────────────────────────────────────────────────────
top = [by_cat[c][0] for c in SECTIONS_ORDER if by_cat.get(c)]

months_en_es = {"January":"enero","February":"febrero","March":"marzo","April":"abril",
    "May":"mayo","June":"junio","July":"julio","August":"agosto",
    "September":"septiembre","October":"octubre","November":"noviembre","December":"diciembre"}
days_en_es   = {"Monday":"Lunes","Tuesday":"Martes","Wednesday":"Miércoles","Thursday":"Jueves",
    "Friday":"Viernes","Saturday":"Sábado","Sunday":"Domingo"}

date_es = now_et.strftime("%-d de %B de %Y")
for en, es in months_en_es.items():
    date_es = date_es.replace(en, es)
date_display = f"{days_en_es.get(now_et.strftime('%A'), now_et.strftime('%A'))}, {date_es}"
time_display = now_et.strftime("%-I:%M %p ET")

script_es = (f"Bienvenido a Mi Briefing. {edition_es} del {date_display}. "
             + " ".join(f"En {a['cat']}: {a['title_es']}. Fuente: {a['source']}." for a in top)
             + " Eso es todo. Visita Mi Briefing para leer los detalles.")
script_en = (f"Welcome to Mi Briefing. {edition_es}, {date_display}. "
             + " ".join(f"In {a['cat']}: {a['title']}. Source: {a['source']}." for a in top)
             + " That's all for now. Visit Mi Briefing for full stories.")

audio_data = json.dumps({"es": script_es, "en": script_en})

# ── Sources list for footer ────────────────────────────────────────────────
all_sources = sorted(set(a["source"] for a in articles))
sources_str = " · ".join(all_sources)

# ── HTML ──────────────────────────────────────────────────────────────────
HTML = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Mi Briefing — {date_display}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@500;700&family=Source+Sans+3:wght@400;500;600&display=swap" rel="stylesheet">
<style>
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
  :root {{
    --bg: #f7f5f0; --surface: #ffffff; --border: #e2ddd6;
    --text: #1a1814; --muted: #6b6560; --faint: #b0aaa3;
  }}
  body {{ font-family: 'Source Sans 3', sans-serif; background: var(--bg); color: var(--text); font-size: 16px; line-height: 1.6; }}
  a {{ color: inherit; text-decoration: none; }}

  /* MASTHEAD */
  .masthead {{ background: var(--surface); border-bottom: 2px solid var(--text); padding: 1.5rem 0 1rem; text-align: center; }}
  .masthead-eyebrow {{ font-size: 11px; letter-spacing: 3px; text-transform: uppercase; color: var(--muted); margin-bottom: 0.5rem; }}
  .masthead-logo {{ font-family: 'Playfair Display', serif; font-size: clamp(2rem, 6vw, 3.5rem); font-weight: 700; letter-spacing: -1px; line-height: 1; margin-bottom: 0.5rem; }}
  .masthead-meta {{ display: flex; justify-content: center; align-items: center; gap: 1.5rem; font-size: 12px; color: var(--muted); border-top: 1px solid var(--border); margin-top: 0.75rem; padding-top: 0.75rem; flex-wrap: wrap; }}
  .edition-badge {{ background: var(--text); color: white; font-size: 11px; font-weight: 600; padding: 3px 10px; border-radius: 2px; letter-spacing: 1px; text-transform: uppercase; }}

  /* SECTION NAV */
  .section-nav {{ background: var(--surface); border-bottom: 1px solid var(--border); padding: 0.5rem 0; overflow-x: auto; white-space: nowrap; }}
  .section-nav-inner {{ max-width: 960px; margin: 0 auto; padding: 0 1rem; display: flex; gap: 6px; }}
  .nav-pill {{ display: inline-block; font-size: 12px; font-weight: 600; padding: 4px 14px; border-radius: 20px; border: 1px solid var(--border); color: var(--muted); cursor: pointer; text-decoration: none; transition: all 0.15s; }}
  .nav-pill:hover {{ background: var(--text); color: white; border-color: var(--text); }}

  /* TICKER */
  .ticker-wrap {{ background: var(--text); color: white; font-size: 12px; font-weight: 500; overflow: hidden; white-space: nowrap; padding: 6px 0; }}
  .ticker-inner {{ display: inline-block; animation: ticker 40s linear infinite; padding-left: 100%; }}
  .ticker-inner span {{ margin: 0 2rem; }}
  @keyframes ticker {{ from {{ transform: translateX(0); }} to {{ transform: translateX(-100%); }} }}

  /* AUDIO */
  .audio-bar {{ background: var(--surface); border-bottom: 1px solid var(--border); padding: 0.75rem 0; }}
  .audio-inner {{ max-width: 960px; margin: 0 auto; padding: 0 1rem; display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }}
  .audio-label {{ font-size: 13px; font-weight: 600; color: var(--text); white-space: nowrap; }}
  .lang-toggle {{ display: flex; border: 1px solid var(--border); border-radius: 4px; overflow: hidden; }}
  .lang-btn {{ padding: 5px 14px; font-size: 12px; font-weight: 600; cursor: pointer; border: none; background: transparent; color: var(--muted); font-family: 'Source Sans 3', sans-serif; transition: all 0.15s; }}
  .lang-btn.active {{ background: var(--text); color: white; }}
  .play-btn {{ display: flex; align-items: center; gap: 6px; padding: 6px 16px; font-size: 13px; font-weight: 600; background: var(--text); color: white; border: none; border-radius: 4px; cursor: pointer; font-family: 'Source Sans 3', sans-serif; transition: opacity 0.15s; }}
  .play-btn:hover {{ opacity: 0.85; }}
  .audio-progress {{ flex: 1; min-width: 140px; font-size: 12px; color: var(--muted); display: none; }}
  .audio-progress.visible {{ display: block; }}
  .progress-bar-wrap {{ height: 3px; background: var(--border); border-radius: 2px; margin-top: 4px; }}
  .progress-bar-fill {{ height: 3px; background: var(--text); border-radius: 2px; width: 0%; transition: width 0.5s linear; }}

  /* LAYOUT */
  .container {{ max-width: 960px; margin: 0 auto; padding: 0 1rem; }}
  .main {{ padding: 2rem 0 3rem; }}

  /* SECTIONS */
  .news-section {{ margin-bottom: 3rem; scroll-margin-top: 80px; }}
  .section-header {{ display: flex; align-items: center; gap: 10px; margin-bottom: 1rem; padding-bottom: 0.5rem; border-bottom: 1.5px solid var(--text); }}
  .section-dot {{ width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0; }}
  .section-title {{ font-family: 'Playfair Display', serif; font-size: 1.15rem; font-weight: 500; }}

  /* CARDS */
  .card {{ display: block; background: var(--surface); border: 1px solid var(--border); border-radius: 4px; padding: 1rem 1.25rem; transition: border-color 0.15s, box-shadow 0.15s; margin-bottom: 10px; }}
  .card:hover {{ border-color: #999; box-shadow: 0 2px 12px rgba(0,0,0,0.06); }}
  .card-featured {{ padding: 1.25rem 1.5rem; }}
  .card-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 10px; margin-bottom: 10px; }}
  .card-grid-sm {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 10px; margin-bottom: 10px; }}
  .card-grid .card, .card-grid-sm .card {{ margin-bottom: 0; }}
  .card-top {{ display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.5rem; gap: 8px; }}
  .tag {{ font-size: 10px; font-weight: 600; letter-spacing: 1px; text-transform: uppercase; padding: 2px 8px; border-radius: 2px; flex-shrink: 0; white-space: nowrap; }}
  .card-meta {{ font-size: 11px; color: var(--faint); white-space: nowrap; }}
  .card-title {{ font-family: 'Playfair Display', serif; font-size: 0.95rem; font-weight: 500; line-height: 1.35; color: var(--text); }}
  .card-title-big {{ font-size: 1.2rem; }}
  .card-summary {{ margin-top: 0.5rem; font-size: 0.875rem; color: var(--muted); line-height: 1.55; }}

  /* FOOTER */
  .footer {{ border-top: 2px solid var(--text); padding: 1.5rem 0; text-align: center; }}
  .footer p {{ font-size: 12px; color: var(--muted); margin-bottom: 4px; }}
  .footer strong {{ color: var(--text); }}
  .sources-list {{ font-size: 11px; color: var(--faint); margin-top: 6px; line-height: 1.8; }}

  @media (max-width: 600px) {{
    .card-grid, .card-grid-sm {{ grid-template-columns: 1fr; }}
    .masthead-meta {{ gap: 0.5rem; }}
  }}
</style>
</head>
<body>

<header class="masthead">
  <div class="container">
    <p class="masthead-eyebrow">Tu resumen de noticias · Your news briefing</p>
    <h1 class="masthead-logo">Mi Briefing</h1>
    <div class="masthead-meta">
      <span>{date_display}</span>
      <span class="edition-badge">{edition_es}</span>
      <span>Actualizado · {time_display}</span>
    </div>
  </div>
</header>

<div class="ticker-wrap">
  <div class="ticker-inner">
    <span>S&amp;P 500 — en seguimiento</span><span>·</span>
    <span>Dow Jones — en seguimiento</span><span>·</span>
    <span>Nasdaq — en seguimiento</span><span>·</span>
    <span>EUR/USD — en seguimiento</span><span>·</span>
    <span>Petróleo WTI — en seguimiento</span><span>·</span>
    <span>Bitcoin — en seguimiento</span><span>·</span>
    <span>Oro — en seguimiento</span><span>·</span>
    <span>Bono 10Y EE.UU. — en seguimiento</span>
  </div>
</div>

<nav class="section-nav">
  <div class="section-nav-inner">
    <a class="nav-pill" href="#internacional">🌍 Internacional</a>
    <a class="nav-pill" href="#geopolitica">🗺️ Geopolítica</a>
    <a class="nav-pill" href="#mercados">📈 Mercados</a>
    <a class="nav-pill" href="#politica">🏛️ Política EE.UU.</a>
    <a class="nav-pill" href="#ciencia">🔬 Ciencia y Salud</a>
    <a class="nav-pill" href="#deportes">⚽ Deportes</a>
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
  <div class="container" id="internacional">
    {sections_html}
  </div>
</main>

<footer class="footer">
  <div class="container">
    <p><strong>Mi Briefing</strong> — Resumen de noticias para familia y amigos</p>
    <p>Actualizado automáticamente · 6:00 AM ET y 2:00 PM ET</p>
    <p class="sources-list">{sources_str}</p>
  </div>
</footer>

<script>
const SCRIPTS = {audio_data};
let currentLang = 'es', speaking = false, utterance = null;

function setLang(lang) {{
  currentLang = lang;
  document.getElementById('btn-es').classList.toggle('active', lang === 'es');
  document.getElementById('btn-en').classList.toggle('active', lang === 'en');
  document.getElementById('play-label').textContent = lang === 'es' ? 'Reproducir' : 'Play';
  if (speaking) stopAudio();
}}

function toggleAudio() {{ speaking ? stopAudio() : startAudio(); }}

function startAudio() {{
  if (!window.speechSynthesis) {{ alert('Tu navegador no soporta síntesis de voz.'); return; }}
  const text = SCRIPTS[currentLang];
  utterance = new SpeechSynthesisUtterance(text);
  utterance.lang  = currentLang === 'es' ? 'es-US' : 'en-US';
  utterance.rate  = 0.92;
  utterance.pitch = 1.0;
  const voices = window.speechSynthesis.getVoices();
  const pick = voices.find(v => currentLang === 'es'
    ? v.lang.startsWith('es') && /Google|Paulina|Monica|Jorge/.test(v.name)
    : v.lang.startsWith('en') && /Google|Samantha|Alex/.test(v.name)
  ) || voices.find(v => currentLang === 'es' ? v.lang.startsWith('es') : v.lang.startsWith('en'));
  if (pick) utterance.voice = pick;
  const total = text.length;
  utterance.onboundary = (e) => {{
    if (e.name === 'word') {{
      const pct = Math.min(100, Math.round((e.charIndex / total) * 100));
      document.getElementById('progress-fill').style.width = pct + '%';
      document.getElementById('progress-text').textContent =
        (currentLang === 'es' ? 'Reproduciendo' : 'Playing') + '... ' + pct + '%';
    }}
  }};
  utterance.onend = utterance.onerror = resetPlayer;
  window.speechSynthesis.speak(utterance);
  speaking = true;
  document.getElementById('play-icon').textContent  = '⏹';
  document.getElementById('play-label').textContent = currentLang === 'es' ? 'Detener' : 'Stop';
  document.getElementById('audio-progress').classList.add('visible');
}}

function stopAudio() {{ window.speechSynthesis.cancel(); resetPlayer(); }}

function resetPlayer() {{
  speaking = false;
  document.getElementById('play-icon').textContent  = '▶';
  document.getElementById('play-label').textContent = currentLang === 'es' ? 'Reproducir' : 'Play';
  document.getElementById('progress-fill').style.width = '0%';
  document.getElementById('audio-progress').classList.remove('visible');
}}

// Add section IDs for nav links
const sectionMap = {{
  'Internacional': 'internacional', 'Geopolítica': 'geopolitica',
  'Mercados': 'mercados', 'Política EE.UU.': 'politica',
  'Ciencia y Salud': 'ciencia', 'Deportes': 'deportes'
}};
document.querySelectorAll('.news-section').forEach(sec => {{
  const title = sec.querySelector('.section-title');
  if (title) {{
    const text = title.textContent.trim().replace(/^\\S+\\s*/, ''); // strip icon
    const id = sectionMap[text];
    if (id) sec.id = id;
  }}
}});

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

print(f"\n✅  docs/index.html listo — {len(articles)} artículos en 6 secciones — {edition_es} — {time_display}")
