import feedparser
import json
from datetime import datetime
import pytz
import os

ET = pytz.timezone("America/New_York")
now_et = datetime.now(ET)
hour = now_et.hour
edition = "morning" if hour < 13 else "afternoon"
edition_es = "Edición matutina" if edition == "morning" else "Edición vespertina"
edition_label = "🌅 Morning Edition" if edition == "morning" else "🌆 Afternoon Edition"

FEEDS = [
    {"url": "https://feeds.bbci.co.uk/news/world/rss.xml",         "source": "BBC",         "lang": "en", "cat": "Internacional"},
    {"url": "https://feeds.reuters.com/reuters/worldNews",          "source": "Reuters",     "lang": "en", "cat": "Internacional"},
    {"url": "https://rss.dw.com/rdf/rss-es-world",                 "source": "DW Español",  "lang": "es", "cat": "Internacional"},
    {"url": "https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/section/internacional/portada", "source": "El País", "lang": "es", "cat": "Internacional"},
    {"url": "https://feeds.bbci.co.uk/news/business/rss.xml",       "source": "BBC Business","lang": "en", "cat": "Economía"},
    {"url": "https://feeds.reuters.com/reuters/businessNews",       "source": "Reuters Biz", "lang": "en", "cat": "Economía"},
    {"url": "https://rss.dw.com/rdf/rss-es-eco",                   "source": "DW Economía", "lang": "es", "cat": "Economía"},
    {"url": "https://feeds.reuters.com/reuters/technologyNews",     "source": "Reuters Tech","lang": "en", "cat": "Tecnología"},
    {"url": "https://feeds.bbci.co.uk/news/technology/rss.xml",    "source": "BBC Tech",    "lang": "en", "cat": "Tecnología"},
    {"url": "https://feeds.bbci.co.uk/news/science_and_environment/rss.xml", "source": "BBC Climate","lang": "en", "cat": "Clima"},
]

ITEMS_PER_FEED = 3
articles = []

for feed_meta in FEEDS:
    try:
        feed = feedparser.parse(feed_meta["url"])
        for entry in feed.entries[:ITEMS_PER_FEED]:
            summary = getattr(entry, "summary", "") or ""
            # Strip HTML tags simply
            import re
            summary = re.sub('<[^<]+?>', '', summary).strip()
            summary = summary[:220] + ("..." if len(summary) > 220 else "")

            pub = getattr(entry, "published_parsed", None)
            if pub:
                dt = datetime(*pub[:6], tzinfo=pytz.utc).astimezone(ET)
                time_str = dt.strftime("%-I:%M %p ET")
            else:
                time_str = "—"

            articles.append({
                "title": entry.title,
                "link": entry.link,
                "summary": summary,
                "source": feed_meta["source"],
                "lang": feed_meta["lang"],
                "cat": feed_meta["cat"],
                "time": time_str,
            })
    except Exception as e:
        print(f"Error fetching {feed_meta['url']}: {e}")

# Group by category
from collections import defaultdict
by_cat = defaultdict(list)
for a in articles:
    by_cat[a["cat"]].append(a)

CAT_COLORS = {
    "Internacional": ("intl",   "#1a3a5c", "#e8f0fa"),
    "Economía":      ("eco",    "#1a4a2e", "#e8f5ee"),
    "Tecnología":    ("tech",   "#3a1a5c", "#f0e8fa"),
    "Clima":         ("clima",  "#1a3a3a", "#e8f5f5"),
    "Inversiones":   ("inv",    "#5c3a00", "#faf0e8"),
}

def build_article_card(a, featured=False):
    slug, text_color, bg_color = CAT_COLORS.get(a["cat"], ("other","#333","#f5f5f5"))
    lang_flag = "🇬🇧" if a["lang"] == "en" else "🇪🇸"
    size_class = "card-featured" if featured else "card-normal"
    return f"""
    <a href="{a['link']}" target="_blank" rel="noopener" class="card {size_class}">
      <div class="card-top">
        <span class="tag" style="background:{bg_color};color:{text_color}">{a['cat']}</span>
        <span class="card-meta">{lang_flag} {a['source']} · {a['time']}</span>
      </div>
      <h3 class="card-title {'card-title-big' if featured else ''}">{a['title']}</h3>
      {'<p class="card-summary">' + a['summary'] + '</p>' if featured and a['summary'] else ''}
    </a>"""

def build_section(cat, items):
    if not items:
        return ""
    slug, text_color, bg_color = CAT_COLORS.get(cat, ("other","#333","#f5f5f5"))
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

date_str = now_et.strftime("%A, %B %d, %Y")
date_es  = now_et.strftime("%-d de %B de %Y")

# Map English month names to Spanish
months_en_es = {
    "January":"enero","February":"febrero","March":"marzo","April":"abril",
    "May":"mayo","June":"junio","July":"julio","August":"agosto",
    "September":"septiembre","October":"octubre","November":"noviembre","December":"diciembre"
}
days_en_es = {
    "Monday":"Lunes","Tuesday":"Martes","Wednesday":"Miércoles","Thursday":"Jueves",
    "Friday":"Viernes","Saturday":"Sábado","Sunday":"Domingo"
}
for en, es in months_en_es.items():
    date_es = date_es.replace(en, es)
day_en = now_et.strftime("%A")
date_display = f"{days_en_es.get(day_en, day_en)}, {date_es}"

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
    --bg: #f7f5f0;
    --surface: #ffffff;
    --border: #e2ddd6;
    --text: #1a1814;
    --muted: #6b6560;
    --faint: #b0aaa3;
    --accent: #1a3a5c;
  }}
  body {{
    font-family: 'Source Sans 3', sans-serif;
    background: var(--bg);
    color: var(--text);
    font-size: 16px;
    line-height: 1.6;
    min-height: 100vh;
  }}
  a {{ color: inherit; text-decoration: none; }}

  /* ── HEADER ── */
  .masthead {{
    background: var(--surface);
    border-bottom: 2px solid var(--text);
    padding: 1.5rem 0 1rem;
    text-align: center;
  }}
  .masthead-eyebrow {{
    font-size: 11px;
    letter-spacing: 3px;
    text-transform: uppercase;
    color: var(--muted);
    margin-bottom: 0.5rem;
  }}
  .masthead-logo {{
    font-family: 'Playfair Display', serif;
    font-size: clamp(2rem, 6vw, 3.5rem);
    font-weight: 700;
    letter-spacing: -1px;
    color: var(--text);
    line-height: 1;
    margin-bottom: 0.5rem;
  }}
  .masthead-meta {{
    display: flex;
    justify-content: center;
    align-items: center;
    gap: 1.5rem;
    font-size: 12px;
    color: var(--muted);
    border-top: 1px solid var(--border);
    margin-top: 0.75rem;
    padding-top: 0.75rem;
  }}
  .edition-badge {{
    background: var(--text);
    color: white;
    font-size: 11px;
    font-weight: 600;
    padding: 3px 10px;
    border-radius: 2px;
    letter-spacing: 1px;
    text-transform: uppercase;
  }}

  /* ── TICKER ── */
  .ticker-wrap {{
    background: var(--text);
    color: white;
    font-size: 12px;
    font-weight: 500;
    overflow: hidden;
    white-space: nowrap;
    padding: 6px 0;
  }}
  .ticker-inner {{
    display: inline-block;
    animation: ticker 30s linear infinite;
    padding-left: 100%;
  }}
  .ticker-inner span {{ margin: 0 2rem; }}
  .ticker-up   {{ color: #7de8a4; }}
  .ticker-down {{ color: #f08080; }}
  @keyframes ticker {{ from {{ transform: translateX(0); }} to {{ transform: translateX(-100%); }} }}

  /* ── LAYOUT ── */
  .container {{ max-width: 960px; margin: 0 auto; padding: 0 1rem; }}
  .main {{ padding: 2rem 0 3rem; }}

  /* ── SECTIONS ── */
  .news-section {{ margin-bottom: 2.5rem; }}
  .section-header {{
    display: flex; align-items: center; gap: 10px;
    margin-bottom: 1rem;
    padding-bottom: 0.5rem;
    border-bottom: 1.5px solid var(--text);
  }}
  .section-dot {{ width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0; }}
  .section-title {{
    font-family: 'Playfair Display', serif;
    font-size: 1.1rem;
    font-weight: 500;
    letter-spacing: 0.5px;
    color: var(--text);
  }}

  /* ── CARDS ── */
  .card {{
    display: block;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 4px;
    padding: 1rem 1.25rem;
    transition: border-color 0.15s, box-shadow 0.15s;
    margin-bottom: 10px;
  }}
  .card:hover {{
    border-color: #999;
    box-shadow: 0 2px 12px rgba(0,0,0,0.06);
  }}
  .card-featured {{ padding: 1.25rem 1.5rem; }}
  .card-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
    gap: 10px;
    margin-bottom: 0;
  }}
  .card-grid .card {{ margin-bottom: 0; }}
  .card-top {{
    display: flex; align-items: center; justify-content: space-between;
    margin-bottom: 0.5rem; gap: 8px;
  }}
  .tag {{
    font-size: 10px; font-weight: 600; letter-spacing: 1px;
    text-transform: uppercase; padding: 2px 8px; border-radius: 2px;
    flex-shrink: 0;
  }}
  .card-meta {{ font-size: 11px; color: var(--faint); }}
  .card-title {{
    font-family: 'Playfair Display', serif;
    font-size: 0.95rem; font-weight: 500; line-height: 1.35;
    color: var(--text);
  }}
  .card-title-big {{ font-size: 1.2rem; }}
  .card-summary {{
    margin-top: 0.5rem;
    font-size: 0.875rem; color: var(--muted); line-height: 1.55;
  }}

  /* ── FOOTER ── */
  .footer {{
    border-top: 2px solid var(--text);
    padding: 1.5rem 0;
    text-align: center;
  }}
  .footer p {{ font-size: 12px; color: var(--muted); margin-bottom: 4px; }}
  .footer strong {{ color: var(--text); }}
  .sources-list {{ font-size: 11px; color: var(--faint); margin-top: 6px; }}

  @media (max-width: 600px) {{
    .card-grid {{ grid-template-columns: 1fr; }}
    .masthead-meta {{ flex-wrap: wrap; gap: 0.5rem; }}
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
      <span>Actualizado · {now_et.strftime("%-I:%M %p ET")}</span>
    </div>
  </div>
</header>

<div class="ticker-wrap">
  <div class="ticker-inner">
    <span>S&amp;P 500 <span class="ticker-up">▲</span> en seguimiento</span>
    <span>·</span>
    <span>EUR/USD — en seguimiento</span>
    <span>·</span>
    <span>Petróleo WTI — en seguimiento</span>
    <span>·</span>
    <span>Bitcoin — en seguimiento</span>
    <span>·</span>
    <span>S&amp;P 500 <span class="ticker-up">▲</span> en seguimiento</span>
    <span>·</span>
    <span>Oro — en seguimiento</span>
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
    <p class="sources-list">Fuentes: BBC News · Reuters · DW Español · El País · AP News</p>
  </div>
</footer>

</body>
</html>"""

os.makedirs("docs", exist_ok=True)
with open("docs/index.html", "w", encoding="utf-8") as f:
    f.write(HTML)

print(f"✅ Generated docs/index.html — {len(articles)} articles — {edition_es} — {now_et.strftime('%I:%M %p ET')}")
