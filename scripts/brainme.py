#!/usr/bin/env python3
"""Herramienta de brainme: estado del proyecto y orden sin romper enlaces.

Subcomandos (se corren desde la raíz del proyecto):
  llevar       lleva algo al contexto general, después de revisar que no identifique al proyecto
  guia         una guía del skill con las plantillas que usa su flujo (inbox, guardar, jardin...)
  inbox        lo que hay en 00_inbox/, con el origen que llevarán sus notas
  leer         varias notas completas, con sus originales
  comprueba    después de escribir: qué quedó suelto, incompleto o con enlaces rotos
  estado       resumen compacto para ponerse al día (inbox, preguntas, decisiones, mapa)
  mapa         mapa de enlaces entre notas: lo más conectado, islas, enlaces rotos,
               los vecinos de una nota (--nota) o el camino entre dos (--camino)
  buscar       notas que hablan de algo, sin importar tildes ni plurales, y los originales
  procesado    saca del inbox un archivo ya procesado, sin escribir encima de otro
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
  versiones    plan para dar a cada entregable su carpeta, con las versiones anteriores en versiones/
  multiproyecto  panorama de una carpeta multiproyecto: contexto general y proyectos, sin abrir notas
  crear        carpetas, tablero y CLAUDE.md de un proyecto (suelto, contexto general o de un multiproyecto)
  jardin       lista de trabajo del jardín (sueño): tablero, supuestos, lo editado, duplicados, mapa
  archivar     pasa una nota obsoleta o fusionada a archive/, sin romper enlaces (o los reapunta)
  texto        texto de un Word, Excel o PowerPoint (.docx, .xlsx, .pptx), para leerlo

Solo usa la biblioteca estándar de Python (3.9 o superior).
"""

import argparse
import datetime
import difflib
import hashlib
import json
import os
import re
import shutil
import sys
import unicodedata
import zipfile
import xml.etree.ElementTree as ET
from urllib.parse import unquote

VERSION = "3.3.0"
# Última versión que cambió algo dentro de los proyectos: los anteriores piden migrar
VERSION_PROYECTO = "3.2.0"

# Las carpetas de 05_exports (reports/, presentations/...) aparecen con su primer entregable
ESTRUCTURA = [
    "00_inbox", "01_knowledge", "02_decisions", "03_open_questions/archive",
    "04_sources/literature", "04_sources/web", "05_exports",
]
RAICES_ESTRUCTURA = {"00_inbox", "01_knowledge", "02_decisions", "03_open_questions",
                     "04_sources", "05_exports"}
# Carpetas que nunca se recorren ni se mueven. graphify-out/ y .graphifyignore son de
# proyectos que usaron Graphify con versiones anteriores: se dejan como están.
PROTEGIDAS = {".git", ".obsidian", ".trash", ".claude", ".brainme", "graphify-out",
              "node_modules", ".claude-plugin"}
# Se quedan donde están (no son "por ordenar")
SE_QUEDAN_RAIZ = {"claude.md", "readme.md", "agents.md", ".graphifyignore", ".gitignore",
                  "bitacora.md", "tablero.md"}
CARPETAS_QUE_SE_QUEDAN = {"docs", "_taller"}
# Versiones viejas de entregables y generadores: fuera del índice, las búsquedas y el grafo.
# Las versiones viven en 05_exports/<tipo>/<entregable>/versiones/ (_versiones/ es de 3.0)
APARTE = {"_versiones", "_taller"}
VERSIONES = "versiones"
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
            print("%s | %s | %s | %s | %s | %s%s" % (
                a["ruta"], a["categoria"], a.get("titulo") or "-", a.get("palabras", "-"),
                len(a["usado_por"]), (a.get("vista_previa") or "")[:140],
                sugerir_destino(a["ruta"], [x["ruta"] for x in por_ordenar])))


TIPO_POR_CATEGORIA = {"imagen": "diagrams", "office": "data", "presentacion": "presentations"}


def sugerir_destino(ruta, todas):
    """Un archivo con número de versión es un entregable: la más alta va en la carpeta de su nombre
    sin versión, y las anteriores en su versiones/."""
    m = RE_VERSION_ARCHIVO.match(ruta.rsplit("/", 1)[-1])
    if not m:
        return ""
    hermanas = [RE_VERSION_ARCHIVO.match(r.rsplit("/", 1)[-1]) for r in todas]
    ultima = max(int(h.group("n")) for h in hermanas if h and clave(h.group("base")) == clave(m.group("base")))
    vieja = int(m.group("n")) < ultima
    return " -> entregable con versiones%s: 05_exports/%s/%s/%s" % (
        ", anterior" if vieja else "", TIPO_POR_CATEGORIA.get(categoria(ruta), "reports"),
        slug_tag(m.group("base")) or m.group("base"), VERSIONES + "/" if vieja else "")


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
    movidos = {m["a"] for m in reg["movimientos"]}
    faltan = [m for m in plan_entregables(listar_archivos(raiz))[0] if m["de"] in movidos]
    if faltan:
        print("Entregables recién movidos con versiones por ordenar: %d -> brainme versiones --plan .brainme/plan-versiones.json"
              % len(faltan))


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


TIPOS = {"01_knowledge": ("conocimiento", "tema"), "02_decisions": ("decision",), "03_open_questions": ("pregunta",),
         "04_sources": ("literatura", "fuente-web"), "05_exports": ("entregable",)}
RE_SIN_LLENAR = re.compile(r"(?<!\]\()<(?!https?:|!--|/)[^<>\n]*(?:[ |]|AAAA)[^<>\n]*>")


def sin_codigo(texto):
    """El texto sin bloques ni tramos de código."""
    texto = re.sub(r"^(```|~~~).*?^\1[ \t]*$", "", texto, flags=re.M | re.S)
    return re.sub(r"`[^`\n]*`", "", texto)


def por_corregir(raiz, r, texto, datos):
    """Lo que le falta a una nota según las convenciones; para un entregable, también lo que cita."""
    fm, carpeta, faltas = leer_fm(texto), r.split("/")[0], []
    tipo = plano(fm.get("tipo") or "")
    if not texto.startswith("---\n"):
        return ["sin frontmatter"]
    if tipo not in TIPOS.get(carpeta, (tipo,)):
        faltas.append("tipo «%s»: aquí va %s" % (fm.get("tipo") or "", " o ".join(TIPOS[carpeta])))
    campos = ["resumen"] + (["autor"] if carpeta[:2] in ("01", "02", "03") or (carpeta[:2] == "05" and not fm.get("archivo")) else [])
    if tipo in ("conocimiento", "decision", "pregunta"):
        campos.append("origen")
    campos += {"conocimiento": ["certeza", "como_se_sabe"], "decision": ["estado"], "pregunta": ["estado", "prioridad"]}.get(tipo, [])
    if tipo == "decision" and (fm.get("estado") or "").lower() == "tomada":
        campos.append("decidido_por")
    vacios = [c for c in campos if not (fm.get(c) or "").strip()]
    if vacios:
        faltas.append("falta " + ", ".join(vacios))
    if tipo == "conocimiento" and fm.get("certeza") and plano(fm["certeza"]) not in ("confirmado", "supuesto"):
        faltas.append("certeza «%s»: va confirmado o supuesto" % fm["certeza"])
    limpio = sin_codigo(texto)
    if "Instrucciones de la plantilla" in texto or RE_SIN_LLENAR.search(re.sub(r"<!--.*?-->", "", limpio, flags=re.S)):
        faltas.append("quedan partes de la plantilla sin llenar")
    if any(clave(partir_wiki(m.group(2))[0].rsplit("/", 1)[-1]) == clave(nombre_nota(r)) for m in RE_WIKI.finditer(limpio)):
        faltas.append("se enlaza a sí misma")
    cuerpo = re.sub(r"^## Texto exacto.*?(?=^## |\Z)", "", limpio, flags=re.M | re.S)
    if any("—" in l for l in cuerpo.split("\n") if not l.lstrip().startswith((">", "|"))):
        faltas.append("usa raya (—)")
    if carpeta == "05_exports":
        partes = r.split("/")
        if len(partes) != 4 or re.sub(r"-v\d+.*$", "", nombre_nota(r)) != partes[2]:
            faltas.append("va en su propia carpeta: 05_exports/<tipo>/<entregable>/")
        citadas = {x: leer_fm(leer_texto(os.path.join(raiz, x))[0] or "") for x in sorted(datos[1].get(r, ()))}
        viejas = [x for x, f in citadas.items() if f.get("archivada")]
        dudas = [x for x, f in citadas.items() if es_supuesto(f)]
        if viejas:
            faltas.append("cita notas archivadas: " + lista_notas(viejas, 6))
        if dudas and not re.search(r"supuest|sin (datos|confirmar|comprobar)|por confirmar|hipotesis", plano(texto)):
            faltas.append("cita supuestos y no lo dice: " + lista_notas(dudas, 6))
    return faltas


HISTORIA = os.path.join(".brainme", "historia.json")


def historia_de(texto):
    """Lo que una nota no pierde al ampliarla: su origen y las líneas de ## Actualizaciones."""
    s = re.search(r"^## Actualizaciones[ \t]*\n(.*?)(?=^## |\Z)", texto, re.M | re.S)
    lineas = [re.sub(r"\s+", " ", l).strip() for l in re.findall(
        r"^\s*[-*]\s*(\d{4}-\d{2}-\d{2}.*)$", s.group(1) if s else "", re.M)]
    return {"origen": leer_fm(texto).get("origen") or "", "lineas": lineas}


def leer_historia(raiz):
    try:
        with open(os.path.join(raiz, HISTORIA), encoding="utf-8") as f:
            h = json.load(f)
        return h if isinstance(h, dict) else None
    except (OSError, ValueError):
        return None


def guardar_historia(raiz, h):
    os.makedirs(os.path.join(raiz, ".brainme"), exist_ok=True)
    with open(os.path.join(raiz, HISTORIA), "w", encoding="utf-8") as f:
        json.dump(h, f, ensure_ascii=False, indent=1, sort_keys=True)


def usa_brainme(raiz):
    return es_proyecto(leer_texto(os.path.join(raiz, "CLAUDE.md"))[0])


def anotar_historia(raiz, rels):
    """Antes de escribir: cómo está cada nota. No pisa lo ya anotado, que es contra lo que se compara."""
    if not usa_brainme(raiz):
        return
    if not registro_jardin(raiz).get("tablero"):
        anotar_tablero(raiz)
    h = leer_historia(raiz)
    h = {} if h is None else h
    antes, hoy = json.dumps(h, sort_keys=True), datetime.date.today().isoformat()
    # La primera vez en el día se anota cómo amaneció cada nota; las que aparecen después son de hoy
    hay_base = any(v.get("dia") == hoy for v in h.values())
    for r in notas_resumibles(rels):
        k, texto = clave(nombre_nota(r)), leer_texto(os.path.join(raiz, r))[0] or ""
        if k not in h:
            h[k] = dict(historia_de(texto), huella="" if hay_base else huella(texto), dia=hoy)
        elif h[k].get("dia") != hoy:
            h[k].update(huella=huella(texto), dia=hoy)
    if json.dumps(h, sort_keys=True) != antes or not os.path.exists(os.path.join(raiz, HISTORIA)):
        guardar_historia(raiz, h)


def perdidas(raiz, notas):
    """Notas que perdieron su origen o una actualización desde la última vez que se comprobó. Lo
    que no perdió nada queda anotado como está."""
    h, faltas = leer_historia(raiz), []
    if h is None:
        return []
    for r in notas:
        k, hoy = clave(nombre_nota(r)), historia_de(leer_texto(os.path.join(raiz, r))[0] or "")
        antes = h.get(k)
        if antes is not None:
            f = []
            if antes["origen"] and antes["origen"] != hoy["origen"]:
                f.append("cambió su origen; devuélvelo (era «%s»)" % antes["origen"])
            f += ["falta o cambió una actualización; devuélvela («%s»)" % l for l in antes["lineas"] if l not in hoy["lineas"]]
            if f:
                faltas.append((r, f))
                continue
        h[k] = dict({"huella": "", "dia": datetime.date.today().isoformat()}, **dict(antes or {}, **hoy))
    guardar_historia(raiz, h)
    return faltas


def parecida(texto, rels):
    """Sugerencia para un enlace roto: la nota de nombre más parecido."""
    buscado = plano(claves_de_notas([texto])[0]).replace("-", " ")
    nombres = {plano(nombre_nota(r)).replace("-", " "): nombre_nota(r) for r in rels if r.endswith(".md")}
    cerca = difflib.get_close_matches(buscado, list(nombres), n=1, cutoff=0.8)
    return " (¿[[%s]]?)" % nombres[cerca[0]] if cerca else ""


def revision(raiz):
    """(datos del mapa, si hay algo escrito hoy, lo que falta corregir) de lo escrito en el último día."""
    rels = listar_archivos(raiz)
    datos, problemas = mapa_de_enlaces(raiz, rels), []
    conocidas = leer_historia(raiz)
    sin_historia = perdidas(raiz, datos[0])
    hoy = datetime.date.today().isoformat()
    # Lo escrito hoy: lo que no existía o dice otra cosa que al empezar el día. Sin ese registro,
    # la fecha del archivo
    if conocidas is None:
        desde = datetime.datetime.now().timestamp() - 86400
        nuevas = {r for r in datos[0] if os.path.getmtime(os.path.join(raiz, r)) > desde}
    else:
        nuevas = {r for r in datos[0] if (conocidas.get(clave(nombre_nota(r))) or {}).get("huella")
                  != huella(leer_texto(os.path.join(raiz, r))[0] or "")}
    islas, sin_salida = sueltas(datos)
    flojas = [r for r in islas + sin_salida if r in nuevas]
    if flojas:
        problemas.append("Escritas hoy, sin enlaces a otra nota (%d): %s" % (len(flojas), lista_notas(flojas, len(flojas))))
    solos = sorted(r for r in nuevas if r.startswith("05_exports/") and not datos[1][r])
    if solos:
        problemas.append("Entregables de hoy que no enlazan lo que los sustenta (%d): %s" % (
            len(solos), lista_notas(solos, len(solos))))
    for origen, texto in datos[3]:
        if origen in nuevas:
            problemas.append("Escrita hoy, con enlace roto: %s en [[%s]]%s" % (texto, nombre_nota(origen), parecida(texto, rels)))
    # El tablero se carga en cada sesión: sus enlaces también llegan a una nota
    tablero = leer_texto(os.path.join(raiz, TABLERO))[0] or ""
    layout = Layout(raiz, buscar_vault(raiz), rels)
    for m in RE_WIKI.finditer(sin_codigo(tablero)):
        if partir_wiki(m.group(2))[0] and not layout.resolver_wiki(partir_wiki(m.group(2))[0], TABLERO):
            problemas.append("Enlace roto en el tablero: %s%s" % (m.group(0), parecida(m.group(0), rels)))
    # Los campos se piden a las notas nuevas y a las que dicen que son de hoy
    faltas = ["  [[%s]]: %s" % (nombre_nota(r), "; ".join(f)) for r, f in sin_historia]
    for r in sorted(nuevas):
        texto = leer_texto(os.path.join(raiz, r))[0] or ""
        es_nueva = conocidas is not None and not (conocidas.get(clave(nombre_nota(r))) or {}).get("huella")
        declara = RE_FECHA.search(leer_fm(texto).get("fecha") or "") or historia_de(texto)["lineas"]
        if "/archive/" not in r and (es_nueva or (declara and fecha_de_cambio(raiz, r, texto) == hoy)):
            f = por_corregir(raiz, r, texto, datos)
            if f:
                faltas.append("  [[%s]]: %s" % (nombre_nota(r), "; ".join(f)))
    if faltas:
        problemas.append("Por corregir en lo escrito hoy (%d):\n%s%s" % (
            len(faltas), "\n".join(faltas[:15]), "\n  ... y %d más" % (len(faltas) - 15) if len(faltas) > 15 else ""))
    return datos, bool(nuevas), problemas


def cmd_comprueba(args):
    """Línea del mapa y, de lo escrito en el último día, lo que quedó sin enlaces, con enlaces
    rotos, incompleto o sin parte de su historia."""
    raiz = os.path.abspath(args.raiz)
    if args.dejar:
        h = leer_historia(raiz) or {}
        notas = {clave(nombre_nota(r)): r for r in notas_resumibles(listar_archivos(raiz))}
        for n in claves_de_notas(args.dejar):
            if n not in notas:
                print("No encuentro [[%s]]." % n)
                sys.exit(2)
            h[n] = dict(h.get(n) or {}, **historia_de(leer_texto(os.path.join(raiz, notas[n]))[0] or ""))
        guardar_historia(raiz, h)
    datos, hay, problemas = revision(raiz)
    print(linea_mapa(datos))
    if problemas:
        print("\n".join(problemas))
    elif hay:
        print("Lo escrito hoy está completo.")


NOMBRES_CAT = {"pdf": "PDFs", "imagen": "imágenes", "office": "archivos de Office",
               "presentacion": "presentaciones", "web": "páginas HTML", "video_audio": "videos o audios", "otro": "otros archivos"}


def cmd_estado(args):
    raiz = os.path.abspath(args.raiz)
    texto_claude, _ = leer_texto(os.path.join(raiz, "CLAUDE.md"))
    if es_multi(texto_claude):
        print("Esta es la raíz de una carpeta multiproyecto: su panorama sale con brainme multiproyecto.")
        return
    configurado = es_proyecto(texto_claude)
    if not configurado and multi_a_mano(raiz) == raiz:
        print("Esta carpeta agrupa proyectos brainme: es multiproyecto, armada a mano. Ofrece "
              "convertirla (references/multiproyecto.md) en vez de configurarla como proyecto.")
        return
    print("Proyecto: %s | %s" % (os.path.basename(raiz),
                                 "configurado con brainme" if configurado else "SIN CONFIGURAR"))
    rels = listar_archivos(raiz)
    estado_multi(raiz, rels, texto_claude, configurado)
    estado_tablero(raiz)

    inbox =[r for r in rels if r.startswith("00_inbox/") and not r.startswith("00_inbox/archive/")]
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
    estado_32(raiz, rels)

    datos = mapa_de_enlaces(raiz, rels)
    print(linea_mapa(datos))
    if datos[0]:
        print("Lo más conectado: " + ", ".join(
            "[[%s]] (%d)" % (nombre_nota(r), n) for r, n in mas_conectadas(datos, 5)))


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
    Los wikilinks van por nombre, así que mover una nota no los rompe. Las imágenes y los
    links externos no se tocan."""
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
    """Enlaces (wikilinks y links internos) entre las notas de la estructura.
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
    atomicas = [r for r in notas if r.split("/")[0] in CARPETAS_ATOMICAS and "/archive/" not in r]
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


def es_supuesto(fm):
    return (fm.get("certeza") or "").lower().startswith("supuest")


def con_resumen(raiz, rel):
    r = resumen_de(raiz, rel)
    fm = leer_fm(leer_texto(os.path.join(raiz, rel))[0] or "")
    marca = " (supuesto)" if es_supuesto(fm) else ""
    if fm.get("archivada"):
        por = fm.get("reemplazada_por")
        marca += " (archivada%s)" % (", reemplazada por " + por if por else "")
    return "[[%s]]%s%s" % (nombre_nota(rel), marca, " · " + r if r else "")


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
    detalle_mapa(datos)


def detalle_mapa(datos, dejadas=()):
    """Islas, notas sin enlaces de salida y enlaces rotos, con nombres."""
    rotos = [(o, t) for o, t in datos[3] if claves_de_notas([t])[0] not in dejadas]
    islas, sin_salida = ([r for r in lista if clave(nombre_nota(r)) not in dejadas] for lista in sueltas(datos))
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
    carpetas = rel.split("/")[:-1]
    return any(p in APARTE for p in carpetas) or (
        carpetas[:1] == ["05_exports"] and VERSIONES in carpetas)


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


INTERROGATIVAS = {"que": "qué", "cual": "cuál", "cuales": "cuáles", "cuanto": "cuánto", "cuanta": "cuánta", "cuantos": "cuántos",
                  "cuantas": "cuántas", "quien": "quién", "quienes": "quiénes", "como": "cómo", "donde": "dónde", "cuando": "cuándo"}


def limpiar_resumen(resumen):
    """Sin rótulos («Pregunta para encontrarla:», «Decisión:»), con ¿? y con las tildes que no dependen
    del sentido: -ción, -sión y la palabra que abre una pregunta."""
    resumen = re.sub(r"\s+", " ", str(resumen)).strip()
    resumen = re.sub(r"(^|[.!?]\s+)(?:pregunta(?: para encontrarla)?|decisi[oó]n|conocimiento|resumen)\s*:\s*", r"\1",
                     resumen, flags=re.I)
    resumen = re.sub(r"(?<=[csx])ion\b", "ión", resumen)

    def pregunta(m):
        palabra = m.group(2)
        bien = INTERROGATIVAS.get(plano(palabra))
        return m.group(1) + "¿" + (bien.capitalize() if bien else palabra) + m.group(3) if bien else m.group(0)

    resumen = re.sub(r"(^|[.!?]\s+)¿?([^\W\d_]+)([^.!?¿]*\?)", pregunta, resumen)
    return re.sub(r"(^|[.!?]\s+)([^\W\d_])", lambda m: m.group(1) + m.group(2).upper(), resumen)


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
        resumen = limpiar_resumen(resumen)
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
        print('Autor: no definido. Pregúntale su nombre al usuario y corre: brainme autor "Nombre"')


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
        print('Falta el autor: pregúntale su nombre al usuario y corre brainme autor "Nombre".')
        sys.exit(2)
    if not args.texto and not args.handoff:
        print('Uso: brainme bitacora "qué se hizo" [--sigue "qué sigue"] | --handoff archivo | --ultimas N')
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
    cuidar_tablero(raiz, hoy)
    # Es lo último que se corre en cada flujo: aquí sale lo que quedó por corregir
    problemas = revision(raiz)[2] if usa_brainme(raiz) else []
    if problemas:
        print("Antes de terminar, corrige:\n" + "\n".join(problemas))


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


# --------------------------------------------------------------- multiproyecto

PROYECTOS = "proyectos"
RE_ANIO = re.compile(r"^\d{4}$")
RE_SECCION_PROYECTO = re.compile(r"^## brainme[ \t]*$", re.M)
RE_SECCION_MULTI = re.compile(r"^## brainme · (?:multiproyecto|espacio)[ \t]*$", re.M)  # espacio: hasta la 3.2
PLANTILLAS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "templates")


def es_proyecto(texto):
    return bool(texto and RE_SECCION_PROYECTO.search(texto))


def es_multi(texto):
    return bool(texto and RE_SECCION_MULTI.search(texto))


def campo(texto, nombre):
    """Valor de '**Nombre:** valor', hasta el siguiente ' · **' o el fin de la línea."""
    m = re.search(r"\*\*%s:\*\*[ \t]*(.*?)(?=[ \t]+·[ \t]+\*\*|[ \t]*$)" % re.escape(nombre),
                  texto or "", re.M)
    return m.group(1).strip() if m else ""


def prefijo_de(texto):
    m = re.match(r"`?([A-Za-z0-9_-]+)", campo(texto, "Prefijo de notas"))
    return m.group(1) if m else ""


def nombre_multi(texto, base):
    return campo(texto, "Multiproyecto") or campo(texto, "Espacio") or os.path.basename(base)


def general_de(texto_multi):
    return campo(texto_multi, "Contexto general").strip("`/ ")


def buscar_multi(carpeta):
    """(raíz, texto del CLAUDE.md) de la carpeta multiproyecto que contiene a carpeta, o (None, None)."""
    d = carpeta
    while True:
        texto = leer_texto(os.path.join(d, "CLAUDE.md"))[0]
        if es_multi(texto):
            return d, texto
        padre = os.path.dirname(d)
        if padre == d:
            return None, None
        d = padre


def proyectos_bajo(carpeta, niveles=2):
    """Carpetas con un proyecto brainme dentro de carpeta, hasta esos niveles."""
    hallados = []
    try:
        hijos = sorted(os.listdir(carpeta))
    except OSError:
        return hallados
    for h in hijos:
        ruta = os.path.join(carpeta, h)
        if h.startswith(".") or h in PROTEGIDAS or not os.path.isdir(ruta):
            continue
        if es_proyecto(leer_texto(os.path.join(ruta, "CLAUDE.md"))[0]):
            hallados.append(ruta)
        elif niveles > 1:
            hallados += proyectos_bajo(ruta, niveles - 1)
    return hallados


def multi_a_mano(carpeta):
    """La carpeta, o una hasta 3 niveles arriba, con un CLAUDE.md propio y al menos dos
    proyectos brainme adentro, pero sin la sección de multiproyecto: una carpeta armada a mano."""
    casa, d = os.path.expanduser("~"), carpeta
    for _ in range(4):
        if d in (casa, os.path.dirname(d)):
            return None
        texto = leer_texto(os.path.join(d, "CLAUDE.md"))[0]
        if texto and not es_proyecto(texto) and len(proyectos_bajo(d, 3)) >= 2:
            return d
        d = os.path.dirname(d)
    return None


def ficha_comun(texto_multi):
    """Campos de '### Ficha de cada proyecto', siempre con estado y prefijo."""
    m = re.search(r"^### Ficha de cada proyecto[ \t]*\n(.*?)(?=^#|\Z)", texto_multi, re.M | re.S)
    campos = re.findall(r"^- \*\*(.+?):\*\*", m.group(1), re.M) if m else []
    for fijo in ("Prefijo de notas", "Estado"):
        if fijo not in campos:
            campos.insert(0, fijo)
    return campos


# --------------------------------------------------------------- tablero

TABLERO = "tablero.md"
LINEAS_TABLERO = 40
LINEA_TABLERO = "Lo vigente del proyecto está en su tablero: @tablero.md"
RE_IMPORTA_TABLERO = re.compile(r"@tablero\.md\b")
RE_PLACEHOLDER = re.compile(r"<[^<>\n]+>")


def crear_tablero(destino):
    """Crea tablero.md desde la plantilla si falta. True si lo creó."""
    ruta = os.path.join(destino, TABLERO)
    if os.path.exists(ruta):
        return False
    texto = leer_texto(os.path.join(PLANTILLAS, TABLERO))[0]
    escribir_texto(ruta, texto.replace("<AAAA-MM-DD>", datetime.date.today().isoformat(), 1), False)
    return True


def importar_tablero(texto):
    """CLAUDE.md con la línea que carga el tablero en cada sesión, al final de ## brainme."""
    s = seccion(texto, "brainme")
    if RE_IMPORTA_TABLERO.search(texto or "") or not s:
        return texto
    despues = texto[s[1]:]
    return texto[:s[1]].rstrip("\n") + "\n\n" + LINEA_TABLERO + "\n" + ("\n" + despues if despues else "")


def seccion_tablero(texto, titulo):
    """Viñetas de una sección del tablero, sin las que siguen siendo placeholder."""
    m = re.search(r"^## %s[ \t]*\n(.*?)(?=^## |\Z)" % re.escape(titulo), texto or "", re.M | re.S)
    vinetas = []
    for linea in (m.group(1).split("\n") if m else []):
        linea = re.sub(r"^\s*[-*]\s+(\[[ xX]\]\s+)?", "", linea, count=1) if re.match(r"^\s*[-*]\s", linea) else ""
        if linea.strip() and not RE_PLACEHOLDER.search(linea):
            vinetas.append(linea.strip())
    return vinetas


def cuerpo_tablero(texto):
    cuerpo = re.sub(r"\A---\n.*?\n---[ \t]*(?:\n|\Z)", "", texto, flags=re.S)
    return hashlib.sha1(re.sub(r"\s+", " ", cuerpo).strip().encode("utf-8")).hexdigest()[:16]


def anotar_tablero(raiz):
    """Cómo está el tablero, para saber después si de verdad cambió."""
    if not usa_brainme(raiz):
        return
    texto = leer_texto(os.path.join(raiz, TABLERO))[0]
    reg = registro_jardin(raiz)
    if texto and reg.get("tablero") != cuerpo_tablero(texto):
        reg["tablero"] = cuerpo_tablero(texto)
        guardar_jardin(raiz, reg)


def cuidar_tablero(raiz, hoy):
    """Devuelve al tablero su frontmatter si lo perdió, anota cuándo cambió y, si no cambió,
    recuerda sus próximos pasos."""
    ruta = os.path.join(raiz, TABLERO)
    tablero, crlf = leer_texto(ruta)
    if not tablero or not usa_brainme(raiz):
        return
    antes = registro_jardin(raiz).get("tablero")
    cambio = bool(antes) and antes != cuerpo_tablero(tablero)
    fecha = leer_fm(tablero).get("actualizado") or ""
    if not tablero.startswith("---\n"):
        escribir_texto(ruta, "---\ntipo: tablero\nactualizado: %s\n---\n\n%s" % (hoy, tablero.lstrip("\n")), crlf)
        print("Tablero: le devolví su encabezado.")
    elif cambio and fecha != hoy:
        nuevo = re.sub(r"^actualizado:.*$", "actualizado: " + hoy, tablero, count=1, flags=re.M)
        escribir_texto(ruta, nuevo if "actualizado:" in tablero.split("\n---", 1)[0] else
                       tablero.replace("---\n", "---\nactualizado: %s\n" % hoy, 1), crlf)
        print("Tablero: anoté que se actualizó hoy.")
    elif not cambio and fecha != hoy:
        pasos = [p.rstrip(".") for p in seccion_tablero(tablero, "Próximos pasos")]
        print("Tablero sin cambios hoy. %sSi lo hecho resuelve un paso, cambia el plan o comprueba una regla, ponlo al día (un paso resuelto sale de la lista)."
              % ("Próximos pasos: " + " / ".join(pasos[:4]) + ". " if pasos else ""))
    anotar_tablero(raiz)


def estado_tablero(raiz):
    """Línea del tablero en brainme estado: tamaño, fecha y qué le falta."""
    texto = leer_texto(os.path.join(raiz, TABLERO))[0]
    if texto is None:
        return
    lineas = len(texto.rstrip("\n").split("\n"))
    print("Tablero: %d líneas · actualizado %s" % (lineas, leer_fm(texto).get("actualizado") or "sin fecha"))
    cuerpo = texto.split("\n---", 1)[-1] if texto.startswith("---\n") else texto
    if RE_PLACEHOLDER.search(cuerpo):
        print("Tablero por llenar: quedan campos de la plantilla <...>")
    if lineas > LINEAS_TABLERO:
        print("Tablero largo: %d líneas (máximo %d): baja el detalle a notas y deja el enlace"
              % (lineas, LINEAS_TABLERO))


def cmd_crear(args):
    """Estructura y CLAUDE.md de un proyecto: suelto, contexto general o proyecto de una carpeta
    multiproyecto. Dentro de una, la carpeta se indica desde su raíz."""
    raiz = os.path.abspath(args.raiz)
    base, texto_multi = buscar_multi(raiz)
    destino = os.path.normpath(os.path.join(base or raiz, args.carpeta)) if args.carpeta else raiz
    nombre = os.path.basename(destino)
    if not base:
        base, texto_multi = buscar_multi(destino)
    ficha, prefijo = [], ""
    if base:
        general = general_de(texto_multi)
        anio = os.path.dirname(destino)
        if os.path.dirname(anio) == os.path.join(base, PROYECTOS) and RE_ANIO.match(os.path.basename(anio)):
            prefijo = (args.prefijo or "").strip().strip("`")
            if not prefijo:
                print("Un proyecto de una carpeta multiproyecto necesita --prefijo para sus notas (por ejemplo, acme-).")
                sys.exit(1)
            prefijo += "" if prefijo.endswith("-") else "-"
            for otro in proyectos_bajo(os.path.join(base, PROYECTOS)):
                if otro != destino and prefijo_de(leer_texto(os.path.join(otro, "CLAUDE.md"))[0]) == prefijo:
                    print("El prefijo %s ya lo usa %s: elige otro." % (prefijo, os.path.relpath(otro, base)))
                    sys.exit(1)
            ficha = ficha_comun(texto_multi)
        elif destino != os.path.join(base, general):
            print("En la carpeta multiproyecto %s, cada proyecto va en %s/<año>/ (por ejemplo, %s/%d/acme-precios) "
                  "y el contexto general es %s/." % (os.path.basename(base), PROYECTOS, PROYECTOS,
                                                     datetime.date.today().year, general))
            sys.exit(1)
    for c in ESTRUCTURA:
        os.makedirs(os.path.join(destino, c), exist_ok=True)
    ruta = os.path.join(destino, "CLAUDE.md")
    actual, crlf = leer_texto(ruta)
    if es_proyecto(actual):
        print("Carpetas listas. %s ya tenía CLAUDE.md con brainme: lo dejé como estaba." % nombre)
        return
    texto = (leer_texto(os.path.join(PLANTILLAS, "CLAUDE.md"))[0]
             .replace("<Nombre del proyecto>", nombre).replace("<nombre de la carpeta>", nombre)
             .replace("<AAAA-MM-DD>", datetime.date.today().isoformat()))
    texto = re.sub(r"(\*\*Versi[oó]n:\*\*\s*)[\d.]+", r"\g<1>" + VERSION, texto)
    if args.trata:
        texto = re.sub(r"<una o dos frases[^>]*>", lambda m: " ".join(args.trata.split()), texto)
    if ficha:
        valores = {"Estado": "activo", "Prefijo de notas": "`%s`" % prefijo}
        texto = texto.rstrip("\n") + "\n\n## Proyecto\n\n" + "\n".join(
            "- **%s:** %s" % (c, valores.get(c, "<por completar>")) for c in ficha) + "\n"
    if actual is not None:
        texto = actual.rstrip("\n") + "\n\n" + texto[texto.index("## brainme"):]
    escribir_texto(ruta, texto, crlf)
    crear_tablero(destino)
    rel = os.path.relpath(destino, base) if base else nombre
    print("Creé %s: carpetas, tablero.md y CLAUDE.md%s." % (rel, " con su ficha y el prefijo " + prefijo if ficha else ""))
    pendientes = [c for c in ficha if c not in ("Estado", "Prefijo de notas")]
    if pendientes:
        print("Ficha por completar: " + ", ".join(pendientes))
    if not args.trata:
        print("Falta «De qué trata» en CLAUDE.md: pídeselo al usuario.")


def resumen_de_proyecto(ruta):
    """(texto del CLAUDE.md, cifras, última entrada de bitácora) sin abrir notas."""
    texto = leer_texto(os.path.join(ruta, "CLAUDE.md"))[0] or ""
    rels = listar_archivos(ruta)
    preguntas = [r for r in rels if r.startswith("03_open_questions/") and "/archive/" not in r
                 and r.endswith(".md")]
    inbox = [r for r in rels if r.startswith("00_inbox/")]
    cifras = [cuantos(len(notas_resumibles(rels)), "nota", "notas"),
              cuantos(len(preguntas), "pregunta abierta", "preguntas abiertas")]
    if inbox:
        cifras.append("inbox %d" % len(inbox))
    if texto.count("<por completar>"):
        cifras.append("ficha: %s" % cuantos(texto.count("<por completar>"), "campo por completar",
                                            "campos por completar"))
    entradas = entradas_bitacora(leer_texto(os.path.join(ruta, BITACORA))[0])
    ultima = entradas[-1] if entradas else None
    return texto, " · ".join(cifras), ultima


def linea_ultima(ultima, ruta=None):
    pasos = seccion_tablero(leer_texto(os.path.join(ruta, TABLERO))[0], "Próximos pasos") if ruta else []
    sigue = "\n  sigue (tablero): %s" % pasos[0][:160] if pasos else ""
    if not ultima:
        return "sin bitácora todavía" + sigue
    return "última sesión: %s · %s" % (ultima["fecha"], ultima["linea"][:160]) + sigue


def cmd_multiproyecto(args):
    raiz = os.path.abspath(args.raiz)
    base, texto = buscar_multi(raiz)
    if not base:
        a_mano = multi_a_mano(raiz)
        if not a_mano:
            print("Esta carpeta no está dentro de una carpeta multiproyecto de brainme.")
            return
        print("Carpeta multiproyecto armada a mano, sin la sección de brainme: %s" % a_mano)
        print("Proyectos brainme adentro: " + ", ".join(os.path.relpath(p, a_mano) for p in proyectos_bajo(a_mano, 3)))
        print("Para convertirla: references/multiproyecto.md, parte «Convertir una carpeta armada a mano».")
        return
    general = general_de(texto)
    print("Multiproyecto: %s · contexto general: %s/" % (nombre_multi(texto, base), general))
    if es_proyecto(leer_texto(os.path.join(base, general, "CLAUDE.md"))[0]):
        _, cifras, ultima = resumen_de_proyecto(os.path.join(base, general))
        print("Contexto general: %s\n  %s" % (cifras, linea_ultima(ultima, os.path.join(base, general))))
    else:
        print("Contexto general: sin crear (brainme crear %s)" % general)
    carpeta = os.path.join(base, PROYECTOS)
    filas, cerrados, fuera = [], [], []
    for anio in sorted(os.listdir(carpeta)) if os.path.isdir(carpeta) else []:
        ruta_anio = os.path.join(carpeta, anio)
        if anio.startswith(".") or not os.path.isdir(ruta_anio):
            continue
        if not RE_ANIO.match(anio):
            fuera.append(anio)
            continue
        for h in sorted(os.listdir(ruta_anio)):
            ruta, rel = os.path.join(ruta_anio, h), anio + "/" + h
            if h.startswith(".") or not os.path.isdir(ruta):
                continue
            if not es_proyecto(leer_texto(os.path.join(ruta, "CLAUDE.md"))[0]):
                fuera.append(rel)
                continue
            ficha, cifras, ultima = resumen_de_proyecto(ruta)
            estado = campo(ficha, "Estado") or "sin estado en la ficha"
            if estado.startswith("cerrado"):
                cerrados.append(rel)
                continue
            filas.append(((ultima or {}).get("fecha", ""), rel, "- %s · %s · %s%s\n  %s\n  %s" % (
                rel, prefijo_de(ficha) or "sin prefijo", campo(ficha, "De qué trata")[:140],
                "" if estado == "activo" else " [%s]" % estado, cifras, linea_ultima(ultima, ruta))))
    filas.sort(key=lambda f: (f[0], f[1]), reverse=True)
    print("Proyectos abiertos (%d), el más reciente primero:" % len(filas) if filas else
          "Proyectos abiertos: ninguno (di «nuevo proyecto: <nombre>»).")
    for _, _, fila in filas:
        print(fila)
    if cerrados:
        print("Cerrados (%d): %s" % (len(cerrados), ", ".join(cerrados)))
    if fuera:
        print("En %s/, fuera de <año>/<proyecto> o sin brainme: %s" % (PROYECTOS, ", ".join(fuera)))


def estado_multi(raiz, rels, texto_claude, configurado):
    """Línea de brainme estado: a qué carpeta multiproyecto pertenece, y notas sin prefijo."""
    base, texto = buscar_multi(raiz)
    if not base:
        a_mano = multi_a_mano(raiz) if configurado else None
        if a_mano:
            print("Carpeta multiproyecto armada a mano: %s, con este y otros proyectos brainme adentro. "
                  "Ofrece convertirla (references/multiproyecto.md)." % os.path.relpath(a_mano, raiz))
        return
    prefijo = prefijo_de(texto_claude)
    general = raiz == os.path.join(base, general_de(texto))
    print("Multiproyecto: %s · %s" % (nombre_multi(texto, base),
                                "este es su contexto general" if general else
                                "proyecto con prefijo %s" % prefijo if prefijo else "proyecto sin prefijo en su ficha"))
    if prefijo:
        sin = [r for r in notas_resumibles(rels) if not nombre_nota(r).lower().startswith(prefijo.lower())]
        if sin:
            print("Notas sin el prefijo %s: %d -> %s" % (prefijo, len(sin), lista_notas(sin, 6)))

# --------------------------------------------------------------- migrar

def exports_vacias(raiz):
    """Carpetas de 05_exports sin ningún archivo: vuelven a aparecer con su primer entregable."""
    base = os.path.join(raiz, "05_exports")
    vacias = []
    for c in sorted(os.listdir(base)) if os.path.isdir(base) else []:
        ruta = os.path.join(base, c)
        if os.path.isdir(ruta) and not c.startswith(".") and not any(
                a.lower() not in IGNORAR_ARCHIVOS for _, _, archivos in os.walk(ruta) for a in archivos):
            vacias.append("05_exports/" + c)
    return vacias


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
    if not os.path.exists(os.path.join(raiz, TABLERO)) or not RE_IMPORTA_TABLERO.search(claude_md):
        cambios.append(("tablero", "Crear %s (objetivo, plan, próximos pasos y reglas aprendidas) y "
                        "cargarlo en cada sesión desde CLAUDE.md" % TABLERO))
    vacias = exports_vacias(raiz)
    if vacias:
        cambios.append(("exports_vacias", "Quitar de 05_exports las carpetas vacías (%s): aparecen con su "
                        "primer entregable" % ", ".join(c.split("/", 1)[1] + "/" for c in vacias)))
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
    elif clave_cambio == "tablero":
        crear_tablero(raiz)
        texto, crlf = leer_texto(ruta_claude)
        escribir_texto(ruta_claude, importar_tablero(texto), crlf)
    elif clave_cambio == "exports_vacias":
        for rel in exports_vacias(raiz):
            shutil.rmtree(os.path.join(raiz, rel))


def version_de(nombre):
    m = RE_VERSION_ARCHIVO.match(nombre)
    return int(m.group("n")) if m else None


def base_de(nombre):
    """Nombre del entregable: el del archivo sin versión ni extensión."""
    m = RE_VERSION_ARCHIVO.match(nombre)
    return m.group("base") if m else os.path.splitext(nombre)[0]


def plan_entregables(rels, archivar=()):
    """Cada entregable en 05_exports/<tipo>/<entregable>/: la versión vigente y su ficha
    (<entregable>.md) a la vista, las anteriores en versiones/. Agrupa por nombre sin versión.
    Devuelve (movimientos, grupos {carpeta: [destinos]}, por revisar, carpetas propias, sin tipo)."""
    grupos, propias, sin_tipo = {}, {}, []
    for r in rels:
        partes = r.split("/")
        if partes[0] != "05_exports":
            continue
        if len(partes) == 2:
            sin_tipo.append(r)
            continue
        tipo, dentro, archivo = partes[1], partes[2:-1], partes[-1]
        if not dentro:                                    # suelto en <tipo>/
            nombre, sub, vieja = base_de(archivo), [], False
        elif dentro[0] == "_versiones":                   # versiones apartadas por brainme 3.0
            nombre, sub, vieja = base_de(archivo), dentro[1:], True
        elif len(dentro) == 1:                            # ya en la carpeta del entregable
            nombre, sub, vieja = dentro[0], [], False
        elif dentro[1] in (VERSIONES, "_versiones") or dentro[1] in archivar:
            nombre, sub, vieja = dentro[0], dentro[2:], True
        else:                                             # carpeta del usuario dentro del entregable
            c = "/".join(partes[:4])
            propias[c] = propias.get(c, 0) + 1
            continue
        grupos.setdefault((tipo, nombre), []).append((r, archivo, sub, vieja))

    movimientos, resumen, revisar = [], {}, []
    for (tipo, nombre), items in sorted(grupos.items()):
        carpeta = "05_exports/%s/%s" % (tipo, nombre)
        vigente = max([version_de(a) for _, a, _, v in items if not v and version_de(a) is not None],
                      default=None)
        tallos = {}
        for _, a, _, _ in items:
            tallos[os.path.splitext(a)[0]] = tallos.get(os.path.splitext(a)[0], 0) + 1
        # Ficha: <entregable>.md; si no hay, el .md más nuevo que acompaña a un archivo de su
        # mismo nombre pasa a serlo
        nombre_ficha = nombre + ".md"
        ficha = next((r for r, a, _, v in items if a == nombre_ficha and not v), None)
        if not ficha:
            fichas = sorted((version_de(a) or 0, r) for r, a, _, _ in items
                            if a.endswith(".md") and tallos[os.path.splitext(a)[0]] > 1)
            ficha = fichas[-1][1] if fichas else None
        for r, a, sub, vieja in items:
            n = version_de(a)
            if r == ficha:
                destino = "%s/%s" % (carpeta, nombre_ficha)
            elif vieja or (n is not None and vigente is not None and n < vigente):
                destino = "/".join([carpeta, VERSIONES] + sub + [a])
            else:
                destino = "%s/%s" % (carpeta, a)
            resumen.setdefault(carpeta, []).append(destino)
            if destino != r:
                movimientos.append({"de": r, "a": destino})
                if len(items) == 1 and n is None and not re.match(r"^[a-z0-9._-]+$", nombre):
                    revisar.append(r)
    return movimientos, resumen, revisar, propias, sin_tipo


def cmd_versiones(args):
    raiz = os.path.abspath(args.raiz)
    movimientos, resumen, revisar, propias, sin_tipo = plan_entregables(
        listar_archivos(raiz), tuple(args.archivar or ()))
    tocadas = sorted({carpeta_de(m["a"]).split("/" + VERSIONES)[0] for m in movimientos})
    if not movimientos:
        print("Los entregables de 05_exports ya están cada uno en su carpeta.")
    else:
        print("Entregables por ordenar: %d archivos en %d carpetas" % (len(movimientos), len(tocadas)))
        for c in tocadas[:15]:
            destinos = resumen[c]
            vista = [d for d in destinos if carpeta_de(d) == c]
            print("  %s/: %d a la vista, %d en %s/" % (
                c[len("05_exports/"):], len(vista), len(destinos) - len(vista), VERSIONES))
        if len(tocadas) > 15:
            print("  ... y %d más" % (len(tocadas) - 15))
    if revisar:
        print("Revisa con el usuario (sin versión ni archivos hermanos; por defecto, carpeta propia):")
        for r in revisar:
            print("  " + r)
    if propias:
        print("Carpetas propias dentro de un entregable (se quedan; con --archivar <nombre> pasan a %s/):"
              % VERSIONES)
        for c, n in sorted(propias.items()):
            print("  %s/ (%s)" % (c, cuantos(n, "archivo", "archivos")))
    if sin_tipo:
        print("Sueltos en 05_exports/, sin carpeta de tipo: " + ", ".join(sin_tipo))
    if args.plan and movimientos:
        plan = {"movimientos": movimientos}
        os.makedirs(os.path.dirname(os.path.join(raiz, args.plan)) or raiz, exist_ok=True)
        with open(os.path.join(raiz, args.plan), "w", encoding="utf-8") as f:
            json.dump(plan, f, ensure_ascii=False, indent=1)
        print("Plan escrito en %s: córrelo con brainme mover --plan %s" % (args.plan, args.plan))


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
            creado = reg.get("textos", {}).get(rel, CABECERA_BITACORA)
            if os.path.exists(ruta) and (leer_texto(ruta)[0] or "") == creado:
                os.remove(ruta)
            elif os.path.exists(ruta):
                print("Dejo %s porque ya tiene contenido nuevo." % rel)
        for rel in reg.get("carpetas_quitadas", []):
            os.makedirs(os.path.join(raiz, rel), exist_ok=True)
        shutil.rmtree(carpeta)
        print("Migración deshecha: %s restaurados." % ", ".join(reg["copias"] or ["nada"]))
        return
    claude_md = leer_texto(os.path.join(raiz, "CLAUDE.md"))[0] or ""
    if not es_proyecto(claude_md):
        print("Esta carpeta no está configurada con brainme (falta ## brainme en CLAUDE.md).")
        sys.exit(1)
    cambios = revisar_migracion(raiz)
    rels = listar_archivos(raiz)
    print("brainme del proyecto: %s · brainme del skill: %s" % (
        version_del_proyecto(claude_md) or "2.0 o anterior", VERSION))
    if not args.aplicar:
        print("Cambios automáticos (brainme migrar --aplicar): %d" % len(cambios))
        for _, desc in cambios:
            print("  - " + desc)
        print("Con ayudantes, después:")
        print("  - Notas sin resumen: %d (ayudante de resúmenes)" % len(notas_sin_resumen(raiz, rels)))
        print("  - Entregables por ordenar en 05_exports: %d archivos (brainme versiones)"
              % len(plan_entregables(rels)[0]))
        if not leer_config().get("autor"):
            print("  - Autor de este computador: no definido (brainme autor)")
        return
    if not cambios:
        print("No hay cambios automáticos pendientes.")
        return
    carpeta = os.path.join(base, ahora())
    copias, creados = [], []
    quitadas = exports_vacias(raiz) if any(k == "exports_vacias" for k, _ in cambios) else []
    for rel in ("CLAUDE.md", ".claude/settings.json"):
        if os.path.exists(os.path.join(raiz, rel)):
            os.makedirs(os.path.dirname(os.path.join(carpeta, "originales", rel)), exist_ok=True)
            shutil.copy2(os.path.join(raiz, rel), os.path.join(carpeta, "originales", rel))
            copias.append(rel)
    for k, desc in cambios:
        if k == "bitacora":
            creados.append(BITACORA)
        if k == "tablero" and not os.path.exists(os.path.join(raiz, TABLERO)):
            creados.append(TABLERO)
        aplicar_cambio(raiz, k)
        print("  ✓ " + desc)
    textos = {rel: leer_texto(os.path.join(raiz, rel))[0] for rel in creados}
    with open(os.path.join(carpeta, "registro.json"), "w", encoding="utf-8") as f:
        json.dump({"version": VERSION, "cambios": [k for k, _ in cambios], "copias": copias,
                   "creados": creados, "textos": textos, "carpetas_quitadas": quitadas},
                  f, ensure_ascii=False, indent=1)
    print("Migración aplicada. Para deshacerla: brainme migrar --deshacer")


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
    por_ordenar = plan_entregables(rels)[0]
    if por_ordenar:
        print("Entregables por ordenar en 05_exports: %d archivos (brainme versiones)" % len(por_ordenar))
    entradas = entradas_bitacora(leer_texto(os.path.join(raiz, BITACORA))[0])
    if entradas:
        print("Bitácora (últimas %d):" % min(3, len(entradas)))
        for e in entradas[-3:]:
            print("  %s %s · %s" % (e["fecha"], e["hora"], e["linea"][:160]))
    if not leer_config().get("autor"):
        print("Autor de este computador: no definido (brainme autor)")


# --------------------------------------------------------------- jardín

JARDIN = os.path.join(".brainme", "jardin.json")
UMBRAL_JARDIN = 15
TANDA_JARDIN = 20
MIN_NOTAS_TEMA = 6
RE_FECHA = re.compile(r"\d{4}-\d{2}-\d{2}")
RE_ORIGEN_INBOX = re.compile(r"^(.+?)\s*\(inbox,\s*(\d{4}-\d{2}-\d{2})\)")
PALABRAS_VACIAS = {"de", "del", "la", "las", "el", "los", "en", "y", "o", "a", "al", "por", "para",
                   "con", "sin", "un", "una", "que", "se", "su", "sus", "es", "no", "decision", "pregunta"}
MAX_TEMA = 12  # más conexiones que esto: nota o tag general, no un tema
TAGS_GENERICOS = {"literatura", "fuente", "entregable", "tema", "conocimiento", "decision", "pregunta"}


def vigente(rel):
    return "/archive/" not in rel


def de_memoria(rel):
    """Notas vigentes de 01 a 04: las que el jardín verifica (los entregables no)."""
    return vigente(rel) and rel.split("/")[0] in CARPETAS_ATOMICAS


def registro_jardin(raiz):
    """{"ultimo": fecha del último jardín cerrado, "revisadas": {nota: huella}}."""
    try:
        with open(os.path.join(raiz, JARDIN), encoding="utf-8") as f:
            reg = json.load(f)
    except (OSError, ValueError):
        reg = {}
    reg = reg if isinstance(reg, dict) else {}
    if not isinstance(reg.get("revisadas"), dict):
        reg["revisadas"] = {}
    if not isinstance(reg.get("dejadas"), list):
        reg["dejadas"] = []
    return reg


def guardar_jardin(raiz, reg):
    os.makedirs(os.path.join(raiz, ".brainme"), exist_ok=True)
    with open(os.path.join(raiz, JARDIN), "w", encoding="utf-8") as f:
        json.dump(reg, f, ensure_ascii=False, indent=1, sort_keys=True)


CAMPOS_HUELLA = ("certeza", "como_se_sabe", "estado", "decidido_por", "reemplaza_a", "fiabilidad", "leido", "origen")


def enlace_plano(nombre, texto):
    """Un enlace interno según a qué nota apunta, sin carpeta: moverla o pasarlo a wikilink no lo cambia."""
    nombre = clave(unquote(nombre).strip().rsplit("/", 1)[-1])
    nombre = nombre[:-3] if nombre.endswith(".md") else nombre
    texto = texto.strip("|\\ ")
    return "[[%s%s]]" % (nombre, "|" + texto if texto and clave(texto) != nombre else "")


def huella(texto):
    """Cambia cuando cambia lo que la nota dice: su texto, a qué notas enlaza o cómo se sabe.
    El resumen, los tags y la carpeta de un enlace no la cambian."""
    fm = leer_fm(texto)
    cuerpo = re.sub(r"\A---\n.*?\n---[ \t]*(?:\n|\Z)", "", texto, flags=re.S)

    def md(m):
        url = m.group(3).strip("<>")
        return m.group(0) if es_url_externa(url) else enlace_plano(url.split("#", 1)[0], m.group(2))

    cuerpo = RE_WIKI.sub(lambda m: enlace_plano(partir_wiki(m.group(2))[0], partir_wiki(m.group(2))[2]),
                         RE_MDLINK.sub(md, cuerpo))
    partes = [fm.get(k) or "" for k in CAMPOS_HUELLA]
    return hashlib.sha1("\n".join(partes + [re.sub(r"\s+", " ", cuerpo).strip()]).encode("utf-8")).hexdigest()[:16]


def por_revisar(raiz, info):
    """Notas de memoria nuevas, o que cambiaron desde que el jardín las revisó: primero los
    supuestos, luego conocimiento, decisiones, preguntas y fuentes, de lo último a lo más viejo."""
    revisadas = registro_jardin(raiz)["revisadas"]
    faltan = [r for r in info if de_memoria(r) and revisadas.get(clave(nombre_nota(r))) != info[r][2]]
    faltan.sort(key=lambda r: (info[r][1], r), reverse=True)
    return sorted(faltan, key=lambda r: (not es_supuesto(info[r][0]), r.split("/")[0]))


def fecha_de_cambio(raiz, rel, texto):
    """La fecha más reciente que declara la nota (frontmatter y ## Actualizaciones). La del
    archivo cambia con cada sincronización de iCloud: queda para las notas sin fechas."""
    fm = leer_fm(texto)
    fechas = [m.group(0) for m in (RE_FECHA.search(fm.get(k) or "") for k in
                                   ("fecha", "fecha_resolucion", "actualizado", "archivada")) if m]
    s = re.search(r"^## Actualizaciones[ \t]*\n(.*?)(?=^## |\Z)", texto, re.M | re.S)
    if s:
        fechas += re.findall(r"^\s*[-*]\s*(\d{4}-\d{2}-\d{2})", s.group(1), re.M)
    if fechas:
        return max(fechas)
    return datetime.date.fromtimestamp(os.path.getmtime(os.path.join(raiz, rel))).isoformat()


def datos_de_notas(raiz, rels):
    """{nota: (frontmatter, fecha de cambio, huella)} de las notas de la estructura."""
    info = {}
    for r in notas_resumibles(rels):
        texto = leer_texto(os.path.join(raiz, r))[0] or ""
        info[r] = (leer_fm(texto), fecha_de_cambio(raiz, r, texto), huella(texto))
    return info


def archivo_original(raiz, origen, rels):
    """La ruta del original que nombra un origen: el que archivó el inbox o un archivo del
    proyecto (un contrato junto a su nota)."""
    m = RE_ORIGEN_INBOX.match(origen.strip())
    if m:
        carpeta = os.path.join(raiz, ".brainme", "inbox-procesado", m.group(2))
        nombre = clave(m.group(1).strip())
        for a in sorted(os.listdir(carpeta)) if os.path.isdir(carpeta) else []:
            if clave(a) == nombre or clave(os.path.splitext(a)[0]) == nombre:
                return ".brainme/inbox-procesado/%s/%s" % (m.group(2), a)
    wiki = RE_WIKI.search(origen)
    nombre = clave((partir_wiki(wiki.group(2))[0] if wiki else m.group(1) if m else origen).strip().rsplit("/", 1)[-1])
    base = os.path.join(raiz, ".brainme", "inbox-procesado")
    if not m and nombre and "." in nombre:  # sin fecha: el más reciente con ese nombre
        for d in sorted(os.listdir(base), reverse=True) if os.path.isdir(base) else []:
            for a in os.listdir(os.path.join(base, d)) if os.path.isdir(os.path.join(base, d)) else []:
                if clave(a) == nombre:
                    return ".brainme/inbox-procesado/%s/%s" % (d, a)
    return next((r for r in rels if nombre and not r.endswith(".md")
                 and clave(r.rsplit("/", 1)[-1]) == nombre), None)


def originales_de(raiz, rel, rels):
    """Los originales de la nota: el de su origen (o el PDF o la página de una fuente) y los
    que nombran sus ## Actualizaciones con «origen: ...»."""
    texto = leer_texto(os.path.join(raiz, rel))[0] or ""
    fm = leer_fm(texto)
    hallados = [archivo_original(raiz, fm.get(k) or "", rels) for k in ("origen", "pdf")]
    if not any(hallados):
        hallados.append(fm.get("source_url"))
    s = re.search(r"^## Actualizaciones[ \t]*\n(.*?)(?=^## |\Z)", texto, re.M | re.S)
    for m in re.finditer(r"origen:\s*(\[\[[^\]]+\]\]|.+?\(inbox,\s*\d{4}-\d{2}-\d{2}\)|[^\s·()]+\.\w{2,5}\b)", s.group(1) if s else ""):
        hallados.append(archivo_original(raiz, m.group(1), rels))
    hallados = [h for h in dict.fromkeys(hallados) if h]
    if not hallados and clave(fm.get("origen") or "").startswith("conversaci"):
        return "%s, sin original" % fm["origen"]
    return "original: " + ", ".join(hallados) if hallados else ""


def palabras_de_nombre(nombre, prefijo):
    if prefijo and clave(nombre).startswith(clave(prefijo)):
        nombre = nombre[len(prefijo):]
    return {p for p in re.split(r"[-_\s]+", clave(nombre)) if len(p) > 1 and p not in PALABRAS_VACIAS}


def posibles_duplicados(rels, prefijo, n=30):
    """Pares de notas de la misma carpeta con nombres casi iguales."""
    por_carpeta = {}
    for r in rels:
        por_carpeta.setdefault(r.split("/")[0], []).append((r, palabras_de_nombre(nombre_nota(r), prefijo)))
    pares = []
    for lista in por_carpeta.values():
        for i, (a, pa) in enumerate(lista):
            for b, pb in lista[i + 1:]:
                comunes = pa & pb
                if len(comunes) >= 2 and len(comunes) >= 0.6 * len(pa | pb):
                    pares.append((-len(comunes) / len(pa | pb), a, b))
    return [(a, b) for _, a, b in sorted(pares)[:n]]


def tags_de(fm):
    valor = (fm.get("tags") or "").strip().strip("[]")
    return [clave(t.strip().strip("\"'")) for t in valor.split(",") if t.strip()]


def originales_desde(raiz, ultimo):
    base = os.path.join(raiz, ".brainme", "inbox-procesado")
    total = 0
    for d in sorted(os.listdir(base)) if os.path.isdir(base) else []:
        if RE_FECHA.fullmatch(d) and (not ultimo or d > ultimo) and os.path.isdir(os.path.join(base, d)):
            total += len([a for a in os.listdir(os.path.join(base, d)) if not a.startswith(".")])
    return total


def claves_de_notas(nombres):
    claves = [clave(n.strip().strip("![]").split("|")[0].split("#")[0].rsplit("/", 1)[-1]) for n in nombres]
    return [n[:-3] if n.endswith(".md") else n for n in claves]


def dejar_en_jardin(raiz, info, nombres):
    """El usuario decide dejar como está una nota suelta o archivada, un enlace roto, o dos notas
    parecidas sin fusionar."""
    pedidas = sorted(set(claves_de_notas(nombres)))
    rotos = set(claves_de_notas(t for _, t in mapa_de_enlaces(raiz, listar_archivos(raiz))[3]))
    ajenas = [n for n in pedidas if n not in {clave(nombre_nota(r)) for r in info} | rotos]
    if ajenas or len(pedidas) > 2:
        print("--dejar lleva una nota, un enlace roto o un par de notas%s." % (": no encuentro " + ", ".join(ajenas) if ajenas else ""))
        sys.exit(2)
    reg = registro_jardin(raiz)
    reg["dejadas"] = sorted(set(reg["dejadas"]) | {" ~ ".join(pedidas)})
    guardar_jardin(raiz, reg)
    print("Queda así, y el jardín no lo vuelve a listar: %s." % " ~ ".join("[[%s]]" % n for n in pedidas))


def marcar_jardin(raiz, info, nombres, tanda, sin_revisar):
    """Anota las notas revisadas; sin nombres, cierra el jardín si no queda ninguna por revisar."""
    reg = registro_jardin(raiz)
    memoria = {clave(nombre_nota(r)): r for r in info if de_memoria(r)}
    pedidas = claves_de_notas(nombres)
    ajenas = [n for n in pedidas if n not in memoria]
    if ajenas:
        print("No encuentro estas notas, y no anoté ninguna: %s" % ", ".join(ajenas))
        sys.exit(2)
    if tanda:
        pedidas += [n for n in reg.get("tanda") or [] if n in memoria]
        if not pedidas:
            print("No hay una tanda por anotar: córrela con brainme jardin.")
            sys.exit(2)
    saltadas = [clave(nombre_nota(r)) for r in por_revisar(raiz, info)] if sin_revisar else []
    for n in pedidas + saltadas:
        reg["revisadas"][n] = info[memoria[n]][2]
    if tanda:
        reg["tanda"] = []
    reg["revisadas"] = {n: h for n, h in reg["revisadas"].items() if n in memoria}
    guardar_jardin(raiz, reg)
    faltan = por_revisar(raiz, info)
    if pedidas:
        print("Revisadas: %d. Por revisar: %d." % (len(set(pedidas)), len(faltan)))
        return
    if saltadas:
        print("Quedan sin revisar, por decisión del usuario: %s." % cuantos(len(saltadas), "nota", "notas"))
    if faltan:
        print("No cierro el jardín: quedan %s por revisar (brainme jardin)." % cuantos(len(faltan), "nota", "notas"))
        sys.exit(2)
    reg.update(ultimo=datetime.date.today().isoformat(), autor=leer_config().get("autor"))
    guardar_jardin(raiz, reg)
    print("Jardín cerrado el %s. brainme estado avisa cuando vuelva a tocar." % reg["ultimo"])


def cmd_jardin(args):
    """Lista de trabajo del jardín, de lo que cambia más rápido a lo estable."""
    raiz = os.path.abspath(args.raiz)
    rels = listar_archivos(raiz)
    anotar_historia(raiz, rels)
    info = datos_de_notas(raiz, rels)
    if args.hecho is not None:
        marcar_jardin(raiz, info, args.hecho, args.tanda, args.sin_revisar)
        return
    if args.dejar:
        dejar_en_jardin(raiz, info, args.dejar)
        return
    dejadas = set(registro_jardin(raiz)["dejadas"])
    prefijo = prefijo_de(leer_texto(os.path.join(raiz, "CLAUDE.md"))[0] or "")
    vigentes = [r for r in info if de_memoria(r)]
    ultimo = registro_jardin(raiz).get("ultimo")
    faltan = por_revisar(raiz, info)
    tanda = faltan[:TANDA_JARDIN]
    print("Jardín: %s. Por revisar: %s. Del inbox: %s." % (
        "último el %s" % ultimo if ultimo else "nunca cerrado", cuantos(len(faltan), "nota", "notas"),
        cuantos(originales_desde(raiz, ultimo), "original procesado", "originales procesados")))

    datos = mapa_de_enlaces(raiz, rels)
    excluir = TAGS_GENERICOS | ({clave(prefijo.rstrip("-"))} if prefijo else set())
    # Mismo tema: solo entre notas de conocimiento, decisiones y preguntas. Una nota o un
    # tag que conecta con muchas (más de MAX_TEMA) es general y no dice de qué trata otra.
    del_tema = [r for r in vigentes if r.split("/")[0] in ("01_knowledge", "02_decisions", "03_open_questions")]
    uso = {}
    for r in del_tema:
        for tg in set(tags_de(info[r][0])):
            uso[tg] = uso.get(tg, 0) + 1
    tags = {r: {tg for tg in tags_de(info[r][0]) if tg not in excluir and uso[tg] <= MAX_TEMA}
            for r in del_tema}

    def vecinos(r):
        return datos[1].get(r, set()) | datos[2].get(r, set())

    especificas = {r for r in datos[0] if len(vecinos(r)) <= MAX_TEMA}

    def mismo_tema(r):
        """Notas que comparten tags o enlaces específicos con r: donde un mismo hecho puede
        contarse distinto."""
        if r not in tags:
            return []
        vr, puntos = vecinos(r) & especificas, []
        for x in del_tema:
            p = len(tags[r] & tags[x]) + len(vr & vecinos(x)) + (x in vr)
            if x != r and p >= 2:
                puntos.append((-p, x))
        return [x for _, x in sorted(puntos)[:3]]

    estado_tablero(raiz)
    if tanda:
        print("Esta tanda (%d de %d), contra su original y las de su mismo tema:" % (len(tanda), len(faltan)))
    for r in tanda:
        fm = info[r][0]
        original, tema = originales_de(raiz, r, rels), mismo_tema(r)
        print("  [[%s]] (%s)%s%s%s" % (
            nombre_nota(r), info[r][1],
            " · supuesto: " + (fm.get("como_se_sabe") or "sin anotar cómo se sabe") if es_supuesto(fm) else "",
            " · " + original if original else "", " · mismo tema: " + lista_notas(tema) if tema else ""))
    reg = registro_jardin(raiz)
    if reg.get("tanda") != [clave(nombre_nota(r)) for r in tanda]:
        reg["tanda"] = [clave(nombre_nota(r)) for r in tanda]
        guardar_jardin(raiz, reg)
    if tanda:
        print("Para leerlas con sus originales: brainme leer --tanda")
        print("Cuando las hayas revisado todas: brainme jardin --hecho --tanda (o --hecho <notas>, si solo algunas)%s" % (
            ". Quedan %d para las tandas que siguen." % (len(faltan) - len(tanda)) if len(faltan) > len(tanda) else ""))
    sup = sorted(r for r in vigentes if es_supuesto(info[r][0]) and r not in faltan)
    if sup:
        print("Supuestos ya revisados que siguen sin confirmar (%d): %s" % (len(sup), lista_notas(sup, len(sup))))
    duplicados = [(a, b) for a, b in posibles_duplicados(vigentes, prefijo, 1000)
                  if " ~ ".join(sorted((clave(nombre_nota(a)), clave(nombre_nota(b))))) not in dejadas][:30]
    if duplicados:
        print("Posibles duplicados, por nombre: " + ", ".join(
            "[[%s]] ~ [[%s]]" % (nombre_nota(a), nombre_nota(b)) for a, b in duplicados))

    for r in sorted(info):
        if vigente(r) or r.startswith("03_open_questions/") or clave(nombre_nota(r)) in dejadas:
            continue
        por = info[r][0].get("reemplazada_por")
        desde = sorted(x for x in datos[2][r] if vigente(x) and clave(nombre_nota(x)) not in claves_de_notas([por or ""]))
        if desde:
            print("Enlaces a la nota archivada [[%s]]%s: en %s" % (
                nombre_nota(r), " (reemplazada por %s)" % por if por else "", lista_notas(desde)))
    print(linea_mapa(datos))
    detalle_mapa(datos, dejadas)

    conteo, con_tema = {}, set()
    for r in vigentes:
        fm = info[r][0]
        if (fm.get("tipo") or "").lower() == "tema":
            con_tema.update(tags_de(fm))
        elif r.split("/")[0] in ("01_knowledge", "02_decisions", "03_open_questions"):
            for t in tags_de(fm):
                conteo[t] = conteo.get(t, 0) + 1
    temas = sorted(((n, t) for t, n in conteo.items()
                    if n >= MIN_NOTAS_TEMA and t not in con_tema and t not in excluir), reverse=True)
    if temas:
        print("Tags de %d notas o más sin página de tema: %s" % (
            MIN_NOTAS_TEMA, ", ".join("%s (%d)" % (t, n) for n, t in temas[:8])))
    sin = [r for r in vigentes if r.startswith("01_knowledge/") and not info[r][0].get("certeza")
           and (info[r][0].get("tipo") or "conocimiento").lower() == "conocimiento"]
    if sin:
        print("Notas de conocimiento sin certeza: %d (márcala al verificar cada una)" % len(sin))
    print("Para cerrarlo, sin notas por revisar: brainme jardin --hecho")


def cmd_archivar(args):
    """Pasa una nota obsoleta o fusionada a <carpeta>/archive/, sin romper enlaces."""
    raiz = os.path.abspath(args.raiz)
    base = os.path.join(raiz, ".brainme", "archivados")
    if args.deshacer:
        regs = sorted(os.listdir(base)) if os.path.isdir(base) else []
        if not regs:
            print("No hay notas archivadas que deshacer.")
            sys.exit(1)
        carpeta = os.path.join(base, regs[-1])
        with open(os.path.join(carpeta, "registro.json"), encoding="utf-8") as f:
            reg = json.load(f)
        archivada = os.path.join(raiz, reg["a"])
        if os.path.exists(archivada):
            os.remove(archivada)
        for rel in reg["copias"]:
            os.makedirs(os.path.dirname(os.path.join(raiz, rel)), exist_ok=True)
            shutil.copy2(os.path.join(carpeta, "originales", rel), os.path.join(raiz, rel))
        try:
            os.rmdir(os.path.dirname(archivada))
        except OSError:
            pass
        shutil.rmtree(carpeta)
        print("Deshecho: [[%s]] volvió a %s/ y sus enlaces quedaron como estaban." % (
            nombre_nota(reg["de"]), carpeta_de(reg["de"])))
        return
    if not args.nota:
        print("Uso: brainme archivar <nota> [--por <nota>] [--repuntar] | --deshacer")
        sys.exit(1)
    rels = listar_archivos(raiz)
    vigentes = [r for r in notas_resumibles(rels) if vigente(r)]
    r = buscar_nota(vigentes, args.nota)
    if r.split("/")[0] not in ("01_knowledge", "02_decisions", "04_sources"):
        print("Se archivan notas de 01_knowledge, 02_decisions y 04_sources; las preguntas se gradúan (flujo Preguntas abiertas).")
        sys.exit(1)
    por = buscar_nota(vigentes, args.por) if args.por else None
    if por == r or (args.repuntar and not por):
        print("--por necesita otra nota vigente, y --repuntar necesita --por.")
        sys.exit(1)
    destino = r.split("/")[0] + "/archive/" + r.rsplit("/", 1)[-1]
    if os.path.exists(os.path.join(raiz, destino)):
        print("Ya hay una nota archivada en %s." % destino)
        sys.exit(1)

    layout = Layout(raiz, buscar_vault(raiz), rels)
    nombre = nombre_nota(r)
    nuevo_nombre = nombre_nota(por) if args.repuntar else nombre
    cuenta, cambios = [0], {}
    for rel in rels:
        if rel == r or aparte(rel) or not rel.lower().endswith((".md", ".canvas")):
            continue
        texto, crlf = leer_texto(os.path.join(raiz, rel))
        if texto is None:
            continue
        if rel.lower().endswith(".md"):
            # La nota que queda cuenta de dónde viene: su mención a la archivada no se repunta a sí misma
            repunta = args.repuntar and rel != por
            apunta = nuevo_nombre if repunta else nombre

            def fw(m, n, rel=rel, repunta=repunta, apunta=apunta):
                obj, frag, alias = partir_wiki(m.group(2))
                if not obj or layout.resolver_wiki(obj, rel) != r or (not repunta and "/" not in obj):
                    return None
                cuenta[0] += 1
                return "%s[[%s%s%s]]" % (m.group(1), apunta, "" if repunta else frag, alias)

            def fm_(m, n, rel=rel, apunta=apunta):
                url = m.group(3)
                limpia = (url[1:-1] if url.startswith("<") else url).split("#", 1)[0]
                if not limpia or es_url_externa(limpia) or layout.resolver_md(limpia, rel)[0] != r:
                    return None
                cuenta[0] += 1
                return "%s[[%s|%s]]" % (m.group(1), apunta, m.group(2))

            nuevo = transformar_enlaces(texto, fw, fm_)
        else:
            try:
                datos = json.loads(texto)
            except ValueError:
                continue
            for nodo in datos.get("nodes", []):
                obj = layout.desde_vault(nfc(nodo.get("file") or "")) if nodo.get("type") == "file" else None
                if obj and layout.existe(obj) == r:
                    nodo["file"] = layout.vault_rel(por if args.repuntar else destino)
                    cuenta[0] += 1
            nuevo = json.dumps(datos, ensure_ascii=False, indent="\t")
        if nuevo != texto:
            cambios[rel] = (nuevo, crlf)

    carpeta = os.path.join(base, ahora())
    copias = [r] + sorted(cambios)
    for rel in copias:
        os.makedirs(os.path.dirname(os.path.join(carpeta, "originales", rel)), exist_ok=True)
        shutil.copy2(os.path.join(raiz, rel), os.path.join(carpeta, "originales", rel))
    with open(os.path.join(carpeta, "registro.json"), "w", encoding="utf-8") as f:
        json.dump({"de": r, "a": destino, "por": por, "copias": copias}, f, ensure_ascii=False, indent=1)
    for rel, (nuevo, crlf) in cambios.items():
        escribir_texto(os.path.join(raiz, rel), nuevo, crlf)
    texto, crlf = leer_texto(os.path.join(raiz, r))
    campos = {"archivada": datetime.date.today().isoformat()}
    if por:
        campos["reemplazada_por"] = "[[%s]]" % nombre_nota(por)
    os.makedirs(os.path.dirname(os.path.join(raiz, destino)), exist_ok=True)
    os.rename(os.path.join(raiz, r), os.path.join(raiz, destino))
    escribir_texto(os.path.join(raiz, destino), fusionar_frontmatter(texto, campos, []), crlf)
    print("Archivé [[%s]] en %s/%s." % (nombre, carpeta_de(destino),
                                        " Reemplazada por [[%s]]." % nombre_nota(por) if por else ""))
    if cuenta[0]:
        print("%s %s en %s." % ("Reapunté a [[%s]]" % nuevo_nombre if args.repuntar else "Corregí con su nombre",
                                cuantos(cuenta[0], "enlace", "enlaces"), cuantos(len(cambios), "archivo", "archivos")))
    print("Para deshacer: brainme archivar --deshacer")


def estado_32(raiz, rels):
    """Líneas de estado que agregó brainme 3.2: supuestos y cuándo toca el jardín."""
    anotar_historia(raiz, rels)
    info = datos_de_notas(raiz, rels)
    vigentes = [r for r in info if de_memoria(r)]
    sup = [r for r in vigentes if es_supuesto(info[r][0])]
    if sup:
        print("Supuestos sin confirmar: %d -> %s" % (len(sup), lista_notas(sup, 6)))
    sin = archivos_sin_ficha(raiz, rels)
    if sin:
        cats = {}
        for r in sin:
            cats[categoria(r)] = cats.get(categoria(r), 0) + 1
        print("Archivos sin ficha: %s -> %s (dales ficha o enlázalos desde una nota)" % (
            ", ".join(cuantos(n, UNO_CAT.get(c, c), NOMBRES_CAT.get(c, c)) for c, n in sorted(cats.items())),
            ", ".join(r.rsplit("/", 1)[-1] for r in sin[:6]) + (" ..." if len(sin) > 6 else "")))
    ultimo, faltan = registro_jardin(raiz).get("ultimo"), por_revisar(raiz, info)
    if len(faltan) >= UMBRAL_JARDIN:
        print("Jardín: %s, con %d notas por revisar (toca revisar el jardín)" % (
            "último el %s" % ultimo if ultimo else "nunca cerrado", len(faltan)))


# ------------------------------------------------------------ buscar

VACIAS_BUSCAR = (PALABRAS_VACIAS - {"decision", "pregunta"}) | {
    "sobre", "cual", "cuales", "como", "donde", "cuando", "quien", "hay", "son", "lo", "nos", "le", "fue",
    "cuanto", "cuanta", "cuantos", "cuantas", "quienes", "sabemos", "dice", "dicen", "tenemos", "va", "van", "ser", "esta", "estan"}
MAX_BUSCAR = 12


def plano(s):
    """Minúsculas y sin tildes."""
    return "".join(c for c in unicodedata.normalize("NFKD", s.lower()) if not unicodedata.combining(c))


def raiz_de_palabra(p):
    """Quita el plural (precios -> precio, decisiones -> decision), la r del infinitivo (durar ->
    dura) y, en palabras largas, la terminación (estratifican y estratificación -> estratif)."""
    if len(p) > 4 and re.search(r"[aei]r$", p):
        p = p[:-1]
    elif len(p) > 4 and re.search(r"[lrdnzjs]es$", p):
        p = p[:-2]
    elif len(p) > 3 and p.endswith("s"):
        p = p[:-1]
    return p[:max(8, len(p) - 5)] if len(p) >= 10 and p.isalpha() else p


def patrones_de(terminos):
    palabras = re.findall(r"[^\W_]+", plano(" ".join(terminos)))
    utiles = [p for p in palabras if p not in VACIAS_BUSCAR] or palabras
    raices = {raiz_de_palabra(p): p for p in reversed(utiles)}
    return [(raices[r], re.compile(r"(?<![^\W_])" + re.escape(r))) for r in reversed(list(raices))]


def linea_con(texto, patrones, largo=160):
    """La línea que tiene más de las palabras buscadas."""
    mejor, puntos = "", 0
    for linea in texto.split("\n"):
        n = sum(1 for _, p in patrones if p.search(plano(linea)))
        if n > puntos and not linea.lstrip().startswith("#"):
            mejor, puntos = re.sub(r"\s+", " ", linea).strip(" -*>"), n
    return mejor if len(mejor) <= largo else mejor[:largo - 1] + "…"


def buscar_en_notas(raiz, patrones):
    """[(cuántas palabras tiene, puntaje, nota, cuerpo)], de la mejor a la peor. Pesan más el
    nombre, el título, los tags y el resumen que el cuerpo, y lo que se sabe (01 a 03) que las
    fuentes y los entregables."""
    halladas = []
    for r in notas_resumibles(listar_archivos(raiz)):
        texto = leer_texto(os.path.join(raiz, r))[0] or ""
        fm = leer_fm(texto)
        cuerpo = re.sub(r"\A---\n.*?\n---[ \t]*(?:\n|\Z)", "", texto, flags=re.S)
        campos = [(4, plano(nombre_nota(r).replace("-", " "))), (4, plano(fm.get("titulo") or "")),
                  (3, plano(fm.get("tags") or "")), (3, plano(" ".join(fm.get(k) or "" for k in CAMPOS_RESUMEN))),
                  (1, plano(cuerpo))]
        tiene = [max([peso for peso, c in campos if p.search(c)] or [0]) for _, p in patrones]
        if any(tiene):
            veces = sum(min(3, len(p.findall(campos[-1][1]))) for _, p in patrones)
            halladas.append((sum(1 for x in tiene if x), sum(tiene) + veces / 10 + (r[:2] in ("01", "02", "03")) * 3,
                             r, cuerpo))
    return sorted(halladas, key=lambda h: (-h[0], -h[1], h[2]))


def ultima_actualizacion(cuerpo, largo=160):
    """La última línea con fecha de ## Actualizaciones: lo que la nota dice hoy."""
    s = re.search(r"^## Actualizaciones[ \t]*\n(.*?)(?=^## |\Z)", cuerpo, re.M | re.S)
    lineas = re.findall(r"^\s*[-*]\s*(\d{4}-\d{2}-\d{2}.*)$", s.group(1), re.M) if s else []
    ultima = max(enumerate(lineas), key=lambda x: (x[1][:10], x[0]))[1] if lineas else ""
    return ultima if len(ultima) <= largo else ultima[:largo - 1] + "…"


def mostrar_notas(raiz, titulo, lista, patrones, tope=MAX_BUSCAR):
    if not lista:
        return
    print("%s (%d):" % (titulo, len(lista)))
    for _, _, r, cuerpo in lista[:tope]:
        frase = linea_con(cuerpo, patrones)
        print("  %s (%s)%s" % (con_resumen(raiz, r), carpeta_de(r), "\n      … " + frase if frase else ""))
        ultima = ultima_actualizacion(cuerpo)
        if ultima and ultima[:60] not in frase:
            print("      última actualización: " + ultima)
    if len(lista) > tope:
        print("  ... y %d más: agrega una palabra para acotar" % (len(lista) - tope))


def cmd_buscar(args):
    """Notas que hablan de lo buscado: primero las que tienen todas las palabras. Después, el
    contexto general, los originales del inbox y la bitácora."""
    raiz = os.path.abspath(args.raiz)
    busquedas = [b for b in " ".join(args.palabras).split(",") if patrones_de([b])]
    if not busquedas:
        print("Dime qué buscar: brainme buscar <palabras>, o varias búsquedas separadas con comas")
        sys.exit(2)
    anotar_historia(raiz, listar_archivos(raiz))
    for b in busquedas:
        if len(busquedas) > 1:
            print("=== %s" % b.strip())
        buscar_una(raiz, patrones_de([b]), 5 if len(busquedas) > 1 else MAX_BUSCAR)


def buscar_una(raiz, patrones, tope):
    buscado, n = ", ".join(r for r, _ in patrones), len(patrones)
    minimo = min(2, n)  # con menos palabras, la coincidencia dice poco
    halladas = buscar_en_notas(raiz, patrones)
    todas = [h for h in halladas if h[0] == n]
    parte = [h for h in halladas if h[0] < n] if len(todas) < 5 else []
    if not halladas:
        print("Ninguna nota habla de: %s." % buscado)
    mostrar_notas(raiz, "Notas con: %s" % buscado, [h for h in todas if vigente(h[2])], patrones, tope)
    mostrar_notas(raiz, "Con algunas de esas palabras", [h for h in parte if vigente(h[2])], patrones, tope)
    mostrar_notas(raiz, "Archivadas", [h for h in todas + parte if not vigente(h[2]) and h[0] >= minimo], patrones, tope)

    base, texto = buscar_multi(raiz)
    general = os.path.join(base, general_de(texto)) if base and general_de(texto) else ""
    if os.path.isdir(general) and os.path.realpath(general) != os.path.realpath(raiz):
        mostrar_notas(general, "En el contexto general (%s/)" % os.path.basename(general),
                      [h for h in buscar_en_notas(general, patrones) if vigente(h[2]) and h[0] >= minimo], patrones, 6)

    def textos_con(carpeta):
        hallados = []
        for d, _, archivos in os.walk(os.path.join(raiz, carpeta)):
            for a in sorted(archivos):
                texto = leer_texto(os.path.join(d, a))[0]
                tiene = sum(1 for _, p in patrones if p.search(plano(texto))) if texto else 0
                if tiene:
                    hallados.append((tiene, os.path.relpath(os.path.join(d, a), raiz).replace(os.sep, "/"), texto))
        return sorted(hallados, key=lambda o: (o[0], o[1]), reverse=True)

    pendientes = [o for o in textos_con("00_inbox") if o[0] >= minimo] or textos_con("00_inbox")[:3]
    if pendientes:
        print("En el inbox, sin procesar (%d):" % len(pendientes))
        for _, rel, texto in pendientes[:tope]:
            print("  %s\n      … %s" % (rel, linea_con(texto, patrones)))
    originales = textos_con(os.path.join(".brainme", "inbox-procesado"))
    # Con una sola de las palabras, solo si nada coincide más, y pocos
    originales = [o for o in originales if o[0] >= minimo] or originales[:3]
    if originales:
        print("Originales del inbox (%d; con todas las palabras, %d):" % (
            len(originales), sum(1 for o in originales if o[0] == n)))
        for _, rel, texto in originales[:tope]:
            print("  %s\n      … %s" % (rel, linea_con(texto, patrones)))
        if len(originales) > tope:
            print("  ... y %d más" % (len(originales) - tope))
    lineas = [l.strip(" -") for l in (leer_texto(os.path.join(raiz, BITACORA))[0] or "").split("\n")
              if sum(1 for _, p in patrones if p.search(plano(l))) >= minimo]
    if lineas:
        print("Bitácora (%d): %s" % (len(lineas), " / ".join(l[:160] for l in lineas[-3:])))
    rels = listar_archivos(raiz)
    ciegos = archivos_sin_ficha(raiz, rels) + [r for r in rels if r.startswith("00_inbox/") and categoria(r) in CON_FICHA]
    if ciegos and not todas:
        print("Sin leer, porque no tienen ficha (%d): %s" % (
            len(ciegos), ", ".join(r.rsplit("/", 1)[-1] for r in ciegos[:6]) + (" ..." if len(ciegos) > 6 else "")))


# ------------------------------------------------------------ leer

MAX_LEER = 24000
MAX_ORIGINAL = 5000


def cmd_leer(args):
    """Varias notas completas de una vez; con --originales (o --tanda, las del jardín), también el
    texto de sus originales, cada uno una sola vez."""
    raiz = os.path.abspath(args.raiz)
    rels = listar_archivos(raiz)
    anotar_historia(raiz, rels)
    notas = {clave(nombre_nota(r)): r for r in rels if r.endswith(".md") and not aparte(r)}
    pedidas = list(registro_jardin(raiz).get("tanda") or []) if args.tanda else []
    sueltas_ = []
    for n in args.notas:
        ruta = n.strip().strip("[]")
        k = claves_de_notas([n])[0]
        if k in notas:
            pedidas.append(k)
        elif os.path.isfile(os.path.join(raiz, ruta)) and os.path.realpath(os.path.join(raiz, ruta)).startswith(os.path.realpath(raiz) + os.sep):
            sueltas_.append(ruta)
        else:
            print("No encuentro %s." % n)
    pedidas = [k for k in dict.fromkeys(pedidas) if k in notas]
    if not pedidas and not sueltas_:
        print("Dime qué leer: brainme leer <nota> ... [--originales], o --tanda")
        sys.exit(2)
    gastado, quedan, vistos = 0, [], set()

    def imprimir(titulo, texto):
        bloque = "=== %s\n\n%s\n" % (titulo, texto.strip())
        print(bloque)
        return len(bloque)

    for k in pedidas:
        if gastado > MAX_LEER:
            quedan.append(k)
            continue
        texto = leer_texto(os.path.join(raiz, notas[k]))[0] or ""
        gastado += imprimir(notas[k], texto)
        if not (args.originales or args.tanda):
            continue
        for rel in originales_de(raiz, notas[k], rels).replace("original: ", "", 1).split(", "):
            if rel in vistos or not os.path.isfile(os.path.join(raiz, rel)):
                continue
            vistos.add(rel)
            t = leer_texto(os.path.join(raiz, rel))[0]
            gastado += imprimir("original: " + rel, t[:MAX_ORIGINAL] + (
                "\n… (sigue: léelo completo con Read)" if len(t) > MAX_ORIGINAL else "") if t else "(léelo con Read o con brainme texto)")
    for ruta in sueltas_:
        t = leer_texto(os.path.join(raiz, ruta))[0]
        gastado += imprimir(ruta, t if t else "(léelo con Read o con brainme texto)")
    if quedan:
        print("Faltan %d: brainme leer %s%s" % (len(quedan), " ".join(quedan), " --originales" if args.originales or args.tanda else ""))


# ------------------------------------------------------------ inbox y procesado

RESERVAS = os.path.join(".brainme", "inbox.json")
LARGO_INBOX = 3000
EXT_TEXTO = {".md", ".txt", ".vtt", ".srt", ".html", ".htm", ".csv", ".json", ".rtf", ".eml"}


def archivos_del_inbox(raiz):
    return [r for r in listar_archivos(raiz) if r.startswith("00_inbox/")]


def reservar_nombres(raiz):
    """{archivo del inbox: nombre que tendrá al salir}. Se reservan todos juntos, antes de
    escribir las notas, para que su origen no cambie después."""
    hoy = datetime.date.today().isoformat()
    try:
        with open(os.path.join(raiz, RESERVAS), encoding="utf-8") as f:
            reg = json.load(f)
        reservas = reg["nombres"] if reg.get("fecha") == hoy else {}
    except (OSError, ValueError, KeyError, AttributeError):
        reservas = {}
    actuales = archivos_del_inbox(raiz)
    reservas = {r: n for r, n in reservas.items() if r in actuales}
    destino = os.path.join(raiz, ".brainme", "inbox-procesado", hoy)
    archivados = os.listdir(destino) if os.path.isdir(destino) else []
    visibles = {clave(r.rsplit("/", 1)[-1]) for r in listar_archivos(raiz) if not r.startswith("00_inbox/")}
    for r in actuales:
        if r in reservas:
            continue
        nombre = r.rsplit("/", 1)[-1]
        base, ext = os.path.splitext(nombre)
        usados = {clave(x) for f in archivados + list(reservas.values()) for x in (f, os.path.splitext(f)[0] + ext)}
        if ext.lower() not in EXT_TEXTO:  # va a una carpeta visible, donde los nombres son únicos
            usados |= visibles
        final, n = nombre, 2
        while clave(final) in usados:
            final, n = "%s-%d%s" % (base, n, ext), n + 1
        reservas[r] = final
    os.makedirs(os.path.join(raiz, ".brainme"), exist_ok=True)
    with open(os.path.join(raiz, RESERVAS), "w", encoding="utf-8") as f:
        json.dump({"fecha": hoy, "nombres": reservas}, f, ensure_ascii=False, indent=1, sort_keys=True)
    return reservas


def cmd_inbox(args):
    """Lo que hay en el inbox y el origen que llevará lo que salga de cada archivo."""
    raiz = os.path.abspath(args.raiz)
    anotar_historia(raiz, listar_archivos(raiz))
    reservas = reservar_nombres(raiz)
    if not reservas:
        print("El inbox está vacío.")
        return
    hoy = datetime.date.today().isoformat()
    print("En el inbox (%d):" % len(reservas))
    for r in sorted(reservas):
        texto = leer_texto(os.path.join(raiz, r))[0] if os.path.splitext(r)[1].lower() in EXT_TEXTO else None
        palabras = len(texto.split()) if texto else 0
        print("  %s · %s · origen: \"%s (inbox, %s)\"" % (
            r, "%s%s" % (cuantos(palabras, "palabra", "palabras"), ", largo: al lector" if palabras > LARGO_INBOX else "")
            if texto is not None else os.path.splitext(r)[1].lstrip(".") or "sin extensión", reservas[r], hoy))
    if NO_DESCARGADOS:
        print("Sin descargar de iCloud: pide al usuario que los abra (%d)" % len(NO_DESCARGADOS))


def cmd_procesado(args):
    """Saca del inbox un archivo ya procesado, con el nombre que reservó brainme inbox: a
    .brainme/inbox-procesado/<hoy>/ o a --a. Nunca escribe encima de otro archivo."""
    raiz = os.path.abspath(args.raiz)
    inbox, hoy = os.path.realpath(os.path.join(raiz, "00_inbox")), datetime.date.today().isoformat()
    salen = []
    for a in args.archivos:
        ruta = next((r for r in (os.path.join(raiz, a), os.path.join(raiz, "00_inbox", a)) if os.path.isfile(r)), None)
        if not ruta or not os.path.realpath(ruta).startswith(inbox + os.sep):
            print("No está en 00_inbox/, y no moví nada: %s" % a)
            sys.exit(2)
        salen.append(os.path.relpath(os.path.realpath(ruta), os.path.realpath(raiz)).replace(os.sep, "/"))
    rel = (args.a or ".brainme/inbox-procesado/%s" % hoy).strip("/")
    if args.a and (rel.split("/")[0] not in RAICES_ESTRUCTURA - {"00_inbox"} or ".." in rel.split("/")):
        print("--a va a una carpeta de 01 a 05 (por ejemplo, 01_knowledge).")
        sys.exit(2)
    reservas = reservar_nombres(raiz)
    destino = os.path.join(raiz, rel)
    os.makedirs(destino, exist_ok=True)
    for r in salen:
        ruta, nombre = os.path.join(raiz, r), r.rsplit("/", 1)[-1]
        final = next((n for k, n in reservas.items() if clave(k) == clave(r)), nombre)
        base, ext = os.path.splitext(final)
        usados, n = {clave(x) for x in os.listdir(destino)}, 2
        if args.a:
            usados |= {clave(x.rsplit("/", 1)[-1]) for x in listar_archivos(raiz) if not x.startswith("00_inbox/")}
        while clave(final) in usados:
            final, n = "%s-%d%s" % (base, n, ext), n + 1
        os.rename(ruta, os.path.join(destino, final))
        print("%s -> %s/%s · origen: \"%s (inbox, %s)\"%s" % (
            nombre, rel, final, final, hoy, " (ya había otro %s: sus notas llevan este origen)" % nombre if final != nombre else ""))
        carpeta = os.path.realpath(os.path.dirname(ruta))
        while carpeta.startswith(inbox + os.sep) and not [x for x in os.listdir(carpeta) if x.lower() not in IGNORAR_ARCHIVOS]:
            shutil.rmtree(carpeta)
            carpeta = os.path.dirname(carpeta)


# ------------------------------------------------------------ llevar al contexto general

MESES = "enero febrero marzo abril mayo junio julio agosto setiembre septiembre octubre noviembre diciembre".split()


def nombres_propios(texto):
    """Palabras con mayúscula que no abren una frase, una viñeta ni un título."""
    hallados = set()
    for linea in texto.split("\n"):
        linea = re.sub(r"^[\s>*#\-\d.]+", "", linea)
        for m in re.finditer(r"\b([A-ZÁÉÍÓÚÑ][\wáéíóúñÁÉÍÓÚÑ]{2,})", linea):
            antes = linea[:m.start()].rstrip(" «\"(¿¡*_")
            if antes and antes[-1] not in ".!?:":
                hallados.add(m.group(1))
    return hallados


def datos_que_identifican(raiz, texto, prefijo):
    """{motivo: palabras} de lo que en el texto puede identificar al proyecto."""
    del_proyecto = set()
    for r in notas_resumibles(listar_archivos(raiz)):
        fuente = leer_texto(os.path.join(raiz, r))[0] or ""
        del_proyecto |= {plano(x) for x in nombres_propios(re.sub(r"\A---\n.*?\n---[ \t]*\n", "", fuente, flags=re.S))}
    ficha = leer_texto(os.path.join(raiz, "CLAUDE.md"))[0] or ""
    del_proyecto |= {plano(x) for x in nombres_propios(ficha.split("## Proyecto", 1)[-1] if "## Proyecto" in ficha else "")}
    palabras = re.findall(r"[^\W\d_]{3,}", texto)
    propios = {x for x in palabras if plano(x) in del_proyecto and x[0].isupper()} | nombres_propios(texto)
    hallado = {
        "nombres": sorted(propios),
        "cifras": sorted(set(re.findall(r"(?<![\w.])\d[\d.,]*\d|(?<![\w.])\d(?![\w)]|\. )", texto))),
        "fechas": sorted({x for x in palabras if plano(x) in MESES}),
        "enlaces a notas del proyecto": sorted({m.group(0) for m in RE_WIKI.finditer(texto)
                                                if prefijo and clave(partir_wiki(m.group(2))[0]).startswith(clave(prefijo))}),
        "correos o webs": sorted(set(re.findall(r"\S+@\S+\.\w+|https?://\S+", texto)))}
    return {k: v for k, v in hallado.items() if v}


def cmd_llevar(args):
    """Revisa que un texto no identifique al proyecto y, con --ok, lo deja en el inbox del contexto
    general y lo anota en la nota de la que sale."""
    raiz = os.path.abspath(args.raiz)
    base, texto_multi = buscar_multi(raiz)
    general = os.path.join(base, general_de(texto_multi)) if base and general_de(texto_multi) else ""
    if not os.path.isdir(general) or os.path.realpath(general) == os.path.realpath(raiz):
        print("Esto se corre desde un proyecto de una carpeta multiproyecto con contexto general.")
        sys.exit(2)
    autor = leer_config().get("autor")
    if not autor:
        print('Falta el autor: pregúntale su nombre al usuario y corre brainme autor "Nombre".')
        sys.exit(2)
    borrador = leer_texto(os.path.join(raiz, args.borrador))[0]
    if not (borrador or "").strip():
        print("No encuentro el borrador, o está vacío: %s" % args.borrador)
        sys.exit(2)
    if borrador.startswith("---\n"):
        print("El borrador lleva solo el texto: el frontmatter lo pongo yo.")
        sys.exit(2)
    prefijo = prefijo_de(leer_texto(os.path.join(raiz, "CLAUDE.md"))[0] or "")
    nota = buscar_nota(notas_resumibles(listar_archivos(raiz)), args.de)
    permitidas = {plano(x) for x in args.permitir or []}
    hallado = {k: [x for x in v if plano(x) not in permitidas] for k, v in datos_que_identifican(raiz, borrador, prefijo).items()}
    hallado = {k: v for k, v in hallado.items() if v}
    if hallado:
        print("No lo llevo: esto puede identificar al proyecto. Reescríbelo, o pregúntale al usuario y repite con --permitir.")
        for k, v in hallado.items():
            print("  %s: %s" % (k, ", ".join(v)))
        sys.exit(2)
    hoy = datetime.date.today().isoformat()
    tema = slug_tag(args.tema) or "aprendizaje"
    if not args.ok:
        print("Sin datos que identifiquen al proyecto. Muéstrale al usuario el texto y lo que quitaste; con su OK, repite con --ok:")
        print("\n" + borrador.strip())
        return
    rel, n = "desde-un-proyecto-%s-%s" % (hoy, tema), 2
    destino = os.path.join(general, "00_inbox", rel + ".md")
    while os.path.exists(destino):
        destino, n = os.path.join(general, "00_inbox", "%s-%d.md" % (rel, n)), n + 1
    os.makedirs(os.path.dirname(destino), exist_ok=True)
    escribir_texto(destino, '---\nautor: "%s"\nfecha: %s\norigen: "un proyecto, con OK del usuario"\n---\n\n%s\n' % (
        autor, hoy, borrador.strip()), False)
    ruta = os.path.join(raiz, nota)
    texto, crlf = leer_texto(ruta)
    linea = "- %s: Llevada al contexto general (%s) · %s" % (hoy, hoy, autor)
    if re.search(r"^## Actualizaciones[ \t]*$", texto, re.M):
        texto = re.sub(r"(^## Actualizaciones[ \t]*\n(?:(?!^## ).*\n?)*?)(?=\n*(?:^## |\Z))",
                       lambda m: m.group(1).rstrip("\n") + "\n" + linea + "\n", texto, count=1, flags=re.M)
    else:
        texto = texto.rstrip("\n") + "\n\n## Actualizaciones\n" + linea + "\n"
    escribir_texto(ruta, texto, crlf)
    print("Llevado a %s/00_inbox/%s, y anotado en [[%s]]. El contexto general lo procesa en su próxima sesión." % (
        os.path.basename(general), os.path.basename(destino), nombre_nota(nota)))


# ------------------------------------------------------------ guías

SKILL_DIR = os.path.dirname(PLANTILLAS)
GUIAS = {"inbox": ("references/inbox.md", "templates/note.md", "references/redaccion.md"),
         "guardar": ("templates/note.md", "references/redaccion.md"),
         "entregables": ("references/entregables.md", "templates/deliverable-card.md", "references/redaccion.md"),
         "jardin": ("references/jardin.md", "templates/tema.md"),
         "fuentes": ("templates/web-source.md", "templates/literature-note.md"),
         "handoff": ("references/handoff.md", "templates/note.md"),
         "multiproyecto": ("references/multiproyecto.md", "templates/CLAUDE-multiproyecto.md"), "configurar": ("references/configurar.md",),
         "ordenar": ("references/ordenar.md",), "migrar": ("references/migrar.md",), "redaccion": ("references/redaccion.md",)}


def cmd_guia(args):
    """Las guías de un flujo, con las plantillas y reglas que usa, en una sola lectura."""
    nombres = [plano(n) for n in args.nombres]
    ajenas = [n for n in nombres if n not in GUIAS and n != "convenciones"]
    if ajenas:
        print("No hay guía %s. Hay: convenciones, %s." % (", ".join(ajenas), ", ".join(sorted(GUIAS))))
        sys.exit(2)
    print("Si el comando brainme no existe: python3 \"%s\"" % os.path.abspath(__file__))
    if "convenciones" in nombres:
        texto = leer_texto(os.path.join(SKILL_DIR, "SKILL.md"))[0] or ""
        print("\n=== SKILL.md, Convenciones de las notas\n\n" + texto.split("## Convenciones de las notas", 1)[-1].strip())
    for rel in dict.fromkeys(x for n in nombres for x in GUIAS.get(n, ())):
        print("\n=== %s\n\n%s" % (rel, (leer_texto(os.path.join(SKILL_DIR, rel))[0] or "").strip()))


# ------------------------------------------------------------ archivos sin ficha

CON_FICHA = ("pdf", "imagen", "office", "presentacion")
UNO_CAT = {"pdf": "PDF", "imagen": "imagen", "office": "archivo de Office", "presentacion": "presentación"}


def archivos_sin_ficha(raiz, rels):
    """PDFs, imágenes, Office y presentaciones de la estructura (sin inbox ni versiones)
    que ninguna nota enlaza, incrusta ni nombra en su frontmatter (archivo, pdf). En un
    entregable de 05_exports, la ficha de su carpeta cuenta para todos sus archivos."""
    archivos = [r for r in rels if categoria(r) in CON_FICHA and estado_de(r) == "ordenado"
                and not r.startswith("00_inbox/") and not aparte(r) and "/archive/" not in r
                and not RE_COPIA_CONFLICTO.match(r.rsplit("/", 1)[-1])]
    if not archivos:
        return []
    notas = [r for r in rels if r.endswith(".md") and estado_de(r) == "ordenado"
             and not r.startswith("00_inbox/")]
    layout = Layout(raiz, buscar_vault(raiz), rels)
    layout.rels = notas
    con = {e["destino"] for e in recorrer_enlaces(raiz, layout) if e["destino"]}
    nombrados = set()
    for r in notas:
        fm = leer_fm(leer_texto(os.path.join(raiz, r))[0] or "")
        for campo in ("archivo", "pdf"):
            v = (fm.get(campo) or "").strip()
            if v:
                nombrados.add(clave(v.rsplit("/", 1)[-1]))
    stems = {clave(r[:-3]) for r in notas}
    sin = []
    for r in archivos:
        carpeta = carpeta_de(r)
        ficha_carpeta = r.startswith("05_exports/") and clave(
            carpeta + "/" + carpeta.rsplit("/", 1)[-1]) in stems
        if r not in con and clave(r.rsplit("/", 1)[-1]) not in nombrados and not ficha_carpeta:
            sin.append(r)
    return sin


# ------------------------------------------------------------ texto de Office

NS_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
NS_A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
NS_P = "{http://schemas.openxmlformats.org/presentationml/2006/main}"
NS_S = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
NS_R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
FILAS_HOJA = 500


def xml_de(z, nombre):
    try:
        return ET.fromstring(z.read(nombre))
    except (KeyError, ET.ParseError):
        return None


def destino_rel(base, target):
    """Ruta dentro del zip de un Target de un archivo .rels relativo a la carpeta base."""
    if target.startswith("/"):
        return target.lstrip("/")
    return os.path.normpath(os.path.join(base, target)).replace(os.sep, "/")


def rels_de(z, nombre):
    """Id -> (tipo, ruta en el zip) del .rels de una parte (p. ej. ppt/slides/slide1.xml)."""
    carpeta, archivo = nombre.rsplit("/", 1)
    x = xml_de(z, "%s/_rels/%s.rels" % (carpeta, archivo))
    if x is None:
        return {}
    return {r.get("Id"): (r.get("Type") or "", destino_rel(carpeta, r.get("Target") or ""))
            for r in x}


def parrafo_docx(p):
    partes = []
    for el in p.iter():
        if el.tag == NS_W + "t":
            partes.append(el.text or "")
        elif el.tag == NS_W + "tab":
            partes.append("\t")
        elif el.tag in (NS_W + "br", NS_W + "cr"):
            partes.append("\n")
    return "".join(partes)


def texto_docx(z):
    doc = xml_de(z, "word/document.xml")
    cuerpo = doc.find(NS_W + "body") if doc is not None else None
    lineas = []
    for el in (list(cuerpo) if cuerpo is not None else []):
        if el.tag == NS_W + "p":
            lineas.append(parrafo_docx(el))
        elif el.tag == NS_W + "tbl":
            for fila in el.iter(NS_W + "tr"):
                lineas.append(" | ".join(" ".join(parrafo_docx(p) for p in c.iter(NS_W + "p")).strip()
                                         for c in fila.findall(NS_W + "tc")))
            lineas.append("")
    return lineas


def parrafos_a(raiz_xml):
    return [t for t in ("".join(x.text or "" for x in p.iter(NS_A + "t")).strip()
                        for p in raiz_xml.iter(NS_A + "p")) if t]


def texto_pptx(z):
    rels = rels_de(z, "ppt/presentation.xml")
    pres = xml_de(z, "ppt/presentation.xml")
    orden = []
    if pres is not None:
        for s in pres.iter(NS_P + "sldId"):
            tipo, ruta = rels.get(s.get(NS_R + "id"), ("", ""))
            if ruta:
                orden.append(ruta)
    if not orden:
        orden = sorted((n for n in z.namelist() if re.match(r"ppt/slides/slide\d+\.xml$", n)),
                       key=lambda n: int(re.search(r"(\d+)\.xml$", n).group(1)))
    lineas = []
    for i, ruta in enumerate(orden, 1):
        diapo = xml_de(z, ruta)
        if diapo is None:
            continue
        lineas += ["## Diapositiva %d" % i] + (parrafos_a(diapo) or ["(sin texto: imagen o gráfico)"])
        for tipo, destino in rels_de(z, ruta).values():
            if tipo.endswith("/notesSlide"):
                notas = xml_de(z, destino)
                cuerpo = [] if notas is None else [
                    t for sp in notas.iter(NS_P + "sp")
                    if any(ph.get("type") == "body" for ph in sp.iter(NS_P + "ph"))
                    for t in parrafos_a(sp)]
                if cuerpo:
                    lineas.append("Notas: " + " ".join(cuerpo))
        lineas.append("")
    return lineas


def columna(ref):
    n = 0
    for c in re.match(r"[A-Z]*", ref or "").group(0):
        n = n * 26 + ord(c) - 64
    return n


def texto_xlsx(z, max_filas):
    compartidas = []
    sst = xml_de(z, "xl/sharedStrings.xml")
    if sst is not None:
        compartidas = ["".join(t.text or "" for t in si.iter(NS_S + "t")) for si in sst.findall(NS_S + "si")]
    libro = xml_de(z, "xl/workbook.xml")
    rels = rels_de(z, "xl/workbook.xml")
    lineas = []
    for hoja in ([] if libro is None else libro.iter(NS_S + "sheet")):
        x = xml_de(z, rels.get(hoja.get(NS_R + "id"), ("", ""))[1])
        lineas.append("## Hoja: %s" % hoja.get("name"))
        filas, resto = 0, 0
        for fila in ([] if x is None else x.iter(NS_S + "row")):
            celdas = {}
            for c in fila.findall(NS_S + "c"):
                v, tipo = c.find(NS_S + "v"), c.get("t")
                if tipo == "inlineStr":
                    valor = "".join(t.text or "" for t in c.iter(NS_S + "t"))
                elif v is None:
                    continue
                elif tipo == "s":
                    i = int(v.text or 0)
                    valor = compartidas[i] if i < len(compartidas) else ""
                else:
                    valor = v.text or ""
                if valor.strip():
                    celdas[columna(c.get("r")) or len(celdas) + 1] = valor.strip().replace("\n", " ")
            if not celdas:
                continue
            if max_filas and filas >= max_filas:
                resto += 1
                continue
            filas += 1
            lineas.append(" | ".join(celdas.get(i, "") for i in range(1, max(celdas) + 1)))
        if resto:
            lineas.append("(%s más: --filas 0 las muestra todas)" % cuantos(resto, "fila", "filas"))
        lineas.append("")
    return lineas


def cmd_texto(args):
    ruta = os.path.join(os.path.abspath(args.raiz), os.path.expanduser(args.archivo))
    ext = os.path.splitext(ruta)[1].lower()
    if not os.path.isfile(ruta):
        print("No encuentro %s." % args.archivo)
        sys.exit(2)
    if ext not in (".docx", ".xlsx", ".pptx"):
        print("brainme texto lee .docx, .xlsx y .pptx. Un .doc o .rtf: textutil -convert txt -stdout "
              "\"<archivo>\". Keynote, Pages o Numbers: expórtalo a PDF o al formato de Office.")
        sys.exit(2)
    try:
        with zipfile.ZipFile(ruta) as z:
            lineas = (texto_docx(z) if ext == ".docx" else texto_pptx(z) if ext == ".pptx"
                      else texto_xlsx(z, args.filas))
    except zipfile.BadZipFile:
        print("%s no se puede abrir: no es un archivo de Office válido o está dañado." % args.archivo)
        sys.exit(1)
    texto = re.sub(r"\n{3,}", "\n\n", "\n".join(lineas)).strip()
    print(texto if texto else "(%s no tiene texto)" % args.archivo)


def main():
    p = argparse.ArgumentParser(description="Estado y orden de un proyecto brainme, sin romper enlaces.")
    p.add_argument("--raiz", default=".", help="carpeta del proyecto (por defecto, la actual)")
    sub = p.add_subparsers(dest="cmd")
    co = sub.add_parser("comprueba")
    co.add_argument("--dejar", nargs="+", metavar="NOTA", help="el usuario cambió a propósito el origen o una actualización")
    si = sub.add_parser("sincroniza")
    si.set_defaults(dejar=None)  # el nombre de comprueba hasta la 3.2
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
    ve.add_argument("--plan", help="ruta del plan para brainme mover")
    ve.add_argument("--archivar", action="append", metavar="CARPETA",
                    help="carpeta propia de un entregable cuyo contenido pasa a versiones/ (repetible)")
    ja = sub.add_parser("jardin")
    ja.add_argument("--hecho", nargs="*", metavar="NOTA",
                    help="anota las notas revisadas; sin notas, cierra el jardín si no queda ninguna por revisar")
    ja.add_argument("--dejar", nargs="+", metavar="NOTA",
                    help="una nota suelta o archivada, o un par parecido, que el usuario decide dejar así")
    ja.add_argument("--tanda", action="store_true", help="con --hecho: las notas de la última tanda que mostró jardin")
    ja.add_argument("--sin-revisar", action="store_true",
                    help="con --hecho: cierra sin revisar las que faltan (solo si el usuario decide saltarlas)")
    ar = sub.add_parser("archivar")
    ar.add_argument("nota", nargs="?")
    ar.add_argument("--por", help="la nota que la reemplaza o donde quedó su contenido")
    ar.add_argument("--repuntar", action="store_true", help="los enlaces a la nota pasan a la de --por")
    ar.add_argument("--deshacer", action="store_true", help="revierte el último archivado")
    po = sub.add_parser("procesado")
    po.add_argument("archivos", nargs="+")
    po.add_argument("--a", help="carpeta de 01 a 05; sin ella, va a .brainme/inbox-procesado/<hoy>/")
    le = sub.add_parser("leer")
    le.add_argument("notas", nargs="*")
    le.add_argument("--originales", action="store_true", help="también el texto de sus originales")
    le.add_argument("--tanda", action="store_true", help="las notas de la última tanda del jardín, con sus originales")
    ll = sub.add_parser("llevar")
    ll.add_argument("borrador", help="archivo con el texto, sin frontmatter")
    ll.add_argument("--de", required=True, help="la nota de la que sale")
    ll.add_argument("--tema", required=True)
    ll.add_argument("--permitir", nargs="+", metavar="PALABRA", help="lo que el usuario dijo que puede quedarse")
    ll.add_argument("--ok", action="store_true", help="el usuario ya aprobó el texto: lo lleva")
    sub.add_parser("inbox")
    gu = sub.add_parser("guia")
    gu.add_argument("nombres", nargs="+", metavar="GUIA", help="convenciones, " + ", ".join(sorted(GUIAS)))
    bu = sub.add_parser("buscar")
    bu.add_argument("palabras", nargs="+")
    tx = sub.add_parser("texto")
    tx.add_argument("archivo")
    tx.add_argument("--filas", type=int, default=FILAS_HOJA,
                    help="máximo de filas por hoja de Excel (0: todas; por defecto %d)" % FILAS_HOJA)
    sub.add_parser("multiproyecto")
    sub.add_parser("espacio")  # el nombre de multiproyecto hasta la 3.2
    cr = sub.add_parser("crear")
    cr.add_argument("carpeta", nargs="?", help="por defecto, la actual; en una carpeta multiproyecto, desde su raíz")
    cr.add_argument("--prefijo", help="prefijo de las notas (proyectos de una carpeta multiproyecto)")
    cr.add_argument("--trata", help="de qué trata, en una o dos frases")
    sub.add_parser("version")
    args = p.parse_args()
    comandos = {"comprueba": cmd_comprueba, "sincroniza": cmd_comprueba, "estado": cmd_estado, "mapa": cmd_mapa, "nombres": cmd_nombres, "inventario": cmd_inventario, "respaldo": cmd_respaldo, "mover": cmd_mover,
                "verificar": cmd_verificar, "deshacer": cmd_deshacer,
                "a-wikilinks": cmd_a_wikilinks, "sin-resumen": cmd_sin_resumen,
                "poner-resumenes": cmd_poner_resumenes, "autor": cmd_autor,
                "bitacora": cmd_bitacora, "consumo": cmd_consumo, "migrar": cmd_migrar,
                "versiones": cmd_versiones, "multiproyecto": cmd_multiproyecto, "espacio": cmd_multiproyecto, "crear": cmd_crear,
                "jardin": cmd_jardin, "archivar": cmd_archivar, "buscar": cmd_buscar, "procesado": cmd_procesado, "inbox": cmd_inbox, "guia": cmd_guia, "leer": cmd_leer, "llevar": cmd_llevar, "texto": cmd_texto,
                "version": lambda a: print(VERSION)}
    if args.cmd not in comandos:
        p.print_help()
        sys.exit(1)
    comandos[args.cmd](args)


if __name__ == "__main__":
    main()
