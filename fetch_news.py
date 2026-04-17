import feedparser
import json
from datetime import datetime
import pytz
import re
import os
import asyncio
import edge_tts
from urllib.request import urlopen, Request
from urllib.parse import quote

# --- Configuración de Tiempo ---
ET = pytz.timezone("America/New_York")
now_et = datetime.now(ET)
hour = now_et.hour
edition = "morning" if hour < 13 else "afternoon"
edition_es = "Edición matutina" if edition == "morning" else "Edición vespertina"

# --- Traducción via MyMemory ---
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

# --- RSS Feeds ---
FEEDS = [
    {"url": "https://feeds.bbci.co.uk/news/world/rss.xml",         "source": "BBC",         "lang": "en", "cat": "Internacional"},
    {"url": "https://feeds.reuters.com/reuters/worldNews",          "source": "Reuters",     "lang": "en", "cat": "Internacional"},
    {"url": "https://rss.dw.com/rdf/rss-es-world",                 "source": "DW Español",  "lang": "es", "cat": "Internacional"},
    {"url": "https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/section/internacional/portada", "source": "El País", "lang": "es", "cat": "Internacional"},
    {"url": "https://feeds.bbci.co.uk/news/business/rss.xml",       "source": "BBC Negocios","lang": "en", "cat": "Economía"},
    {"url": "https://rss.dw.com/rdf/rss-es-eco",                   "source": "DW Economía", "lang": "es", "cat": "Economía"},
    {"url": "https://feeds.bbci.co.uk/news/technology/rss.xml",    "source": "BBC Tech",    "lang": "en", "cat": "Tecnología"},
]

articles = []
for feed_meta in FEEDS:
    try:
        feed = feedparser.parse(feed_meta["url"])
        for entry in feed.entries[:3]:
            summary = getattr(entry, "summary", "") or ""
            summary = re.sub('<[^<]+?>', '', summary).strip()
            summary = summary[:220] + ("..." if len(summary) > 220 else "")

            title_es = entry.title
            summary_es = summary

            if feed_meta["lang"] == "en":
                title_es = translate_to_spanish(entry.title)
                if summary:
                    summary_es = translate_to_spanish(summary)

            pub = getattr(entry, "published_parsed", None)
            time_str = datetime(*pub[:6], tzinfo=pytz.utc).astimezone(ET).strftime("%-I:%M %p ET") if pub else "—"

            articles.append({
                "title_es": title_es,
                "title_en": entry.title,
                "link": entry.link,
                "summary_es": summary_es,
                "source": feed_meta["source"],
                "cat": feed_meta["cat"],
                "time": time_str,
                "lang": feed_meta["lang"]
            })
    except Exception as e:
        print(f"Error: {e}")

# --- Organización y HTML ---
from collections import defaultdict
by_cat = defaultdict(list)
for a in articles: by_cat[a["cat"]].append(a)

def build_article_card(a, featured=False):
    source_flag = "🇬🇧" if a["lang"] == "en" else "🇪🇸"
    return f"""
    <a href="{a['link']}" target="_blank" class="card {'card-featured' if featured else 'card-normal'}">
      <div class="card-top"><span class="tag">{a['cat']}</span><span class="card-meta">{source_flag} {a['source']} · {a['time']}</span></div>
      <h3 class="card-title">{a['title_es']}</h3>
      {f'<p class="card-summary">{a["summary_es"]}</p>' if featured else ''}
    </a>"""

sections_html = "".join([f'<section class="news-section"><h2>{c}</h2>' + build_article_card(by_cat[c][0], True) + '</div></section>' for c in by_cat])

# --- Preparación de Textos para Audio ---
top_articles = [by_cat[c][0] for c in by_cat if by_cat[c]]
date_display = now_et.strftime("%d/%m/%Y")

text_es = f"Bienvenido a Mi Briefing. {edition_es}. Las noticias: " + " ".join([f"{a['title_es']}. Fuente: {a['source']}." for a in top_articles[:5]])
text_en = f"Welcome to Mi Briefing. {edition}. Top stories: " + " ".join([f"{a['title_en']}. Source: {a['source']}." for a in top_articles[:5]])

# --- Función para generar los MP3 ---
async def generate_audios():
    os.makedirs("docs", exist_ok=True)
    await edge_tts.Communicate(text_es, "es-ES-AlvaroNeural").save("docs/news_es.mp3")
    await edge_tts.Communicate(text_en, "en-US-AndrewNeural").save("docs/news_en.mp3")

asyncio.run(generate_audios())

# --- Generación del HTML Final ---
HTML = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Mi Briefing</title>
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700&family=Source+Sans+3:wght@400;600&display=swap" rel="stylesheet">
<style>
  body {{ font-family: 'Source Sans 3', sans-serif; background: #f7f5f0; color: #1a1814; padding: 20px; }}
  .container {{ max-width: 800px; margin: 0 auto; }}
  .masthead {{ text-align: center; border-bottom: 2px solid #000; padding-bottom: 20px; margin-bottom: 20px; }}
  .card {{ background: #fff; border: 1px solid #ddd; padding: 15px; margin-bottom: 10px; display: block; text-decoration: none; color: inherit; border-radius: 5px; }}
  .tag {{ font-weight: bold; text-transform: uppercase; font-size: 10px; background: #eee; padding: 2px 5px; }}
  .audio-bar {{ background: #fff; padding: 15px; border-radius: 8px; margin-bottom: 20px; display: flex; align-items: center; gap: 15px; border: 1px solid #ddd; }}
  .play-btn {{ background: #000; color: #fff; border: none; padding: 10px 20px; cursor: pointer; border-radius: 5px; font-weight: bold; }}
  .progress-bar {{ flex: 1; height: 5px; background: #eee; border-radius: 5px; position: relative; overflow: hidden; }}
  .progress-fill {{ width: 0%; height: 100%; background: #000; transition: width 0.3s; }}
</style>
</head>
<body>
<div class="container">
  <header class="masthead">
    <h1>Mi Briefing</h1>
    <p>{edition_es} — {date_display}</p>
  </header>

  <div class="audio-bar">
    <button class="play-btn" onclick="toggleAudio()" id="btn-text">▶ Reproducir Resumen</button>
    <div class="progress-bar"><div class="progress-fill" id="fill"></div></div>
    <select id="lang" onchange="stopAudio()">
      <option value="es">Español</option>
      <option value="en">English</option>
    </select>
  </div>

  <main>{sections_html}</main>
</div>

<script>
  let audio = new Audio();
  function toggleAudio() {{
    if (!audio.paused) {{ stopAudio(); return; }}
    const lang = document.getElementById('lang').value;
    audio.src = lang === 'es' ? 'news_es.mp3' : 'news_en.mp3';
    audio.play();
    document.getElementById('btn-text').innerText = '⏹ Detener';
    audio.ontimeupdate = () => {{
      document.getElementById('fill').style.width = (audio.currentTime / audio.duration * 100) + '%';
    }};
    audio.onended = stopAudio;
  }}
  function stopAudio() {{
    audio.pause(); audio.currentTime = 0;
    document.getElementById('btn-text').innerText = '▶ Reproducir Resumen';
    document.getElementById('fill').style.width = '0%';
  }}
</script>
</body>
</html>"""

with open("docs/index.html", "w", encoding="utf-8") as f:
    f.write(HTML)

print("¡Listo! HTML y Audios generados en /docs")
