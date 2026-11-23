"""Selección editorial compartida por la portada y el boletín."""
from collections import Counter, defaultdict
from functools import lru_cache
from html import unescape
import re
import unicodedata
from urllib.parse import parse_qsl, urlencode, urlsplit

STOP = set("the a an in on at to of and or for is are was were has have had be been as by its with from after says said el la los las de en un una y o que se su por con del al es son ha le lo las tras segun fue sido para como sobre ante".split())


@lru_cache(maxsize=4096)
def palabras(title):
    plain = unicodedata.normalize("NFKD", unescape(title).casefold())
    plain = "".join(c for c in plain if not unicodedata.combining(c))
    return tuple(re.findall(r"[^\W_]+", plain))


def enlace(url):
    try:
        parts = urlsplit(url)
        if not parts.hostname or parts.scheme not in {"http", "https"}:
            return None
        query = sorted((k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
                       if not k.lower().startswith("utm_") and k.lower() not in {"fbclid", "gclid"})
        return parts.netloc.lower(), parts.path.rstrip("/"), urlencode(query)
    except ValueError:
        return None


def similares(a, b, threshold):
    x, y = palabras(a), palabras(b)
    if not x or not y:
        return False
    if x == y:
        return True
    left, right = set(x) - STOP, set(y) - STOP
    common = left & right
    if len(common) < 4:
        return False
    if {w for w in left if w.isdigit()} != {w for w in right if w.isdigit()}:
        return False
    return len(common) / len(left | right) >= threshold


def seleccionar(items, limites, reglas):
    orden = sorted(items, key=lambda a: (a["prioridad"], -a["pub_ts"]))
    grupos = []
    por_url = {}
    for a in orden:
        url = enlace(a["link"])
        grupo = por_url.get(url) if url else None
        if grupo is None:
            for g in grupos:
                b = g[0]
                if a["pub_ts"] and b["pub_ts"] and abs(a["pub_ts"] - b["pub_ts"]) > reglas["ventana_horas"] * 3600:
                    continue
                if any(similares(a[k], b[k], reglas["umbral_similitud"]) for k in ("title", "title_es")):
                    grupo = g
                    break
        if grupo is None:
            grupo = []
            grupos.append(grupo)
        grupo.append(a)
        if url:
            por_url[url] = grupo

    pendientes = defaultdict(list)
    for grupo in grupos:
        a = grupo[0].copy()
        fuentes = list(dict.fromkeys(x["source"] for x in grupo))
        a["multi_source"] = len(fuentes) > 1
        a["principal"] = fuentes[0]
        a["source"] = " · ".join(fuentes[:reglas["max_fuentes_combinadas"]])
        pendientes[a["seccion"]].append(a)

    seleccion = defaultdict(list)
    for sec, candidatos in pendientes.items():
        usados = Counter()
        while candidatos and len(seleccion[sec]) < limites[sec]:
            a = min(candidatos, key=lambda x: (usados[x["principal"]], -x["pub_ts"], x["prioridad"]))
            seleccion[sec].append(a)
            usados[a["principal"]] += 1
            candidatos.remove(a)
    return seleccion, len(items) - len(grupos)
