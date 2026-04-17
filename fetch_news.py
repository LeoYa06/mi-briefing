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

# ── 1. CONFIGURACIÓN DE TIEMPO (Texas/New York) ──────────────────────
ET = pytz.timezone("America/New_York")
now_et = datetime.now(ET)
hour = now_et.hour
edition = "morning" if hour < 13 else "afternoon"
edition_es = "Edición matutina" if edition == "morning" else "Edición vespertina"

# ── 2. TRADUCCIÓN VIA MYMEMORY ───────────────────────────────────────
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

# ── 3. RSS FEEDS ─────────────────────────────────────────────────────
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
        print(f"Error procesando {feed_meta['source']}: {e}")

# ── 4. ORGANIZACIÓN POR CATEGORÍAS ───────────────────────────────────
from collections import defaultdict
by_cat = defaultdict(list)
for a in articles:
    by_cat[a["cat"]].append(a)

def build_article_card(a, featured=False):
    source_flag = "🇬🇧" if a["lang"] == "en" else "🇪🇸"
    return f"""
    <a href="{a['link']}" target="_blank" class="card {'card-featured' if featured else 'card-normal'}">
      <div class="card-top">
        <span class="tag">{a['cat']}</span>
        <span class="card-meta">{source_flag} {a['source']} · {a['time']}</span>
      </div>
      <h3 class="card-title">{a['title_es']}</h3>
      {f'<p class="card-summary">{a["summary_es"]}</p>' if featured else ''}
    </a>"""

sections_html = ""
for cat in ["Internacional", "Economía", "Tecnología"]:
    items = by_cat.get(cat, [])
    if items:
        sections_html += f'<section class="news-section"><h2>{cat}</h2>'
        sections_html += build_article_card(items[0], featured=True)
        if len(items) > 1:
            sections_html += '<div class="card-grid">'
            for rest in items[1:]:
                sections_html += build_article_card(rest, featured=False)
            sections_html += '</div>'
        sections_html += '</section>'

# ── 5. PREPARACIÓN DE TEXTOS PARA AUDIO ─────────────────────────────
top_articles = [by_cat[c][0] for c in by_cat if by_cat[c]]
date_display = now_et.strftime("%d/%m/%Y")

text_es = f"Bienvenido a Mi Briefing. {edition_es}. Las noticias principales de hoy son: " + " ".join([f"{a['title_es']}. Fuente: {a['source']}." for a in top_articles[:5]])
text_en = f"Welcome to Mi Briefing. {edition} edition. Today's top stories: " + " ".join([f"{a['title_en']}. Source: {a['source']}." for a in top_articles[:5]])

async def generate_audios():
    os.makedirs("docs", exist_ok=True)
    
    # Intentaremos hasta 3 veces por si falla la conexión
    for intento in range(3):
        try:
            print(f"Intento {intento + 1}: Generando audios neuronales...")
            
            communicate_es = edge_tts.Communicate(text_es, "es-ES-AlvaroNeural")
            communicate_en = edge_tts.Communicate(text_en, "en-US-AndrewNeural")
            
            # Guardamos los archivos
            await communicate_es.save("docs/news_es.mp3")
            await communicate_en.save("docs/news_en.mp3")
            
            # Verificamos si el archivo de audio tiene un tamaño real (ej. más de 2000 bytes)
            if os.path.exists("docs/news_es.mp3") and os.path.getsize("docs/news_es.mp3") > 100:
                print(f"¡Éxito! Audio generado correctamente ({os.path.getsize('docs/news_es.mp3')} bytes)")
                return # Salimos del bucle si tuvo éxito
            
        except Exception as e:
            print(f"Error en intento {intento + 1}: {e}")
            await asyncio.sleep(2) # Esperamos 2 segundos antes de reintentar

    print("ADVERTENCIA: No se pudo generar un audio válido tras 3 intentos.")

# Ejecutamos la generación
asyncio.run(generate_audios())
# ── 7. GENERACIÓN DEL HTML FINAL ─────────────────────────────────────
HTML = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Mi Briefing — {date_display}</title>
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700&family=Source+Sans+3:wght@400;600&display=swap" rel="stylesheet">
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: 'Source Sans 3', sans-serif; background: #f7f5f0; color: #1a1814; line-height: 1.6; padding: 20px; }}
  .container {{ max-width: 900px; margin: 0 auto; }}
  .masthead {{ text-align: center; border-bottom: 3px solid #000; padding-bottom: 20px; margin-bottom: 30px; }}
  .masthead h1 {{ font-family: 'Playfair Display', serif; font-size: 3rem; }}
  
  .audio-bar {{ background: #fff; padding: 20px; border-radius: 10px; margin-bottom: 30px; display: flex; align-items: center; gap: 20px; border: 1px solid #ddd; box-shadow: 0 4px 6px rgba(0,0,0,0.05); }}
  .play-btn {{ background: #000; color: #fff; border: none; padding: 12px 25px; cursor: pointer; border-radius: 6px; font-weight: 600; display: flex; align-items: center; gap: 10px; }}
  .progress-bar {{ flex: 1; height: 6px; background: #eee; border-radius: 3px; overflow: hidden; }}
  .progress-fill {{ width: 0%; height: 100%; background: #000; transition: width 0.3s; }}
  select {{ padding: 8px; border-radius: 5px; border: 1px solid #ccc; }}

  .news-section {{ margin-bottom: 40px; }}
  .news-section h2 {{ font-family: 'Playfair Display', serif; border-bottom: 1px solid #000; margin-bottom: 15px; text-transform: uppercase; font-size: 1.2rem; }}
  .card {{ background: #fff; border: 1px solid #ddd; padding: 20px; margin-bottom: 15px; display: block; text-decoration: none; color: inherit; border-radius: 8px; transition: 0.2s; }}
  .card:hover {{ transform: translateY(-3px); box-shadow: 0 6px 12px rgba(0,0,0,0.1); }}
  .card-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 15px; }}
  .tag {{ font-weight: bold; font-size: 10px; background: #000; color: #fff; padding: 3px 8px; border-radius: 3px; }}
  .card-meta {{ font-size: 12px; color: #888; margin-left: 10px; }}
  .card-title {{ margin-top: 10px; font-family: 'Playfair Display', serif; font-size: 1.3rem; }}
  
  @media (max-width: 600px) {{ .card-grid {{ grid-template-columns: 1fr; }} .masthead h1 {{ font-size: 2rem; }} }}
</style>
</head>
<body>
<div class="container">
  <header class="masthead">
    <h1>Mi Briefing</h1>
    <p>{edition_es} — {date_display} — {now_et.strftime("%I:%M %p ET")}</p>
  </header>

  <div class="audio-bar">
    <button class="play-btn" onclick="toggleAudio()" id="btn-text"><span>▶</span> Reproducir Resumen</button>
    <div class="progress-bar"><div class="progress-fill" id="fill"></div></div>
    <select id="lang" onchange="stopAudio()">
      <option value="es">Español 🇪🇸</option>
      <option value="en">English 🇬🇧</option>
    </select>
  </div>

  <main>{sections_html}</main>

  <footer style="text-align: center; margin-top: 50px; color: #888; font-size: 12px;">
    <p>Actualizado automáticamente via GitHub Actions</p>
  </footer>
</div>

<script>
  let audio = new Audio();
  function toggleAudio() {{
    if (!audio.paused) {{ 
      stopAudio(); 
    }} else {{
      const lang = document.getElementById('lang').value;
      audio.src = lang === 'es' ? 'news_es.mp3' : 'news_en.mp3';
      audio.play().catch(e => alert("Error al reproducir: " + e));
      document.getElementById('btn-text').innerHTML = '<span>⏹</span> Detener';
      
      audio.ontimeupdate = () => {{
        const pct = (audio.currentTime / audio.duration * 100);
        document.getElementById('fill').style.width = pct + '%';
      }};
      audio.onended = stopAudio;
    }}
  }}

  function stopAudio() {{
    audio.pause(); 
    audio.currentTime = 0;
    document.getElementById('btn-text').innerHTML = '<span>▶</span> Reproducir Resumen';
    document.getElementById('fill').style.width = '0%';
  }}
</script>
</body>
</html>"""

# ── 8. GUARDAR EL HTML (ÚLTIMO PASO) ────────────────────────────────
with open("docs/index.html", "w", encoding="utf-8") as f:
    f.write(HTML)

print("¡Proceso finalizado con éxito! Archivos generados en /docs")
