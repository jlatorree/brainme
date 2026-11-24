#!/usr/bin/env python3
"""brainme: la herramienta del skill. Lee el proyecto y escribe solo lo indispensable.

Comandos (se corren desde la raíz del proyecto):
  crear       carpetas, tablero y CLAUDE.md de un proyecto, o de una carpeta multiproyecto
  autor       quién trabaja en este computador, para firmar la bitácora
  estado      para ponerse al día: inbox, preguntas, decisiones, tablero y última sesión
  buscar      notas que hablan de algo, sin importar tildes ni plurales
  leer        notas completas con sus enlaces, y el texto de Word, Excel o PowerPoint
  inbox       lo que hay en 00_inbox/ y el origen que llevará lo que salga de cada archivo
  procesado   saca del inbox un archivo ya procesado, sin escribir encima de otro
  comprueba   lo escrito hoy (o, con --todo, todo el proyecto): resumen, enlaces y nombres
  bitacora    agrega o muestra entradas de bitacora.md, también los handoffs
  ordenar     pone en la estructura una carpeta con avance previo (scripts/ordenar.py)

Solo lee y escribe dentro del proyecto. No mueve ni reescribe notas, salvo `ordenar mover` y
`ordenar deshacer`, que mueven archivos con un plan aprobado y corrigen sus enlaces. Usa solo
la biblioteca estándar de Python (3.9 o superior).
"""

import argparse
import datetime
import json
import os
import re
import sys
import unicodedata
import zipfile
import xml.etree.ElementTree as ET

VERSION = "4.1.0"

CARPETAS = ["00_inbox", "01_knowledge", "02_decisions", "03_open_questions", "04_sources", "05_exports"]
CARPETAS_NOTAS = ("01_knowledge", "02_decisions", "03_open_questions", "04_sources", "05_exports")
# Nunca se recorren
OCULTAS = {".git", ".obsidian", ".trash", ".claude", ".brainme", "graphify-out", "node_modules", ".claude-plugin"}
# Se recorren para que sus enlaces funcionen, pero sus notas no se buscan ni se revisan
APARTE = {"versiones", "_versiones", "_taller"}
IGNORAR = {".ds_store", "icon\r"}
OFFICE = (".docx", ".xlsx", ".pptx")
TEXTO = {".md", ".txt", ".vtt", ".srt", ".html", ".htm", ".csv", ".json", ".rtf", ".eml"}

BITACORA, TABLERO = "bitacora.md", "tablero.md"
PROCESADOS = os.path.join(".brainme", "inbox-procesado")
PROYECTOS = "proyectos"
PLANTILLAS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "templates")

RE_WIKI = re.compile(r"(!?)\[\[([^\[\]]+?)\]\]")
RE_PROYECTO = re.compile(r"^## brainme[ \t]*$", re.M)
RE_MULTI = re.compile(r"^## brainme · (?:multiproyecto|espacio)[ \t]*$", re.M)  # «espacio»: hasta la 3.2
RE_PLACEHOLDER = re.compile(r"<[^<>\n]+>")
RE_ANIO = re.compile(r"^\d{4}$")

# Comandos de versiones anteriores: qué usar ahora
VIEJOS = {"texto": "brainme leer <archivo>", "jardin": "brainme comprueba --todo", "verificar": "brainme comprueba --todo",
          "sincroniza": "brainme comprueba", "mapa": "brainme leer <nota> (muestra sus enlaces)",
          "nombres": "brainme buscar <palabras>", "multiproyecto": "brainme estado, en la raíz de la carpeta multiproyecto",
          "espacio": "brainme estado, en la raíz de la carpeta multiproyecto",
          "guia": "lee references/<flujo>.md, en la carpeta del skill",
          "inventario": "brainme ordenar inventario", "mover": "brainme ordenar mover --plan <plan>",
          "respaldo": "brainme ordenar respaldo", "deshacer": "brainme ordenar deshacer",
          "a-wikilinks": "brainme ordenar wikilinks"}


# ---------------------------------------------------------------- utilidades

def nfc(s):
    return unicodedata.normalize("NFC", s)


def clave(s):
    return nfc(s).lower()


def plano(s):
    """Minúsculas y sin tildes."""
    return "".join(c for c in unicodedata.normalize("NFKD", s.lower()) if not unicodedata.combining(c))


def hoy():
    return datetime.date.today().isoformat()


def cuantos(n, uno, varios):
    return "%d %s" % (n, uno if n == 1 else varios)


def leer_texto(ruta):
    try:
        with open(ruta, "rb") as f:
            return f.read().decode("utf-8").replace("\r\n", "\n")
    except (OSError, UnicodeDecodeError):
        return None


def escribir(ruta, texto):
    os.makedirs(os.path.dirname(ruta) or ".", exist_ok=True)
    with open(ruta, "w", encoding="utf-8") as f:
        f.write(texto)


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


def resumen_de(fm):
    """El resumen de una nota (en notas antiguas, a veces description o summary)."""
    return fm.get("resumen") or fm.get("description") or fm.get("summary") or ""


def valor(fm, nombre):
    """Un campo del frontmatter, vacío si quedó el <...> de la plantilla."""
    v = (fm.get(nombre) or "").strip()
    return "" if RE_PLACEHOLDER.search(v) else v


def cuerpo_de(texto):
    return re.sub(r"\A---\n.*?\n---[ \t]*(?:\n|\Z)", "", texto or "", flags=re.S)


def sin_codigo(texto):
    texto = re.sub(r"^(```|~~~).*?^\1[ \t]*$", "", texto, flags=re.M | re.S)
    return re.sub(r"`[^`\n]*`", "", texto)


def destinos(texto):
    """Nombres a los que apuntan los wikilinks del texto (también los del frontmatter)."""
    salida = []
    for m in RE_WIKI.finditer(sin_codigo(texto or "")):
        objetivo = re.split(r"[|#]", m.group(2), 1)[0].rstrip("\\").strip()
        if objetivo:
            salida.append(objetivo)
    return salida


def nombre_nota(rel):
    return rel.rsplit("/", 1)[-1][:-3]


def wiki(rel):
    return "[[%s]]" % nombre_nota(rel)


def lista(rels, n=8):
    return ", ".join(wiki(r) for r in rels[:n]) + (" y %d más" % (len(rels) - n) if len(rels) > n else "")


def listar(raiz):
    """Rutas relativas (con /) de los archivos del proyecto, sin las carpetas ocultas."""
    salida = []
    for d, carpetas, archivos in os.walk(raiz):
        carpetas[:] = sorted(c for c in carpetas if c not in OCULTAS)
        rel_d = os.path.relpath(d, raiz)
        for a in sorted(archivos):
            if a.lower() in IGNORAR or a.endswith(".icloud"):
                continue
            salida.append((a if rel_d == "." else os.path.join(rel_d, a)).replace(os.sep, "/"))
    return salida


def es_nota(rel):
    partes = rel.split("/")
    return rel.endswith(".md") and partes[0] in CARPETAS_NOTAS and not APARTE & set(partes)


def archivada(rel):
    return "/archive/" in rel


# ----------------------------------------------------------------- proyecto

def campo(texto, nombre):
    """Valor de '**Nombre:** valor', hasta el siguiente ' · **' o el fin de la línea."""
    m = re.search(r"\*\*%s:\*\*[ \t]*(.*?)(?=[ \t]+·[ \t]+\*\*|[ \t]*$)" % re.escape(nombre), texto or "", re.M)
    return m.group(1).strip() if m else ""


def prefijo_de(texto):
    m = re.match(r"`?([A-Za-z0-9_-]+)", campo(texto, "Prefijo de notas"))
    return m.group(1) if m else ""


def buscar_multi(carpeta):
    """(raíz, texto del CLAUDE.md) de la carpeta multiproyecto que contiene a carpeta, o (None, None)."""
    d = os.path.abspath(carpeta)
    while True:
        texto = leer_texto(os.path.join(d, "CLAUDE.md"))
        if texto and RE_MULTI.search(texto):
            return d, texto
        padre = os.path.dirname(d)
        if padre == d:
            return None, None
        d = padre


class Proyecto:
    """Los archivos del proyecto y, en una carpeta multiproyecto, los del contexto general:
    con ellos se resuelven los wikilinks, igual que en Obsidian."""

    def __init__(self, raiz):
        self.raiz = os.path.abspath(raiz)
        self.claude = leer_texto(os.path.join(self.raiz, "CLAUDE.md")) or ""
        self.archivos = listar(self.raiz)
        self.notas = [r for r in self.archivos if es_nota(r)]
        self.multi, self.texto_multi = buscar_multi(self.raiz)
        self.general = None
        if self.multi:
            g = os.path.join(self.multi, campo(self.texto_multi, "Contexto general").strip("`/ "))
            if os.path.isdir(g) and os.path.realpath(g) != os.path.realpath(self.raiz) and g != self.multi:
                self.general = g
        self.prefijo = prefijo_de(self.claude)
        nombres = self.archivos + (listar(self.general) if self.general else [])
        self.por_nombre = {clave(r.rsplit("/", 1)[-1]) for r in nombres}
        self.por_stem = {}
        for r in self.archivos:
            if r.endswith(".md"):
                self.por_stem.setdefault(clave(nombre_nota(r)), r)
        self.stems = {clave(nombre_nota(r)) for r in nombres if r.endswith(".md")}
        self._textos = {}

    def texto(self, rel):
        if rel not in self._textos:
            self._textos[rel] = leer_texto(os.path.join(self.raiz, rel)) or ""
        return self._textos[rel]

    @staticmethod
    def stem(objetivo):
        nombre = clave(objetivo.rsplit("/", 1)[-1])
        return nombre[:-3] if nombre.endswith(".md") else nombre

    def existe(self, objetivo):
        """Un wikilink funciona si hay una nota con ese nombre o un archivo con ese nombre y extensión."""
        return clave(objetivo.rsplit("/", 1)[-1]) in self.por_nombre or self.stem(objetivo) in self.stems

    def enlaza_nota(self, objetivo, propia):
        """El wikilink lleva a otra nota (del proyecto o del contexto general), no a un archivo ni a sí misma."""
        return self.stem(objetivo) in self.stems and self.stem(objetivo) != clave(propia)

    def nota(self, objetivo):
        """Nota del proyecto a la que apunta un wikilink, o None."""
        return self.por_stem.get(self.stem(objetivo))

    def reemplazos(self):
        """{decisión: la decisión que la reemplaza}, según el reemplaza_a de cada una."""
        salida = {}
        for r in self.notas:
            for d in destinos(leer_fm(self.texto(r)).get("reemplaza_a") or ""):
                vieja = self.nota(d)
                if vieja and vieja != r:
                    salida[vieja] = r
        return salida

    def enlaces(self):
        """(sale, entra): de cada nota, las notas del proyecto que enlaza y las que la enlazan."""
        sale = {r: set() for r in self.notas}
        entra = {r: set() for r in self.notas}
        for r in self.notas:
            for d in destinos(self.texto(r)):
                destino = self.nota(d)
                if destino and destino != r:
                    sale[r].add(destino)
                    if destino in entra:
                        entra[destino].add(r)
        return sale, entra


def ruta_config():
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config")
    return os.path.join(base, "brainme", "config.json")


def leer_config():
    try:
        with open(ruta_config(), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


# -------------------------------------------------------------------- crear

def plantilla(nombre, valores):
    texto = leer_texto(os.path.join(PLANTILLAS, nombre))
    for k, v in valores.items():
        texto = texto.replace(k, v)
    return texto


def crear_tablero(destino):
    if not os.path.exists(os.path.join(destino, TABLERO)):
        escribir(os.path.join(destino, TABLERO), plantilla(TABLERO, {"<AAAA-MM-DD>": hoy()}))


def ficha_comun(texto_multi):
    """Campos de '### Ficha de cada proyecto', siempre con estado y prefijo."""
    m = re.search(r"^### Ficha de cada proyecto[ \t]*\n(.*?)(?=^#|\Z)", texto_multi or "", re.M | re.S)
    campos = re.findall(r"^- \*\*(.+?):\*\*", m.group(1), re.M) if m else []
    for fijo in ("Prefijo de notas", "Estado"):
        if fijo not in campos:
            campos.insert(0, fijo)
    return campos


def cmd_crear(args):
    raiz = os.path.abspath(args.raiz)
    trata = " ".join((args.trata or "").split())
    if args.multiproyecto:
        crear_multi(raiz, trata, args.general)
        return
    base, texto_multi = buscar_multi(raiz)
    destino = os.path.normpath(os.path.join(base or raiz, args.carpeta)) if args.carpeta else raiz
    nombre = os.path.basename(destino)
    ficha, prefijo = [], ""
    if base:
        anio = os.path.dirname(destino)
        general = os.path.join(base, campo(texto_multi, "Contexto general").strip("`/ "))
        if os.path.dirname(anio) == os.path.join(base, PROYECTOS) and RE_ANIO.match(os.path.basename(anio)):
            prefijo = (args.prefijo or "").strip().strip("`")
            if not prefijo:
                print("Un proyecto de una carpeta multiproyecto necesita --prefijo para sus notas (por ejemplo, acme-).")
                sys.exit(2)
            prefijo += "" if prefijo.endswith("-") else "-"
            ficha = ficha_comun(texto_multi)
        elif destino != general:
            print("En esta carpeta multiproyecto, cada proyecto va en %s/<año>/<proyecto> (por ejemplo, %s/%d/acme) y el "
                  "contexto general es %s/." % (PROYECTOS, PROYECTOS, datetime.date.today().year, os.path.basename(general)))
            sys.exit(2)
    for c in CARPETAS:
        os.makedirs(os.path.join(destino, c), exist_ok=True)
    ruta = os.path.join(destino, "CLAUDE.md")
    actual = leer_texto(ruta)
    if actual and RE_PROYECTO.search(actual):
        crear_tablero(destino)
        print("Carpetas listas. %s ya tenía CLAUDE.md con brainme: lo dejé como estaba." % nombre)
        return
    texto = plantilla("CLAUDE.md", {"<Nombre del proyecto>": nombre, "<nombre de la carpeta>": nombre,
                                    "<AAAA-MM-DD>": hoy()})
    if trata:
        texto = re.sub(r"<una o dos frases[^>]*>", lambda m: trata, texto)
    if ficha:
        valores = {"Estado": "activo", "Prefijo de notas": "`%s`" % prefijo}
        texto = texto.rstrip("\n") + "\n\n## Proyecto\n\n" + "\n".join(
            "- **%s:** %s" % (c, valores.get(c, "<por completar>")) for c in ficha) + "\n"
    if actual:
        texto = actual.rstrip("\n") + "\n\n" + texto[texto.index("## brainme"):]
    escribir(ruta, texto)
    crear_tablero(destino)
    print("Creé %s: carpetas, tablero.md y CLAUDE.md%s." % (
        os.path.relpath(destino, base) if base else nombre, ", con su ficha y el prefijo " + prefijo if ficha else ""))
    if not trata:
        print("Falta «De qué trata» en CLAUDE.md: pídeselo al usuario.")


def crear_multi(raiz, trata, general):
    general = (general or "general").strip("/ ")
    ruta = os.path.join(raiz, "CLAUDE.md")
    actual = leer_texto(ruta)
    if actual and RE_MULTI.search(actual):
        print("Esta carpeta ya es multiproyecto: la dejé como estaba.")
        return
    if actual and RE_PROYECTO.search(actual):
        print("Esta carpeta es un proyecto brainme. Una carpeta multiproyecto los agrupa desde la carpeta de arriba.")
        sys.exit(2)
    nombre = os.path.basename(raiz)
    texto = plantilla("CLAUDE-multiproyecto.md", {"<Nombre de la carpeta multiproyecto>": nombre, "<nombre>": nombre,
                                                  "<general>": general, "<AAAA-MM-DD>": hoy()})
    if trata:
        texto = texto.replace("<una o dos frases>", trata)
    if actual:
        texto = actual.rstrip("\n") + "\n\n" + texto[texto.index("## brainme"):]
    escribir(ruta, texto)
    os.makedirs(os.path.join(raiz, PROYECTOS), exist_ok=True)
    print("Creé la carpeta multiproyecto: CLAUDE.md y %s/." % PROYECTOS)
    args = argparse.Namespace(raiz=raiz, carpeta=general, trata="Lo que sirve a todos los proyectos", prefijo=None,
                              multiproyecto=False, general=None)
    cmd_crear(args)


# -------------------------------------------------------------------- autor

def cmd_autor(args):
    """El autor vive en este computador, no en la carpeta compartida: cada persona firma con su nombre."""
    cfg = leer_config()
    if args.nombre:
        cfg["autor"] = " ".join(args.nombre.split())
        escribir(ruta_config(), json.dumps(cfg, ensure_ascii=False, indent=1))
        print("Autor guardado en este computador: %s" % cfg["autor"])
    elif cfg.get("autor"):
        print("Autor: %s" % cfg["autor"])
    else:
        print('Autor: no definido. Pregúntale su nombre al usuario y corre: brainme autor "Nombre"')


# ------------------------------------------------------------------- estado

def preguntas_abiertas(p):
    abiertas = []
    orden = {"alta": 0, "media": 1, "baja": 2}
    for r in p.notas:
        if r.startswith("03_open_questions/") and not archivada(r):
            fm = leer_fm(p.texto(r))
            if not (fm.get("estado") or "abierta").lower().startswith("resuelta"):
                prio = valor(fm, "prioridad")
                abiertas.append((orden.get(prio.lower(), 3), prio, r, valor(fm, "quien_puede_responder")))
    return [(prio, r, quien) for _, prio, r, quien in sorted(abiertas)]


def ultima_entrada(raiz):
    entradas = entradas_bitacora(leer_texto(os.path.join(raiz, BITACORA)))
    return entradas[-1] if entradas else None


def proximo_paso(raiz):
    tablero = leer_texto(os.path.join(raiz, TABLERO)) or ""
    m = re.search(r"^## Próximos pasos[ \t]*\n(.*?)(?=^## |\Z)", tablero, re.M | re.S)
    for linea in (m.group(1).split("\n") if m else []):
        linea = re.sub(r"^\s*[-*]\s+(\[[ xX]\]\s+)?", "", linea)
        if linea.strip() and not RE_PLACEHOLDER.search(linea):
            return linea.strip()
    return ""


def cmd_estado(args):
    raiz = os.path.abspath(args.raiz)
    texto = leer_texto(os.path.join(raiz, "CLAUDE.md")) or ""
    if RE_MULTI.search(texto):
        panorama(raiz, texto)
        return
    if not RE_PROYECTO.search(texto):
        print("Esta carpeta no tiene brainme todavía: sigue references/configurar.md.")
        return
    p = Proyecto(raiz)
    linea = "Proyecto: %s" % os.path.basename(raiz)
    if p.multi:
        linea += " · carpeta multiproyecto %s%s" % (os.path.basename(p.multi), " · prefijo " + p.prefijo if p.prefijo else
                                                    " · su contexto general" if not p.general else "")
    print(linea)
    inbox = [r for r in p.archivos if r.startswith("00_inbox/")]
    print("Inbox sin procesar: %d%s" % (len(inbox), " -> " + ", ".join(r[9:] for r in inbox[:8]) +
                                        (" ..." if len(inbox) > 8 else "") if inbox else ""))
    abiertas = preguntas_abiertas(p)
    print("Preguntas abiertas: %d" % len(abiertas))
    for prio, r, quien in abiertas[:10]:
        print("  %s%s%s" % ("[%s] " % prio if prio else "", wiki(r), " · puede responder: " + quien if quien else ""))
    if len(abiertas) > 10:
        print("  ... y %d más" % (len(abiertas) - 10))
    decisiones = sorted((r for r in p.notas if r.startswith("02_decisions/") and not archivada(r)),
                        key=lambda r: -os.path.getmtime(os.path.join(raiz, r)))[:5]
    if decisiones:
        print("Últimas decisiones: " + ", ".join("%s (%s)" % (wiki(r), datetime.date.fromtimestamp(
            os.path.getmtime(os.path.join(raiz, r))).isoformat()) for r in decisiones))
    tablero = leer_texto(os.path.join(raiz, TABLERO))
    if tablero is None:
        print("Tablero: no hay (brainme crear lo crea)")
    else:
        print("Tablero: actualizado %s%s" % (leer_fm(tablero).get("actualizado") or "sin fecha",
                                             " · por llenar: quedan campos <...>" if RE_PLACEHOLDER.search(cuerpo_de(tablero)) else ""))
    ultima = ultima_entrada(raiz)
    print("Última sesión: %s" % ("%s %s · %s" % (ultima["fecha"], ultima["hora"], ultima["linea"][:200]) if ultima
                                 else "sin bitácora todavía"))
    malas = revisar(p, p.notas)
    resumen = ["%s %s" % (len(v), k) for k, v in malas.items() if v and k in ("sin resumen", "con enlaces rotos", "sueltas")]
    print("Notas: %d%s" % (len(p.notas), " · " + ", ".join(resumen) + " (brainme comprueba --todo)" if resumen else ""))


def panorama(raiz, texto):
    general = campo(texto, "Contexto general").strip("`/ ")
    print("Carpeta multiproyecto: %s · contexto general: %s/" % (campo(texto, "Multiproyecto") or os.path.basename(raiz),
                                                                 general))
    g = os.path.join(raiz, general)
    if general and RE_PROYECTO.search(leer_texto(os.path.join(g, "CLAUDE.md")) or ""):
        print("Contexto general: " + resumen_proyecto(g))
    else:
        print("Contexto general: sin crear (brainme crear %s)" % general)
    abiertos, cerrados = [], []
    carpeta = os.path.join(raiz, PROYECTOS)
    for anio in sorted(os.listdir(carpeta)) if os.path.isdir(carpeta) else []:
        if not RE_ANIO.match(anio) or not os.path.isdir(os.path.join(carpeta, anio)):
            continue
        for h in sorted(os.listdir(os.path.join(carpeta, anio))):
            ruta = os.path.join(carpeta, anio, h)
            ficha = leer_texto(os.path.join(ruta, "CLAUDE.md")) or ""
            if not os.path.isdir(ruta) or not RE_PROYECTO.search(ficha):
                continue
            estado = campo(ficha, "Estado") or "sin estado"
            if estado.startswith("cerrado"):
                cerrados.append("%s/%s" % (anio, h))
                continue
            ultima = ultima_entrada(ruta)
            abiertos.append(((ultima or {}).get("fecha", ""), "- %s/%s · %s%s\n  %s" % (
                anio, h, campo(ficha, "De qué trata")[:140], "" if estado == "activo" else " [%s]" % estado,
                resumen_proyecto(ruta))))
    print("Proyectos abiertos (%d), el más reciente primero:" % len(abiertos) if abiertos else
          "Proyectos abiertos: ninguno (di «nuevo proyecto: <nombre>»).")
    for _, fila in sorted(abiertos, reverse=True):
        print(fila)
    if cerrados:
        print("Cerrados (%d): %s" % (len(cerrados), ", ".join(cerrados)))


def resumen_proyecto(ruta):
    archivos = listar(ruta)
    notas = [r for r in archivos if es_nota(r)]
    preguntas = [r for r in notas if r.startswith("03_open_questions/") and not archivada(r)]
    inbox = [r for r in archivos if r.startswith("00_inbox/")]
    ultima, paso = ultima_entrada(ruta), proximo_paso(ruta)
    return "%s · %s%s · última sesión: %s%s" % (
        cuantos(len(notas), "nota", "notas"), cuantos(len(preguntas), "pregunta", "preguntas"),
        " · inbox %d" % len(inbox) if inbox else "",
        "%s, %s" % (ultima["fecha"], ultima["linea"][:120]) if ultima else "ninguna",
        " · sigue: " + paso[:120] if paso else "")


# ---------------------------------------------------------------- comprueba

def palabras_nombre(rel, prefijo):
    n = nombre_nota(rel).lower()
    if prefijo and n.startswith(prefijo.lower()):
        n = n[len(prefijo):]
    return {w for w in re.split(r"[-_ ]+", plano(n)) if len(w) > 2 and w not in VACIAS | {"decision", "pregunta", "nota"}}


def revisar(p, notas, hoy=False):
    """{problema: [notas]} según las reglas de una nota: resumen, al menos un enlace a otra nota,
    ningún enlace roto y, en un proyecto de una carpeta multiproyecto, su prefijo. Una decisión
    tomada dice quién la tomó y una pregunta abierta, su prioridad. Lo escrito hoy (hoy=True)
    dice además quién lo escribió: de lo escrito antes a mano no siempre se sabe."""
    malas = {"sin resumen": [], "sueltas": [], "con enlaces rotos": [], "sin el prefijo": [], "sin autor": [],
             "sin decidido_por": [], "sin prioridad": [], "reemplazo sin cerrar": []}
    rotos, reemplazos = {}, p.reemplazos()
    for r in notas:
        texto = p.texto(r)
        fm = leer_fm(texto)
        if not resumen_de(fm):
            malas["sin resumen"].append(r)
        ds = destinos(texto)
        faltan = sorted({d for d in ds if not p.existe(d)})
        if faltan:
            malas["con enlaces rotos"].append(r)
            rotos[r] = faltan
        if not any(p.enlaza_nota(d, nombre_nota(r)) for d in ds):
            malas["sueltas"].append(r)
        if archivada(r):
            continue
        if p.prefijo and not nombre_nota(r).lower().startswith(p.prefijo.lower()):
            malas["sin el prefijo"].append(r)
        if hoy and not valor(fm, "autor"):
            malas["sin autor"].append(r)
        estado = valor(fm, "estado").lower()
        if r.startswith("02_decisions/"):
            if estado in ("tomada", "revertida") and not valor(fm, "decidido_por"):
                malas["sin decidido_por"].append(r)
            if r in reemplazos and estado != "revertida":
                malas["reemplazo sin cerrar"].append(r)
        if r.startswith("03_open_questions/") and not estado.startswith("resuelta") and not valor(fm, "prioridad"):
            malas["sin prioridad"].append(r)
    malas["rotos"], malas["reemplazos"] = rotos, reemplazos
    return malas


def de_hoy(p):
    inicio = datetime.datetime.combine(datetime.date.today(), datetime.time()).timestamp()
    return [r for r in p.notas if os.path.getmtime(os.path.join(p.raiz, r)) >= inicio]


def problemas_de(p, notas, tope=20, hoy=False):
    malas = revisar(p, notas, hoy)
    lineas = []
    textos = {"sin resumen": "Sin resumen", "sueltas": "Sin enlace a otra nota",
              "con enlaces rotos": "Con enlaces rotos", "sin el prefijo": "Sin el prefijo %s" % p.prefijo,
              "sin autor": "Sin autor (brainme autor)", "sin decidido_por": "Decisiones sin decidido_por",
              "sin prioridad": "Preguntas abiertas sin prioridad",
              "reemplazo sin cerrar": "Decisiones reemplazadas que no dicen estado: revertida"}
    for k, titulo in textos.items():
        if malas[k]:
            if k == "con enlaces rotos":
                detalle = "; ".join("%s -> %s" % (wiki(r), ", ".join("[[%s]]" % d for d in malas["rotos"][r]))
                                    for r in malas[k][:tope])
            elif k == "reemplazo sin cerrar":
                detalle = "; ".join("%s (la reemplaza %s)" % (wiki(r), wiki(malas["reemplazos"][r])) for r in malas[k][:tope])
            else:
                detalle = lista(malas[k], tope)
            lineas.append("%s (%d): %s%s" % (titulo, len(malas[k]), detalle,
                                              " y %d más" % (len(malas[k]) - tope)
                                              if len(malas[k]) > tope and k in ("con enlaces rotos", "reemplazo sin cerrar") else ""))
    tablero = leer_texto(os.path.join(p.raiz, TABLERO)) or ""
    rotos_tablero = sorted({d for d in destinos(tablero) if not p.existe(d)})
    if rotos_tablero:
        lineas.append("En el tablero, enlaces rotos: " + ", ".join("[[%s]]" % d for d in rotos_tablero))
    return lineas


def duplicados(p, notas):
    """Pares de notas de 01 a 03 cuyos nombres comparten casi todas las palabras (las versiones
    de un entregable no son duplicados)."""
    pares = []
    palabras = [(r, palabras_nombre(r, p.prefijo)) for r in notas if not archivada(r) and r[:2] in ("01", "02", "03")]
    for i, (a, pa) in enumerate(palabras):
        for b, pb in palabras[i + 1:]:
            if len(pa) >= 2 and len(pb) >= 2 and len(pa & pb) / len(pa | pb) >= 0.75:
                pares.append((a, b))
    return pares


def cmd_comprueba(args):
    p = Proyecto(args.raiz)
    if args.todo:
        lineas = problemas_de(p, p.notas)
        pares = duplicados(p, p.notas)
        if pares:
            lineas.append("Posibles duplicados (%d): %s" % (len(pares), "; ".join(
                "%s y %s" % (wiki(a), wiki(b)) for a, b in pares[:15])))
        supuestos = [r for r in p.notas if not archivada(r) and (leer_fm(p.texto(r)).get("certeza") or "").lower() == "supuesto"]
        if supuestos:
            lineas.append("Supuestos, por si ya se confirmaron (%d): %s" % (len(supuestos), lista(supuestos, 15)))
        print("\n".join(lineas) if lineas else "Revisé %s: todo en orden." % cuantos(len(p.notas), "nota", "notas"))
        return
    hoy_ = de_hoy(p)
    lineas = problemas_de(p, hoy_, hoy=True)
    if lineas:
        print("Por corregir en lo escrito hoy:\n" + "\n".join(lineas))
    elif hoy_:
        print("Lo escrito hoy está completo (%s)." % cuantos(len(hoy_), "nota", "notas"))
    else:
        print("Hoy no se escribió ninguna nota.")


# ------------------------------------------------------------------- buscar

VACIAS = {"de", "del", "la", "las", "el", "los", "en", "y", "o", "a", "al", "por", "para", "con", "un", "una", "que",
          "se", "su", "sus", "es", "sobre", "cual", "cuales", "como", "donde", "cuando", "quien", "hay", "son", "lo",
          "nos", "le", "fue", "cuanto", "cuanta", "cuantos", "cuantas", "quienes", "sabemos", "dice", "dicen",
          "tenemos", "va", "van", "ser", "esta", "estan", "mas", "pero", "sin"}
MAX_BUSCAR = 12


def raiz_de_palabra(w):
    """Quita el plural, la r del infinitivo y, en palabras largas, la terminación
    (estratifican y estratificación -> estratif)."""
    if len(w) > 4 and re.search(r"[aei]r$", w):
        w = w[:-1]
    elif len(w) > 4 and re.search(r"[lrdnzjs]es$", w):
        w = w[:-2]
    elif len(w) > 3 and w.endswith("s"):
        w = w[:-1]
    return w[:max(8, len(w) - 5)] if len(w) >= 10 and w.isalpha() else w


def patrones_de(texto):
    palabras = re.findall(r"[^\W_]+", plano(texto))
    utiles = [w for w in palabras if w not in VACIAS] or palabras
    raices = list(dict.fromkeys(raiz_de_palabra(w) for w in utiles))
    return [(r, re.compile(r"(?<![^\W_])" + re.escape(r))) for r in raices]


def linea_con(texto, patrones, largo=160):
    """La línea que tiene más de las palabras buscadas."""
    mejor, puntos = "", 0
    for linea in texto.split("\n"):
        n = sum(1 for _, pat in patrones if pat.search(plano(linea)))
        if n > puntos and not linea.lstrip().startswith("#"):
            mejor, puntos = re.sub(r"\s+", " ", linea).strip(" -*>"), n
    return mejor if len(mejor) <= largo else mejor[:largo - 1] + "…"


def ultima_actualizacion(cuerpo, largo=160):
    """La última línea con fecha de ## Actualizaciones: lo que la nota dice hoy."""
    s = re.search(r"^## Actualizaciones[ \t]*\n(.*?)(?=^## |\Z)", cuerpo, re.M | re.S)
    lineas = re.findall(r"^\s*[-*]\s*(\d{4}-\d{2}-\d{2}.*)$", s.group(1), re.M) if s else []
    ultima = max(lineas, key=lambda x: x[:10]) if lineas else ""
    return ultima if len(ultima) <= largo else ultima[:largo - 1] + "…"


def buscar_en(notas, leer, patrones):
    """[(cuántas palabras tiene, puntaje, nota)], de la mejor a la peor. Pesan más el nombre y el
    resumen que el cuerpo, y lo que se sabe (01 a 03) que las fuentes y los entregables."""
    halladas = []
    for r in notas:
        texto = leer(r)
        fm = leer_fm(texto)
        campos = [(4, plano(nombre_nota(r).replace("-", " "))), (3, plano(resumen_de(fm) + " " +
                                                                         (fm.get("titulo") or "") + " " + (fm.get("tags") or ""))),
                  (1, plano(cuerpo_de(texto)))]
        tiene = [max([peso for peso, c in campos if pat.search(c)] or [0]) for _, pat in patrones]
        if any(tiene):
            veces = sum(min(3, len(pat.findall(campos[-1][1]))) for _, pat in patrones)
            halladas.append((sum(1 for x in tiene if x), sum(tiene) + veces / 10 + (r[:2] in ("01", "02", "03")) * 3, r))
    return sorted(halladas, key=lambda h: (-h[0], -h[1], h[2]))


def marca(texto, rel, reemplazos=None):
    """Lo que hay que saber antes de creerle a la nota: si está archivada, si es un supuesto y,
    en una decisión, si se revirtió o la reemplazó otra."""
    fm = leer_fm(texto)
    marcas = (["archivada"] if archivada(rel) else []) + (["supuesto"] if valor(fm, "certeza").lower() == "supuesto" else [])
    if rel.startswith("02_decisions/") and valor(fm, "estado").lower() == "revertida":
        marcas.append("revertida")
    if reemplazos and rel in reemplazos:
        marcas.append("reemplazada por %s" % wiki(reemplazos[rel]))
    return " [%s]" % ", ".join(marcas) if marcas else ""


def mostrar(titulo, halladas, leer, patrones, tope, reemplazos=None):
    if not halladas:
        return
    print("%s (%d):" % (titulo, len(halladas)))
    for _, _, r in halladas[:tope]:
        texto = leer(r)
        resumen = resumen_de(leer_fm(texto))
        print("  %s%s (%s)%s" % (wiki(r), marca(texto, r, reemplazos), r.rsplit("/", 1)[0], ": " + resumen[:200] if resumen else ""))
        frase, ultima = linea_con(cuerpo_de(texto), patrones), ultima_actualizacion(cuerpo_de(texto))
        if frase:
            print("      … " + frase)
        if ultima and ultima[:60] not in frase:
            print("      última actualización: " + ultima)
    if len(halladas) > tope:
        print("  ... y %d más: agrega una palabra para acotar" % (len(halladas) - tope))


def cmd_buscar(args):
    busquedas = [b for b in " ".join(args.palabras).split(",") if patrones_de(b)]
    if not busquedas:
        print("Dime qué buscar: brainme buscar <palabras>, o varias búsquedas separadas con comas")
        sys.exit(2)
    p = Proyecto(args.raiz)
    for b in busquedas:
        if len(busquedas) > 1:
            print("=== %s" % b.strip())
        buscar_una(p, patrones_de(b), 5 if len(busquedas) > 1 else MAX_BUSCAR)


def buscar_una(p, patrones, tope):
    n = len(patrones)
    halladas = buscar_en(p.notas, p.texto, patrones)
    todas = [h for h in halladas if h[0] == n]
    reemplazos = p.reemplazos()
    if not halladas:
        print("Ninguna nota habla de: %s." % ", ".join(r for r, _ in patrones))
    mostrar("Notas con todas las palabras", todas, p.texto, patrones, tope, reemplazos)
    if len(todas) < 5:
        mostrar("Con algunas de las palabras", [h for h in halladas if h[0] < n], p.texto, patrones, tope, reemplazos)
    minimo = min(2, n)
    if p.general:
        notas = [r for r in listar(p.general) if es_nota(r)]
        leer = lambda r: leer_texto(os.path.join(p.general, r)) or ""
        mostrar("En el contexto general (%s/)" % os.path.basename(p.general),
                [h for h in buscar_en(notas, leer, patrones) if h[0] >= minimo], leer, patrones, 6)
    for titulo, carpeta in (("En el inbox, sin procesar", "00_inbox"), ("Originales ya procesados", PROCESADOS)):
        hallados = []
        for d, _, archivos in os.walk(os.path.join(p.raiz, carpeta)):
            for a in sorted(archivos):
                texto = leer_texto(os.path.join(d, a)) if os.path.splitext(a)[1].lower() in TEXTO else None
                tiene = sum(1 for _, pat in patrones if pat.search(plano(texto))) if texto else 0
                if tiene >= minimo:
                    hallados.append((tiene, os.path.relpath(os.path.join(d, a), p.raiz).replace(os.sep, "/"), texto))
        hallados.sort(key=lambda o: (-o[0], o[1]))
        if hallados:
            print("%s (%d):" % (titulo, len(hallados)))
            for _, rel, texto in hallados[:tope]:
                print("  %s\n      … %s" % (rel, linea_con(texto, patrones)))
    lineas = [l.strip(" -") for l in (leer_texto(os.path.join(p.raiz, BITACORA)) or "").split("\n")
              if sum(1 for _, pat in patrones if pat.search(plano(l))) >= minimo]
    if lineas:
        print("Bitácora (%d): %s" % (len(lineas), " / ".join(l[:160] for l in lineas[-3:])))


# --------------------------------------------------------------------- leer

MAX_LEER = 24000


def original_de(p, texto):
    """Ruta del original de una nota, si su origen es un archivo del inbox ya procesado."""
    m = re.match(r"^(.+?)\s*\(inbox,\s*(\d{4}-\d{2}-\d{2})\)", leer_fm(texto).get("origen") or "")
    if not m:
        return ""
    rel = os.path.join(PROCESADOS, m.group(2), m.group(1)).replace(os.sep, "/")
    if os.path.isfile(os.path.join(p.raiz, rel)):
        return rel
    nombre = clave(m.group(1))  # un original con valor propio quedó en 01 a 05
    return next((r for r in p.archivos if clave(r.rsplit("/", 1)[-1]) == nombre), "")


def cmd_leer(args):
    p = Proyecto(args.raiz)
    sale, entra = p.enlaces()
    reemplazos = p.reemplazos()
    gastado, quedan = 0, []
    for pedido in args.cosas:
        if gastado > MAX_LEER:
            quedan.append(pedido)
            continue
        objetivo = pedido.strip().strip("[]")
        rel = p.nota(objetivo)
        ruta = os.path.realpath(os.path.join(p.raiz, objetivo))
        if rel:
            texto = p.texto(rel)
            pie = ["Enlaza: " + (lista(sorted(sale.get(rel, ()), key=nombre_nota), 15) or "ninguna nota"),
                   "La enlazan: " + (lista(sorted(entra.get(rel, ()), key=nombre_nota), 15) or "ninguna nota")]
            if rel in reemplazos:
                pie.append("La reemplaza: " + wiki(reemplazos[rel]))
            original = original_de(p, texto)
            if original:
                pie.append("Original: " + original)
            bloque = "=== %s\n\n%s\n\n%s\n" % (rel, texto.strip(), "\n".join(pie))
        elif os.path.isfile(ruta) and ruta.startswith(os.path.realpath(p.raiz) + os.sep):
            bloque = "=== %s\n\n%s\n" % (objetivo, texto_de_archivo(ruta))
        else:
            print("No encuentro %s." % pedido)
            continue
        print(bloque)
        gastado += len(bloque)
    if quedan:
        print("Faltan %d: brainme leer %s" % (len(quedan), " ".join(quedan)))


def texto_de_archivo(ruta):
    ext = os.path.splitext(ruta)[1].lower()
    if ext in OFFICE:
        try:
            with zipfile.ZipFile(ruta) as z:
                lineas = texto_docx(z) if ext == ".docx" else texto_pptx(z) if ext == ".pptx" else texto_xlsx(z)
        except zipfile.BadZipFile:
            return "(no se puede abrir: no es un archivo de Office válido o está dañado)"
        texto = re.sub(r"\n{3,}", "\n\n", "\n".join(lineas)).strip()
        return texto or "(no tiene texto)"
    texto = leer_texto(ruta)
    if texto is not None:
        return texto.strip()
    if ext in (".doc", ".rtf"):
        return '(un .doc o .rtf se lee con: textutil -convert txt -stdout "<archivo>")'
    return "(no es texto: un PDF o una imagen se leen con Read)"


# Office: el texto de Word, PowerPoint y Excel, sin bibliotecas externas
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


def rels_de(z, nombre):
    """Id -> (tipo, ruta en el zip) del .rels de una parte (p. ej. ppt/slides/slide1.xml)."""
    carpeta, archivo = nombre.rsplit("/", 1)
    x = xml_de(z, "%s/_rels/%s.rels" % (carpeta, archivo))
    if x is None:
        return {}
    salida = {}
    for r in x:
        target = r.get("Target") or ""
        ruta = target.lstrip("/") if target.startswith("/") else os.path.normpath(os.path.join(carpeta, target)).replace(os.sep, "/")
        salida[r.get("Id")] = (r.get("Type") or "", ruta)
    return salida


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
    return [t for t in ("".join(x.text or "" for x in p.iter(NS_A + "t")).strip() for p in raiz_xml.iter(NS_A + "p")) if t]


def texto_pptx(z):
    rels = rels_de(z, "ppt/presentation.xml")
    pres = xml_de(z, "ppt/presentation.xml")
    orden = [rels.get(s.get(NS_R + "id"), ("", ""))[1] for s in pres.iter(NS_P + "sldId")] if pres is not None else []
    orden = [o for o in orden if o] or sorted((n for n in z.namelist() if re.match(r"ppt/slides/slide\d+\.xml$", n)),
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
                cuerpo = [] if notas is None else [t for sp in notas.iter(NS_P + "sp")
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


def texto_xlsx(z):
    sst = xml_de(z, "xl/sharedStrings.xml")
    compartidas = ["".join(t.text or "" for t in si.iter(NS_S + "t")) for si in sst.findall(NS_S + "si")] if sst is not None else []
    libro, rels = xml_de(z, "xl/workbook.xml"), rels_de(z, "xl/workbook.xml")
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
            if filas >= FILAS_HOJA:
                resto += 1
                continue
            filas += 1
            lineas.append(" | ".join(celdas.get(i, "") for i in range(1, max(celdas) + 1)))
        if resto:
            lineas.append("(%s más, sin mostrar)" % cuantos(resto, "fila", "filas"))
        lineas.append("")
    return lineas


# ------------------------------------------------------- inbox y procesado

LARGO = 3000


def nombre_libre(carpeta, nombre):
    """El nombre, o nombre-2, -3..., si ya hay un archivo así en la carpeta."""
    usados = {clave(x) for x in os.listdir(carpeta)} if os.path.isdir(carpeta) else set()
    base, ext = os.path.splitext(nombre)
    final, n = nombre, 2
    while clave(final) in usados:
        final, n = "%s-%d%s" % (base, n, ext), n + 1
    return final


def cmd_inbox(args):
    raiz = os.path.abspath(args.raiz)
    inbox = [r for r in listar(raiz) if r.startswith("00_inbox/")]
    if not inbox:
        print("El inbox está vacío.")
        return
    destino = os.path.join(raiz, PROCESADOS, hoy())
    print("En el inbox (%d):" % len(inbox))
    for r in inbox:
        ruta, ext = os.path.join(raiz, r), os.path.splitext(r)[1].lower()
        texto = texto_de_archivo(ruta) if ext in OFFICE or ext in TEXTO else None
        palabras = len(texto.split()) if texto else 0
        tipo = (cuantos(palabras, "palabra", "palabras") + (", largo: al lector" if palabras > LARGO else "")
                if texto is not None else (ext.lstrip(".") or "sin extensión") + ": al lector")
        print('  %s · %s · origen: "%s (inbox, %s)"' % (r, tipo, nombre_libre(destino, r.rsplit("/", 1)[-1]), hoy()))


def cmd_procesado(args):
    """Saca del inbox archivos ya procesados: a .brainme/inbox-procesado/<hoy>/, o con --a a una
    carpeta de 01 a 05. Nunca escribe encima de otro archivo."""
    raiz = os.path.abspath(args.raiz)
    inbox = os.path.realpath(os.path.join(raiz, "00_inbox"))
    rel = (args.a or os.path.join(PROCESADOS, hoy())).strip("/")
    if args.a and (rel.split("/")[0] not in CARPETAS_NOTAS or ".." in rel.split("/")):
        print("--a va a una carpeta de 01 a 05 (por ejemplo, 04_sources).")
        sys.exit(2)
    salen = []
    for a in args.archivos:
        ruta = next((r for r in (os.path.join(raiz, a), os.path.join(raiz, "00_inbox", a)) if os.path.isfile(r)), None)
        if not ruta or not os.path.realpath(ruta).startswith(inbox + os.sep):
            print("No está en 00_inbox/, y no moví nada: %s" % a)
            sys.exit(2)
        salen.append(ruta)
    destino = os.path.join(raiz, rel)
    os.makedirs(destino, exist_ok=True)
    for ruta in salen:
        nombre = os.path.basename(ruta)
        final = nombre_libre(destino, nombre)
        os.rename(ruta, os.path.join(destino, final))
        print('%s -> %s/%s%s' % (nombre, rel, final, " (ya había otro %s: el origen de sus notas es \"%s (inbox, %s)\")"
                                 % (nombre, final, hoy()) if final != nombre else ""))
        carpeta = os.path.realpath(os.path.dirname(ruta))
        while carpeta.startswith(inbox + os.sep) and not [x for x in os.listdir(carpeta) if x.lower() not in IGNORAR]:
            for x in os.listdir(carpeta):
                os.remove(os.path.join(carpeta, x))
            os.rmdir(carpeta)
            carpeta = os.path.dirname(carpeta)


# ----------------------------------------------------------------- bitácora

CABECERA = "# Bitácora\n\nQué se hizo en cada sesión, quién lo hizo y qué sigue. Lo más reciente va al final.\n"
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
            entradas.append({"fecha": fecha, "hora": m_ent.group(1), "tipo": "entrada", "linea": m_ent.group(2),
                             "bloque": [linea]})
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
    texto = leer_texto(ruta) or ""
    entradas = entradas_bitacora(texto)
    if args.ultimas:
        for e in entradas[-args.ultimas:]:
            print("%s %s · %s" % (e["fecha"], e["hora"], e["linea"]))
        if not entradas:
            print("Bitácora: sin entradas todavía.")
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
        print('Uso: brainme bitacora "qué se hizo" [--sigue "qué sigue"] | --handoff <archivo> | --ultimas N')
        sys.exit(2)
    momento = datetime.datetime.now()
    hora = momento.strftime("%H:%M")
    nuevo = texto if texto.strip() else CABECERA
    dias = [m.group(1) for m in map(RE_DIA.match, nuevo.split("\n")) if m]
    if not dias or dias[-1] != hoy():
        nuevo = nuevo.rstrip("\n") + "\n\n## %s\n" % hoy()
    if args.handoff:
        cuerpo = (leer_texto(os.path.join(raiz, args.handoff)) or "").strip()
        if not cuerpo:
            print("No encuentro el handoff en %s." % args.handoff)
            sys.exit(2)
        nuevo = nuevo.rstrip("\n") + "\n\n### %s · Handoff · %s\n\n%s\n" % (hora, autor, cuerpo)
        print("Handoff guardado en %s: %s %s" % (BITACORA, hoy(), hora))
    else:
        linea = " ".join(args.texto.split()) + (" **Sigue:** " + " ".join(args.sigue.split()) if args.sigue else "")
        ultima = nuevo.rstrip("\n").split("\n")[-1]
        nuevo = nuevo.rstrip("\n") + ("\n" if RE_ENTRADA.match(ultima) else "\n\n") + "- %s · %s · %s\n" % (hora, autor, linea)
        print("Bitácora: %s %s · %s" % (hoy(), hora, linea))
    escribir(ruta, nuevo)
    # Es lo último de cada flujo: aquí sale lo que quedó por corregir y si el tablero sigue igual
    ruta_tablero = os.path.join(raiz, TABLERO)
    if os.path.exists(ruta_tablero) and datetime.date.fromtimestamp(os.path.getmtime(ruta_tablero)).isoformat() != hoy():
        paso = proximo_paso(raiz)
        print("Tablero sin cambios hoy.%s Si lo hecho resuelve un paso o cambia el plan, actualízalo (y su fecha)."
              % (" Próximo paso: %s." % paso.rstrip(".") if paso else ""))
    if RE_PROYECTO.search(leer_texto(os.path.join(raiz, "CLAUDE.md")) or ""):
        p = Proyecto(raiz)
        lineas = problemas_de(p, de_hoy(p), hoy=True)
        if lineas:
            print("Antes de terminar, corrige:\n" + "\n".join(lineas))


# ------------------------------------------------------------------ ordenar

def cmd_ordenar(args):
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import ordenar
    ordenar.ejecutar(args)


# --------------------------------------------------------------------- main

def main():
    resto = sys.argv[1:]
    while resto[:1] and resto[0].startswith("--raiz"):
        resto = resto[1 if "=" in resto[0] else 2:]
    if resto[:1] and resto[0] in VIEJOS:
        print("En brainme 4 no existe «%s»: usa %s." % (resto[0], VIEJOS[resto[0]]))
        sys.exit(2)
    ap = argparse.ArgumentParser(prog="brainme", description="La herramienta del skill brainme.")
    ap.add_argument("--raiz", default=".", help="carpeta del proyecto (por defecto, la actual)")
    ap.add_argument("--version", action="version", version="brainme " + VERSION)
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("crear", help="carpetas, tablero y CLAUDE.md")
    s.add_argument("carpeta", nargs="?", help="dentro de una carpeta multiproyecto, desde su raíz")
    s.add_argument("--trata", help="de qué trata, en una o dos frases")
    s.add_argument("--prefijo", help="prefijo de las notas de un proyecto de una carpeta multiproyecto")
    s.add_argument("--multiproyecto", action="store_true", help="convierte esta carpeta en multiproyecto")
    s.add_argument("--general", help="carpeta del contexto general (por defecto, general)")
    s.set_defaults(fn=cmd_crear)

    s = sub.add_parser("autor", help="quién firma la bitácora en este computador")
    s.add_argument("nombre", nargs="?")
    s.set_defaults(fn=cmd_autor)

    sub.add_parser("estado", help="para ponerse al día").set_defaults(fn=cmd_estado)

    s = sub.add_parser("buscar", help="notas que hablan de algo")
    s.add_argument("palabras", nargs="+")
    s.set_defaults(fn=cmd_buscar)

    s = sub.add_parser("leer", help="notas o archivos completos")
    s.add_argument("cosas", nargs="+", metavar="nota-o-archivo")
    s.set_defaults(fn=cmd_leer)

    sub.add_parser("inbox", help="lo que hay en 00_inbox/").set_defaults(fn=cmd_inbox)

    s = sub.add_parser("procesado", help="saca del inbox archivos ya procesados")
    s.add_argument("archivos", nargs="+")
    s.add_argument("--a", help="carpeta de destino, de 01 a 05 (por defecto, el archivo de originales)")
    s.set_defaults(fn=cmd_procesado)

    s = sub.add_parser("comprueba", help="lo escrito hoy, o todo el proyecto con --todo")
    s.add_argument("--todo", action="store_true")
    s.set_defaults(fn=cmd_comprueba)

    s = sub.add_parser("bitacora", help="agrega o muestra entradas de bitacora.md")
    s.add_argument("texto", nargs="?")
    s.add_argument("--sigue")
    s.add_argument("--handoff", metavar="ARCHIVO")
    s.add_argument("--ultimas", type=int)
    s.add_argument("--handoff-ultimo", action="store_true")
    s.set_defaults(fn=cmd_bitacora)

    s = sub.add_parser("ordenar", help="ordena una carpeta con avance previo, sin romper enlaces")
    s.add_argument("accion", choices=["inventario", "respaldo", "mover", "deshacer", "wikilinks"])
    s.add_argument("--plan", help="para mover: el plan en JSON")
    s.add_argument("--tabla", action="store_true", help="para inventario: una línea por archivo por ordenar")
    s.add_argument("--registro", help="para deshacer: el registro de un orden anterior")
    s.set_defaults(fn=cmd_ordenar)

    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
