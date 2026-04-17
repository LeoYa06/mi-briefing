import feedparser
import json
from datetime import datetime
import pytz
import re
import os
from urllib.request import urlopen, Request
from urllib.parse import quote

ET = pytz.timezone("America/New_York")
now_et = datetime.now(ET)
hour = now_et.hour
edition = "morning" if hour < 13 else "afternoon"
edition_es = "Edición matutina" if edition == "morning" else "Edición vespertina"

# ── Translation via MyMemory (free, no key, 1000 req/day) ──────────────────
def translate_to_spanish(text):
    if not text or len(text.strip()) == 0:
        return text
    try:
        encoded = quote(text[:500])
        url = f"https://api.mymemory.translated.net/get?q={encoded}&langpair=en|es"
        req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(req, timeout=5) as r:
            data = json.loads(r.read().decode())
        translated = data.get("responseData", {}).get("translatedText", "")
        if translated and translated.lower() != text.lower():
            return translated
    except Exception as e:
        print(f"  Translation error: {e}")
    return text

# ── RSS Feeds ──────────────────────────────────────────────────────────────
FEEDS = [
    {"url": "https://feeds.bbci.co.uk/news/world/rss.xml",         "source": "BBC",         "lang": "en", "cat": "Internacional"},
    {"url": "https://feeds.reuters.com/reuters/worldNews",          "source": "Reuters",     "lang": "en", "cat": "Internacional"},
    {"url": "https://rss.dw.com/rdf/rss-es-world",                 "source": "DW Español",  "lang": "es", "cat": "Internacional"},
    {"url": "https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/section/internacional/portada",
                                                                    "source": "El País",     "lang": "es", "cat": "Internacional"},
    {"url": "https://feeds.bbci.co.uk/news/business/rss.xml",       "source": "BBC Negocios","lang": "en", "cat": "Economía"},
    {"url": "https://feeds.reuters.com/reuters/businessNews",       "source": "Reuters Eco", "lang": "en", "cat": "Economía"},
    {"url": "https://rss.dw.com/rdf/rss-es-eco",                   "source": "DW Economía", "lang": "es", "cat": "Economía"},
    {"url": "https://feeds.reuters.com/reuters/technologyNews",     "source": "Reuters Tech","lang": "en", "cat": "Tecnología"},
    {"url": "https://feeds.bbci.co.uk/news/technology/rss.xml",    "source": "BBC Tech",    "lang": "en", "cat": "Tecnología"},
    {"url": "https://feeds.bbci.co.uk/news/science_and_environment/rss.xml",
                                                                    "source": "BBC Clima",   "lang": "en", "cat": "Clima"},
]

ITEMS_PER_FEED = 3
articles = []

for feed_meta in FEEDS:
    try:
        feed = feedparser.parse(feed_meta["url"])
        for entry in feed.entries[:ITEMS_PER_FEED]:
            summary = getattr(entry, "summary", "") or ""
            summary = re.sub('<[^<]+?>', '', summary).strip()
            summary = summary[:220] + ("..." if len(summary) > 220 else "")

            title_es = entry.title
            summary_es = summary

            if feed_meta["lang"] == "en":
                print(f"  Translating: {entry.title[:60]}...")
                title_es  = translate_to_spanish(entry.title)
                if summary:
                    summary_es = translate_to_spanish(summary)

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
        print(f"Error fetching {feed_meta['url']}: {e}")

# ── Group by category ──────────────────────────────────────────────────────
from collections import defaultdict
by_cat = defaultdict(list)
for a in articles:
    by_cat[a["cat"]].append(a)

CAT_COLORS = {
    "Internacional": ("#1a3a5c", "#e8f0fa"),
    "Economía":      ("#1a4a2e", "#e8f5ee"),
    "Tecnología":    ("#3a1a5c", "#f0e8fa"),
    "Clima":         ("#1a3a3a", "#e8f5f5"),
}

def build_article_card(a, featured=False):
    text_color, bg_color = CAT_COLORS.get(a["cat"], ("#333", "#f5f5f5"))
    source_flag = "🇬🇧" if a["lang"] == "en" else "🇪🇸"
    title_display   = a["title_es"]
    summary_display = a.get("summary_es", "")
    return f"""
    <a href="{a['link']}" target="_blank" rel="noopener" class="card {'card-featured' if featured else 'card-normal'}">
      <div class="card-top">
        <span class="tag" style="background:{bg_color};color:{text_color}">{a['cat']}</span>
        <span class="card-meta">{source_flag} {a['source']} · {a['time']}</span>
      </div>
      <h3 class="card-title {'card-title-big' if featured else ''}">{title_display}</h3>
      {'<p class="card-summary">' + summary_display + '</p>' if featured and summary_display else ''}
    </a>"""

def build_section(cat, items):
    if not items:
        return ""
    text_color, _ = CAT_COLORS.get(cat, ("#333", "#f5f5f5"))
    featured = items[0]
    rest = items[1:]
    cards_html = build_article_card(featured, featured=True)
    if rest:
        cards_html += '<div class="card-grid">'
        for a in rest:
            cards_html += build_article_card(a, featured=False)
        cards_html += '</div>'
    return f"""
    <section class="news-section">
      <div class="section-header">
        <span class="section-dot" style="background:{text_color}"></span>
        <h2 class="section-title">{cat}</h2>
      </div>
      {cards_html}
    </section>"""

sections_html = ""
for cat in ["Internacional", "Economía", "Tecnología", "Clima"]:
    sections_html += build_section(cat, by_cat.get(cat, []))



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

  .masthead {{ background: var(--surface); border-bottom: 2px solid var(--text); padding: 1.5rem 0 1rem; text-align: center; }}
  .masthead-eyebrow {{ font-size: 11px; letter-spacing: 3px; text-transform: uppercase; color: var(--muted); margin-bottom: 0.5rem; }}
  .masthead-logo {{ font-family: 'Playfair Display', serif; font-size: clamp(2rem, 6vw, 3.5rem); font-weight: 700; letter-spacing: -1px; line-height: 1; margin-bottom: 0.5rem; }}
  .masthead-meta {{ display: flex; justify-content: center; align-items: center; gap: 1.5rem; font-size: 12px; color: var(--muted); border-top: 1px solid var(--border); margin-top: 0.75rem; padding-top: 0.75rem; flex-wrap: wrap; }}
  .edition-badge {{ background: var(--text); color: white; font-size: 11px; font-weight: 600; padding: 3px 10px; border-radius: 2px; letter-spacing: 1px; text-transform: uppercase; }}

  .ticker-wrap {{ background: var(--text); color: white; font-size: 12px; font-weight: 500; overflow: hidden; white-space: nowrap; padding: 6px 0; }}
  .ticker-inner {{ display: inline-block; animation: ticker 35s linear infinite; padding-left: 100%; }}
  .ticker-inner span {{ margin: 0 2rem; }}
  @keyframes ticker {{ from {{ transform: translateX(0); }} to {{ transform: translateX(-100%); }} }}

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

  .container {{ max-width: 960px; margin: 0 auto; padding: 0 1rem; }}
  .main {{ padding: 2rem 0 3rem; }}
  .news-section {{ margin-bottom: 2.5rem; }}
  .section-header {{ display: flex; align-items: center; gap: 10px; margin-bottom: 1rem; padding-bottom: 0.5rem; border-bottom: 1.5px solid var(--text); }}
  .section-dot {{ width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0; }}
  .section-title {{ font-family: 'Playfair Display', serif; font-size: 1.1rem; font-weight: 500; }}
  .card {{ display: block; background: var(--surface); border: 1px solid var(--border); border-radius: 4px; padding: 1rem 1.25rem; transition: border-color 0.15s, box-shadow 0.15s; margin-bottom: 10px; }}
  .card:hover {{ border-color: #999; box-shadow: 0 2px 12px rgba(0,0,0,0.06); }}
  .card-featured {{ padding: 1.25rem 1.5rem; }}
  .card-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 10px; }}
  .card-grid .card {{ margin-bottom: 0; }}
  .card-top {{ display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.5rem; gap: 8px; }}
  .tag {{ font-size: 10px; font-weight: 600; letter-spacing: 1px; text-transform: uppercase; padding: 2px 8px; border-radius: 2px; flex-shrink: 0; }}
  .card-meta {{ font-size: 11px; color: var(--faint); }}
  .card-title {{ font-family: 'Playfair Display', serif; font-size: 0.95rem; font-weight: 500; line-height: 1.35; }}
  .card-title-big {{ font-size: 1.2rem; }}
  .card-summary {{ margin-top: 0.5rem; font-size: 0.875rem; color: var(--muted); line-height: 1.55; }}
  .footer {{ border-top: 2px solid var(--text); padding: 1.5rem 0; text-align: center; }}
  .footer p {{ font-size: 12px; color: var(--muted); margin-bottom: 4px; }}
  .footer strong {{ color: var(--text); }}
  .sources-list {{ font-size: 11px; color: var(--faint); margin-top: 6px; }}
  @media (max-width: 600px) {{ .card-grid {{ grid-template-columns: 1fr; }} }}
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
    <span>EUR/USD — en seguimiento</span><span>·</span>
    <span>Petróleo WTI — en seguimiento</span><span>·</span>
    <span>Bitcoin — en seguimiento</span><span>·</span>
    <span>Oro — en seguimiento</span><span>·</span>
    <span>Nasdaq — en seguimiento</span>
  </div>
</div>

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
  <div class="container">
    <p><strong>Mi Briefing</strong> — Resumen de noticias para familia y amigos</p>
    <p>Actualizado automáticamente a las 6:00 AM y 2:00 PM ET</p>
    <p class="sources-list">Fuentes: BBC News · Reuters · DW Español · El País</p>
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

print(f"OK  docs/index.html — {len(articles)} articulos — {edition_es} — {time_display}")
