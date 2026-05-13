"""
Mundial 2026 — mundial.py
Genera docs/mundial/index.html
Pagina independiente dedicada al Mundial FIFA 2026
Se actualiza automaticamente cada manana con el workflow de GitHub Actions
"""

import feedparser
import json
import re
import os
from datetime import datetime, timezone, date
from urllib.request import urlopen, Request
from urllib.parse import quote
import pytz

ET     = pytz.timezone("America/New_York")
now_et = datetime.now(ET)

# ── Countdown ──────────────────────────────────────────────────────────────
KICKOFF = date(2026, 6, 11)   # Mexico vs Canada — primer partido
today   = now_et.date()
days_left = (KICKOFF - today).days

if days_left > 0:
    countdown_txt = str(days_left) + " dias para el pitazo inicial"
    countdown_sub = "Mexico vs Canada · 11 de junio, 2026 · Ciudad de Mexico"
elif days_left == 0:
    countdown_txt = "HOY EMPIEZA EL MUNDIAL"
    countdown_sub = "Mexico vs Canada · Ciudad de Mexico"
else:
    countdown_txt = "El Mundial esta en curso"
    countdown_sub = "FIFA World Cup 2026"

# ── Dates ──────────────────────────────────────────────────────────────────
MONTHS_ES = {
    "January":"enero","February":"febrero","March":"marzo","April":"abril",
    "May":"mayo","June":"junio","July":"julio","August":"agosto",
    "September":"septiembre","October":"octubre","November":"noviembre","December":"diciembre"
}
DAYS_ES = {
    "Monday":"Lunes","Tuesday":"Martes","Wednesday":"Miercoles","Thursday":"Jueves",
    "Friday":"Viernes","Saturday":"Sabado","Sunday":"Domingo"
}
date_es = now_et.strftime("%-d de %B de %Y")
for en, es in MONTHS_ES.items():
    date_es = date_es.replace(en, es)
day_name     = DAYS_ES.get(now_et.strftime("%A"), now_et.strftime("%A"))
date_full    = day_name + ", " + date_es
time_display = now_et.strftime("%-I:%M %p ET")
day_of_year  = now_et.timetuple().tm_yday

# ── Datos curiosos del Mundial (rotan cada dia) ────────────────────────────
DATOS = [
    {
        "titulo": "El estadio mas grande del torneo",
        "emoji": "🏟️",
        "texto": "El MetLife Stadium en Nueva Jersey tendra capacidad para 82,500 espectadores y sera sede de la gran final el 19 de julio de 2026. Es el estadio de la NFL con mayor capacidad en EE.UU. y estara techado especialmente para el evento.",
        "fuente": "FIFA"
    },
    {
        "titulo": "Ecuador en el Mundial por cuarta vez",
        "emoji": "🇪🇨",
        "texto": "La Tri clasifica a su cuarto Mundial consecutivo. En 2002 debuto, en 2006 llego a octavos de final —su mejor resultado— y en 2014 cayo en grupo. En 2022 gano el partido inaugural contra Qatar. Ahora busca superar los octavos de final por primera vez desde Alemania 2006.",
        "fuente": "Federacion Ecuatoriana de Futbol"
    },
    {
        "titulo": "Por primera vez, tres paises organizan el Mundial",
        "emoji": "🌎",
        "texto": "EE.UU., Canada y Mexico co-organizan el Mundial 2026, la primera vez en la historia que tres naciones comparten la sede. Se jugaran 104 partidos en 16 estadios — el torneo mas grande de la historia con 48 selecciones en vez de las 32 habituales.",
        "fuente": "FIFA"
    },
    {
        "titulo": "El balon oficial se llama Pulsivo",
        "emoji": "⚽",
        "texto": "Adidas presento 'Pulsivo', el balon oficial del Mundial 2026. Incorpora tecnologia de posicionamiento en tiempo real que transmite datos de velocidad, trayectoria y efecto a los sistemas de arbitraje. Es el balon mas tecnologico en la historia del torneo.",
        "fuente": "Adidas / FIFA"
    },
    {
        "titulo": "Argentina llega como campeona defensora",
        "emoji": "🇦🇷",
        "texto": "La Albiceleste de Lionel Messi defiendeee el titulo conquistado en Qatar 2022. Messi, con 38 anos, podria jugar su ultimo Mundial. Argentina ganaria el Mundial 1978, 1986 y 2022 — siempre en anos terminados en 6 o 2. Los datos historicos estan de su lado.",
        "fuente": "AFA"
    },
    {
        "titulo": "Brasil busca su sexta estrella",
        "emoji": "🇧🇷",
        "texto": "La Canarinha es el unico equipo con cinco titulos mundiales (1958, 1962, 1970, 1994, 2002) y el unico que ha participado en todos los Mundiales. Lleva 24 anos sin ganar el torneo — la sequa mas larga de su historia. 2026 es considerado el momento de la revancha.",
        "fuente": "CBF"
    },
    {
        "titulo": "El grupo de la muerte podria incluir a Ecuador",
        "emoji": "💀",
        "texto": "Con 48 equipos y grupos de 3, el formato cambia radicalmente. Solo el ultimo de cada grupo queda eliminado, lo que da mas chances a selecciones como Ecuador. La Tri podria clasificar a octavos incluso con un empate y una derrota si los resultados acompanan.",
        "fuente": "Analisis FIFA"
    },
    {
        "titulo": "Espana llega como bicampeon de Europa",
        "emoji": "🇪🇸",
        "texto": "La Roja gano la Eurocopa 2024 con una generacion liderada por Lamine Yamal, que tenia 16 anos en ese torneo. Para 2026 tendra 18 y sera uno de los jugadores mas seguidos del planeta. Espana no gana el Mundial desde 2010 en Sudafrica.",
        "fuente": "RFEF"
    },
    {
        "titulo": "Dallas tendra mas partidos que cualquier otra sede",
        "emoji": "🤠",
        "texto": "El AT&T Stadium en Dallas, Texas sera la sede con mas partidos del torneo: 9 en total, incluyendo un partido de cuartos de final. Texas es el estado con la comunidad latina mas grande de EE.UU., lo que garantiza un ambiente explosivo en cada partido.",
        "fuente": "FIFA"
    },
    {
        "titulo": "Francia, el otro gran favorito",
        "emoji": "🇫🇷",
        "texto": "Les Bleus llegaran con Kylian Mbappe como capitan y maximo referente. Francia gano el Mundial 2018 y fue finalista en 2022 —perdio en penales contra Argentina. Con una plantilla que mezcla experiencia y juventud, muchos la consideran la favorita numero uno junto a Brasil.",
        "fuente": "FFF"
    },
    {
        "titulo": "El arbitraje con semiautomatismo en offside",
        "emoji": "🤖",
        "texto": "El Mundial 2026 usara tecnologia semiautomatica de offside en todos los partidos — la misma que elimino controversias en Qatar 2022. Las decisiones de fuera de juego se tomaran en segundos en vez de minutos, cambiando la dinamica del juego por completo.",
        "fuente": "FIFA"
    },
    {
        "titulo": "Mexico, el pais con mas Mundiales como sede",
        "emoji": "🇲🇽",
        "texto": "Con 2026, Mexico se convierte en el primer pais en organizar tres Mundiales (1970, 1986 y ahora 2026). El Estadio Azteca en Ciudad de Mexico sera sede de partidos de grupo y es el unico estadio donde se jugaran Mundiales en tres ediciones diferentes.",
        "fuente": "FMF"
    },
]

dato_hoy = DATOS[day_of_year % len(DATOS)]

# ── Translation ────────────────────────────────────────────────────────────
_tc = 0
MAX_T = 200

def translate(text):
    global _tc
    if not text or _tc >= MAX_T:
        return text
    try:
        enc = quote(text[:400])
        url = "https://api.mymemory.translated.net/get?q=" + enc + "&langpair=en|es"
        req = Request(url, headers={"User-Agent":"Mozilla/5.0"})
        with urlopen(req, timeout=6) as r:
            data = json.loads(r.read().decode())
        t = data.get("responseData",{}).get("translatedText","")
        if t and t.lower() != text.lower():
            _tc += 1
            return t
    except:
        pass
    return text

# ── Deduplication ──────────────────────────────────────────────────────────
STOP = {
    'the','a','an','in','on','at','to','of','and','or','for','is','are',
    'was','were','has','have','had','be','been','as','by','its','this',
    'that','with','from','after','over','will','who','says','said','new',
    'el','la','los','las','de','en','un','una','y','o','que','se','su',
    'por','con','del','al','es','son','ha','le','lo','mas','no','si'
}

def kw(t):
    t = re.sub(r'[^\w\s]', ' ', t.lower())
    return set(w for w in t.split() if len(w) > 3 and w not in STOP)

def sim(a, b):
    sa, sb = kw(a), kw(b)
    if not sa or not sb:
        return 0
    j  = len(sa & sb) / len(sa | sb)
    ga = set(a.lower()[i:i+4] for i in range(max(0, len(a)-3)))
    gb = set(b.lower()[i:i+4] for i in range(max(0, len(b)-3)))
    n  = len(ga & gb) / max(len(ga | gb), 1)
    return j * 0.65 + n * 0.35

def dedup(articles, thr=0.42):
    groups, used = [], set()
    for i, a in enumerate(articles):
        if i in used:
            continue
        g = [a]
        for j, b in enumerate(articles):
            if j <= i or j in used:
                continue
            if sim(a['title'], b['title']) >= thr:
                g.append(b)
                used.add(j)
        used.add(i)
        groups.append(g)
    merged = []
    for g in groups:
        g.sort(key=lambda x: (-x.get('prio', 5), -x.get('ts', 0)))
        p = g[0].copy()
        if len(g) > 1:
            srcs = list(dict.fromkeys(s for x in g for s in x['source'].split(' · ')))
            p['source'] = ' · '.join(srcs[:3])
        merged.append(p)
    return merged

# ── FIFA/Mundial RSS feeds ─────────────────────────────────────────────────
MUNDIAL_FEEDS = [
    {"url":"https://feeds.bbci.co.uk/sport/football/rss.xml",      "src":"BBC Football", "lang":"en","prio":1},
    {"url":"https://www.theguardian.com/football/rss",              "src":"Guardian Ftbl","lang":"en","prio":1},
    {"url":"https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/section/deportes/portada",
                                                                    "src":"El Pais Dep.", "lang":"es","prio":1},
    {"url":"https://feeds.reuters.com/reuters/sportsNews",          "src":"Reuters Sport","lang":"en","prio":2},
    {"url":"https://www.eluniverso.com/arc/outboundfeeds/rss/category/deportes/?outputType=xml",
                                                                    "src":"El Universo",  "lang":"es","prio":1},
]

# Keywords para filtrar noticias del Mundial y selecciones
MUNDIAL_KW = [
    'mundial','world cup','fifa','2026','wc2026',
    'ecuador','tri ','la tri','seleccion ecuatoriana',
    'argentina','brasil','brazil','france','espana','spain',
    'messi','mbappe','vinicius','yamal',
    'group stage','fase de grupos','convocatoria','squad',
    'estadio','stadium','sede','host city',
]

def fetch_mundial_news(n=8):
    raw = []
    for f in MUNDIAL_FEEDS:
        try:
            feed = feedparser.parse(f["url"])
            for e in feed.entries[:8]:
                title = (e.get("title","") or "").strip()
                if not title:
                    continue
                # Filter: only Mundial-related
                title_lower = title.lower()
                summ_lower  = (getattr(e,'summary','') or '').lower()
                if not any(k in title_lower or k in summ_lower for k in MUNDIAL_KW):
                    continue
                summ = re.sub(r'<[^<]+?>','',getattr(e,'summary','') or '').strip()
                summ = summ[:220] + ('...' if len(summ)>220 else '')
                title_es = translate(title) if f['lang']=='en' else title
                pub  = getattr(e,'published_parsed',None)
                ts, tstr = 0, "—"
                if pub:
                    try:
                        dt   = datetime(*pub[:6],tzinfo=timezone.utc).astimezone(ET)
                        ts   = dt.timestamp()
                        tstr = dt.strftime("%-I:%M %p ET")
                    except:
                        pass
                raw.append({
                    "title":    title,
                    "title_es": title_es,
                    "summary":  summ,
                    "link":     e.get("link","#"),
                    "source":   f["src"],
                    "lang":     f["lang"],
                    "time":     tstr,
                    "ts":       ts,
                    "prio":     f["prio"],
                })
        except Exception as ex:
            print("  x " + f['src'] + ": " + str(ex))
    return dedup(raw)[:n]

print("Fetching Mundial 2026 news...")
noticias = fetch_mundial_news(8)

# Separate Ecuador news for featured spot
ecuador_kw = ['ecuador','tri ','la tri','seleccion ecuatoriana','moisés','caicedo','enner','valencia']
noticias_ecu   = [a for a in noticias if any(k in (a['title']+a['title_es']).lower() for k in ecuador_kw)]
noticias_resto = [a for a in noticias if a not in noticias_ecu]
print("  Total: " + str(len(noticias)) + " | Ecuador: " + str(len(noticias_ecu)) + " | Otros: " + str(len(noticias_resto)))

# ── HTML card builders ─────────────────────────────────────────────────────
def flag(lang):
    return "🇬🇧" if lang == "en" else "🇪🇸"

def hero_card(a, grad, tag, show_summary=True):
    parts = []
    parts.append('<div style="background:linear-gradient(135deg,' + grad + ');border-radius:12px;overflow:hidden;margin-bottom:8px;">')
    parts.append('<div style="padding:1.1rem 1.2rem .9rem;">')
    parts.append('<span style="display:inline-block;background:rgba(255,255,255,.18);color:#fff;font-size:9px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;padding:2px 10px;border-radius:20px;margin-bottom:8px;">' + tag + '</span><br>')
    parts.append('<a href="' + a['link'] + '" target="_blank" style="font-family:Georgia,serif;font-size:1.05rem;font-weight:700;color:#fff;text-decoration:none;line-height:1.35;display:block;margin-bottom:6px;">' + a['title_es'] + '</a>')
    if show_summary and a.get('summary'):
        parts.append('<p style="font-size:11.5px;color:rgba(255,255,255,.8);line-height:1.5;margin:0;">' + a['summary'][:180] + '</p>')
    parts.append('</div>')
    parts.append('<div style="background:rgba(0,0,0,.2);padding:.5rem 1.2rem;">')
    parts.append('<span style="font-size:10px;color:rgba(255,255,255,.6);">' + flag(a['lang']) + ' ' + a['source'] + ' · ' + a['time'] + '</span>')
    parts.append('</div>')
    parts.append('</div>')
    return "\n".join(parts)

def mini_card(a, accent):
    parts = []
    parts.append('<div style="display:flex;background:#fff;border-radius:8px;border:1px solid #e8e2d8;overflow:hidden;margin-bottom:6px;">')
    parts.append('<div style="width:4px;background:' + accent + ';flex-shrink:0;"></div>')
    parts.append('<div style="padding:.65rem .9rem;flex:1;">')
    parts.append('<a href="' + a['link'] + '" target="_blank" style="font-family:Georgia,serif;font-size:.9rem;font-weight:600;color:#1a1208;text-decoration:none;line-height:1.35;display:block;margin-bottom:3px;">' + a['title_es'] + '</a>')
    parts.append('<span style="font-size:10px;color:#a09688;">' + flag(a['lang']) + ' ' + a['source'] + ' · ' + a['time'] + '</span>')
    parts.append('</div>')
    parts.append('</div>')
    return "\n".join(parts)

def sec_hd(icon, label, color):
    parts = []
    parts.append('<div style="display:flex;align-items:center;gap:8px;padding:1rem 0 .5rem;">')
    parts.append('<span style="font-size:10px;font-weight:700;letter-spacing:2px;text-transform:uppercase;color:' + color + ';white-space:nowrap;">' + icon + ' ' + label + '</span>')
    parts.append('<div style="flex:1;height:1.5px;background:' + color + ';opacity:.25;"></div>')
    parts.append('</div>')
    return "\n".join(parts)

# ── Build content blocks ───────────────────────────────────────────────────

# Ecuador block
ecu_html = sec_hd("🇪🇨", "LA TRI EN EL MUNDIAL", "#065f46")
if noticias_ecu:
    ecu_html += hero_card(noticias_ecu[0], "#064e3b,#059669", "Ecuador")
    for a in noticias_ecu[1:3]:
        ecu_html += mini_card(a, "#059669")
else:
    ecu_html += '<p style="font-size:13px;color:#5c5248;padding:.5rem 0;">No hay noticias de La Tri en este momento. Vuelve pronto.</p>'

# World news block
world_html = sec_hd("🌍", "LO QUE PASA EN EL MUNDIAL", "#1e3a5f")
if noticias_resto:
    world_html += hero_card(noticias_resto[0], "#1e3a5f,#2563eb", "Mundial 2026")
    for a in noticias_resto[1:5]:
        world_html += mini_card(a, "#2563eb")
else:
    world_html += '<p style="font-size:13px;color:#5c5248;padding:.5rem 0;">Cargando noticias del Mundial...</p>'

# Dato del dia block
dato_html_parts = []
dato_html_parts.append(sec_hd("💡", "DATO DEL DIA", "#92400e"))
dato_html_parts.append('<div style="background:#fffbeb;border-radius:10px;border:1px solid #fde68a;padding:1rem 1.1rem;margin-bottom:8px;">')
dato_html_parts.append('<div style="display:flex;align-items:flex-start;gap:10px;">')
dato_html_parts.append('<span style="font-size:1.8rem;flex-shrink:0;">' + dato_hoy['emoji'] + '</span>')
dato_html_parts.append('<div>')
dato_html_parts.append('<div style="font-family:Georgia,serif;font-size:.95rem;font-weight:700;color:#78350f;margin-bottom:.4rem;">' + dato_hoy['titulo'] + '</div>')
dato_html_parts.append('<p style="font-size:.84rem;color:#92400e;line-height:1.6;margin:0 0 .4rem;">' + dato_hoy['texto'] + '</p>')
dato_html_parts.append('<span style="font-size:9px;color:#b45309;">Fuente: ' + dato_hoy['fuente'] + '</span>')
dato_html_parts.append('</div>')
dato_html_parts.append('</div>')
dato_html_parts.append('</div>')
dato_html = "\n".join(dato_html_parts)

# Teams to watch block
teams = [
    {"flag":"🇦🇷","name":"Argentina","desc":"Campeon defensor. Messi busca su ultima gloria.","color":"#1d4ed8"},
    {"flag":"🇧🇷","name":"Brasil",   "desc":"Cinco estrellas, 24 anos sin ganar. Hambre de revancha.","color":"#15803d"},
    {"flag":"🇫🇷","name":"Francia",  "desc":"Mbappe capitan. Finalista en Qatar 2022.","color":"#1d4ed8"},
    {"flag":"🇪🇸","name":"Espana",   "desc":"Bicampeon de Europa. Generacion Yamal.","color":"#dc2626"},
    {"flag":"🇪🇨","name":"Ecuador",  "desc":"La Tri busca superar octavos por primera vez desde 2006.","color":"#065f46"},
    {"flag":"🏴󠁧󠁢󠁥󠁮󠁧󠁿","name":"Inglaterra","desc":"Kane y la generacion que no quiere esperar mas.","color":"#1d4ed8"},
]

teams_html_parts = []
teams_html_parts.append(sec_hd("👀", "SELECCIONES A SEGUIR", "#374151"))
teams_html_parts.append('<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:8px;">')
for t in teams:
    teams_html_parts.append('<div style="background:#fff;border-radius:8px;border:1px solid #e8e2d8;padding:.75rem .9rem;">')
    teams_html_parts.append('<div style="font-size:1.3rem;margin-bottom:3px;">' + t['flag'] + ' <strong style="font-size:.85rem;color:#1a1208;">' + t['name'] + '</strong></div>')
    teams_html_parts.append('<p style="font-size:11px;color:#6b6560;line-height:1.4;margin:0;">' + t['desc'] + '</p>')
    teams_html_parts.append('</div>')
teams_html_parts.append('</div>')
teams_html = "\n".join(teams_html_parts)

# ── Write HTML ─────────────────────────────────────────────────────────────
os.makedirs("docs/mundial", exist_ok=True)

with open("docs/mundial/index.html", "w", encoding="utf-8") as f:
    w = f.write

    w("<!DOCTYPE html>\n")
    w("<html lang='es'>\n")
    w("<head>\n")
    w("<meta charset='UTF-8'>\n")
    w("<meta name='viewport' content='width=device-width,initial-scale=1'>\n")
    w("<meta name='theme-color' content='#0a1628'>\n")
    w("<meta property='og:title' content='Mundial 2026 - " + countdown_txt + "'>\n")
    w("<meta property='og:description' content='Todo sobre el FIFA World Cup 2026. Ecuador, favoritos, datos y noticias diarias.'>\n")
    w("<title>Mundial 2026 — " + countdown_txt + "</title>\n")
    w("<style>\n")
    w("*,*::before,*::after{box-sizing:border-box;margin:0;padding:0;}\n")
    w("body{font-family:Helvetica Neue,Arial,sans-serif;background:#f0ece4;-webkit-font-smoothing:antialiased;}\n")
    w("a{color:inherit;text-decoration:none;}\n")
    w("</style>\n")
    w("</head>\n")
    w("<body>\n")

    w("<div style='background:#f0ece4;padding:12px;min-height:100vh;'>\n")
    w("<div style='max-width:560px;margin:0 auto;'>\n")

    # ── Header
    w("<div style='background:linear-gradient(160deg,#0a1628,#1a3a5f);border-radius:12px 12px 0 0;padding:1.5rem 1.4rem 1.2rem;text-align:center;position:relative;overflow:hidden;'>\n")
    w("<p style='font-size:9px;letter-spacing:3px;text-transform:uppercase;color:rgba(255,255,255,.4);margin-bottom:.5rem;'>FIFA WORLD CUP</p>\n")
    w("<div style='font-size:2.8rem;margin-bottom:.3rem;'>🏆</div>\n")
    w("<h1 style='font-family:Georgia,serif;font-size:1.9rem;font-weight:700;color:#fff;letter-spacing:-0.5px;line-height:1;margin-bottom:.4rem;'>Mundial 2026</h1>\n")
    w("<p style='font-size:11px;color:rgba(255,255,255,.55);margin-bottom:1rem;'>EE.UU. · Canada · Mexico</p>\n")
    # Countdown badge
    w("<div style='background:rgba(255,255,255,.1);border:1px solid rgba(255,255,255,.2);border-radius:10px;padding:.75rem 1rem;display:inline-block;'>\n")
    w("<div style='font-family:Georgia,serif;font-size:2rem;font-weight:700;color:#fbbf24;line-height:1;'>" + str(days_left) + "</div>\n")
    w("<div style='font-size:10px;color:rgba(255,255,255,.6);margin-top:2px;'>" + countdown_txt.replace(str(days_left) + " dias para el pitazo inicial","dias para el pitazo inicial") + "</div>\n")
    w("<div style='font-size:9px;color:rgba(255,255,255,.35);margin-top:3px;'>" + countdown_sub + "</div>\n")
    w("</div>\n")
    w("</div>\n")

    # ── Updated bar
    w("<div style='background:#fdf8f0;border:1px solid #e8e2d8;border-top:none;padding:.6rem 1.2rem;text-align:center;'>\n")
    w("<span style='font-size:10px;color:#a09688;'>Actualizado " + date_full + " · " + time_display + "</span>\n")
    w("<span style='margin:0 8px;color:#e8e2d8;'>|</span>\n")
    w("<a href='https://leoya06.github.io/mi-briefing/newsletter/latest.html' style='font-size:10px;color:#2563eb;'>Ver Al Dia newsletter</a>\n")
    w("</div>\n")

    # ── Body
    w("<div style='background:#f5f1eb;border:1px solid #e8e2d8;border-top:none;padding:.6rem 1.2rem 1rem;'>\n")
    w(ecu_html + "\n")
    w(dato_html + "\n")
    w(world_html + "\n")
    w(teams_html + "\n")
    w("</div>\n")

    # ── Share CTA
    w("<div style='background:linear-gradient(135deg,#1a3a5f,#2563eb);padding:.85rem 1.2rem;text-align:center;'>\n")
    w("<p style='font-size:12px;font-weight:600;color:#fff;margin:0;'>Comparte con los aficionados del futbol 📲⚽</p>\n")
    w("</div>\n")

    # ── Footer
    w("<div style='background:#0a1628;border-radius:0 0 12px 12px;padding:1rem 1.4rem;text-align:center;'>\n")
    w("<p style='font-size:12px;color:rgba(255,255,255,.5);margin-bottom:4px;'>Hecho con ❤️ · <strong style='color:#fbbf24;'>Mundial 2026</strong></p>\n")
    w("<p style='font-size:10px;color:rgba(255,255,255,.3);margin-bottom:6px;'>BBC · The Guardian · El Pais · El Universo · Reuters</p>\n")
    w("<a href='https://leoya06.github.io/mi-briefing/' style='font-size:11px;color:#60a5fa;'>Ver Mi Briefing completo</a>\n")
    w("</div>\n")

    w("</div>\n")
    w("</div>\n")
    w("</body>\n")
    w("</html>\n")

print("OK: docs/mundial/index.html")
print("Countdown: " + countdown_txt)
print("Dato del dia: " + dato_hoy['titulo'])
print("Noticias: " + str(len(noticias)))
print("Traducciones: " + str(_tc))
