"""Portada estática. Los enlaces y textos externos se validan al mostrarlos."""
from html import escape, unescape
from pathlib import Path
from unicodedata import normalize
from urllib.parse import urlsplit
import re


def texto(value):
    return escape(unescape(value or "").strip())


def url(value):
    try:
        u = urlsplit(value)
        if u.scheme in {"https", "http"} and u.hostname:
            return escape(value, quote=True)
    except ValueError:
        pass
    return ""


def slug(name):
    plain = normalize("NFKD", name).encode("ascii", "ignore").decode()
    return re.sub("[^a-z0-9]+", "-", plain.lower()).strip("-")


def tipo(tags):
    labels = {"opinion": "Opinión", "analysis": "Análisis", "analisis": "Análisis",
              "investigation": "Investigación", "investigacion": "Investigación",
              "news": "Noticia", "noticia": "Noticia"}
    values = [slug(t.get("term", "")) for t in tags]
    return next((v for k, v in labels.items() if k in values), "")


def articulo(a, size):
    title = texto(a["title_es"])
    link = url(a["link"])
    headline = f'<a href="{link}">{title}</a>' if link else title
    img = url(a.get("image", ""))
    photo = (f'<img alt="" src="{img}" onerror="this.hidden=true" loading="lazy">'
             if img and size != "breve" else "")
    summary = texto(a.get("summary_es"))
    desc = f'<p>{summary}</p>' if summary and summary != title else ""
    links = [(name, url(href)) for name, href in a.get("coberturas", []) if url(href)]
    compare = ""
    if len(links) > 1:
        lista = "".join(f'<li><a href="{href}">{texto(name)} ↗</a></li>' for name, href in links)
        compare = f'<details><summary>Comparar coberturas ({len(links)})</summary><ul>{lista}</ul></details>'
    origin = texto(a.get("principal", a["source"]))
    meta = " · ".join(texto(v) for v in (a.get("tipo"), a.get("time")) if v and v != "—")
    return f'<article class="{size}">{photo}<div><small>{origin}</small><h3>{headline}</h3>{desc}<aside>{meta}</aside>{compare}</div></article>'


def contenido(by_sec, order):
    sections = []
    nav = []
    for sec in order:
        items = by_sec.get(sec, [])
        if not items:
            continue
        sid = slug(sec)
        nav.append(f'<a href="#{sid}">{texto(sec)}</a>')
        primero = not sections
        lead = articulo(items[0], "apertura" if primero else "principal")
        visibles = 3 if primero else 2
        others = "".join(articulo(a, "breve") for a in items[1:visibles])
        rest = items[visibles:]
        extra = ""
        if rest:
            label = "Ver otro titular" if len(rest) == 1 else f"Ver {len(rest)} titulares más"
            extra = f'<details class="extra"><summary>{label}</summary>{"".join(articulo(a,"breve") for a in rest)}</details>'
        sections.append(f'<section id="{sid}"><h2>{texto(sec)}</h2><div class="stories">{lead}<div>{others}</div></div>{extra}</section>')
    return "".join(nav), "".join(sections)


def render(by_sec, order, site, date, edition, time, audio_controls, audio_script):
    nav, sections = contenido(by_sec, order)
    css = Path(__file__).with_name("portada.css").read_text(encoding="utf8")
    agencies = ' · '.join(f'<a href="{href}">{name} ↗</a>' for name, href in [
        ("AP News","https://apnews.com/world-news"), ("Reuters","https://www.reuters.com/world/"),
        ("Agencia EFE","https://efe.com/mundo/"), ("DW Español","https://www.dw.com/es/actualidad/s-30684")])
    nombre = texto(site["nombre"])
    return f'''<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{nombre} · {texto(date)}</title><style>{css}</style></head><body><a class="skip" href="#portada">Saltar a las noticias</a>
<header><div class="folio"><span>{texto(date)}</span><span>{texto(edition)}</span></div>
<h1>{nombre}</h1><div class="bar"><span>Actualizado {texto(time)}</span>{audio_controls}</div></header>
<nav aria-label="Secciones">{nav}</nav><main id="portada">{sections}</main>
<footer><b>Consulta directa</b><div>{agencies}</div></footer>{audio_script}</body></html>'''
