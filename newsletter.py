import feedparser
import json
import re
import os
from datetime import datetime, timezone
from urllib.request import urlopen, Request
from urllib.parse import quote
import pytz

ET = pytz.timezone("America/New_York")
now_et = datetime.now(ET)

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
day_of_year  = now_et.timetuple().tm_yday
time_display = now_et.strftime("%-I:%M %p ET")

# ── Greetings ──────────────────────────────────────────────────────────────
GREETINGS = [
    "Feliz lunes! Semana nueva, noticias frescas. Aqui va tu resumen para arrancar con todo 💪",
    "Martes de informacion. Porque estar al dia es el mejor habito que puedes tener ☕",
    "Mitad de semana, mitad del mundo cubierto. Lo mas importante de hoy 🌍",
    "Jueves, ya casi viernes. Esto es lo que no te puedes perder hoy 📰",
    "Viernes! Tomaté 3 minutos para saber que paso esta semana 🎉",
    "Fin de semana, pero el mundo no para. Lo importante de este sabado 🌅",
    "Domingo de lectura. Pontete al dia antes de que empiece la semana ☀️",
]
greeting = GREETINGS[now_et.weekday()]

# ── Historias ──────────────────────────────────────────────────────────────
HISTORIAS = [
    {
        "titulo": "La historia del Dia del Trabajo",
        "emoji": "✊",
        "texto": "El 1 de mayo de 1886, miles de trabajadores en Chicago exigieron una jornada de 8 horas. Lo que empezo como huelga termino en tragedia cuando una bomba estallo en la plaza Haymarket. Cuatro activistas fueron ejecutados. Decadas despues, el mundo adopto el 1 de mayo como Dia Internacional del Trabajo.",
        "dato": "EE.UU. y Canada celebran su Labor Day en septiembre, para diferenciarse de las raices socialistas del 1 de mayo."
    },
    {
        "titulo": "El dia que pisamos la Luna",
        "emoji": "🌕",
        "texto": "El 20 de julio de 1969, Neil Armstrong bajo del modulo lunar Eagle. Cerca de 600 millones de personas lo vieron en vivo. La mision Apollo 11 fue el resultado de una carrera espacial de una decada entre EE.UU. y la Union Sovietica.",
        "dato": "Los astronautas dejaron en la Luna una placa: Vinimos en paz de parte de toda la humanidad."
    },
    {
        "titulo": "La caida del Muro de Berlin",
        "emoji": "🧱",
        "texto": "El 9 de noviembre de 1989, un portavoz del gobierno de Alemania Oriental anuncio por error que los ciudadanos podian cruzar la frontera de inmediato. Miles corrieron al muro. Los guardias abrieron los checkpoints y esa noche la gente empezo a derribarlo con martillos.",
        "dato": "El Muro de Berlin tenia 155 km y estuvo en pie 28 anos, 2 meses y 27 dias."
    },
    {
        "titulo": "El nacimiento de los Estados Unidos",
        "emoji": "🦅",
        "texto": "El 4 de julio de 1776, el Congreso Continental adopto la Declaracion de Independencia, redactada principalmente por Thomas Jefferson. Las 13 colonias americanas se separaban de Gran Bretana. Pocos saben que fue aprobada el 2 de julio — el 4 fue cuando se termino de imprimir.",
        "dato": "Adams y Jefferson murieron el mismo dia: 4 de julio de 1826, exactamente 50 anos despues."
    },
    {
        "titulo": "El dia que Mandela salio libre",
        "emoji": "🕊️",
        "texto": "El 11 de febrero de 1990, despues de 27 anos en prision, Nelson Mandela camino libre por las puertas de la carcel Victor Verster en Sudafrica. Cuatro anos despues se convirtio en el primer presidente negro elegido democraticamente en el pais.",
        "dato": "Mandela paso 18 de sus 27 anos en la isla Robben, en una celda de 2x2 metros."
    },
    {
        "titulo": "El Titanic y la noche mas larga",
        "emoji": "🚢",
        "texto": "En la madrugada del 15 de abril de 1912, el RMS Titanic se hundio en el Atlantico Norte. De 2,224 personas a bordo, solo 710 sobrevivieron. El barco llevaba botes salvavidas para menos de la mitad de los pasajeros.",
        "dato": "El barco Carpathia respondio al SOS y navego 93 km a toda velocidad para rescatar sobrevivientes."
    },
    {
        "titulo": "Yuri Gagarin y el primer viaje al espacio",
        "emoji": "🚀",
        "texto": "El 12 de abril de 1961, Yuri Gagarin se convirtio en el primer ser humano en viajar al espacio. Su vuelo duro 108 minutos orbitando la Tierra. La hazana sovietica acelero el programa espacial que llevaria al hombre a la Luna.",
        "dato": "Gagarin murio en 1968 en un accidente a los 34 anos, sin ver el alunizaje que su vuelo inspiro."
    },
    {
        "titulo": "El discurso que cambio America",
        "emoji": "✊",
        "texto": "El 28 de agosto de 1963, Martin Luther King Jr. se paro frente a 250,000 personas en Washington D.C. Gran parte del discurso fue improvisado. Sus palabras sobre igualdad racial son uno de los momentos mas poderosos del siglo XX.",
        "dato": "King tenia 34 anos cuando dio ese discurso. Cinco anos despues fue asesinado en Memphis."
    },
    {
        "titulo": "Einstein y la formula que cambio el mundo",
        "emoji": "🧠",
        "texto": "El 14 de marzo de 1879 nacio Albert Einstein. De nino sus profesores lo creian lento. A los 26 anos, trabajando en una oficina de patentes, publico cuatro articulos que revolucionaron la fisica, incluyendo E=mc2.",
        "dato": "Einstein gano el Nobel en 1921, pero no por la relatividad, sino por el efecto fotoelectrico."
    },
    {
        "titulo": "El origen del Ano Nuevo",
        "emoji": "🎆",
        "texto": "Celebrar el inicio del ano es una tradicion de mas de 4,000 anos. Los babilonios lo festejaban en primavera. Los romanos movieron la fecha al 1 de enero en honor a Jano, el dios de los comienzos, de ahi viene January.",
        "dato": "En Japon, el Ano Nuevo (Oshoogatsu) es la festividad mas importante del ano."
    },
    {
        "titulo": "Colon y el encuentro de dos mundos",
        "emoji": "⛵",
        "texto": "El 12 de octubre de 1492, Rodrigo de Triana grito Tierra desde la carabela Pinta. Colon penso que habia llegado a Asia. En realidad habia pisado el Caribe, conectando dos mundos que no sabian que existian el uno al otro.",
        "dato": "Colon murio en 1506 creyendo que habia llegado a Asia."
    },
    {
        "titulo": "Hiroshima y el inicio de la era nuclear",
        "emoji": "☁️",
        "texto": "El 6 de agosto de 1945, el bombardero Enola Gay lanzo sobre Hiroshima la primera bomba atomica usada en combate. En segundos murieron 80,000 personas. Japon se rindio el 15 de agosto, terminando la Segunda Guerra Mundial.",
        "dato": "Un arbol ginkgo biloba a 1 km del epicentro sobrevivio la explosion. Hoy sigue vivo."
    },
]

historia = HISTORIAS[day_of_year % len(HISTORIAS)]

# ── Market data fetched server-side ───────────────────────────────────────
def get_markets():
    m = {
        "sp500":   {"label":"S&P 500",  "val":"—","chg":"—","up":None},
        "nasdaq":  {"label":"Nasdaq",   "val":"—","chg":"—","up":None},
        "eurusd":  {"label":"EUR/USD",  "val":"—","chg":"—","up":None},
        "bitcoin": {"label":"Bitcoin",  "val":"—","chg":"—","up":None},
        "gold":    {"label":"Oro",      "val":"—","chg":"—","up":None},
        "oil":     {"label":"Petroleo", "val":"—","chg":"—","up":None},
    }
    hdrs = {"User-Agent":"Mozilla/5.0 (compatible; newsletter/1.0)","Accept":"application/json"}

    # Yahoo Finance
    try:
        syms = "%5EGSPC,%5EIXIC,GC%3DF,CL%3DF"
        url  = "https://query1.finance.yahoo.com/v7/finance/quote?symbols=" + syms + "&fields=regularMarketPrice,regularMarketChangePercent"
        req  = Request(url, headers=hdrs)
        with urlopen(req, timeout=10) as r:
            data = json.loads(r.read().decode())
        for q in data.get("quoteResponse",{}).get("result",[]):
            sym   = q.get("symbol","")
            price = q.get("regularMarketPrice", 0)
            chg   = q.get("regularMarketChangePercent", 0)
            up    = chg >= 0
            chg_s = ("+" if up else "") + "{:.2f}%".format(chg)
            if sym == "^GSPC":
                m["sp500"]  = {"label":"S&P 500", "val":"{:,.0f}".format(price), "chg":chg_s,"up":up}
            elif sym == "^IXIC":
                m["nasdaq"] = {"label":"Nasdaq",  "val":"{:,.0f}".format(price), "chg":chg_s,"up":up}
            elif sym == "GC=F":
                m["gold"]   = {"label":"Oro",     "val":"${:.1f}".format(price), "chg":chg_s,"up":up}
            elif sym == "CL=F":
                m["oil"]    = {"label":"Petroleo","val":"${:.1f}".format(price), "chg":chg_s,"up":up}
        print("  Stocks OK")
    except Exception as e:
        print("  Stocks error: " + str(e))

    # EUR/USD via Frankfurter (ECB data, free)
    try:
        req = Request("https://api.frankfurter.app/latest?from=EUR&to=USD", headers=hdrs)
        with urlopen(req, timeout=8) as r:
            data = json.loads(r.read().decode())
        rate = data["rates"]["USD"]
        m["eurusd"] = {"label":"EUR/USD","val":"{:.4f}".format(rate),"chg":"","up":None}
        print("  EUR/USD OK: " + str(rate))
    except Exception as e:
        print("  EUR/USD error: " + str(e))

    # Bitcoin via CoinGecko (free, no key)
    try:
        url = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd&include_24hr_change=true"
        req = Request(url, headers=hdrs)
        with urlopen(req, timeout=8) as r:
            data = json.loads(r.read().decode())
        price = data["bitcoin"]["usd"]
        chg   = data["bitcoin"].get("usd_24h_change", 0)
        up    = chg >= 0
        m["bitcoin"] = {
            "label":"Bitcoin",
            "val":"${:,.0f}".format(price),
            "chg": ("+" if up else "") + "{:.2f}%".format(chg),
            "up": up
        }
        print("  Bitcoin OK: $" + "{:,.0f}".format(price))
    except Exception as e:
        print("  Bitcoin error: " + str(e))

    return m

print("Fetching market data...")
markets = get_markets()

def mkt_cell(key, info):
    val_color = "#f5e6c8"
    if info["up"] is True:
        chg_color = "#4ade80"
        arrow = "▲ "
    elif info["up"] is False:
        chg_color = "#f87171"
        arrow = "▼ "
    else:
        chg_color = "rgba(255,255,255,.4)"
        arrow = ""
    chg_txt = arrow + info["chg"] if info["chg"] else "—"
    lines = []
    lines.append('<div style="text-align:center;padding:0 4px;">')
    lines.append('<div style="font-size:8px;letter-spacing:.5px;text-transform:uppercase;color:rgba(255,255,255,.4);margin-bottom:2px;">' + info["label"] + '</div>')
    lines.append('<div style="font-size:12px;font-weight:600;color:' + val_color + ';">' + info["val"] + '</div>')
    lines.append('<div style="font-size:10px;color:' + chg_color + ';">' + chg_txt + '</div>')
    lines.append('</div>')
    return "\n".join(lines)

markets_html = "\n".join(mkt_cell(k, v) for k, v in markets.items())

# ── Translation ────────────────────────────────────────────────────────────
_tc = 0
MAX_T = 300

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

# ── Feeds ──────────────────────────────────────────────────────────────────
FEEDS = {
    "int": [
        {"url":"https://feeds.bbci.co.uk/news/world/rss.xml",       "src":"BBC",         "lang":"en","prio":1},
        {"url":"https://feeds.reuters.com/reuters/worldNews",        "src":"Reuters",     "lang":"en","prio":1},
        {"url":"https://www.theguardian.com/world/rss",              "src":"The Guardian","lang":"en","prio":2},
        {"url":"https://rss.dw.com/rdf/rss-es-world",                "src":"DW Espanol",  "lang":"es","prio":1},
        {"url":"https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/section/internacional/portada",
                                                                     "src":"El Pais",     "lang":"es","prio":1},
    ],
    "ecu": [
        {"url":"https://www.eluniverso.com/arc/outboundfeeds/rss/?outputType=xml",
                                                                     "src":"El Universo", "lang":"es","prio":1},
        {"url":"https://rss.dw.com/rdf/rss-es-world",                "src":"DW Espanol",  "lang":"es","prio":2},
    ],
    "dep": [
        {"url":"https://feeds.bbci.co.uk/sport/rss.xml",             "src":"BBC Sport",   "lang":"en","prio":1},
        {"url":"https://www.theguardian.com/sport/rss",              "src":"Guardian Sp.","lang":"en","prio":2},
        {"url":"https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/section/deportes/portada",
                                                                     "src":"El Pais Dep.","lang":"es","prio":1},
        {"url":"https://www.eluniverso.com/arc/outboundfeeds/rss/category/deportes/?outputType=xml",
                                                                     "src":"El Universo D.","lang":"es","prio":1},
    ],
}

MUNDIAL_KW = ['mundial','world cup','fifa','2026','copa del mundo',
              'seleccion','qualifier','clasificatori','wc2026']

def fetch(feeds, n=5):
    raw = []
    for f in feeds:
        try:
            feed = feedparser.parse(f["url"])
            for e in feed.entries[:6]:
                title = (e.get("title","") or "").strip()
                if not title:
                    continue
                summ = re.sub(r'<[^<]+?>', '', getattr(e,'summary','') or '').strip()
                summ = summ[:200] + ('...' if len(summ) > 200 else '')
                title_es = translate(title) if f['lang'] == 'en' else title
                pub  = getattr(e, 'published_parsed', None)
                ts, tstr = 0, "—"
                if pub:
                    try:
                        dt   = datetime(*pub[:6], tzinfo=timezone.utc).astimezone(ET)
                        ts   = dt.timestamp()
                        tstr = dt.strftime("%-I:%M %p ET")
                    except:
                        pass
                raw.append({
                    "title":    title,
                    "title_es": title_es,
                    "link":     e.get("link","#"),
                    "summary":  summ,
                    "source":   f["src"],
                    "lang":     f["lang"],
                    "time":     tstr,
                    "ts":       ts,
                    "prio":     f["prio"]
                })
        except Exception as ex:
            print("  x " + f['src'] + ": " + str(ex))
    return dedup(raw)[:n]

print("Fetching news...")
ni     = fetch(FEEDS["int"], 4)[:3]
ne     = fetch(FEEDS["ecu"], 5)[:3]
nd_all = fetch(FEEDS["dep"], 10)
mundial = [a for a in nd_all if any(k in (a['title']+a['title_es']).lower() for k in MUNDIAL_KW)]
otros   = [a for a in nd_all if a not in mundial]
nd      = (mundial + otros)[:3]
print("OK Int:" + str(len(ni)) + " Ecu:" + str(len(ne)) + " Dep:" + str(len(nd)))

# ── HTML builders ──────────────────────────────────────────────────────────
def flag(lang):
    return "🇬🇧" if lang == "en" else "🇪🇸"

def top_card(a, grad, tag):
    parts = []
    parts.append('<div style="background:linear-gradient(135deg,' + grad + ');border-radius:10px;overflow:hidden;margin-bottom:6px;">')
    parts.append('<div style="padding:1rem 1.1rem .85rem;">')
    parts.append('<span style="display:inline-block;background:rgba(255,255,255,.18);color:#fff;font-size:9px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;padding:2px 9px;border-radius:20px;margin-bottom:7px;">' + tag + '</span><br>')
    parts.append('<a href="' + a['link'] + '" target="_blank" style="font-family:Georgia,serif;font-size:1rem;font-weight:700;color:#fff;text-decoration:none;line-height:1.35;">' + a['title_es'] + '</a>')
    parts.append('</div>')
    parts.append('<div style="background:rgba(0,0,0,.15);padding:.5rem 1.1rem;">')
    parts.append('<span style="font-size:10px;color:rgba(255,255,255,.7);">' + flag(a['lang']) + ' ' + a['source'] + ' · ' + a['time'] + '</span>')
    parts.append('</div>')
    parts.append('</div>')
    return "\n".join(parts)

def mini_card(a, color):
    parts = []
    parts.append('<div style="display:flex;background:#fff;border-radius:8px;border:1px solid #e8e2d8;overflow:hidden;margin-bottom:6px;">')
    parts.append('<div style="width:4px;background:' + color + ';flex-shrink:0;"></div>')
    parts.append('<div style="padding:.6rem .9rem;flex:1;">')
    parts.append('<a href="' + a['link'] + '" target="_blank" style="font-family:Georgia,serif;font-size:.9rem;font-weight:600;color:#1a1208;text-decoration:none;line-height:1.35;display:block;margin-bottom:3px;">' + a['title_es'] + '</a>')
    parts.append('<span style="font-size:10px;color:#a09688;">' + flag(a['lang']) + ' ' + a['source'] + ' · ' + a['time'] + '</span>')
    parts.append('</div>')
    parts.append('</div>')
    return "\n".join(parts)

def sec_hd(icon, label, color):
    parts = []
    parts.append('<div style="display:flex;align-items:center;gap:8px;padding:1.1rem 0 .55rem;">')
    parts.append('<span style="font-size:10px;font-weight:700;letter-spacing:2px;text-transform:uppercase;color:' + color + ';white-space:nowrap;">' + icon + ' ' + label + '</span>')
    parts.append('<div style="flex:1;height:1.5px;background:' + color + ';opacity:.25;"></div>')
    parts.append('</div>')
    return "\n".join(parts)

def build_section(icon, label, color, items, grad, tag):
    parts = [sec_hd(icon, label, color)]
    if items:
        parts.append(top_card(items[0], grad, tag))
        for a in items[1:]:
            parts.append(mini_card(a, color))
    return "\n".join(parts)

def build_historia(h):
    parts = []
    parts.append(sec_hd("📖", "HISTORIA DEL DIA", "#92400e"))
    parts.append('<div style="background:#fffbeb;border-radius:10px;border:1px solid #fde68a;padding:1.1rem 1.2rem;margin-bottom:8px;">')
    parts.append('<div style="font-size:2rem;text-align:center;margin-bottom:.6rem;">' + h['emoji'] + '</div>')
    parts.append('<div style="font-family:Georgia,serif;font-size:.98rem;font-weight:700;color:#78350f;text-align:center;margin-bottom:.6rem;">' + h['titulo'] + '</div>')
    parts.append('<p style="font-size:.84rem;color:#92400e;line-height:1.65;margin:0 0 .7rem;">' + h['texto'] + '</p>')
    parts.append('<div style="background:#fef3c7;border-radius:6px;padding:.55rem .9rem;border-left:3px solid #f59e0b;">')
    parts.append('<span style="font-size:.8rem;color:#78350f;"><strong>Dato:</strong> ' + h['dato'] + '</span>')
    parts.append('</div>')
    parts.append('</div>')
    return "\n".join(parts)

s_int  = build_section("🌍","NOTICIAS INTERNACIONALES","#1e3a5f", ni, "#1e3a5f,#1e4a8f","Internacional")
s_ecu  = build_section("🇪🇨","ECUADOR HOY","#065f46", ne, "#065f46,#059669","Ecuador")
s_dep  = build_section("⚽","DEPORTES Y MUNDIAL 2026","#7c2d12", nd, "#7c2d12,#b45309","Deportes")
s_hist = build_historia(historia)

preheader = ni[0]['title_es'] if ni else "Tu resumen de hoy esta listo."

# ── Write HTML ─────────────────────────────────────────────────────────────
os.makedirs("docs/newsletter", exist_ok=True)
fname = "docs/newsletter/al-dia-" + now_et.strftime('%Y-%m-%d') + ".html"

for path in [fname, "docs/newsletter/latest.html"]:
    with open(path, "w", encoding="utf-8") as f:
        w = f.write

        w("<!DOCTYPE html>\n")
        w("<html lang='es'>\n")
        w("<head>\n")
        w("<meta charset='UTF-8'>\n")
        w("<meta name='viewport' content='width=device-width,initial-scale=1'>\n")
        w("<meta name='theme-color' content='#1a1208'>\n")
        w("<title>Al Dia - " + date_full + "</title>\n")
        w("</head>\n")
        w("<body style='margin:0;padding:0;background:#f0ece4;font-family:Helvetica Neue,Arial,sans-serif;'>\n")

        # Preheader
        w("<div style='display:none;max-height:0;overflow:hidden;font-size:1px;color:#f0ece4;'>")
        w(preheader + " · Al Dia Newsletter</div>\n")

        w("<div style='background:#f0ece4;padding:16px;min-height:100vh;'>\n")
        w("<div style='max-width:560px;margin:0 auto;'>\n")

        # Header
        w("<div style='background:#1a1208;border-radius:12px 12px 0 0;padding:1.5rem 1.4rem 1.2rem;text-align:center;'>\n")
        w("<p style='font-size:9px;letter-spacing:3px;text-transform:uppercase;color:rgba(255,255,255,.4);margin:0 0 .4rem;'>Tu resumen diario · " + date_full + "</p>\n")
        w("<h1 style='font-family:Georgia,serif;font-size:2.2rem;font-weight:700;color:#f5e6c8;letter-spacing:-1px;line-height:1;margin:0 0 .3rem;'>Al Dia</h1>\n")
        w("<p style='font-size:11px;color:rgba(255,255,255,.5);margin:0 0 .75rem;'>Mantente informado con lo que importa hoy</p>\n")
        w("<span style='display:inline-block;background:rgba(255,255,255,.1);border:1px solid rgba(255,255,255,.15);color:rgba(255,255,255,.75);font-size:10px;font-weight:600;padding:4px 14px;border-radius:20px;'>" + date_full + " &nbsp;·&nbsp; 3 min de lectura</span>\n")
        w("</div>\n")

        # Greeting
        w("<div style='background:#fdf8f0;border:1px solid #e8e2d8;border-top:none;padding:1rem 1.4rem;'>\n")
        w("<p style='font-size:13.5px;color:#5c5248;line-height:1.65;margin:0;'>" + greeting + "</p>\n")
        w("</div>\n")

        # Body sections
        w("<div style='background:#f5f1eb;border:1px solid #e8e2d8;border-top:none;padding:.6rem 1.2rem 1rem;'>\n")
        w(s_int + "\n")
        w(s_ecu + "\n")
        w(s_dep + "\n")
        w(s_hist + "\n")
        w("</div>\n")

        # Markets
        w("<div style='background:#1a1208;padding:.9rem 1rem;'>\n")
        w("<div style='font-size:9px;letter-spacing:2px;text-transform:uppercase;color:rgba(255,255,255,.4);text-align:center;margin-bottom:.6rem;'>MERCADOS · " + time_display + " ET</div>\n")
        w("<div style='display:grid;grid-template-columns:repeat(3,1fr);gap:8px;'>\n")
        w(markets_html + "\n")
        w("</div>\n")
        w("<div style='font-size:9px;color:rgba(255,255,255,.25);text-align:center;margin-top:.5rem;'>Fuente: Yahoo Finance · CoinGecko · BCE</div>\n")
        w("</div>\n")

        # CTA
        w("<div style='background:#25D366;padding:.7rem 1.2rem;text-align:center;'>\n")
        w("<p style='font-size:12px;font-weight:600;color:#fff;margin:0;'>Comparte Al Dia con tu familia y amigos 📲</p>\n")
        w("</div>\n")

        # Footer
        w("<div style='background:#fff;border-radius:0 0 12px 12px;border:1px solid #e8e2d8;border-top:none;padding:1rem 1.4rem;text-align:center;'>\n")
        w("<p style='font-size:12px;color:#5c5248;margin-bottom:4px;'>Hecho con cafe · <strong style='color:#1a1208;'>Al Dia</strong> · Actualizado " + time_display + "</p>\n")
        w("<p style='font-size:10px;color:#a09688;margin-bottom:6px;'>BBC · Reuters · The Guardian · El Pais · El Universo · DW Espanol</p>\n")
        w("<a href='https://leoya06.github.io/mi-briefing/' style='font-size:11px;color:#2563eb;text-decoration:none;'>Ver Mi Briefing completo</a>\n")
        w("</div>\n")

        w("</div>\n")
        w("</div>\n")
        w("</body>\n")
        w("</html>\n")

print("OK: " + fname)
print("Historia: " + historia['titulo'])
print("Traducciones: " + str(_tc))
print("Mercados: " + str({k: v['val'] for k, v in markets.items()}))
