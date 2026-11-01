#!/usr/bin/env python3
"""Herramienta de brainme: estado del proyecto y orden sin romper enlaces.

Subcomandos (se corren desde la raíz del proyecto):
  sincroniza   resumen del mapa y, si el proyecto usa Graphify, graphify update .
  estado       resumen compacto para ponerse al día (inbox, preguntas, decisiones, mapa)
  mapa         mapa de enlaces entre notas: lo más conectado, islas, enlaces rotos,
               los vecinos de una nota (--nota) o el camino entre dos (--camino)
  nombres      índice de nombres de notas por carpeta (para detectar duplicados)
  inventario   lista lo que hay y qué falta ordenar -> .brainme/inventario.json
  respaldo     zip de todo el proyecto -> .brainme/respaldos/
  mover        ejecuta un plan de movimientos y corrige los enlaces
  verificar    reporta enlaces rotos y nombres repetidos
  deshacer     revierte el último orden (o el registro indicado)
  a-wikilinks  convierte links markdown internos entre notas en wikilinks
  sin-resumen  notas sin resumen, en lotes para el ayudante de resúmenes
  poner-resumenes  escribe en el frontmatter los resúmenes de un archivo JSON
  autor        nombre de quien trabaja en este computador (para firmar notas y bitácora)
  bitacora     agrega o muestra entradas de bitacora.md (incluidos los handoffs)
  consumo      tokens de contexto por respuesta, leídos de los registros de Claude Code
  migrar       revisa y aplica lo que le falta a un proyecto de una versión anterior
  versiones    plan para llevar versiones viejas de entregables a _versiones/

Solo usa la biblioteca estándar de Python (3.9 o superior).
"""

import argparse
import datetime
import json
import os
import re
import shutil
import subprocess
import sys
import unicodedata
import zipfile
from urllib.parse import unquote

VERSION = "2.2.0"
# Última versión que cambió algo dentro de los proyectos: los anteriores piden migrar
VERSION_PROYECTO = "2.1.0"

ESTRUCTURA = [
    "00_inbox", "01_knowledge", "02_decisions", "03_open_questions/archive",
    "04_sources/literature", "04_sources/web", "05_exports/reports",
    "05_exports/diagrams", "05_exports/data", "05_exports/presentations",
]
RAICES_ESTRUCTURA = {"00_inbox", "01_knowledge", "02_decisions", "03_open_questions",
                     "04_sources", "05_exports"}
# Carpetas que nunca se recorren ni se mueven
PROTEGIDAS = {".git", ".obsidian", ".trash", ".claude", ".brainme", "graphify-out",
              "node_modules", ".claude-plugin"}
# Se quedan donde están (no son "por ordenar")
SE_QUEDAN_RAIZ = {"claude.md", "readme.md", "agents.md", ".graphifyignore", ".gitignore",
                  "bitacora.md"}
CARPETAS_QUE_SE_QUEDAN = {"docs", "_taller"}
# Versiones viejas de entregables y generadores: fuera del índice, las búsquedas y el grafo
APARTE = {"_versiones", "_taller"}
IGNORAR_ARCHIVOS = {".ds_store", "icon\r"}

CATEGORIAS = {
    "nota": {".md"},
    "pdf": {".pdf"},
    "imagen": {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".bmp", ".tif", ".tiff", ".heic"},
    "office": {".xlsx", ".xls", ".docx", ".doc", ".csv", ".numbers", ".pages", ".odt", ".ods"},
    "presentacion": {".key", ".pptx", ".ppt", ".odp"},
    "canvas": {".canvas"},
    "base": {".base"},
    "web": {".html", ".htm"},
    "texto": {".txt", ".rtf"},
    "video_audio": {".mp4", ".mov", ".m4v", ".mp3", ".wav", ".m4a", ".aac"},
}

RE_WIKI = re.compile(r"(!?)\[\[([^\[\]]+?)\]\]")
RE_MDLINK = re.compile(r"(!?)\[((?:[^\[\]]|\[[^\[\]]*\])*)\]\((<[^>]+>|[^)\s]+)((?:\s+\"[^\"]*\")?)\)")
RE_ESQUEMA = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.\-]*:")
RE_FENCE = re.compile(r"^\s*(```|~~~)")
RE_INLINE_CODE = re.compile(r"(`+)(.+?)\1")


# ---------------------------------------------------------------- utilidades

def nfc(s):
    return unicodedata.normalize("NFC", s)


def clave(s):
    return nfc(s).lower()


def categoria(nombre):
    ext = os.path.splitext(nombre)[1].lower()
    for cat, exts in CATEGORIAS.items():
        if ext in exts:
            return cat
    return "otro"


def slug_tag(texto):
    t = unicodedata.normalize("NFKD", texto)
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = t.lower().strip()
    t = re.sub(r"[^a-z0-9_/\-]+", "-", t)
    t = re.sub(r"-{2,}", "-", t).strip("-/")
    if not t or t.isdigit():
        return ""
    return t


def ahora():
    return datetime.datetime.now().strftime("%Y%m%d-%H%M%S")


def carpeta_de(rel):
    return rel.rsplit("/", 1)[0] if "/" in rel else ""


def buscar_vault(raiz):
    d = raiz
    while True:
        if os.path.isdir(os.path.join(d, ".obsidian")):
            return d
        padre = os.path.dirname(d)
        if padre == d:
            return raiz
        d = padre


def leer_texto(ruta):
    try:
        with open(ruta, "rb") as f:
            datos = f.read()
        texto = datos.decode("utf-8")
    except (OSError, UnicodeDecodeError):
        return None, False
    crlf = "\r\n" in texto
    return texto.replace("\r\n", "\n"), crlf


def escribir_texto(ruta, texto, crlf):
    if crlf:
        texto = texto.replace("\n", "\r\n")
    with open(ruta, "w", encoding="utf-8", newline="") as f:
        f.write(texto)


NO_DESCARGADOS = []


def listar_archivos(raiz):
    """Rutas relativas (con /) de todos los archivos del proyecto, sin carpetas protegidas."""
    salida = []
    del NO_DESCARGADOS[:]
    for d, carpetas, archivos in os.walk(raiz):
        rel_d = os.path.relpath(d, raiz)
        carpetas[:] = sorted(c for c in carpetas if c not in PROTEGIDAS)
        for a in sorted(archivos):
            rel = a if rel_d == "." else os.path.join(rel_d, a)
            if a.endswith(".icloud"):
                NO_DESCARGADOS.append(rel.replace(os.sep, "/"))
                continue
            if a.lower() in IGNORAR_ARCHIVOS:
                continue
            salida.append(rel.replace(os.sep, "/"))
    return salida


def estado_de(rel):
    partes = rel.split("/")
    if len(partes) == 1 and (partes[0].lower() in SE_QUEDAN_RAIZ or partes[0].startswith(".")):
        return "se_queda"
    if partes[0] in CARPETAS_QUE_SE_QUEDAN:
        return "se_queda"
    if partes[0] in RAICES_ESTRUCTURA:
        return "ordenado"
    return "por_ordenar"


# ------------------------------------------------------ recorrer y reescribir

def segmentos_sin_codigo(linea):
    """Divide una línea en (texto, es_codigo) según los `code spans`."""
    partes, pos = [], 0
    for m in RE_INLINE_CODE.finditer(linea):
        if m.start() > pos:
            partes.append((linea[pos:m.start()], False))
        partes.append((m.group(0), True))
        pos = m.end()
    if pos < len(linea):
        partes.append((linea[pos:], False))
    return partes


def transformar_enlaces(texto, fn_wiki, fn_md):
    """Aplica fn_wiki / fn_md a cada enlace fuera de bloques de código.
    Cada fn recibe (match, n_linea) y devuelve el reemplazo o None (sin cambio)."""
    lineas = texto.split("\n")
    en_fence, marca = False, None
    for i, linea in enumerate(lineas):
        m_f = RE_FENCE.match(linea)
        if m_f:
            if not en_fence:
                en_fence, marca = True, m_f.group(1)
            elif m_f.group(1) == marca:
                en_fence, marca = False, None
            continue
        if en_fence:
            continue
        nuevas = []
        for seg, es_codigo in segmentos_sin_codigo(linea):
            if not es_codigo:
                seg = RE_WIKI.sub(lambda m: _o(fn_wiki(m, i + 1), m), seg)
                seg = RE_MDLINK.sub(lambda m: _o(fn_md(m, i + 1), m), seg)
            nuevas.append(seg)
        lineas[i] = "".join(nuevas)
    return "\n".join(lineas)


def _o(valor, m):
    return m.group(0) if valor is None else valor


def partir_wiki(interior):
    """'ruta/nota#sec|alias' -> (objetivo, fragmento, alias_con_barra)."""
    alias = ""
    idx = interior.find("|")
    if idx >= 0:
        alias = interior[idx:]
        interior = interior[:idx]
        if interior.endswith("\\"):  # [[nota\|alias]] dentro de tablas
            interior = interior[:-1]
            alias = "\\" + alias
    frag = ""
    idx = interior.find("#")
    if idx >= 0:
        frag = interior[idx:]
        interior = interior[:idx]
    return interior.strip(), frag, alias


# ------------------------------------------------------------------- layout

class Layout:
    """Índice de archivos del proyecto para resolver enlaces como Obsidian."""

    def __init__(self, raiz, vault, rels):
        self.raiz, self.vault = raiz, vault
        self.pref = os.path.relpath(raiz, vault).replace(os.sep, "/")
        self.pref = "" if self.pref == "." else self.pref + "/"
        self.rels = list(rels)
        self.por_ruta = {clave(r): r for r in self.rels}
        self.por_stem_md, self.por_nombre = {}, {}
        for r in self.rels:
            nombre = r.rsplit("/", 1)[-1]
            self.por_nombre.setdefault(clave(nombre), []).append(r)
            if nombre.lower().endswith(".md"):
                self.por_stem_md.setdefault(clave(nombre[:-3]), []).append(r)

    def existe(self, rel):
        return self.por_ruta.get(clave(rel))

    def vault_rel(self, rel):
        return self.pref + rel

    def desde_vault(self, vrel):
        """Ruta relativa al vault -> relativa al proyecto (o None si cae fuera)."""
        if self.pref and not clave(vrel).startswith(clave(self.pref)):
            return None
        return vrel[len(self.pref):]

    def _elegir(self, candidatos, carpeta_origen):
        if len(candidatos) == 1:
            return candidatos[0]
        misma = [c for c in candidatos if carpeta_de(c) == carpeta_origen]
        if misma:
            return misma[0]
        return sorted(candidatos, key=lambda c: (c.count("/"), c))[0]

    def unico(self, rel_objetivo):
        nombre = rel_objetivo.rsplit("/", 1)[-1]
        if nombre.lower().endswith(".md"):
            return len(self.por_stem_md.get(clave(nombre[:-3]), [])) == 1
        return len(self.por_nombre.get(clave(nombre), [])) == 1

    def resolver_wiki(self, objetivo, rel_origen):
        """Devuelve la ruta relativa al proyecto del archivo enlazado, o None."""
        if not objetivo:
            return None
        carpeta = carpeta_de(rel_origen)
        obj = nfc(objetivo).strip("/")
        tiene_md = obj.lower().endswith(".md")
        variantes = [obj] if tiene_md else [obj + ".md", obj]
        if "/" not in obj:
            if tiene_md:
                cands = self.por_stem_md.get(clave(obj[:-3]), [])
            else:
                cands = self.por_stem_md.get(clave(obj), []) or self.por_nombre.get(clave(obj), [])
            return self._elegir(cands, carpeta) if cands else None
        for v in variantes:
            # 1) relativa al vault, 2) relativa al proyecto, 3) relativa a la nota
            for base in ("vault", "proyecto", "nota"):
                if base == "vault":
                    rel = self.desde_vault(v)
                elif base == "proyecto":
                    rel = v
                else:
                    rel = os.path.normpath(os.path.join(carpeta, v)).replace(os.sep, "/")
                if rel and self.existe(rel):
                    return self.existe(rel)
        # 4) coincidencia por final de ruta (como Obsidian)
        for v in variantes:
            sufijo = "/" + clave(v)
            cands = [r for r in self.rels if ("/" + clave(r)).endswith(sufijo)]
            if cands:
                return self._elegir(cands, carpeta)
        return None

    def resolver_md(self, url, rel_origen):
        """Devuelve (ruta_proyecto, estilo) con estilo 'relativo' | 'vault' | 'proyecto'."""
        carpeta = carpeta_de(rel_origen)
        base = nfc(unquote(url))
        variantes = [base]
        if not os.path.splitext(base)[1]:
            variantes.append(base + ".md")
        for ruta in variantes:
            if ruta.startswith("/"):
                rel = self.desde_vault(ruta.lstrip("/"))
                if rel and self.existe(rel):
                    return self.existe(rel), "vault_abs"
                continue
            rel = os.path.normpath(os.path.join(carpeta, ruta)).replace(os.sep, "/")
            if self.existe(rel):
                return self.existe(rel), "relativo"
            rel = self.desde_vault(ruta)
            if rel and self.existe(rel):
                return self.existe(rel), "vault"
            if self.existe(ruta):
                return self.existe(ruta), "proyecto"
        return None, None


def repetidos_de(layout):
    rep = {k: v for k, v in layout.por_stem_md.items() if len(v) > 1}
    for k, v in layout.por_nombre.items():
        if len(v) > 1 and not k.endswith(".md"):
            rep[k] = v
    return rep


def es_url_externa(url):
    return bool(RE_ESQUEMA.match(url)) or url.startswith("#")


def texto_wiki_nuevo(layout, rel_obj, frag, alias, embed):
    nombre = rel_obj.rsplit("/", 1)[-1]
    if layout.unico(rel_obj):
        objetivo = nombre[:-3] if nombre.lower().endswith(".md") else nombre
    else:
        objetivo = layout.vault_rel(rel_obj)
        if objetivo.lower().endswith(".md"):
            objetivo = objetivo[:-3]
    return "%s[[%s%s%s]]" % (embed, objetivo, frag, alias)


def url_md_nueva(layout, rel_obj, rel_origen, estilo, original):
    if estilo == "relativo":
        ruta = os.path.relpath(rel_obj, carpeta_de(rel_origen) or ".").replace(os.sep, "/")
    elif estilo == "vault_abs":
        ruta = "/" + layout.vault_rel(rel_obj)
    elif estilo == "vault":
        ruta = layout.vault_rel(rel_obj)
    else:
        ruta = rel_obj
    if original.startswith("<"):
        return "<" + ruta + ">"
    return ruta.replace(" ", "%20")


# ----------------------------------------------------------------- análisis

def analizar_nota(texto):
    """Título, frontmatter y vista previa de una nota."""
    fm, cuerpo = "", texto
    if texto.startswith("---\n"):
        fin = texto.find("\n---", 4)
        if fin > 0:
            fm = texto[4:fin]
            cuerpo = texto[fin + 4:].lstrip("-\n")
    titulo = None
    for campo in ("titulo", "title"):
        m = re.search(r"^%s:\s*[\"']?(.+?)[\"']?\s*$" % campo, fm, re.M)
        if m:
            titulo = m.group(1)
            break
    if not titulo:
        m = re.search(r"^#\s+(.+)$", cuerpo, re.M)
        titulo = m.group(1).strip() if m else None
    tipo = re.search(r"^tipo:\s*(.+)$", fm, re.M)
    tags = re.search(r"^tags:\s*(.*)$", fm, re.M)
    plano = re.sub(r"\s+", " ", cuerpo).strip()
    return {
        "titulo": titulo,
        "tiene_frontmatter": bool(fm),
        "tipo": tipo.group(1).strip() if tipo else None,
        "tags": tags.group(1).strip() if tags else None,
        "palabras": len(plano.split()),
        "vista_previa": plano[:300],
    }


def recorrer_enlaces(raiz, layout):
    """Enlaces de todas las notas y canvas: lista de dicts."""
    enlaces = []
    for rel in layout.rels:
        ruta = os.path.join(raiz, rel)
        if rel.lower().endswith(".md"):
            texto, _ = leer_texto(ruta)
            if texto is None:
                continue

            def fw(m, n, rel=rel):
                obj, frag, alias = partir_wiki(m.group(2))
                if not obj:
                    return None
                destino = layout.resolver_wiki(obj, rel)
                enlaces.append({"origen": rel, "linea": n, "tipo": "wiki", "texto": m.group(0),
                                "destino": destino, "con_ruta": "/" in obj})
                return None

            def fm_(m, n, rel=rel):
                url = m.group(3)
                limpia = url[1:-1] if url.startswith("<") else url
                if es_url_externa(limpia):
                    return None
                camino = limpia.split("#", 1)[0]
                if not camino:
                    return None
                destino, _ = layout.resolver_md(camino, rel)
                enlaces.append({"origen": rel, "linea": n, "tipo": "md", "texto": m.group(0),
                                "destino": destino, "con_ruta": True})
                return None

            transformar_enlaces(texto, fw, fm_)
        elif rel.lower().endswith(".canvas"):
            texto, _ = leer_texto(ruta)
            try:
                datos = json.loads(texto) if texto else {}
            except ValueError:
                continue
            for nodo in datos.get("nodes", []):
                if nodo.get("type") == "file" and nodo.get("file"):
                    destino = layout.desde_vault(nfc(nodo["file"]))
                    destino = layout.existe(destino) if destino else None
                    enlaces.append({"origen": rel, "linea": 0, "tipo": "canvas",
                                    "texto": nodo["file"], "destino": destino, "con_ruta": True})
    return enlaces


# --------------------------------------------------------------- inventario

def cmd_inventario(args):
    raiz = os.path.abspath(args.raiz)
    vault = buscar_vault(raiz)
    rels = listar_archivos(raiz)
    layout = Layout(raiz, vault, rels)
    enlaces = recorrer_enlaces(raiz, layout)
    entrantes, salientes, con_ruta = {}, {}, {}
    for e in enlaces:
        salientes[e["origen"]] = salientes.get(e["origen"], 0) + 1
        if e["con_ruta"] and e["tipo"] != "canvas":
            con_ruta[e["origen"]] = con_ruta.get(e["origen"], 0) + 1
        if e["destino"]:
            entrantes.setdefault(e["destino"], set()).add(e["origen"])

    archivos = []
    for rel in rels:
        if estado_de(rel) != "por_ordenar":
            archivos.append({"ruta": rel, "estado": estado_de(rel), "categoria": categoria(rel)})
            continue
        info = {"ruta": rel, "estado": estado_de(rel), "categoria": categoria(rel),
                "carpeta": rel.rsplit("/", 1)[0] if "/" in rel else "",
                "bytes": os.path.getsize(os.path.join(raiz, rel)),
                "usado_por": sorted(entrantes.get(rel, [])),
                "enlaces_salientes": salientes.get(rel, 0),
                "enlaces_con_ruta": con_ruta.get(rel, 0)}
        if info["categoria"] == "nota":
            texto, _ = leer_texto(os.path.join(raiz, rel))
            if texto is not None:
                info.update(analizar_nota(texto))
        archivos.append(info)

    repetidos = repetidos_de(layout)
    rotos = [e for e in enlaces if not e["destino"]]
    por_ordenar = [a for a in archivos if a["estado"] == "por_ordenar"]
    salida = {
        "proyecto": raiz, "vault": vault, "generado": ahora(),
        "faltan_carpetas": [c for c in ESTRUCTURA if not os.path.isdir(os.path.join(raiz, c))],
        "resumen": {
            "total": len(archivos), "por_ordenar": len(por_ordenar),
            "ordenados": sum(1 for a in archivos if a["estado"] == "ordenado"),
            "se_quedan": sum(1 for a in archivos if a["estado"] == "se_queda"),
        },
        "nombres_repetidos": {k: v for k, v in repetidos.items()},
        "enlaces_rotos_previos": len(rotos),
        "archivos": archivos,
    }
    os.makedirs(os.path.join(raiz, ".brainme"), exist_ok=True)
    destino = os.path.join(raiz, ".brainme", "inventario.json")
    with open(destino, "w", encoding="utf-8") as f:
        json.dump(salida, f, ensure_ascii=False, indent=1)

    r = salida["resumen"]
    print("Proyecto: %s" % raiz)
    print("Vault de Obsidian: %s" % vault)
    print("Archivos: %d en total | %d por ordenar | %d ya ordenados | %d se quedan donde están"
          % (r["total"], r["por_ordenar"], r["ordenados"], r["se_quedan"]))
    if por_ordenar:
        cats, carpetas = {}, {}
        for a in por_ordenar:
            cats[a["categoria"]] = cats.get(a["categoria"], 0) + 1
            top = a["carpeta"].split("/")[0] if a["carpeta"] else "(raíz)"
            carpetas[top] = carpetas.get(top, 0) + 1
        print("Por ordenar, por tipo: " + ", ".join("%s %d" % kv for kv in sorted(cats.items())))
        print("Por ordenar, por carpeta: " + ", ".join("%s %d" % kv for kv in sorted(carpetas.items())))
    if salida["faltan_carpetas"]:
        print("Faltan carpetas de la estructura: " + ", ".join(salida["faltan_carpetas"]))
    if NO_DESCARGADOS:
        print("OJO: %d archivo(s) no están descargados de iCloud (ábrelos en Finder u Obsidian antes de ordenar):"
              % len(NO_DESCARGADOS))
        for x in NO_DESCARGADOS[:10]:
            print("  " + x)
    if repetidos:
        print("Archivos con el mismo nombre (conviene distinguirlos): %d" % len(repetidos))
        for k, v in list(repetidos.items())[:10]:
            print("  %s: %s" % (k, ", ".join(v)))
    print("Enlaces que ya estaban rotos antes de ordenar: %d" % len(rotos))
    print("Detalle por archivo: %s" % destino)
    if getattr(args, "tabla", False) and por_ordenar:
        print("\nPOR ORDENAR (ruta | tipo | título | palabras | usado por | vista previa):")
        for a in por_ordenar:
            print("%s | %s | %s | %s | %s | %s" % (
                a["ruta"], a["categoria"], a.get("titulo") or "-", a.get("palabras", "-"),
                len(a["usado_por"]), (a.get("vista_previa") or "")[:140]))


# ---------------------------------------------------------------- respaldo

def cmd_respaldo(args):
    raiz = os.path.abspath(args.raiz)
    carpeta = os.path.join(raiz, ".brainme", "respaldos")
    os.makedirs(carpeta, exist_ok=True)
    destino = os.path.join(carpeta, "respaldo-%s.zip" % ahora())
    n = 0
    with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as z:
        for d, carpetas, archivos in os.walk(raiz):
            rel_d = os.path.relpath(d, raiz)
            carpetas[:] = [c for c in carpetas
                           if not (rel_d == "." and c in {".brainme", "graphify-out", ".git", ".trash"})]
            for a in archivos:
                if a.lower() in IGNORAR_ARCHIVOS:
                    continue
                ruta = os.path.join(d, a)
                z.write(ruta, os.path.relpath(ruta, raiz))
                n += 1
    print("Respaldo creado: %s (%d archivos, %.1f MB)" % (destino, n, os.path.getsize(destino) / 1e6))


# ------------------------------------------------------------ frontmatter

def _valor_yaml(v):
    if isinstance(v, list):
        return "[" + ", ".join(_valor_yaml(x) for x in v) + "]"
    s = str(v)
    if s == "" or re.search(r"[:#\[\]{},&*!|>'\"%@`]", s) or s != s.strip():
        return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return s


def fusionar_frontmatter(texto, campos, tags):
    """Agrega campos que falten y tags nuevos. Nunca borra ni cambia lo existente."""
    tags = [t for t in (slug_tag(x) for x in tags) if t]
    if not campos and not tags:
        return texto
    if texto.startswith("---\n---"):
        texto = "---\n\n---" + texto[7:]
    if texto.startswith("---\n") and texto.find("\n---", 3) > 0:
        fin = texto.find("\n---", 3)
        fm_lineas = texto[4:fin].split("\n") if texto[4:fin] else []
        resto = texto[fin:]
    else:
        fm_lineas, resto = [], None
    presentes = {m.group(1) for m in (re.match(r"^([A-Za-z_][\w\-]*)\s*:", l) for l in fm_lineas) if m}
    for k, v in campos.items():
        if k not in presentes and k != "tags":
            fm_lineas.append("%s: %s" % (k, _valor_yaml(v)))
    if tags:
        idx = next((i for i, l in enumerate(fm_lineas) if re.match(r"^tags\s*:", l)), None)
        if idx is None:
            fm_lineas.append("tags: [%s]" % ", ".join(tags))
        else:
            valor = fm_lineas[idx].split(":", 1)[1].strip()
            if valor.startswith("["):
                actuales = [x.strip().strip("\"'") for x in valor.strip("[]").split(",") if x.strip()]
                nuevos = actuales + [t for t in tags if t not in actuales]
                fm_lineas[idx] = "tags: [%s]" % ", ".join(nuevos)
            elif valor == "":
                j, actuales, sangria = idx + 1, [], "  "
                while j < len(fm_lineas) and re.match(r"^\s*-\s*", fm_lineas[j]):
                    sangria = re.match(r"^(\s*)-", fm_lineas[j]).group(1)
                    actuales.append(fm_lineas[j].split("-", 1)[1].strip().strip("\"'"))
                    j += 1
                agregar = ["%s- %s" % (sangria, t) for t in tags if t not in actuales]
                fm_lineas[j:j] = agregar
            else:
                actuales = [x.strip().strip("\"'") for x in valor.split(",") if x.strip()]
                nuevos = actuales + [t for t in tags if t not in actuales]
                fm_lineas[idx] = "tags: [%s]" % ", ".join(nuevos)
    bloque = "---\n" + "\n".join(fm_lineas)
    if resto is None:
        return bloque + "\n---\n\n" + texto.lstrip("\n")
    return bloque + resto


# ------------------------------------------------------------------- mover

def ejecutar_movimientos(raiz, movimientos, comun=None, etiqueta="orden"):
    """movimientos: lista de dicts {de, a, frontmatter?, tags?}. Devuelve el registro."""
    comun = comun or {}
    vault = buscar_vault(raiz)
    rels = listar_archivos(raiz)
    viejo = Layout(raiz, vault, rels)

    # 1) Normalizar y validar el plan
    mapa, errores, extras = {}, [], {}
    destinos = {}
    for mv in movimientos:
        de = nfc(mv["de"]).strip("/")
        real = viejo.existe(de)
        if not real:
            errores.append("No existe: %s" % de)
            continue
        a = nfc(mv["a"])
        if a.endswith("/") or a == "":
            a = a + real.rsplit("/", 1)[-1]
        a = os.path.normpath(a).replace(os.sep, "/")
        if a.startswith("../") or a.startswith("/") or a.split("/")[0] in PROTEGIDAS:
            errores.append("Destino no permitido: %s" % a)
            continue
        if real.split("/")[0] in PROTEGIDAS:
            errores.append("Origen protegido: %s" % real)
            continue
        if a == real:
            continue
        mapa[real] = a
        extras[real] = mv
        destinos.setdefault(clave(a), []).append(real)
    movidos = set(mapa)
    for k, v in destinos.items():
        if len(v) > 1:
            errores.append("Varios archivos irían a %s: %s" % (k, ", ".join(v)))
    for real, a in mapa.items():
        ocupado = viejo.existe(a)
        if ocupado and ocupado not in movidos:
            errores.append("Ya existe un archivo en el destino: %s" % a)
    if errores:
        return {"errores": errores}

    nuevos_rels = [mapa.get(r, r) for r in rels]
    nuevo = Layout(raiz, vault, nuevos_rels)
    rotos_antes = sum(1 for e in recorrer_enlaces(raiz, viejo) if not e["destino"])

    # 2) Leer y resolver todos los enlaces con la disposición ANTERIOR
    pendientes = {}  # rel_viejo -> (texto_nuevo, crlf, cambios)
    for rel in rels:
        ruta = os.path.join(raiz, rel)
        rel_n = mapa.get(rel, rel)
        if rel.lower().endswith(".md"):
            texto, crlf = leer_texto(ruta)
            if texto is None:
                continue
            cambios = [0]

            def fw(m, n, rel=rel, rel_n=rel_n, cambios=cambios):
                embed, interior = m.group(1), m.group(2)
                obj, frag, alias = partir_wiki(interior)
                destino_v = viejo.resolver_wiki(obj, rel) if obj else None
                if not destino_v:
                    return None
                destino_n = mapa.get(destino_v, destino_v)
                if nuevo.resolver_wiki(obj, rel_n) == destino_n:
                    return None
                cambios[0] += 1
                return texto_wiki_nuevo(nuevo, destino_n, frag, alias, embed)

            def fm_(m, n, rel=rel, rel_n=rel_n, cambios=cambios):
                embed, txt, url, titulo = m.group(1), m.group(2), m.group(3), m.group(4)
                limpia = url[1:-1] if url.startswith("<") else url
                if es_url_externa(limpia):
                    return None
                camino, _, frag = limpia.partition("#")
                if not camino:
                    return None
                destino_v, estilo = viejo.resolver_md(camino, rel)
                if not destino_v:
                    return None
                destino_n = mapa.get(destino_v, destino_v)
                if nuevo.resolver_md(camino, rel_n)[0] == destino_n:
                    return None
                cambios[0] += 1
                nueva = url_md_nueva(nuevo, destino_n, rel_n, estilo, url)
                if frag:
                    nueva = nueva[:-1] + "#" + frag + ">" if nueva.startswith("<") else nueva + "#" + frag
                return "%s[%s](%s%s)" % (embed, txt, nueva, titulo)

            texto_n = transformar_enlaces(texto, fw, fm_)
            mv = extras.get(rel)
            if mv is not None:
                campos = dict(comun)
                campos.update(mv.get("frontmatter") or {})
                texto_fm = fusionar_frontmatter(texto_n, campos, mv.get("tags") or [])
                if texto_fm != texto_n:
                    texto_n = texto_fm
                    cambios[0] += 1
            if texto_n != texto:
                pendientes[rel] = (texto_n, crlf, cambios[0])
        elif rel.lower().endswith(".canvas"):
            texto, crlf = leer_texto(ruta)
            try:
                datos = json.loads(texto) if texto else None
            except ValueError:
                datos = None
            if not datos:
                continue
            n_camb = 0
            for nodo in datos.get("nodes", []):
                if nodo.get("type") == "file" and nodo.get("file"):
                    rel_obj = viejo.desde_vault(nfc(nodo["file"]))
                    rel_obj = viejo.existe(rel_obj) if rel_obj else None
                    if rel_obj and rel_obj in mapa:
                        nodo["file"] = nuevo.vault_rel(mapa[rel_obj])
                        n_camb += 1
            if n_camb:
                pendientes[rel] = (json.dumps(datos, ensure_ascii=False, indent="\t"), crlf, n_camb)

    # 3) Mover archivos
    hechos = []
    for real, a in mapa.items():
        origen = os.path.join(raiz, real)
        destino = os.path.join(raiz, a)
        os.makedirs(os.path.dirname(destino), exist_ok=True)
        if os.path.exists(destino) and clave(real) != clave(a):
            # destino liberado por otro movimiento aún no ejecutado: usar temporal
            tmp = destino + ".brainme-tmp"
            os.rename(origen, tmp)
            hechos.append((real, a, tmp))
            continue
        os.rename(origen, destino)
        hechos.append((real, a, None))
    for real, a, tmp in hechos:
        if tmp:
            os.rename(tmp, os.path.join(raiz, a))

    # 4) Escribir los textos corregidos en su ubicación nueva
    reescritos = []
    for rel, (texto_n, crlf, n) in pendientes.items():
        escribir_texto(os.path.join(raiz, mapa.get(rel, rel)), texto_n, crlf)
        reescritos.append({"archivo": mapa.get(rel, rel), "cambios": n})

    # 5) Borrar carpetas que quedaron vacías
    borradas = []
    candidatas = sorted({os.path.dirname(r) for r in mapa if "/" in r}, key=lambda c: -c.count("/"))
    for c in candidatas:
        partes = c.split("/")
        while partes:
            actual = "/".join(partes)
            abs_c = os.path.join(raiz, actual)
            if actual in ESTRUCTURA or partes[0] in PROTEGIDAS or actual in RAICES_ESTRUCTURA:
                break
            try:
                restos = [x for x in os.listdir(abs_c) if x.lower() not in IGNORAR_ARCHIVOS]
            except OSError:
                break
            if restos:
                break
            for x in os.listdir(abs_c):
                os.remove(os.path.join(abs_c, x))
            os.rmdir(abs_c)
            borradas.append(actual)
            partes = partes[:-1]

    final = Layout(raiz, vault, listar_archivos(raiz))
    rotos_despues = sum(1 for e in recorrer_enlaces(raiz, final) if not e["destino"])
    registro = {
        "fecha": ahora(), "tipo": etiqueta, "proyecto": raiz, "vault": vault,
        "enlaces_rotos_antes": rotos_antes, "enlaces_rotos_despues": rotos_despues,
        "nombres_repetidos_despues": repetidos_de(final),
        "movimientos": [{"de": d, "a": a} for d, a in mapa.items()],
        "archivos_con_enlaces_corregidos": reescritos,
        "carpetas_vacias_borradas": borradas,
    }
    carpeta = os.path.join(raiz, ".brainme", "registros")
    os.makedirs(carpeta, exist_ok=True)
    ruta_reg = os.path.join(carpeta, "%s-%s.json" % (etiqueta, registro["fecha"]))
    with open(ruta_reg, "w", encoding="utf-8") as f:
        json.dump(registro, f, ensure_ascii=False, indent=1)
    registro["ruta_registro"] = ruta_reg
    return registro


def informar_movimiento(reg):
    if reg.get("errores"):
        print("No se movió nada. Corrige el plan:")
        for e in reg["errores"]:
            print("  - " + e)
        sys.exit(2)
    n_enl = sum(x["cambios"] for x in reg["archivos_con_enlaces_corregidos"])
    print("Archivos movidos: %d" % len(reg["movimientos"]))
    print("Notas o canvas con enlaces o frontmatter actualizados: %d (%d cambios)"
          % (len(reg["archivos_con_enlaces_corregidos"]), n_enl))
    print("Carpetas vacías borradas: %d" % len(reg["carpetas_vacias_borradas"]))
    print("Enlaces rotos: %d antes, %d después%s" % (
        reg["enlaces_rotos_antes"], reg["enlaces_rotos_despues"],
        "" if reg["enlaces_rotos_despues"] <= reg["enlaces_rotos_antes"] else "  <- REVISAR"))
    if reg["nombres_repetidos_despues"]:
        print("Archivos que quedaron con el mismo nombre: %d (renómbralos para que los wikilinks sean inequívocos)"
              % len(reg["nombres_repetidos_despues"]))
    print("Registro (sirve para deshacer): %s" % reg["ruta_registro"])


def cmd_mover(args):
    raiz = os.path.abspath(args.raiz)
    with open(args.plan, encoding="utf-8") as f:
        plan = json.load(f)
    comun = dict(plan.get("frontmatter_comun") or {})
    reg = ejecutar_movimientos(raiz, plan.get("movimientos", []), comun, "orden")
    informar_movimiento(reg)


def cmd_deshacer(args):
    raiz = os.path.abspath(args.raiz)
    ruta = args.registro
    if not ruta:
        carpeta = os.path.join(raiz, ".brainme", "registros")
        regs = sorted(x for x in os.listdir(carpeta) if x.startswith("orden-")) if os.path.isdir(carpeta) else []
        if not regs:
            print("No hay ningún orden que deshacer.")
            return
        ruta = os.path.join(carpeta, regs[-1])
    with open(ruta, encoding="utf-8") as f:
        reg = json.load(f)
    inverso = [{"de": m["a"], "a": m["de"]} for m in reversed(reg["movimientos"])]
    nuevo = ejecutar_movimientos(raiz, inverso, None, "deshacer")
    informar_movimiento(nuevo)
    if not nuevo.get("errores"):
        os.rename(ruta, ruta.replace("orden-", "deshecho-orden-"))
        print("Nota: el frontmatter que se agregó al ordenar se conserva (no molesta).")


# ------------------------------------------------------------ estado

def leer_fm(texto):
    """Campos simples (clave: valor) del frontmatter."""
    campos = {}
    if texto and texto.startswith("---\n"):
        fin = texto.find("\n---", 3)
        for linea in texto[4:fin if fin > 0 else 0].split("\n"):
            m = re.match(r"^([A-Za-z_][\w\-]*)\s*:\s*(.*)$", linea)
            if m:
                campos[m.group(1)] = m.group(2).strip().strip("\"'")
    return campos


def python_de_graphify(raiz):
    marca = os.path.join(raiz, "graphify-out", ".graphify_python")
    if os.path.exists(marca):
        with open(marca, encoding="utf-8") as f:
            return f.read().strip()
    exe = shutil.which("graphify")
    if not exe:
        return None
    with open(exe, encoding="utf-8", errors="ignore") as f:
        primera = f.readline().strip()
    return primera[2:] if primera.startswith("#!") else None


def correr(cmd, raiz):
    try:
        r = subprocess.run(cmd, cwd=raiz, capture_output=True, text=True, timeout=90)
        return r.stdout if r.returncode == 0 else None
    except (OSError, subprocess.SubprocessError):
        return None


RE_FECHA = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def limpiar_respaldos_grafo(raiz):
    """Graphify guarda en graphify-out/AAAA-MM-DD/ una copia del grafo antes de
    sobrescribirlo, una carpeta por día. Deja solo la más reciente."""
    out = os.path.join(raiz, "graphify-out")
    if not os.path.isdir(out):
        return []
    fechas = sorted(n for n in os.listdir(out)
                    if RE_FECHA.match(n) and os.path.isdir(os.path.join(out, n)))
    borradas = []
    for n in fechas[:-1]:
        try:
            shutil.rmtree(os.path.join(out, n))
            borradas.append(n)
        except OSError as e:
            print("No pude borrar el respaldo %s: %s" % (n, e))
    return borradas


def usa_graphify(raiz):
    """El proyecto eligió Graphify para la lectura profunda (configurar o versiones anteriores)."""
    return any(os.path.exists(os.path.join(raiz, n)) for n in ("graphify-out", ".graphifyignore"))


def cmd_sincroniza(args):
    raiz = os.path.abspath(args.raiz)
    if usa_graphify(raiz):
        sincroniza_graphify(raiz)
    print(linea_mapa(mapa_de_enlaces(raiz, listar_archivos(raiz))))


def sincroniza_graphify(raiz):
    exe = shutil.which("graphify")
    if not exe:
        print("Graphify no está instalado en este computador: el mapa de brainme funciona igual "
              "y la lectura profunda queda para un computador que lo tenga.")
        return
    r = subprocess.run([exe, "update", "."], cwd=raiz, capture_output=True, text=True)
    if r.returncode != 0:
        print("graphify update falló (ver references/problemas.md):")
        print("\n".join((r.stdout + r.stderr).strip().splitlines()[-8:]))
        sys.exit(r.returncode)
    print("Graphify al día.")
    borradas = limpiar_respaldos_grafo(raiz)
    if borradas:
        print("Respaldos viejos del grafo borrados: %s (queda el último)." % ", ".join(borradas))
    # Copias en conflicto de iCloud ("graph 2.json"): Graphify regenera el original
    out = os.path.join(raiz, "graphify-out")
    copias = [n for n in os.listdir(out) if RE_COPIA_CONFLICTO.match(n)] if os.path.isdir(out) else []
    for n in copias:
        try:
            os.remove(os.path.join(out, n))
        except OSError:
            pass
    if copias:
        print("Copias en conflicto del grafo borradas: %s." % ", ".join(copias))


NOMBRES_CAT = {"pdf": "PDFs", "imagen": "imágenes", "office": "archivos de Office",
               "web": "páginas HTML", "video_audio": "videos o audios", "otro": "otros archivos"}


def cmd_estado(args):
    raiz = os.path.abspath(args.raiz)
    texto_claude, _ = leer_texto(os.path.join(raiz, "CLAUDE.md"))
    configurado = bool(texto_claude and "## brainme" in texto_claude)
    print("Proyecto: %s | %s" % (os.path.basename(raiz),
                                 "configurado con brainme" if configurado else "SIN CONFIGURAR"))
    rels = listar_archivos(raiz)

    inbox = [r for r in rels if r.startswith("00_inbox/") and not r.startswith("00_inbox/archive/")]
    print("Inbox sin procesar: %d%s" % (len(inbox), (" -> " + ", ".join(
        r.split("/", 1)[1] for r in inbox[:8]) + (" ..." if len(inbox) > 8 else "")) if inbox else ""))

    por_ordenar = [r for r in rels if estado_de(r) == "por_ordenar"]
    print("Archivos fuera de la estructura (por ordenar): %d" % len(por_ordenar))

    abiertas, sin_archivar = [], []
    orden = {"alta": 0, "media": 1, "baja": 2}
    for r in rels:
        if r.startswith("03_open_questions/") and "/archive/" not in r and r.endswith(".md"):
            fm = leer_fm(leer_texto(os.path.join(raiz, r))[0] or "")
            if fm.get("estado", "abierta").lower().startswith("resuelta"):
                sin_archivar.append(r)
            else:
                abiertas.append((orden.get(fm.get("prioridad", "").lower(), 3),
                                 fm.get("prioridad") or "sin prioridad", r.rsplit("/", 1)[-1][:-3]))
    abiertas.sort()
    print("Preguntas abiertas: %d" % len(abiertas))
    for _, prio, nombre in abiertas[:10]:
        print("  [%s] [[%s]]" % (prio, nombre))
    if len(abiertas) > 10:
        print("  ... y %d más" % (len(abiertas) - 10))
    if sin_archivar:
        print("Preguntas marcadas como resueltas sin graduar: " +
              ", ".join("[[%s]]" % r.rsplit("/", 1)[-1][:-3] for r in sin_archivar))

    def recientes(prefijo, n):
        cands = [r for r in rels if r.startswith(prefijo) and r.endswith(".md") and "/archive/" not in r]
        cands.sort(key=lambda r: -os.path.getmtime(os.path.join(raiz, r)))
        return cands[:n]

    decisiones = recientes("02_decisions/", 5)
    if decisiones:
        print("Últimas decisiones: " + ", ".join(
            "[[%s]] (%s)" % (r.rsplit("/", 1)[-1][:-3], datetime.date.fromtimestamp(
                os.path.getmtime(os.path.join(raiz, r))).isoformat()) for r in decisiones))
    hace7 = datetime.datetime.now().timestamp() - 7 * 86400
    movidas = [r for r in rels if r.endswith(".md") and estado_de(r) == "ordenado"
               and not r.startswith("00_inbox/") and os.path.getmtime(os.path.join(raiz, r)) > hace7]
    print("Notas creadas o editadas en los últimos 7 días: %d" % len(movidas))
    estado_21(raiz, rels, texto_claude, configurado)

    datos = mapa_de_enlaces(raiz, rels)
    print(linea_mapa(datos))
    if datos[0]:
        print("Lo más conectado: " + ", ".join(
            "[[%s]] (%d)" % (nombre_nota(r), n) for r, n in mas_conectadas(datos, 5)))
    if not os.path.exists(os.path.join(raiz, "graphify-out", "graph.json")):
        return
    py = python_de_graphify(raiz)
    if py:
        codigo = ("import json; from pathlib import Path; from graphify.detect import detect_incremental; "
                  "r=detect_incremental(Path('.')); "
                  "print(json.dumps([f for v in r.get('new_files',{}).values() for f in v]))")
        salida = correr([py, "-c", codigo], raiz)
        try:
            pend = json.loads(salida.strip().splitlines()[-1]) if salida else None
        except (ValueError, IndexError):
            pend = None
        if pend is not None:
            otros = {}
            for f in pend:
                if os.path.splitext(f)[1].lower() not in (".md", ".txt"):
                    otros[categoria(f)] = otros.get(categoria(f), 0) + 1
            if otros:
                print("Lectura profunda (Graphify): recomendada para " + ", ".join(
                    "%d %s" % (v, NOMBRES_CAT.get(k, k)) for k, v in otros.items()))


def cmd_nombres(args):
    raiz = os.path.abspath(args.raiz)
    grupos = {}
    for r in listar_archivos(raiz):
        if r.endswith(".md") and estado_de(r) == "ordenado" and not r.startswith("00_inbox/") \
                and not aparte(r):
            grupos.setdefault(carpeta_de(r), []).append(r.rsplit("/", 1)[-1][:-3])
    for carpeta in sorted(grupos):
        print("%s (%d): %s" % (carpeta, len(grupos[carpeta]), " · ".join(sorted(grupos[carpeta]))))
    if not grupos:
        print("Aún no hay notas en la estructura.")


# ------------------------------------------------------------ a-wikilinks

def cmd_a_wikilinks(args):
    """Convierte links markdown internos entre notas ([t](nota.md)) en wikilinks.
    En Obsidian funcionan igual; Graphify solo lee bien los wikilinks cuando el nombre
    del archivo tiene espacios. Las imágenes y los links externos no se tocan."""
    raiz = os.path.abspath(args.raiz)
    layout = Layout(raiz, buscar_vault(raiz), listar_archivos(raiz))
    total, archivos = 0, 0
    for rel in layout.rels:
        if not rel.lower().endswith(".md") or estado_de(rel) == "se_queda":
            continue
        ruta = os.path.join(raiz, rel)
        texto, crlf = leer_texto(ruta)
        if texto is None:
            continue
        lineas = texto.split("\n")
        cambios = [0]

        def fm_(m, n, rel=rel, lineas=lineas, cambios=cambios):
            embed, txt, url = m.group(1), m.group(2), m.group(3)
            if embed or re.search(r"[\[\]|]", txt):
                return None
            limpia = url[1:-1] if url.startswith("<") else url
            if es_url_externa(limpia):
                return None
            camino, _, frag = limpia.partition("#")
            if not camino:
                return None
            destino, _ = layout.resolver_md(camino, rel)
            if not destino or not destino.lower().endswith(".md"):
                return None
            nombre = destino.rsplit("/", 1)[-1][:-3]
            objetivo = nombre if layout.unico(destino) else layout.vault_rel(destino)[:-3]
            frag_txt = "#" + unquote(frag) if frag else ""
            barra = "\\|" if lineas[n - 1].lstrip().startswith("|") else "|"
            alias = "" if txt.strip() in ("", nombre, objetivo) else barra + txt
            cambios[0] += 1
            return "[[%s%s%s]]" % (objetivo, frag_txt, alias)

        nuevo = transformar_enlaces(texto, lambda m, n: None, fm_)
        if nuevo != texto:
            escribir_texto(ruta, nuevo, crlf)
            total += cambios[0]
            archivos += 1
    print("Links markdown convertidos a wikilinks: %d (en %d notas)" % (total, archivos))


# --------------------------------------------------------------- verificar

def cmd_verificar(args):
    raiz = os.path.abspath(args.raiz)
    vault = buscar_vault(raiz)
    layout = Layout(raiz, vault, listar_archivos(raiz))
    enlaces = recorrer_enlaces(raiz, layout)
    rotos = [e for e in enlaces if not e["destino"]]
    repetidos = repetidos_de(layout)
    print("Enlaces internos revisados: %d" % len(enlaces))
    print("Enlaces a archivos que no existen: %d" % len(rotos))
    for e in rotos[:40]:
        print("  %s:%d  %s" % (e["origen"], e["linea"], e["texto"]))
    if len(rotos) > 40:
        print("  ... y %d más" % (len(rotos) - 40))
    print("Archivos con el mismo nombre: %d" % len(repetidos))
    for k, v in list(repetidos.items())[:20]:
        print("  %s: %s" % (k, ", ".join(v)))
    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump({"rotos": rotos, "repetidos": repetidos}, f, ensure_ascii=False, indent=1)


# ----------------------------------------------------------- mapa de enlaces

def nombre_nota(rel):
    return rel.rsplit("/", 1)[-1][:-3]


def mapa_de_enlaces(raiz, rels):
    """Wikilinks entre las notas de la estructura, leídos sin Graphify.
    Devuelve (notas, sale, entra, rotos): sale y entra van de cada nota a las notas que
    enlaza o que la enlazan; rotos son (origen, texto) de wikilinks a notas que no existen."""
    notas = notas_resumibles(rels)
    en_mapa = set(notas)
    sale = {r: set() for r in notas}
    entra = {r: set() for r in notas}
    rotos = []
    layout = Layout(raiz, buscar_vault(raiz), rels)
    layout.rels = notas  # recorrer solo las notas del mapa; el índice sigue completo
    for e in recorrer_enlaces(raiz, layout):
        if e["destino"] in en_mapa and e["destino"] != e["origen"]:
            sale[e["origen"]].add(e["destino"])
            entra[e["destino"]].add(e["origen"])
        elif not e["destino"] and e["tipo"] == "wiki":
            rotos.append((e["origen"], e["texto"]))
    return notas, sale, entra, rotos


def mas_conectadas(datos, n):
    notas, sale, entra, _ = datos
    grado = sorted(((len(sale[r] | entra[r]), r) for r in notas), key=lambda x: (-x[0], x[1]))
    return [(r, g) for g, r in grado[:n] if g]


# Donde rige la nota atómica; los entregables de 05_exports pueden quedar sueltos
CARPETAS_ATOMICAS = ("01_knowledge", "02_decisions", "03_open_questions", "04_sources")


def sueltas(datos):
    """Notas atómicas sin ningún enlace (islas) y las que no enlazan a ninguna otra."""
    notas, sale, entra, _ = datos
    atomicas = [r for r in notas if r.split("/")[0] in CARPETAS_ATOMICAS]
    islas = [r for r in atomicas if not sale[r] and not entra[r]]
    sin_salida = [r for r in atomicas if not sale[r] and entra[r]]
    return islas, sin_salida


def lista_notas(rels, n=8):
    return ", ".join("[[%s]]" % nombre_nota(r) for r in rels[:n]) + (" ..." if len(rels) > n else "")


def cuantos(n, singular, plural):
    return "%d %s" % (n, singular if n == 1 else plural)


def linea_mapa(datos):
    notas, sale, _, rotos = datos
    if not notas:
        return "Mapa: todavía no hay notas (nace con la primera)."
    conexiones = len({tuple(sorted((a, b))) for a in sale for b in sale[a]})
    islas, sin_salida = sueltas(datos)
    linea = "Mapa: %s, %s" % (cuantos(len(notas), "nota", "notas"),
                              cuantos(conexiones, "conexión", "conexiones"))
    extra = [cuantos(len(x), s, p) for x, s, p in (
        (islas, "isla", "islas"), (sin_salida, "sin enlaces de salida", "sin enlaces de salida"),
        (rotos, "enlace roto", "enlaces rotos")) if x]
    return linea + (" · " + ", ".join(extra) + " (revisa el jardín)" if extra else "")


def resumen_de(raiz, rel, largo=140):
    r = re.sub(r"\s+", " ", next((v for k, v in leer_fm(leer_texto(os.path.join(raiz, rel))[0] or "").items()
                                  if k in CAMPOS_RESUMEN and v), ""))
    return r if len(r) <= largo else r[:largo - 1] + "…"


def con_resumen(raiz, rel):
    r = resumen_de(raiz, rel)
    return "[[%s]]%s" % (nombre_nota(rel), " · " + r if r else "")


def buscar_nota(notas, nombre):
    n = clave(nombre.strip().strip("[]").split("|")[0].rsplit("/", 1)[-1])
    n = n[:-3] if n.endswith(".md") else n
    exactas = [r for r in notas if clave(nombre_nota(r)) == n]
    if exactas:
        return exactas[0]
    parecidas = [r for r in notas if n in clave(nombre_nota(r))]
    print("No encuentro la nota «%s» en el mapa.%s" % (
        nombre, " Parecidas: " + lista_notas(parecidas) if parecidas else ""))
    sys.exit(1)


def cmd_mapa(args):
    raiz = os.path.abspath(args.raiz)
    datos = mapa_de_enlaces(raiz, listar_archivos(raiz))
    notas, sale, entra, rotos = datos
    if args.nota:
        r = buscar_nota(notas, args.nota)
        print("%s (%s)" % (con_resumen(raiz, r), carpeta_de(r)))
        for titulo, grupo in (("Enlaza a", sale[r]), ("La enlazan", entra[r])):
            print("%s (%d):" % (titulo, len(grupo)))
            for v in sorted(grupo):
                print("  " + con_resumen(raiz, v))
        return
    if args.camino:
        a, b = (buscar_nota(notas, x) for x in args.camino)
        previa, cola = {a: None}, [a]
        while cola and b not in previa:
            actual = cola.pop(0)
            for v in sorted(sale[actual] | entra[actual]):
                if v not in previa:
                    previa[v] = actual
                    cola.append(v)
        if b not in previa:
            print("No hay camino: [[%s]] y [[%s]] no se conectan, ni a través de otras notas." % (
                nombre_nota(a), nombre_nota(b)))
            return
        camino = [b]
        while previa[camino[-1]]:
            camino.append(previa[camino[-1]])
        camino.reverse()
        cadena = "[[%s]]" % nombre_nota(camino[0])
        for x, y in zip(camino, camino[1:]):
            cadena += (" → " if y in sale[x] else " ← ") + "[[%s]]" % nombre_nota(y)
        print("Camino (%d pasos; la flecha va de la nota que enlaza a la enlazada): %s" % (
            len(camino) - 1, cadena))
        for x in camino:
            print("  " + con_resumen(raiz, x))
        return
    print(linea_mapa(datos))
    if not notas:
        return
    print("Lo más conectado: " + ", ".join(
        "[[%s]] (%d)" % (nombre_nota(r), n) for r, n in mas_conectadas(datos, 10)))
    islas, sin_salida = sueltas(datos)
    if islas:
        print("Islas, sin ningún enlace (%d): %s" % (len(islas), lista_notas(islas, 30)))
    if sin_salida:
        print("Sin enlaces de salida (%d): %s" % (len(sin_salida), lista_notas(sin_salida, 30)))
    if rotos:
        print("Enlaces rotos, a notas que no existen (%d):" % len(rotos))
        for origen, texto in rotos[:30]:
            print("  %s en [[%s]]" % (texto, nombre_nota(origen)))
        if len(rotos) > 30:
            print("  ... y %d más" % (len(rotos) - 30))


# ---------------------------------------------- resúmenes, autor y bitácora

RE_COPIA_CONFLICTO = re.compile(r"^.+ \d+\.[A-Za-z0-9]+$")
RE_VERSION_ARCHIVO = re.compile(r"^(?P<base>.+?)-v(?P<n>\d+)(?P<resto>-[^.]*)?\.(?P<ext>[^.]+)$")
CAMPOS_RESUMEN = ("resumen", "description", "summary")
PALABRAS_NOTA_LARGA = 1000
TAMANO_LOTE = 25


def aparte(rel):
    return any(p in APARTE for p in rel.split("/")[:-1])


def notas_resumibles(rels):
    """Notas de la estructura que deberían tener resumen (sin inbox ni carpetas aparte)."""
    return [r for r in rels if r.endswith(".md") and estado_de(r) == "ordenado"
            and not r.startswith("00_inbox/") and not aparte(r)
            and not RE_COPIA_CONFLICTO.match(r.rsplit("/", 1)[-1])]


def tiene_resumen(fm):
    return any((fm.get(k) or "").strip() for k in CAMPOS_RESUMEN)


def enlaces_entrantes(textos):
    """Cuántas notas enlazan a cada nombre (en minúsculas)."""
    cuenta = {}
    for texto in textos:
        for m in RE_WIKI.finditer(texto or ""):
            nombre = m.group(2).split("|")[0].split("#")[0].strip().rsplit("/", 1)[-1]
            if nombre.lower().endswith(".md"):
                nombre = nombre[:-3]
            cuenta[clave(nombre)] = cuenta.get(clave(nombre), 0) + 1
    return cuenta


def notas_sin_resumen(raiz, rels):
    """Notas sin resumen, primero las más enlazadas y después las más recientes."""
    textos, faltan = {}, []
    for r in notas_resumibles(rels):
        textos[r] = leer_texto(os.path.join(raiz, r))[0] or ""
        if not tiene_resumen(leer_fm(textos[r])):
            faltan.append(r)
    entrantes = enlaces_entrantes(textos.values())
    faltan.sort(key=lambda r: (-entrantes.get(clave(r.rsplit("/", 1)[-1][:-3]), 0),
                               -os.path.getmtime(os.path.join(raiz, r))))
    return faltan


def cmd_sin_resumen(args):
    raiz = os.path.abspath(args.raiz)
    faltan = notas_sin_resumen(raiz, listar_archivos(raiz))
    if not faltan:
        print("Todas las notas tienen resumen.")
        return
    if not args.lotes:
        print("Notas sin resumen: %d (primero las más enlazadas)" % len(faltan))
        for r in faltan[:10]:
            print("  " + r)
        if len(faltan) > 10:
            print("  ... y %d más" % (len(faltan) - 10))
        return
    carpeta = os.path.join(raiz, ".brainme", "resumenes")
    os.makedirs(carpeta, exist_ok=True)
    for n in os.listdir(carpeta):
        if n.startswith("lote-") and n.endswith(".json"):
            os.remove(os.path.join(carpeta, n))
    lotes = [faltan[i:i + args.lotes] for i in range(0, len(faltan), args.lotes)]
    rutas = []
    for i, lote in enumerate(lotes, 1):
        ruta = os.path.join(carpeta, "lote-%02d.json" % i)
        with open(ruta, "w", encoding="utf-8") as f:
            json.dump(lote, f, ensure_ascii=False, indent=1)
        rutas.append(os.path.relpath(ruta, raiz))
    print("Notas sin resumen: %d, en %d lotes de hasta %d:" % (len(faltan), len(lotes), args.lotes))
    for r in rutas:
        print("  " + r)


def cmd_poner_resumenes(args):
    """Agrega `resumen:` al frontmatter. No toca el texto de la nota ni un resumen que ya exista."""
    raiz = os.path.abspath(args.raiz)
    with open(os.path.join(raiz, args.desde) if not os.path.isabs(args.desde) else args.desde,
              encoding="utf-8") as f:
        resumenes = json.load(f)
    escritos, ya, faltan, largos = 0, 0, [], 0
    for rel, resumen in resumenes.items():
        rel = nfc(rel).strip("/")
        ruta = os.path.join(raiz, rel)
        resumen = " ".join(str(resumen).split())
        if not resumen or not rel.endswith(".md") or not os.path.isfile(ruta):
            faltan.append(rel)
            continue
        texto, crlf = leer_texto(ruta)
        if texto is None:
            faltan.append(rel)
            continue
        if tiene_resumen(leer_fm(texto)):
            ya += 1
            continue
        largos += len(resumen) > 300
        escribir_texto(ruta, fusionar_frontmatter(texto, {"resumen": resumen}, []), crlf)
        escritos += 1
    print("Resúmenes escritos: %d · ya tenían: %d · no encontrados: %d" % (escritos, ya, len(faltan)))
    if faltan:
        print("  No encontrados: " + ", ".join(faltan[:10]))
    if largos:
        print("  %d resúmenes pasan de 300 caracteres: conviene acortarlos." % largos)


def ruta_config():
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config")
    return os.path.join(base, "brainme", "config.json")


def leer_config():
    try:
        with open(ruta_config(), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def cmd_autor(args):
    """El autor vive en la configuración personal del computador, no en la carpeta
    compartida: cada socio firma con su nombre."""
    cfg = leer_config()
    if args.nombre:
        cfg["autor"] = " ".join(args.nombre.split())
        os.makedirs(os.path.dirname(ruta_config()), exist_ok=True)
        with open(ruta_config(), "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=1)
        print("Autor guardado en este computador: %s" % cfg["autor"])
    elif cfg.get("autor"):
        print("Autor: %s" % cfg["autor"])
    else:
        print('Autor: no definido. Pregúntale su nombre al usuario y corre: BRAIN autor "Nombre"')


BITACORA = "bitacora.md"
CABECERA_BITACORA = ("# Bitácora\n\nQué se hizo en cada sesión, quién lo hizo y qué sigue. "
                     "La escribe brainme; lo más reciente va al final.\n")
RE_ENTRADA = re.compile(r"^- (\d{2}:\d{2}) · (.+)$")
RE_HANDOFF = re.compile(r"^### (\d{2}:\d{2}) · Handoff · (.+)$")
RE_DIA = re.compile(r"^## (\d{4}-\d{2}-\d{2})\s*$")


def entradas_bitacora(texto):
    """Lista de entradas: {fecha, hora, tipo, linea, bloque}."""
    entradas, fecha, actual = [], "", None
    for linea in (texto or "").split("\n"):
        m_dia, m_ent, m_hand = RE_DIA.match(linea), RE_ENTRADA.match(linea), RE_HANDOFF.match(linea)
        if m_dia or m_ent or m_hand:
            actual = None
        if m_dia:
            fecha = m_dia.group(1)
        elif m_ent:
            entradas.append({"fecha": fecha, "hora": m_ent.group(1), "tipo": "entrada",
                             "linea": m_ent.group(2), "bloque": [linea]})
        elif m_hand:
            actual = {"fecha": fecha, "hora": m_hand.group(1), "tipo": "handoff",
                      "linea": "Handoff · " + m_hand.group(2), "bloque": [linea]}
            entradas.append(actual)
        elif actual is not None:
            actual["bloque"].append(linea)
    return entradas


def cmd_bitacora(args):
    raiz = os.path.abspath(args.raiz)
    ruta = os.path.join(raiz, BITACORA)
    texto = leer_texto(ruta)[0] or ""
    entradas = entradas_bitacora(texto)
    if args.ultimas:
        if not entradas:
            print("Bitácora: sin entradas todavía.")
        for e in entradas[-args.ultimas:]:
            print("%s %s · %s" % (e["fecha"], e["hora"], e["linea"]))
        return
    if args.handoff_ultimo:
        handoffs = [e for e in entradas if e["tipo"] == "handoff"]
        if not handoffs:
            print("No hay handoffs en la bitácora.")
            sys.exit(1)
        e = handoffs[-1]
        print("Handoff del %s %s\n" % (e["fecha"], e["hora"]) + "\n".join(e["bloque"][1:]).strip())
        return
    autor = leer_config().get("autor")
    if not autor:
        print('Falta el autor: pregúntale su nombre al usuario y corre BRAIN autor "Nombre".')
        sys.exit(2)
    if not args.texto and not args.handoff:
        print('Uso: BRAIN bitacora "qué se hizo" [--sigue "qué sigue"] | --handoff archivo | --ultimas N')
        sys.exit(1)
    momento = datetime.datetime.now()
    hoy, hora = momento.strftime("%Y-%m-%d"), momento.strftime("%H:%M")
    nuevo = texto if texto.strip() else CABECERA_BITACORA
    dias = [m.group(1) for m in map(RE_DIA.match, nuevo.split("\n")) if m]
    if not dias or dias[-1] != hoy:
        nuevo = nuevo.rstrip("\n") + "\n\n## %s\n" % hoy
    if args.handoff:
        with open(os.path.join(raiz, args.handoff), encoding="utf-8") as f:
            cuerpo = f.read().strip()
        nuevo = nuevo.rstrip("\n") + "\n\n### %s · Handoff · %s\n\n%s\n" % (hora, autor, cuerpo)
        print("Handoff guardado en %s: %s %s" % (BITACORA, hoy, hora))
    else:
        linea = " ".join(args.texto.split())
        if args.sigue:
            linea += " **Sigue:** " + " ".join(args.sigue.split())
        # Las entradas seguidas van juntas; después de un título o un handoff, una línea en blanco
        ultima = nuevo.rstrip("\n").split("\n")[-1]
        nuevo = nuevo.rstrip("\n") + ("\n" if RE_ENTRADA.match(ultima) else "\n\n")
        nuevo += "- %s · %s · %s\n" % (hora, autor, linea)
        print("Bitácora: %s %s · %s" % (hoy, hora, linea))
    escribir_texto(ruta, nuevo, False)


# --------------------------------------------------------------- consumo

def codificar_ruta(ruta):
    """Nombre de carpeta que Claude Code usa en ~/.claude/projects para una ruta."""
    salida = []
    for ch in ruta:
        if ch.isascii() and ch.isalnum():
            salida.append(ch)
        else:
            salida.append("--" if ord(ch) > 0xFFFF else "-")
    return "".join(salida)


def carpetas_de_registros(raiz):
    base = os.path.join(os.environ.get("CLAUDE_CONFIG_DIR") or
                        os.path.join(os.path.expanduser("~"), ".claude"), "projects")
    rutas = {os.path.abspath(raiz), os.path.realpath(raiz)}
    encontradas = []
    for r in rutas:
        for forma in ("NFC", "NFD"):
            d = os.path.join(base, codificar_ruta(unicodedata.normalize(forma, r)))
            if os.path.isdir(d) and d not in encontradas:
                encontradas.append(d)
    if encontradas or not os.path.isdir(base):
        return encontradas
    claves = {nfc(r) for r in rutas}
    for n in os.listdir(base):
        d = os.path.join(base, n)
        for a in (x for x in os.listdir(d) if x.endswith(".jsonl")) if os.path.isdir(d) else []:
            try:
                with open(os.path.join(d, a), encoding="utf-8") as f:
                    for _, linea in zip(range(20), f):
                        cwd = json.loads(linea).get("cwd")
                        if cwd:
                            if nfc(cwd) in claves:
                                encontradas.append(d)
                            break
            except (OSError, ValueError):
                pass
            break
    return encontradas


def contextos_de(ruta, desde):
    """Tokens de contexto de cada respuesta de Claude en un registro (sin repetir mensajes)."""
    vistos, ctxs, fechas = set(), [], []
    try:
        f = open(ruta, encoding="utf-8")
    except OSError:
        return ctxs, fechas
    with f:
        for linea in f:
            try:
                e = json.loads(linea)
            except ValueError:
                continue
            if e.get("type") != "assistant":
                continue
            m = e.get("message") or {}
            u = m.get("usage") or {}
            mid = m.get("id") or e.get("requestId") or e.get("uuid")
            if not u or mid in vistos:
                continue
            vistos.add(mid)
            fecha = (e.get("timestamp") or "")[:10]
            if desde and fecha and fecha < desde:
                continue
            ctx = sum(u.get(k) or 0 for k in
                      ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"))
            if ctx > 0:
                ctxs.append(ctx)
                fechas.append(fecha)
    return ctxs, fechas


def miles(n):
    return format(int(round(n)), ",").replace(",", ".")


def cmd_consumo(args):
    raiz = os.path.abspath(args.raiz)
    carpetas = carpetas_de_registros(raiz)
    if not carpetas:
        print("No encontré registros de Claude Code para esta carpeta.")
        return
    sesiones, ayudantes = [], []
    for c in carpetas:
        for d, _, archivos in os.walk(c):
            for a in archivos:
                if not a.endswith(".jsonl"):
                    continue
                ctxs, fechas = contextos_de(os.path.join(d, a), args.desde)
                if ctxs:
                    (sesiones if d == c else ayudantes).append((min(fechas), ctxs))
    todos = sorted(x for _, cs in sesiones for x in cs)
    if not todos:
        print("No hay respuestas registradas%s." % (" desde " + args.desde if args.desde else ""))
        return
    fechas = sorted(f for f, _ in sesiones)
    p90 = todos[int(len(todos) * 0.9) - 1 if len(todos) >= 10 else -1]
    print("Consumo de Claude Code en %s: %d sesiones, %d respuestas (%s a %s)." % (
        os.path.basename(raiz), len(sesiones), len(todos), fechas[0], fechas[-1]))
    print("Contexto por respuesta: promedio %s · mediana %s · el 10%% más pesado sobre %s · máximo %s." % (
        miles(sum(todos) / len(todos)), miles(todos[len(todos) // 2]), miles(p90), miles(todos[-1])))
    print("Total releído: %s millones de tokens." % ("%.1f" % (sum(todos) / 1e6)).replace(".", ","))
    if ayudantes:
        ctx_ay = [x for _, cs in ayudantes for x in cs]
        print("Ayudantes (subagentes): %d respuestas, promedio %s por respuesta." % (
            len(ctx_ay), miles(sum(ctx_ay) / len(ctx_ay))))
    print("Meta de brainme 2.1: menos de 150.000 por respuesta, en promedio.")
    print("Últimas sesiones (fecha · respuestas · promedio · máximo):")
    for fecha, cs in sorted(sesiones)[-args.sesiones:]:
        print("  %s · %d · %s · %s" % (fecha, len(cs), miles(sum(cs) / len(cs)), miles(max(cs))))


# --------------------------------------------------------------- migrar

LINEAS_IGNORE = ["bitacora.md", "**/_versiones/", "_taller/"]


def version_del_proyecto(texto):
    m = re.search(r"\*\*Versi[oó]n:\*\*\s*([\d.]+)", texto or "")
    return m.group(1) if m else None


def version_tupla(v):
    try:
        return tuple(int(x) for x in v.split("."))
    except (AttributeError, ValueError):
        return (2, 0, 0)


def seccion(texto, titulo):
    """(inicio, fin) de una sección '## titulo' hasta la siguiente '## ' o el final."""
    m = re.search(r"^## %s\s*$" % re.escape(titulo), texto or "", re.M)
    if not m:
        return None
    sig = re.search(r"^## ", texto[m.end():], re.M)
    return m.start(), (m.end() + sig.start()) if sig else len(texto)


def hooks_graphify(datos):
    """Copia de los hooks sin los avisos de Graphify, y cuántos quitó."""
    quitados, nuevos = 0, {}
    for evento, grupos in (datos.get("hooks") or {}).items():
        quedan = []
        for g in grupos:
            if any("graphify" in (h.get("command") or "") for h in g.get("hooks", [])):
                quitados += 1
            else:
                quedan.append(g)
        if quedan:
            nuevos[evento] = quedan
    return nuevos, quitados


def revisar_migracion(raiz):
    """Cambios que se aplican con `migrar --aplicar` (clave, descripción)."""
    cambios = []
    claude_md = leer_texto(os.path.join(raiz, "CLAUDE.md"))[0] or ""
    if version_tupla(version_del_proyecto(claude_md)) < version_tupla(VERSION_PROYECTO):
        cambios.append(("version", "Anotar en CLAUDE.md que el proyecto usa brainme %s" % VERSION))
    s = seccion(claude_md, "graphify")
    if s and re.search(r"codebase|modifying code", claude_md[s[0]:s[1]], re.I):
        cambios.append(("seccion_graphify", "Quitar de CLAUDE.md la sección ## graphify pensada para código"))
    ajustes = os.path.join(raiz, ".claude", "settings.json")
    try:
        with open(ajustes, encoding="utf-8") as f:
            if hooks_graphify(json.load(f))[1]:
                cambios.append(("aviso_graphify",
                                "Quitar el aviso de Graphify que aparece en cada búsqueda (.claude/settings.json)"))
    except (OSError, ValueError):
        pass
    if not os.path.exists(os.path.join(raiz, BITACORA)):
        cambios.append(("bitacora", "Crear %s" % BITACORA))
    ignore = leer_texto(os.path.join(raiz, ".graphifyignore"))[0]
    if ignore is not None:
        faltan = [l for l in LINEAS_IGNORE if l not in ignore.split("\n")]
        if faltan:
            cambios.append(("graphifyignore", "Agregar a .graphifyignore: " + ", ".join(faltan)))
    return cambios


def aplicar_cambio(raiz, clave_cambio):
    ruta_claude = os.path.join(raiz, "CLAUDE.md")
    if clave_cambio == "version":
        texto, crlf = leer_texto(ruta_claude)
        marca = "**Versión:** %s" % VERSION
        if version_del_proyecto(texto):
            texto = re.sub(r"\*\*Versi[oó]n:\*\*\s*[\d.]+", marca, texto, count=1)
        elif re.search(r"^.*Configurado con brainme.*$", texto, re.M):
            texto = re.sub(r"^(.*Configurado con brainme.*?)[ \t]*$", r"\1 · " + marca,
                           texto, count=1, flags=re.M)
        else:
            s = seccion(texto, "brainme")
            texto = texto[:s[1]].rstrip("\n") + "\n\n" + marca + "\n" + ("\n" + texto[s[1]:] if s[1] < len(texto) else "")
        escribir_texto(ruta_claude, texto, crlf)
    elif clave_cambio == "seccion_graphify":
        texto, crlf = leer_texto(ruta_claude)
        s = seccion(texto, "graphify")
        escribir_texto(ruta_claude, (texto[:s[0]].rstrip("\n") + "\n\n" + texto[s[1]:]).rstrip("\n") + "\n", crlf)
    elif clave_cambio == "aviso_graphify":
        ruta = os.path.join(raiz, ".claude", "settings.json")
        with open(ruta, encoding="utf-8") as f:
            datos = json.load(f)
        nuevos, _ = hooks_graphify(datos)
        if nuevos:
            datos["hooks"] = nuevos
        else:
            datos.pop("hooks", None)
        with open(ruta, "w", encoding="utf-8") as f:
            json.dump(datos, f, ensure_ascii=False, indent=2)
            f.write("\n")
    elif clave_cambio == "bitacora":
        escribir_texto(os.path.join(raiz, BITACORA), CABECERA_BITACORA, False)
    elif clave_cambio == "graphifyignore":
        ruta = os.path.join(raiz, ".graphifyignore")
        texto, crlf = leer_texto(ruta)
        faltan = [l for l in LINEAS_IGNORE if l not in texto.split("\n")]
        texto = texto.rstrip("\n") + "\n\n# brainme 2.1: bitácora, versiones viejas y generadores\n" + \
            "\n".join(faltan) + "\n"
        escribir_texto(ruta, texto, crlf)


def versiones_viejas(rels):
    """Entregables en 05_exports con una versión más nueva en la misma carpeta."""
    grupos = {}
    for r in rels:
        if not r.startswith("05_exports/") or aparte(r):
            continue
        m = RE_VERSION_ARCHIVO.match(r.rsplit("/", 1)[-1])
        if m:
            k = (carpeta_de(r), m.group("base"), m.group("resto") or "", m.group("ext").lower())
            grupos.setdefault(k, []).append((int(m.group("n")), r))
    viejas = []
    for lista in grupos.values():
        lista.sort()
        viejas += [r for _, r in lista[:-1]]
    return sorted(viejas)


def cmd_versiones(args):
    raiz = os.path.abspath(args.raiz)
    viejas = versiones_viejas(listar_archivos(raiz))
    if not viejas:
        print("No hay versiones viejas sueltas en 05_exports.")
        return
    print("Versiones viejas con una versión más nueva al lado: %d" % len(viejas))
    for r in viejas[:15]:
        print("  " + r)
    if len(viejas) > 15:
        print("  ... y %d más" % (len(viejas) - 15))
    if args.plan:
        plan = {"movimientos": [{"de": r, "a": carpeta_de(r) + "/_versiones/"} for r in viejas]}
        os.makedirs(os.path.dirname(os.path.join(raiz, args.plan)) or raiz, exist_ok=True)
        with open(os.path.join(raiz, args.plan), "w", encoding="utf-8") as f:
            json.dump(plan, f, ensure_ascii=False, indent=1)
        print("Plan escrito en %s: córrelo con BRAIN mover --plan %s" % (args.plan, args.plan))


def cmd_migrar(args):
    raiz = os.path.abspath(args.raiz)
    base = os.path.join(raiz, ".brainme", "migraciones")
    if args.deshacer:
        regs = sorted(os.listdir(base)) if os.path.isdir(base) else []
        if not regs:
            print("No hay migraciones que deshacer.")
            sys.exit(1)
        carpeta = os.path.join(base, regs[-1])
        with open(os.path.join(carpeta, "registro.json"), encoding="utf-8") as f:
            reg = json.load(f)
        for rel in reg["copias"]:
            shutil.copy2(os.path.join(carpeta, "originales", rel), os.path.join(raiz, rel))
        for rel in reg["creados"]:
            ruta = os.path.join(raiz, rel)
            if os.path.exists(ruta) and (leer_texto(ruta)[0] or "") == CABECERA_BITACORA:
                os.remove(ruta)
            elif os.path.exists(ruta):
                print("Dejo %s porque ya tiene entradas." % rel)
        shutil.rmtree(carpeta)
        print("Migración deshecha: %s restaurados." % ", ".join(reg["copias"] or ["nada"]))
        return
    claude_md = leer_texto(os.path.join(raiz, "CLAUDE.md"))[0] or ""
    if "## brainme" not in claude_md:
        print("Esta carpeta no está configurada con brainme (falta ## brainme en CLAUDE.md).")
        sys.exit(1)
    cambios = revisar_migracion(raiz)
    rels = listar_archivos(raiz)
    print("brainme del proyecto: %s · brainme del skill: %s" % (
        version_del_proyecto(claude_md) or "2.0 o anterior", VERSION))
    if not args.aplicar:
        print("Cambios automáticos (BRAIN migrar --aplicar): %d" % len(cambios))
        for _, desc in cambios:
            print("  - " + desc)
        print("Con ayudantes, después:")
        print("  - Notas sin resumen: %d (ayudante de resúmenes)" % len(notas_sin_resumen(raiz, rels)))
        print("  - Versiones viejas sueltas en 05_exports: %d (BRAIN versiones)" % len(versiones_viejas(rels)))
        if not leer_config().get("autor"):
            print("  - Autor de este computador: no definido (BRAIN autor)")
        return
    if not cambios:
        print("No hay cambios automáticos pendientes.")
        return
    carpeta = os.path.join(base, ahora())
    copias, creados = [], []
    for rel in ("CLAUDE.md", ".claude/settings.json", ".graphifyignore"):
        if os.path.exists(os.path.join(raiz, rel)):
            os.makedirs(os.path.dirname(os.path.join(carpeta, "originales", rel)), exist_ok=True)
            shutil.copy2(os.path.join(raiz, rel), os.path.join(carpeta, "originales", rel))
            copias.append(rel)
    for k, desc in cambios:
        if k == "bitacora":
            creados.append(BITACORA)
        aplicar_cambio(raiz, k)
        print("  ✓ " + desc)
    with open(os.path.join(carpeta, "registro.json"), "w", encoding="utf-8") as f:
        json.dump({"version": VERSION, "cambios": [k for k, _ in cambios], "copias": copias,
                   "creados": creados}, f, ensure_ascii=False, indent=1)
    print("Migración aplicada. Para deshacerla: BRAIN migrar --deshacer")


def estado_21(raiz, rels, texto_claude, configurado):
    """Líneas de estado que agregó brainme 2.1."""
    if configurado and version_tupla(version_del_proyecto(texto_claude)) < version_tupla(VERSION_PROYECTO):
        print("Migración pendiente: el proyecto usa brainme %s y el skill es %s (references/migrar.md)." % (
            version_del_proyecto(texto_claude) or "2.0 o anterior", VERSION))
    sin = notas_sin_resumen(raiz, rels)
    if sin:
        print("Notas sin resumen: %d (ayudante de resúmenes)" % len(sin))
    largas = []
    for r in notas_resumibles(rels):
        if r.split("/")[0] in ("01_knowledge", "02_decisions", "03_open_questions"):
            texto = leer_texto(os.path.join(raiz, r))[0] or ""
            if leer_fm(texto).get("largo", "").lower() not in ("si", "sí", "true") and \
                    analizar_nota(texto)["palabras"] > PALABRAS_NOTA_LARGA:
                largas.append(r.rsplit("/", 1)[-1][:-3])
    if largas:
        print("Notas largas (más de %s palabras): %d -> %s" % (
            miles(PALABRAS_NOTA_LARGA), len(largas), ", ".join("[[%s]]" % n for n in largas[:6]) +
            (" ..." if len(largas) > 6 else "")))
    existentes = {clave(r) for r in rels}
    conflictos = [r for r in rels if RE_COPIA_CONFLICTO.match(r.rsplit("/", 1)[-1]) and clave(
        re.sub(r" \d+(\.[A-Za-z0-9]+)$", r"\1", r)) in existentes]
    if conflictos:
        print("Copias en conflicto de iCloud: %d -> %s" % (len(conflictos), ", ".join(conflictos[:6])))
    viejas = versiones_viejas(rels)
    if viejas:
        print("Versiones viejas sueltas en 05_exports: %d (BRAIN versiones)" % len(viejas))
    entradas = entradas_bitacora(leer_texto(os.path.join(raiz, BITACORA))[0])
    if entradas:
        print("Bitácora (últimas %d):" % min(3, len(entradas)))
        for e in entradas[-3:]:
            print("  %s %s · %s" % (e["fecha"], e["hora"], e["linea"][:160]))
    if not leer_config().get("autor"):
        print("Autor de este computador: no definido (BRAIN autor)")


def main():
    p = argparse.ArgumentParser(description="Estado y orden de un proyecto brainme, sin romper enlaces.")
    p.add_argument("--raiz", default=".", help="carpeta del proyecto (por defecto, la actual)")
    sub = p.add_subparsers(dest="cmd")
    sub.add_parser("sincroniza")
    sub.add_parser("estado")
    ma = sub.add_parser("mapa")
    ma.add_argument("--nota", help="con qué notas se conecta, con su resumen")
    ma.add_argument("--camino", nargs=2, metavar=("A", "B"), help="cómo se conectan dos notas")
    sub.add_parser("nombres")
    inv = sub.add_parser("inventario")
    inv.add_argument("--tabla", action="store_true", help="imprime lo por ordenar en formato compacto")
    sub.add_parser("respaldo")
    m = sub.add_parser("mover")
    m.add_argument("--plan", required=True)
    v = sub.add_parser("verificar")
    v.add_argument("--json")
    d = sub.add_parser("deshacer")
    d.add_argument("--registro")
    sub.add_parser("a-wikilinks")
    sr = sub.add_parser("sin-resumen")
    sr.add_argument("--lotes", type=int, nargs="?", const=TAMANO_LOTE,
                    help="escribe lotes en .brainme/resumenes/ (por defecto de %d notas)" % TAMANO_LOTE)
    pr = sub.add_parser("poner-resumenes")
    pr.add_argument("--desde", required=True, help='JSON {"ruta/nota.md": "resumen"}')
    au = sub.add_parser("autor")
    au.add_argument("nombre", nargs="?")
    bi = sub.add_parser("bitacora")
    bi.add_argument("texto", nargs="?")
    bi.add_argument("--sigue")
    bi.add_argument("--handoff", help="archivo con el texto del handoff")
    bi.add_argument("--ultimas", type=int)
    bi.add_argument("--handoff-ultimo", action="store_true")
    co = sub.add_parser("consumo")
    co.add_argument("--desde", help="AAAA-MM-DD")
    co.add_argument("--sesiones", type=int, default=5)
    mi = sub.add_parser("migrar")
    mi.add_argument("--aplicar", action="store_true")
    mi.add_argument("--deshacer", action="store_true")
    ve = sub.add_parser("versiones")
    ve.add_argument("--plan", help="ruta del plan para BRAIN mover")
    sub.add_parser("version")
    args = p.parse_args()
    comandos = {"sincroniza": cmd_sincroniza, "estado": cmd_estado, "mapa": cmd_mapa, "nombres": cmd_nombres, "inventario": cmd_inventario, "respaldo": cmd_respaldo, "mover": cmd_mover,
                "verificar": cmd_verificar, "deshacer": cmd_deshacer,
                "a-wikilinks": cmd_a_wikilinks, "sin-resumen": cmd_sin_resumen,
                "poner-resumenes": cmd_poner_resumenes, "autor": cmd_autor,
                "bitacora": cmd_bitacora, "consumo": cmd_consumo, "migrar": cmd_migrar,
                "versiones": cmd_versiones, "version": lambda a: print(VERSION)}
    if args.cmd not in comandos:
        p.print_help()
        sys.exit(1)
    comandos[args.cmd](args)


if __name__ == "__main__":
    main()
