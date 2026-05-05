"""
Al Día — newsletter_generator.py
Genera HTML con datos de mercado en tiempo real vía Yahoo Finance (JS)
Comparte el link en WhatsApp — los datos se cargan al abrir la página
"""

import feedparser, json, re, os
from datetime import datetime, timezone
from urllib.request import urlopen, Request
from urllib.parse import quote
import pytz

ET     = pytz.timezone("America/New_York")
now_et = datetime.now(ET)

# ── Dates ──────────────────────────────────────────────────────────────────
MONTHS_ES = {"January":"enero","February":"febrero","March":"marzo","April":"abril",
    "May":"mayo","June":"junio","July":"julio","August":"agosto",
    "September":"septiembre","October":"octubre","November":"noviembre","December":"diciembre"}
DAYS_ES = {"Monday":"Lunes","Tuesday":"Martes","Wednesday":"Miércoles","Thursday":"Jueves",
    "Friday":"Viernes","Saturday":"Sábado","Sunday":"Domingo"}

date_es = now_et.strftime("%-d de %B de %Y")
for en, es in MONTHS_ES.items():
    date_es = date_es.replace(en, es)
day_name    = DAYS_ES.get(now_et.strftime("%A"), now_et.strftime("%A"))
date_full   = f"{day_name}, {date_es}"
day_of_year = now_et.timetuple().tm_yday
time_display = now_et.strftime("%-I:%M %p ET")

# ── Greeting ───────────────────────────────────────────────────────────────
GREETINGS = [
    "¡Feliz lunes! Semana nueva, noticias frescas. Aquí va tu resumen para arrancar con todo 💪",
    "Martes de información. Porque estar al día es el mejor hábito que puedes tener ☕",
    "Mitad de semana, mitad del mundo cubierto. Empecemos con lo más importante de hoy 🌍",
    "Jueves — ya casi viernes. Mientras tanto, esto es lo que no te puedes perder hoy 📰",
    "¡Viernes! Antes de desconectarte, tómate 3 minutos para saber qué pasó esta semana 🎉",
    "Fin de semana, pero el mundo no para. Aquí el resumen de lo importante este sábado 🌅",
    "Domingo de lectura. El mejor momento para ponerte al día antes de que empiece la semana ☀️",
]
greeting = GREETINGS[now_et.weekday()]

# ── Historias del día ──────────────────────────────────────────────────────
HISTORIAS = [
    {"titulo":"La historia del Día del Trabajo","emoji":"✊",
     "texto":"El 1 de mayo de 1886, miles de trabajadores en Chicago salieron a las calles exigiendo una jornada laboral de 8 horas — en esa época, 12 o 14 horas diarias era la norma. Lo que empezó como huelga terminó en tragedia cuando una bomba estalló en la plaza Haymarket. Cuatro activistas fueron ejecutados. Décadas después, el mundo adoptó el 1 de mayo como Día Internacional del Trabajo en su memoria.",
     "dato":"EE.UU. y Canadá celebran su Labor Day en septiembre — justamente para diferenciarse de las raíces socialistas del 1 de mayo."},
    {"titulo":"El día que pisamos la Luna","emoji":"🌕",
     "texto":"El 20 de julio de 1969, Neil Armstrong bajó del módulo lunar Eagle y dijo una de las frases más famosas de la historia. Cerca de 600 millones de personas lo vieron en vivo. La misión Apollo 11 fue el resultado de una carrera espacial de una década entre EE.UU. y la URSS, iniciada cuando los soviéticos lanzaron el Sputnik en 1957.",
     "dato":"Los astronautas dejaron en la Luna una placa que dice: 'Vinimos en paz de parte de toda la humanidad.'"},
    {"titulo":"La caída del Muro de Berlín","emoji":"🧱",
     "texto":"El 9 de noviembre de 1989, un portavoz del gobierno de Alemania Oriental anunció por error que los ciudadanos podían cruzar la frontera 'de inmediato'. Miles corrieron al muro. Los guardias, sin órdenes claras, abrieron los checkpoints. Esa noche la gente empezó a derribarlo con martillos. El símbolo de la Guerra Fría cayó sin una sola bala.",
     "dato":"El Muro de Berlín tenía 155 km de longitud y estuvo en pie 28 años, 2 meses y 27 días."},
    {"titulo":"El nacimiento de los Estados Unidos","emoji":"🦅",
     "texto":"El 4 de julio de 1776, el Congreso Continental adoptó la Declaración de Independencia, redactada principalmente por Thomas Jefferson. Las 13 colonias americanas se separaban oficialmente de Gran Bretaña. Pocos saben que la declaración fue aprobada el 2 de julio — el 4 fue cuando se terminó de imprimir y distribuir.",
     "dato":"John Adams y Thomas Jefferson murieron el mismo día: el 4 de julio de 1826, exactamente 50 años después de la Declaración."},
    {"titulo":"El día que Mandela salió libre","emoji":"🕊️",
     "texto":"El 11 de febrero de 1990, después de 27 años en prisión, Nelson Mandela caminó libre por las puertas de la cárcel Victor Verster en Sudáfrica. El mundo entero lo esperaba. Cuatro años después se convirtió en el primer presidente negro de Sudáfrica, elegido en las primeras elecciones democráticas del país.",
     "dato":"Mandela pasó 18 de sus 27 años de prisión en la isla Robben, en una celda de apenas 2x2 metros."},
    {"titulo":"El Titanic y la noche más larga","emoji":"🚢",
     "texto":"En la madrugada del 15 de abril de 1912, el RMS Titanic se hundió en el Atlántico Norte tras chocar con un iceberg. De 2,224 personas a bordo, solo 710 sobrevivieron. El barco era considerado insumergible, pero llevaba botes salvavidas para menos de la mitad de los pasajeros. La tragedia cambió para siempre las regulaciones marítimas.",
     "dato":"El barco Carpathia respondió al SOS y navegó 93 km a toda velocidad para rescatar a los sobrevivientes."},
    {"titulo":"Yuri Gagarin y el primer viaje al espacio","emoji":"🚀",
     "texto":"El 12 de abril de 1961, Yuri Gagarin se convirtió en el primer ser humano en viajar al espacio. Su vuelo duró 108 minutos orbitando la Tierra. La hazaña soviética sacudió a EE.UU. y aceleró el programa espacial que llevaría al hombre a la Luna ocho años después.",
     "dato":"Gagarin murió en 1968 en un accidente de entrenamiento, a los 34 años, sin llegar a ver el alunizaje que su vuelo inspiró."},
    {"titulo":"El discurso que cambió América","emoji":"✊",
     "texto":"El 28 de agosto de 1963, Martin Luther King Jr. se paró frente a 250,000 personas en Washington D.C. y pronunció 'I Have a Dream'. Gran parte fue improvisado. Sus palabras sobre igualdad racial se convirtieron en uno de los momentos más poderosos del movimiento por los derechos civiles en EE.UU.",
     "dato":"King tenía solo 34 años cuando dio ese discurso. Cinco años después fue asesinado en Memphis."},
    {"titulo":"Einstein y la fórmula que cambió el mundo","emoji":"🧠",
     "texto":"El 14 de marzo de 1879 nació Albert Einstein. De niño sus profesores lo creían lento. A los 26 años, trabajando como empleado en una oficina de patentes, publicó cuatro artículos que revolucionaron la física — incluyendo E=mc², que demostró que la materia y la energía son la misma cosa.",
     "dato":"Einstein ganó el Nobel en 1921, pero no por la relatividad — sino por su explicación del efecto fotoeléctrico."},
    {"titulo":"El origen del Año Nuevo","emoji":"🎆",
     "texto":"Celebrar el inicio del año es una tradición de más de 4,000 años. Los primeros fueron los babilonios, que festejaban el equinoccio de primavera con 11 días de fiesta. Fueron los romanos quienes movieron la celebración al 1 de enero, en honor a Jano, el dios de los comienzos — de ahí viene 'January' en inglés.",
     "dato":"En Japón, el Año Nuevo (Oshōgatsu) es la festividad más importante del año, con 3 días de celebración oficial."},
    {"titulo":"Cristóbal Colón y el encuentro de dos mundos","emoji":"⛵",
     "texto":"El 12 de octubre de 1492, Rodrigo de Triana gritó '¡Tierra!' desde la carabela Pinta. Colón pensó que había llegado a Asia. En realidad, había pisado el Caribe. Ese momento conectó dos mundos que no sabían que existían el uno al otro, cambiando la historia de la humanidad para siempre.",
     "dato":"Colón murió en 1506 creyendo que había llegado a Asia — nunca supo que había 'descubierto' un continente nuevo."},
    {"titulo":"Hiroshima y el inicio de la era nuclear","emoji":"☁️",
     "texto":"El 6 de agosto de 1945, el bombardero Enola Gay lanzó sobre Hiroshima la primera bomba atómica usada en combate. En segundos murieron 80,000 personas. Japón se rindió el 15 de agosto, terminando la Segunda Guerra Mundial — pero comenzando la era nuclear que definiría la política global por décadas.",
     "dato":"Un árbol ginkgo biloba plantado a 1 km del epicentro sobrevivió la explosión. Hoy sigue vivo y se lo llama 'el árbol superviviente'."},
]

historia = HISTORIAS[day_of_year % len(HISTORIAS)]

# ── Translation ────────────────────────────────────────────────────────────
_tc = 0
MAX_T = 300

def translate(text):
    global _tc
    if not text or _tc >= MAX_T: return text
    try:
        enc = quote(text[:400])
        url = f"https://api.mymemory.translated.net/get?q={enc}&langpair=en|es"
        req = Request(url, headers={"User-Agent":"Mozilla/5.0"})
        with urlopen(req, timeout=6) as r:
            data = json.loads(r.read().decode())
        t = data.get("responseData",{}).get("translatedText","")
        if t and t.lower() != text.lower():
            _tc += 1; return t
    except: pass
    return text

# ── Deduplication ──────────────────────────────────────────────────────────
STOP = {'the','a','an','in','on','at','to','of','and','or','for','is','are',
        'was','were','has','have','had','be','been','as','by','its','this',
        'that','with','from','after','over','will','who','says','said','new',
        'el','la','los','las','de','en','un','una','y','o','que','se','su',
        'por','con','del','al','es','son','ha','le','lo','más','no','si'}

def kw(t):
    t = re.sub(r'[^\w\s]',' ',t.lower())
    return set(w for w in t.split() if len(w)>3 and w not in STOP)

def sim(a,b):
    sa,sb = kw(a),kw(b)
    if not sa or not sb: return 0
    j = len(sa&sb)/len(sa|sb)
    ga = set(a.lower()[i:i+4] for i in range(max(0,len(a)-3)))
    gb = set(b.lower()[i:i+4] for i in range(max(0,len(b)-3)))
    n  = len(ga&gb)/max(len(ga|gb),1)
    return j*0.65 + n*0.35

def dedup(articles, thr=0.42):
    groups, used = [], set()
    for i,a in enumerate(articles):
        if i in used: continue
        g = [a]
        for j,b in enumerate(articles):
            if j<=i or j in used: continue
            if sim(a['title'],b['title']) >= thr:
                g.append(b); used.add(j)
        used.add(i); groups.append(g)
    merged = []
    for g in groups:
        g.sort(key=lambda x:(-x.get('prio',5),-x.get('ts',0)))
        p = g[0].copy()
        if len(g)>1:
            srcs = list(dict.fromkeys(s for x in g for s in x['source'].split(' · ')))
            p['source'] = ' · '.join(srcs[:3])
        merged.append(p)
    return merged

# ── Feeds ──────────────────────────────────────────────────────────────────
FEEDS = {
    "int": [
        {"url":"https://feeds.bbci.co.uk/news/world/rss.xml",       "src":"BBC",         "lang":"en","prio":1},
        {"url":"https://feeds.reuters.com/reuters/worldNews",        "src":"Reuters",     "lang":"en","prio":1},
        {"url":"https://www.theguardian.com/world/rss",              "src":"The Guardian","lang":"en","prio":2},
        {"url":"https://rss.dw.com/rdf/rss-es-world",                "src":"DW Español",  "lang":"es","prio":1},
        {"url":"https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/section/internacional/portada",
                                                                     "src":"El País",     "lang":"es","prio":1},
    ],
    "ecu": [
        {"url":"https://www.eluniverso.com/arc/outboundfeeds/rss/?outputType=xml",
                                                                     "src":"El Universo", "lang":"es","prio":1},
        {"url":"https://rss.dw.com/rdf/rss-es-world",                "src":"DW Español",  "lang":"es","prio":2},
    ],
    "dep": [
        {"url":"https://feeds.bbci.co.uk/sport/rss.xml",             "src":"BBC Sport",   "lang":"en","prio":1},
        {"url":"https://www.theguardian.com/sport/rss",              "src":"Guardian Sp.","lang":"en","prio":2},
        {"url":"https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/section/deportes/portada",
                                                                     "src":"El País Dep.","lang":"es","prio":1},
        {"url":"https://www.eluniverso.com/arc/outboundfeeds/rss/category/deportes/?outputType=xml",
                                                                     "src":"El Universo D.","lang":"es","prio":1},
    ],
}

MUNDIAL_KW = ['mundial','world cup','fifa','2026','copa del mundo',
              'selección','qualifier','clasificatori','wc2026']

def fetch(feeds, n=5):
    raw = []
    for f in feeds:
        try:
            feed = feedparser.parse(f["url"])
            for e in feed.entries[:6]:
                title = (e.get("title","") or "").strip()
                if not title: continue
                summ = re.sub(r'<[^<]+?>','',getattr(e,'summary','') or '').strip()
                summ = summ[:200]+('...' if len(summ)>200 else '')
                title_es = translate(title) if f['lang']=='en' else title
                pub = getattr(e,'published_parsed',None)
                ts,tstr = 0,"—"
                if pub:
                    try:
                        dt = datetime(*pub[:6],tzinfo=timezone.utc).astimezone(ET)
                        ts = dt.timestamp()
                        tstr = dt.strftime("%-I:%M %p ET")
                    except: pass
                raw.append({"title":title,"title_es":title_es,
                            "link":e.get("link","#"),"summary":summ,
                            "source":f["src"],"lang":f["lang"],
                            "time":tstr,"ts":ts,"prio":f["prio"]})
        except Exception as ex:
            print(f"  ✗ {f['src']}: {ex}")
    return dedup(raw)[:n]

print("📡 Fetching feeds...")
ni = fetch(FEEDS["int"], 4)[:3]
ne = fetch(FEEDS["ecu"], 5)[:3]
nd_all = fetch(FEEDS["dep"], 10)
mundial = [a for a in nd_all if any(k in (a['title']+a['title_es']).lower() for k in MUNDIAL_KW)]
otros   = [a for a in nd_all if a not in mundial]
nd = (mundial + otros)[:3]
print(f"✓ Int:{len(ni)} Ecu:{len(ne)} Dep:{len(nd)} (Mundial:{len(mundial)})")

# ── Card builders ──────────────────────────────────────────────────────────
def flag(lang): return "🇬🇧" if lang=="en" else "🇪🇸"

def top_card(a, grad, tag):
    return f"""
      <div style="background:linear-gradient(135deg,{grad});border-radius:10px;overflow:hidden;margin-bottom:6px;">
        <div style="padding:1rem 1.1rem .85rem;">
          <span style="display:inline-block;background:rgba(255,255,255,.18);color:#fff;font-size:9px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;padding:2px 9px;border-radius:20px;margin-bottom:7px;">{tag}</span><br>
          <a href="{a['link']}" target="_blank" style="font-family:Georgia,serif;font-size:1rem;font-weight:700;color:#fff;text-decoration:none;line-height:1.35;">{a['title_es']}</a>
        </div>
        <div style="background:rgba(0,0,0,.15);padding:.5rem 1.1rem;">
          <span style="font-size:10px;color:rgba(255,255,255,.7);">{flag(a['lang'])} {a['source']} · {a['time']}</span>
        </div>
      </div>"""

def mini_card(a, color):
    return f"""
      <div style="display:flex;background:#fff;border-radius:8px;border:1px solid #e8e2d8;overflow:hidden;margin-bottom:6px;">
        <div style="width:4px;background:{color};flex-shrink:0;"></div>
        <div style="padding:.6rem .9rem;flex:1;">
          <a href="{a['link']}" target="_blank" style="font-family:Georgia,serif;font-size:.9rem;font-weight:600;color:#1a1208;text-decoration:none;line-height:1.35;display:block;margin-bottom:3px;">{a['title_es']}</a>
          <span style="font-size:10px;color:#a09688;">{flag(a['lang'])} {a['source']} · {a['time']}</span>
        </div>
      </div>"""

def sec_header(icon, label, color):
    return f"""
      <div style="display:flex;align-items:center;gap:8px;padding:1.1rem 0 .55rem;">
        <span style="font-size:10px;font-weight:700;letter-spacing:2px;text-transform:uppercase;color:{color};white-space:nowrap;">{icon} {label}</span>
        <div style="flex:1;height:1.5px;background:{color};opacity:.25;"></div>
      </div>"""

# Build sections
s_int  = sec_header("🌍","NOTICIAS INTERNACIONALES","#1e3a5f")
s_int += top_card(ni[0],"#1e3a5f,#1e4a8f","Internacional") if ni else ""
for a in ni[1:]: s_int += mini_card(a,"#2563eb")

s_ecu  = sec_header("🇪🇨","ECUADOR HOY","#065f46")
s_ecu += top_card(ne[0],"#065f46,#059669","Ecuador") if ne else ""
for a in ne[1:]: s_ecu += mini_card(a,"#059669")

s_dep  = sec_header("⚽","DEPORTES · CAMINO AL MUNDIAL 2026","#7c2d12")
s_dep += top_card(nd[0],"#7c2d12,#b45309","⚽ Deportes") if nd else ""
for a in nd[1:]: s_dep += mini_card(a,"#ea580c")

s_hist = f"""
      {sec_header("📖","HISTORIA DEL DÍA","#92400e")}
      <div style="background:#fffbeb;border-radius:10px;border:1px solid #fde68a;padding:1.1rem 1.2rem;margin-bottom:8px;">
        <div style="font-size:2rem;text-align:center;margin-bottom:.6rem;">{historia['emoji']}</div>
        <div style="font-family:Georgia,serif;font-size:.98rem;font-weight:700;color:#78350f;text-align:center;margin-bottom:.6rem;">{historia['titulo']}</div>
        <p style="font-size:.84rem;color:#92400e;line-height:1.65;margin:0 0 .7rem;">{historia['texto']}</p>
        <div style="background:#fef3c7;border-radius:6px;padding:.55rem .9rem;border-left:3px solid #f59e0b;">
          <span style="font-size:.8rem;color:#78350f;"><strong>💡 Dato:</strong> {historia['dato']}</span>
        </div>
      </div>"""

# ── Market tickers (symbols for Yahoo Finance) ─────────────────────────────
# Loaded via JS when user opens the page — no API key needed
TICKERS = [
    {"sym":"^GSPC",  "label":"S&P 500",   "id":"sp500"},
    {"sym":"^IXIC",  "label":"Nasdaq",     "id":"nasdaq"},
    {"sym":"EURUSD=X","label":"EUR/USD",   "id":"eurusd"},
    {"sym":"BTC-USD","label":"Bitcoin",    "id":"bitcoin"},
    {"sym":"GC=F",   "label":"Oro",        "id":"gold"},
    {"sym":"CL=F",   "label":"Petróleo",   "id":"oil"},
]

tickers_js_symbols = json.dumps([t["sym"] for t in TICKERS])
tickers_html = ""
for t in TICKERS:
    tickers_html += f"""
        <div style="text-align:center;padding:0 4px;">
          <div style="font-size:8px;letter-spacing:.5px;text-transform:uppercase;color:rgba(255,255,255,.4);margin-bottom:2px;">{t['label']}</div>
          <div id="v-{t['id']}" style="font-size:12px;font-weight:600;color:#f5e6c8;">...</div>
          <div id="c-{t['id']}" style="font-size:10px;color:rgba(255,255,255,.5);">—</div>
        </div>"""

market_js = f"""
<script>
(async function() {{
  const symbols = {tickers_js_symbols};
  const ids = {json.dumps([t['id'] for t in TICKERS])};
  const labels = {json.dumps([t['label'] for t in TICKERS])};

  // Use allorigins proxy to bypass CORS on Yahoo Finance
  const joined = symbols.join('%2C');
  const url = `https://query1.finance.yahoo.com/v8/finance/spark?symbols=${{joined}}&range=1d&interval=1d`;
  const proxy = `https://api.allorigins.win/get?url=${{encodeURIComponent(url)}}`;

  try {{
    const res = await fetch(proxy, {{signal: AbortSignal.timeout(8000)}});
    const outer = await res.json();
    const data = JSON.parse(outer.contents);
    const spark = data?.spark?.result || [];

    spark.forEach((r, i) => {{
      const sym = r?.symbol;
      const idx = symbols.indexOf(sym);
      if (idx === -1) return;
      const id = ids[idx];
      const closes = r?.response?.[0]?.indicators?.quote?.[0]?.close || [];
      if (closes.length < 2) return;

      const last  = closes[closes.length - 1];
      const prev  = closes[closes.length - 2];
      const chg   = ((last - prev) / prev * 100);
      const up    = chg >= 0;

      // Format value
      let val;
      if (id === 'eurusd')       val = last.toFixed(4);
      else if (id === 'bitcoin') val = '$' + Math.round(last).toLocaleString();
      else if (id === 'gold' || id === 'oil') val = '$' + last.toFixed(1);
      else val = last.toLocaleString(undefined, {{minimumFractionDigits:0,maximumFractionDigits:0}});

      const vEl = document.getElementById('v-' + id);
      const cEl = document.getElementById('c-' + id);
      if (vEl) vEl.textContent = val;
      if (cEl) {{
        cEl.textContent = (up ? '▲ +' : '▼ ') + Math.abs(chg).toFixed(2) + '%';
        cEl.style.color = up ? '#4ade80' : '#f87171';
      }}
    }});
  }} catch(e) {{
    // Silently fail — markets section shows dashes
    console.log('Market data unavailable:', e.message);
  }}
}})();
</script>"""

preheader = ni[0]['title_es'] if ni else "Tu resumen de hoy está listo."

# ── Full HTML ──────────────────────────────────────────────────────────────
HTML = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="theme-color" content="#1a1208">
<meta property="og:title" content="Al Día — {date_full}">
<meta property="og:description" content="Tu resumen: Internacional · Ecuador · Deportes · Historia del día">
<title>Al Día — {date_full}</title>
<style>
  * {{ box-sizing:border-box; margin:0; padding:0; }}
  body {{ background:#f0ece4; font-family:'Helvetica Neue',Arial,sans-serif; }}
  a {{ color:inherit; }}
  @media(max-width:600px) {{
    .email-wrap {{ padding: 8px !important; }}
    .card-grid {{ grid-template-columns:1fr 1fr !important; }}
  }}
</style>
</head>
<body>

<!-- Hidden preheader for email clients -->
<div style="display:none;max-height:0;overflow:hidden;font-size:1px;color:#f0ece4;">
{preheader} · Al Día Newsletter
&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;
</div>

<div class="email-wrap" style="background:#f0ece4;padding:16px;min-height:100vh;">
<div style="max-width:560px;margin:0 auto;">

  <!-- ── HEADER ── -->
  <div style="background:#1a1208;border-radius:12px 12px 0 0;padding:1.5rem 1.4rem 1.2rem;text-align:center;">
    <p style="font-size:9px;letter-spacing:3px;text-transform:uppercase;color:rgba(255,255,255,.4);margin-bottom:.4rem;">
      Tu resumen diario · {date_full}
    </p>
    <h1 style="font-family:Georgia,serif;font-size:2.2rem;font-weight:700;color:#f5e6c8;letter-spacing:-1px;line-height:1;margin-bottom:.3rem;">
      Al Día
    </h1>
    <p style="font-size:11px;color:rgba(255,255,255,.5);margin-bottom:.75rem;">
      Mantente informado con lo que importa hoy
    </p>
    <span style="display:inline-block;background:rgba(255,255,255,.1);border:1px solid rgba(255,255,255,.15);color:rgba(255,255,255,.75);font-size:10px;font-weight:600;padding:4px 14px;border-radius:20px;">
      📅 {date_full} &nbsp;·&nbsp; ⏱ 3 min de lectura
    </span>
  </div>

  <!-- ── GREETING ── -->
  <div style="background:#fdf8f0;border:1px solid #e8e2d8;border-top:none;padding:1rem 1.4rem;">
    <p style="font-size:13.5px;color:#5c5248;line-height:1.65;">{greeting}</p>
  </div>

  <!-- ── BODY ── -->
  <div style="background:#f5f1eb;border:1px solid #e8e2d8;border-top:none;padding:.6rem 1.2rem 1rem;">
    {s_int}
    {s_ecu}
    {s_dep}
    {s_hist}
  </div>

  <!-- ── MARKETS ── -->
  <div style="background:#1a1208;padding:.9rem 1rem;">
    <div style="font-size:9px;letter-spacing:2px;text-transform:uppercase;color:rgba(255,255,255,.4);text-align:center;margin-bottom:.6rem;">
      📊 MERCADOS · datos en tiempo real
    </div>
    <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:8px;" class="card-grid">
      {tickers_html}
    </div>
    <div style="font-size:9px;color:rgba(255,255,255,.25);text-align:center;margin-top:.5rem;">
      Fuente: Yahoo Finance · Actualizado al abrir
    </div>
  </div>

  <!-- ── WHATSAPP CTA ── -->
  <div style="background:#25D366;padding:.7rem 1.2rem;text-align:center;">
    <p style="font-size:12px;font-weight:600;color:#fff;margin:0;">
      📲 ¿Te gustó? Comparte <strong>Al Día</strong> con tu familia y amigos
    </p>
  </div>

  <!-- ── FOOTER ── -->
  <div style="background:#fff;border-radius:0 0 12px 12px;border:1px solid #e8e2d8;border-top:none;padding:1rem 1.4rem;text-align:center;">
    <p style="font-size:12px;color:#5c5248;margin-bottom:4px;">
      Hecho con ☕ · <strong style="color:#1a1208;">Al Día</strong> · Actualizado {time_display}
    </p>
    <p style="font-size:10px;color:#a09688;margin-bottom:6px;">
      BBC · Reuters · The Guardian · El País · El Universo · DW Español
    </p>
    <a href="../index.html" style="font-size:11px;color:#2563eb;text-decoration:none;">
      Ver Mi Briefing completo →
    </a>
  </div>

</div>
</div>

{market_js}
</body>
</html>"""

os.makedirs("docs/newsletter", exist_ok=True)
fname = f"docs/newsletter/al-dia-{now_et.strftime('%Y-%m-%d')}.html"
with open(fname, "w", encoding="utf-8") as f:
    f.write(HTML)
with open("docs/newsletter/latest.html", "w", encoding="utf-8") as f:
    f.write(HTML)

print(f"\n✅  {fname}")
print(f"    Historia: {historia['titulo']}")
print(f"    Traducciones: {_tc}")
