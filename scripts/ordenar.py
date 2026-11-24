"""brainme ordenar: pone en la estructura de brainme una carpeta que ya tenía trabajo, sin
romper los enlaces de Obsidian. Es lo único de brainme que mueve archivos (con un plan que el
usuario aprobó, después de un respaldo y con deshacer) o les agrega resúmenes que faltan.

  inventario   lo que hay y qué falta ordenar -> .brainme/inventario.json (con --tabla, una línea por archivo)
  respaldo     zip de todo el proyecto -> .brainme/respaldos/
  mover        ejecuta un plan (--plan .brainme/plan-orden.json) y corrige cada enlace que apunta a lo movido
  deshacer     revierte el último orden (o el de --registro)
  wikilinks    convierte los links markdown internos entre notas en wikilinks
  resumenes    reparte en lotes las notas sin resumen, para el ayudante de resúmenes; con
               --poner <archivo>, escribe los resúmenes que faltan (nunca cambia uno que ya está)

Lo llama scripts/brainme.py (brainme ordenar <acción>). Usa solo la biblioteca estándar.
"""

import datetime
import json
import os
import re
import sys
import unicodedata
import zipfile
from urllib.parse import unquote

ESTRUCTURA = ["00_inbox", "01_knowledge", "02_decisions", "03_open_questions", "04_sources", "05_exports"]
RAICES_ESTRUCTURA = set(ESTRUCTURA)
# Nunca se recorren ni se mueven
PROTEGIDAS = {".git", ".obsidian", ".trash", ".claude", ".brainme", "graphify-out", "node_modules", ".claude-plugin"}
# Se quedan donde están: no son "por ordenar"
SE_QUEDAN_RAIZ = {"claude.md", "readme.md", "agents.md", ".gitignore", ".graphifyignore", "bitacora.md", "tablero.md"}
CARPETAS_QUE_SE_QUEDAN = {"docs", "proyectos"}
IGNORAR_ARCHIVOS = {".ds_store", "icon\r", ".gitkeep"}
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
RE_MULTI = re.compile(r"^## brainme · (?:multiproyecto|espacio)[ \t]*$", re.M)

NO_DESCARGADOS = []


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
    print("Detalle por archivo: %s" % os.path.relpath(destino, raiz))
    if getattr(args, "tabla", False) and por_ordenar:
        print("\nPOR ORDENAR (ruta | tipo | título | palabras | usado por | vista previa):")
        for a in por_ordenar:
            print("%s | %s | %s | %s | %s | %s" % (
                a["ruta"], a["categoria"], a.get("titulo") or "-", a.get("palabras", "-"),
                len(a["usado_por"]), (a.get("vista_previa") or "")[:140]))


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
    print("Respaldo creado: %s (%d archivos, %.1f MB)" % (os.path.relpath(destino, raiz), n, os.path.getsize(destino) / 1e6))


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
    print("Registro (sirve para deshacer): %s" % os.path.relpath(reg["ruta_registro"], reg["proyecto"]))


def cmd_mover(args):
    raiz = os.path.abspath(args.raiz)
    ruta = args.plan if os.path.isabs(args.plan) or os.path.isfile(args.plan) else os.path.join(raiz, args.plan)
    try:
        with open(ruta, encoding="utf-8") as f:
            plan = json.load(f)
    except (OSError, ValueError) as e:
        print("No pude leer el plan %s: %s" % (args.plan, e))
        sys.exit(2)
    comun = dict(plan.get("frontmatter_comun") or {})
    reg = ejecutar_movimientos(raiz, plan.get("movimientos", []), comun, "orden")
    informar_movimiento(reg)


def cmd_deshacer(args):
    raiz = os.path.abspath(args.raiz)
    ruta = args.registro
    if ruta and not os.path.isabs(ruta) and not os.path.isfile(ruta):
        ruta = os.path.join(raiz, ruta)
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
    if total:
        print("Respaldo previo: corre antes brainme ordenar respaldo si aún no lo hiciste.")

# ------------------------------------------------------------------ resúmenes

CARPETAS_NOTAS = ("01_knowledge", "02_decisions", "03_open_questions", "04_sources", "05_exports")
LOTE = 25
MAX_RESUMEN = 300
RE_RESUMEN = re.compile(r"^(?:resumen|description|summary)[ \t]*:[ \t]*(.*)$", re.M)


def frontmatter_de(texto):
    if texto.startswith("---\n"):
        fin = texto.find("\n---", 3)
        if fin > 0:
            return texto[4:fin]
    return ""


def tiene_resumen(texto):
    m = RE_RESUMEN.search(frontmatter_de(texto))
    valor = m.group(1).strip().strip("\"'").strip() if m else ""
    return bool(valor) and not valor.startswith("<")


def notas_sin_resumen(raiz):
    salida = []
    for rel in listar_archivos(raiz):
        partes = rel.split("/")
        if rel.lower().endswith(".md") and partes[0] in CARPETAS_NOTAS and "archive" not in partes:
            texto, _ = leer_texto(os.path.join(raiz, rel))
            if texto is not None and not tiene_resumen(texto):
                salida.append(rel)
    return salida


def cmd_resumenes(args):
    raiz = os.path.abspath(args.raiz)
    carpeta = os.path.join(raiz, ".brainme", "resumenes")
    if args.poner:
        ruta = args.poner if os.path.isabs(args.poner) or os.path.isfile(args.poner) else os.path.join(raiz, args.poner)
        try:
            with open(ruta, encoding="utf-8") as f:
                resumenes = json.load(f)
        except (OSError, ValueError) as e:
            print("No pude leer %s: %s" % (args.poner, e))
            sys.exit(2)
        escritos, tenian, malos = 0, 0, []
        for rel, resumen in resumenes.items():
            destino = os.path.realpath(os.path.join(raiz, rel))
            resumen = " ".join(str(resumen).split())
            if not destino.startswith(os.path.realpath(raiz) + os.sep) or not rel.lower().endswith(".md") \
                    or not os.path.isfile(destino):
                malos.append("%s (no está)" % rel)
                continue
            if not resumen or len(resumen) > MAX_RESUMEN:
                malos.append("%s (resumen vacío o de más de %d caracteres)" % (rel, MAX_RESUMEN))
                continue
            texto, crlf = leer_texto(destino)
            if texto is None:
                malos.append("%s (no se puede leer)" % rel)
                continue
            if tiene_resumen(texto):
                tenian += 1
                continue
            fm = frontmatter_de(texto)
            if fm and RE_RESUMEN.search(fm):  # un resumen vacío o con <...>: se quita antes de poner el nuevo
                texto = "---\n" + RE_RESUMEN.sub("", fm, count=1).replace("\n\n", "\n").strip("\n") + texto[4 + len(fm):]
            escribir_texto(destino, fusionar_frontmatter(texto, {"resumen": resumen}, []), crlf)
            escritos += 1
        print("Resúmenes escritos: %d. Ya tenían resumen: %d." % (escritos, tenian))
        if malos:
            print("Sin escribir (%d): %s" % (len(malos), "; ".join(malos)))
        return
    faltan = notas_sin_resumen(raiz)
    if os.path.isdir(carpeta):
        for viejo in os.listdir(carpeta):
            if viejo.startswith("lote-"):
                os.remove(os.path.join(carpeta, viejo))
    if not faltan:
        print("Todas las notas tienen resumen.")
        return
    os.makedirs(carpeta, exist_ok=True)
    lotes = []
    for i in range(0, len(faltan), LOTE):
        nombre = "lote-%02d.json" % (i // LOTE + 1)
        with open(os.path.join(carpeta, nombre), "w", encoding="utf-8") as f:
            json.dump(faltan[i:i + LOTE], f, ensure_ascii=False, indent=1)
        lotes.append(os.path.join(".brainme", "resumenes", nombre))
    print("Sin resumen: %d %s, en %d %s de hasta %d:" % (len(faltan), "nota" if len(faltan) == 1 else "notas",
                                                         len(lotes), "lote" if len(lotes) == 1 else "lotes", LOTE))
    for lote in lotes:
        print("  " + lote)
    print("Un brainme:resumidor por lote, todos a la vez.")


# --------------------------------------------------------------------- entrada

ACCIONES = {"inventario": cmd_inventario, "respaldo": cmd_respaldo, "mover": cmd_mover,
            "deshacer": cmd_deshacer, "wikilinks": cmd_a_wikilinks, "resumenes": cmd_resumenes}


def ejecutar(args):
    raiz = os.path.abspath(args.raiz)
    texto, _ = leer_texto(os.path.join(raiz, "CLAUDE.md"))
    if texto and RE_MULTI.search(texto):
        print("Esta es la raíz de una carpeta multiproyecto: ordena dentro de cada proyecto o del contexto general.")
        sys.exit(2)
    if args.accion == "mover" and not args.plan:
        print("Falta el plan: brainme ordenar mover --plan .brainme/plan-orden.json")
        sys.exit(2)
    ACCIONES[args.accion](args)
