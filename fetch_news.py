"""
Mi Briefing — fetch_news.py
Lee config.json, descarga RSS, deduplica con algoritmo mejorado,
traduce titulares al español y genera docs/index.html
"""

from portada import render, tipo
from seleccion import seleccionar
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
        if str(data.get("responseStatus")) == "200" and not data.get("quotaFinished") and t and t.lower() != text.lower():
            _translation_count += 1
            return t
    except Exception as e:
        print(f"  ⚠ Translation error: {e}")
    return text

# ── Deduplication ──────────────────────────────────────────────────────────
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
                    time_str = dt.strftime("%d/%m · %-I:%M %p ET")
                except Exception:
                    pass

            raw_articles.append({
                "title":        title,
                "title_es":     title_es,
                "link":         entry.get("link", "#"),
                "summary":      summary,
                "summary_es":   summary_es,
                "source":       feed_meta["nombre"],
                "medio":        feed_meta.get("medio", feed_meta["nombre"]),
                "idioma":       feed_meta["idioma"],
                "seccion":      sec,
                "time":         time_str,
                "pub_ts":       pub_ts,
                "prioridad":    feed_meta.get("prioridad", 5),
                "image":        extract_image(entry),
                "tipo":         tipo(entry.get("tags", [])),
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
if not raw_articles:
    raise RuntimeError("Ninguna fuente devolvió noticias. Se conserva la portada anterior.")
limites = {s: CFG["secciones"][s]["max_articulos"] for s in active_secs}
by_sec, total_merged = seleccionar(raw_articles, limites, DEDUP)

# ── Section order ──────────────────────────────────────────────────────────
SECTIONS_ORDER = sorted(
    [s for s in CFG["secciones"] if CFG["secciones"][s].get("activa", True)],
    key=lambda s: CFG["secciones"][s].get("orden", 99)
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
audio_data = json.dumps({"es": script_es, "en": script_en}).replace("<", r"<")

audio_controls = """<div class="audio-bar">
  <div class="audio-in">
    <div class="albl">Escuchar</div>
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
</div>"""
audio_script = f"""<script>
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
</script>"""
HTML = render(by_sec, SECTIONS_ORDER, CFG["site"], date_display, edition_es, time_display, audio_controls, audio_script)

os.makedirs("docs", exist_ok=True)
with open("docs/index.html", "w", encoding="utf-8") as f:
    f.write(HTML)

total_shown = sum(len(v) for v in by_sec.values())
print(f"\n✅  docs/index.html generado")
print(f"    Secciones: {len(by_sec)} | Artículos mostrados: {total_shown} | Duplicados eliminados: {total_merged}")
print(f"    Edición: {edition_es} · {time_display}")
