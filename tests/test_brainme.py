"""Pruebas de scripts/brainme.py. No usan Claude: corren el script sobre proyectos de ejemplo
armados en una carpeta temporal.

    python3 -m unittest discover tests
"""

import datetime
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
import zipfile

SCRIPT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts", "brainme.py")
HOY = datetime.date.today().isoformat()


def nota(tipo, resumen, cuerpo, **campos):
    fm = "".join("%s: %s\n" % kv for kv in campos.items())
    return '---\ntipo: %s\nfecha: 2026-01-10\nresumen: "%s"\n%s---\n\n%s\n' % (tipo, resumen, fm, cuerpo) if resumen else \
        "---\ntipo: %s\nfecha: 2026-01-10\n%s---\n\n%s\n" % (tipo, fm, cuerpo)


NOTAS = {
    "01_knowledge/aforo-del-taller.md": nota("conocimiento", "El taller admite 35 personas.",
                                             "Admite 35 personas. Ver [[decision-sala]].",
                                             origen='"acta-octubre.md (inbox, 2026-01-10)"'),
    "01_knowledge/publico-jubilado.md": nota("conocimiento", "Vendrían más jubilados que niños.",
                                             "Sospecha sin comprobar. Ver [[aforo-del-taller]].", certeza="supuesto"),
    "02_decisions/decision-sala.md": nota("decision", "Se usa la sala azul.", "Se usa la sala azul. [[aforo-del-taller]]",
                                          estado="tomada", decidido_por='"la administradora"'),
    "03_open_questions/pregunta-precio.md": nota("pregunta", "¿Cuánto cobrar?", "Falta decidir. [[aforo-del-taller]]",
                                                 estado="abierta", prioridad="alta", quien_puede_responder='"Rosa"'),
    "03_open_questions/pregunta-horario.md": nota("pregunta", "¿Qué horario?", "Sin decidir. [[decision-sala]]",
                                                  estado="abierta", prioridad="baja"),
    "03_open_questions/archive/pregunta-sala.md": nota("pregunta", "¿Qué sala?", "Resuelta en [[decision-sala]].",
                                                       estado="resuelta"),
    ".brainme/inbox-procesado/2026-01-10/acta-octubre.md": "Reunión de octubre.\n- El taller admite 35 personas en la sala azul.\n",
}


def docx(ruta, parrafos):
    w = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    with zipfile.ZipFile(ruta, "w") as z:
        z.writestr("word/document.xml", "<w:document %s><w:body>%s</w:body></w:document>" % (
            w, "".join("<w:p><w:r><w:t>%s</w:t></w:r></w:p>" % p for p in parrafos)))


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.raiz = os.path.join(self.tmp.name, "taller")
        os.makedirs(self.raiz)
        self.env = dict(os.environ, XDG_CONFIG_HOME=os.path.join(self.tmp.name, "config"))

    def tearDown(self):
        self.tmp.cleanup()

    def brain(self, *args, codigo=0, raiz=None):
        r = subprocess.run([sys.executable, SCRIPT, "--raiz", raiz or self.raiz] + list(args),
                           capture_output=True, text=True, env=self.env)
        self.assertEqual(r.returncode, codigo, r.stdout + r.stderr)
        self.assertNotIn("Traceback", r.stderr)
        return r.stdout

    def escribir(self, rel, texto, viejo=True, raiz=None):
        ruta = os.path.join(raiz or self.raiz, rel)
        os.makedirs(os.path.dirname(ruta), exist_ok=True)
        with open(ruta, "w", encoding="utf-8") as f:
            f.write(texto)
        if viejo:  # escrito antes de hoy
            ayer = time.time() - 3 * 86400
            os.utime(ruta, (ayer, ayer))

    def leer(self, rel, raiz=None):
        with open(os.path.join(raiz or self.raiz, rel), encoding="utf-8") as f:
            return f.read()

    def huellas(self):
        datos = {}
        for d, _, archivos in os.walk(self.raiz):
            for a in archivos:
                with open(os.path.join(d, a), "rb") as f:
                    datos[os.path.relpath(os.path.join(d, a), self.raiz)] = hashlib.sha1(f.read()).hexdigest()
        return datos


class Proyecto(Base):
    def setUp(self):
        super().setUp()
        self.brain("crear", "--trata", "Un taller de lectura inventado")
        self.brain("autor", "Ana P.")
        for rel, texto in NOTAS.items():
            self.escribir(rel, texto)

    def test_crear(self):
        for c in ("00_inbox", "01_knowledge", "02_decisions", "03_open_questions", "04_sources", "05_exports"):
            self.assertTrue(os.path.isdir(os.path.join(self.raiz, c)), c)
        claude = self.leer("CLAUDE.md")
        self.assertIn("## brainme", claude)
        self.assertIn("**De qué trata:** Un taller de lectura inventado", claude)
        self.assertIn("@tablero.md", claude)
        self.assertIn("actualizado: " + HOY, self.leer("tablero.md"))
        # Un CLAUDE.md que ya existía conserva el texto del usuario
        otra = os.path.join(self.tmp.name, "otra")
        self.escribir("CLAUDE.md", "# Mío\n\nMis reglas.\n", raiz=otra)
        self.brain("crear", raiz=otra)
        self.assertTrue(self.leer("CLAUDE.md", otra).startswith("# Mío\n\nMis reglas.\n\n## brainme"))
        self.assertIn("lo dejé como estaba", self.brain("crear", raiz=otra))

    def test_autor(self):
        self.assertIn("Autor: Ana P.", self.brain("autor"))
        self.env["XDG_CONFIG_HOME"] = os.path.join(self.tmp.name, "otro")
        self.assertIn("no definido", self.brain("autor"))

    def test_estado(self):
        self.escribir("00_inbox/apuntes.md", "Algo.\n")
        self.brain("bitacora", "Abrí el taller", "--sigue", "Fijar el precio")
        salida = self.brain("estado")
        self.assertIn("Inbox sin procesar: 1 -> apuntes.md", salida)
        self.assertIn("Preguntas abiertas: 2\n  [alta] [[pregunta-precio]] · puede responder: Rosa\n"
                      "  [baja] [[pregunta-horario]]\n", salida)
        self.assertNotIn("pregunta-sala", salida)
        self.assertIn("Últimas decisiones: [[decision-sala]]", salida)
        self.assertIn("por llenar", salida)
        self.assertIn("Última sesión: %s" % HOY, salida)
        self.assertIn("Abrí el taller **Sigue:** Fijar el precio", salida)
        self.assertIn("Notas: 6", salida)
        self.assertIn("no tiene brainme", self.brain("estado", raiz=self.tmp.name))

    def test_buscar(self):
        salida = self.brain("buscar", "salas", "azules")
        self.assertIn("[[decision-sala]]", salida)
        self.assertIn("acta-octubre.md", salida)  # el original ya procesado
        salida = self.brain("buscar", "jubilados")
        self.assertIn("[[publico-jubilado]] [supuesto]", salida)
        self.assertIn("[[pregunta-sala]] [archivada]", self.brain("buscar", "qué sala"))
        self.brain("bitacora", "Hablé con la administradora sobre el aforo")
        self.assertIn("Bitácora (1)", self.brain("buscar", "administradora aforo"))
        varias = self.brain("buscar", "sala, precio")
        self.assertIn("=== sala", varias)
        self.assertIn("=== precio", varias)
        self.assertIn("Dime qué buscar", self.brain("buscar", ",", codigo=2))

    def test_leer(self):
        salida = self.brain("leer", "aforo-del-taller", "[[decision-sala]]", "no-existe")
        self.assertIn("=== 01_knowledge/aforo-del-taller.md", salida)
        self.assertIn("Enlaza: [[decision-sala]]", salida)
        self.assertIn("La enlazan: [[decision-sala]], [[pregunta-precio]], [[publico-jubilado]]", salida)
        self.assertIn("Original: .brainme/inbox-procesado/2026-01-10/acta-octubre.md", salida)
        self.assertIn("No encuentro no-existe", salida)
        self.assertIn("admite 35 personas en la sala azul",
                      self.brain("leer", ".brainme/inbox-procesado/2026-01-10/acta-octubre.md"))
        docx(os.path.join(self.raiz, "04_sources", "contrato.docx"), ["Contrato", "La renta es de 2,350 soles."])
        self.assertIn("La renta es de 2,350 soles.", self.brain("leer", "04_sources/contrato.docx"))

    def test_inbox_y_procesado(self):
        self.escribir("00_inbox/acta.md", "Reunión.\n")
        self.escribir("00_inbox/largo.txt", "palabra " * 3100)
        self.escribir("00_inbox/plano.pdf", "%PDF")
        docx(os.path.join(self.raiz, "00_inbox", "sub", "estudio.docx"), ["El plazo es el 15 de marzo."])
        salida = self.brain("inbox")
        self.assertIn('00_inbox/acta.md · 1 palabra · origen: "acta.md (inbox, %s)"' % HOY, salida)
        self.assertIn("largo: al lector", salida)
        self.assertIn("pdf: al lector", salida)
        self.assertIn("00_inbox/sub/estudio.docx · 7 palabras", salida)
        self.brain("procesado", "acta.md", "largo.txt")
        self.assertTrue(os.path.isfile(os.path.join(self.raiz, ".brainme/inbox-procesado", HOY, "acta.md")))
        # Otro con el mismo nombre no escribe encima: sale con otro nombre y lo dice
        self.escribir("00_inbox/acta.md", "Otra reunión.\n")
        self.assertIn('origen: "acta-2.md (inbox, %s)"' % HOY, self.brain("inbox"))
        self.assertIn("ya había otro acta.md", self.brain("procesado", "acta.md"))
        self.assertEqual(self.leer(".brainme/inbox-procesado/%s/acta.md" % HOY), "Reunión.\n")
        self.brain("procesado", "plano.pdf", "sub/estudio.docx", "--a", "04_sources")
        self.assertTrue(os.path.isfile(os.path.join(self.raiz, "04_sources/estudio.docx")))
        self.assertFalse(os.path.exists(os.path.join(self.raiz, "00_inbox/sub")))
        self.assertIn("El inbox está vacío", self.brain("inbox"))
        self.assertIn("No está en 00_inbox", self.brain("procesado", "01_knowledge/aforo-del-taller.md", codigo=2))
        self.escribir("00_inbox/x.md", "x\n")
        self.assertIn("--a va a una carpeta", self.brain("procesado", "x.md", "--a", "..", codigo=2))

    def test_comprueba_lo_de_hoy(self):
        self.assertIn("Hoy no se escribió ninguna nota", self.brain("comprueba"))
        self.escribir("01_knowledge/buena.md", nota("conocimiento", "Buena.", "Ver [[aforo-del-taller]] y [[contrato.pdf]].",
                                                    autor='"Ana P."'), viejo=False)
        self.escribir("04_sources/contrato.pdf", "%PDF")
        self.assertIn("Lo escrito hoy está completo (1 nota)", self.brain("comprueba"))
        self.escribir("01_knowledge/sin-resumen.md", nota("conocimiento", "", "Ver [[buena]]."), viejo=False)
        self.escribir("01_knowledge/suelta.md", nota("conocimiento", "Suelta.", "Solo un [[contrato.pdf]] y `[[nada]]`."),
                      viejo=False)
        self.escribir("01_knowledge/rota.md", nota("conocimiento", "Rota.", "Ver [[no-existe]] y [[buena|alias]]."), viejo=False)
        salida = self.brain("comprueba")
        self.assertIn("Sin resumen (1): [[sin-resumen]]", salida)
        self.assertIn("Sin enlace a otra nota (1): [[suelta]]", salida)
        self.assertIn("Con enlaces rotos (1): [[rota]] -> [[no-existe]]", salida)
        self.assertIn("Sin autor (brainme autor) (3): [[rota]], [[sin-resumen]], [[suelta]]", salida)
        self.assertNotIn("aforo-del-taller", salida)  # lo de otros días no se revisa
        # La bitácora lo recuerda al final de cada flujo
        self.assertIn("Antes de terminar, corrige:", self.brain("bitacora", "Guardé notas"))

    def test_comprueba_todo(self):
        self.escribir("01_knowledge/aforo-taller.md", nota("conocimiento", "Aforo.", "[[decision-sala]]"))
        self.escribir("01_knowledge/vieja.md", nota("conocimiento", "", "Sin enlaces."))
        self.escribir("01_knowledge/antigua.md", nota("conocimiento", "", "[[decision-sala]]", description='"Resumen antiguo."'))
        for n in (1, 2):
            self.escribir("05_exports/informe-precios-v%d.md" % n, nota("entregable", "Informe.", "[[decision-sala]]"))
        self.escribir("tablero.md", "---\nactualizado: 2026-01-01\n---\n\n## Objetivo actual\nVer [[no-esta]].\n")
        salida = self.brain("comprueba", "--todo")
        self.assertIn("Sin resumen (1): [[vieja]]", salida)
        self.assertIn("Sin enlace a otra nota (1): [[vieja]]", salida)
        self.assertIn("En el tablero, enlaces rotos: [[no-esta]]", salida)
        self.assertIn("Posibles duplicados (1): [[aforo-del-taller]] y [[aforo-taller]]", salida)
        self.assertIn("Supuestos, por si ya se confirmaron (1): [[publico-jubilado]]", salida)

    def test_campos_de_decisiones_y_preguntas(self):
        self.escribir("02_decisions/decision-precio.md", nota("decision", "Se cobra 20 soles.", "[[pregunta-precio]]",
                                                               estado="tomada", decidido_por='"<persona o instancia>"'))
        self.escribir("02_decisions/decision-horario.md", nota("decision", "Quizá de noche.", "[[pregunta-horario]]",
                                                                estado="propuesta"))
        self.escribir("03_open_questions/pregunta-cupo.md", nota("pregunta", "¿Hay cupo?", "[[aforo-del-taller]]",
                                                                  estado="abierta"))
        salida = self.brain("comprueba", "--todo")
        self.assertIn("Decisiones sin decidido_por (1): [[decision-precio]]", salida)  # el <...> no cuenta
        self.assertIn("Preguntas abiertas sin prioridad (1): [[pregunta-cupo]]", salida)  # la resuelta no
        self.assertNotIn("Sin autor", salida)  # de lo escrito antes no siempre se sabe

    def test_decisiones_que_cambian(self):
        self.escribir("02_decisions/decision-sala-roja.md", nota(
            "decision", "Se usa la sala roja.", "Cambia la sala. [[aforo-del-taller]]", estado="tomada",
            decidido_por='"la administradora"', reemplaza_a='"[[decision-sala]]"'))
        self.assertIn("Decisiones reemplazadas que no dicen estado: revertida (1): [[decision-sala]] (la reemplaza "
                      "[[decision-sala-roja]])", self.brain("comprueba", "--todo"))
        self.assertIn("[[decision-sala]] [reemplazada por [[decision-sala-roja]]]", self.brain("buscar", "sala azul"))
        self.assertIn("La reemplaza: [[decision-sala-roja]]", self.brain("leer", "decision-sala"))
        self.escribir("02_decisions/decision-sala.md", NOTAS["02_decisions/decision-sala.md"].replace(
            "estado: tomada", "estado: revertida"))
        self.assertNotIn("reemplazadas", self.brain("comprueba", "--todo"))
        self.assertIn("[[decision-sala]] [revertida, reemplazada por [[decision-sala-roja]]]",
                      self.brain("buscar", "sala azul"))

    def test_jardin_por_tandas(self):
        salida = self.brain("jardin")
        self.assertIn("Por revisar: 5 notas", salida)  # 01 a 03, sin la archivada
        self.assertLess(salida.index("[[decision-sala]]"), salida.index("[[aforo-del-taller]]"))  # decisiones primero
        self.assertLess(salida.index("[[aforo-del-taller]]"), salida.index("[[publico-jubilado]]"))  # supuestos después
        self.assertIn("[[aforo-del-taller]] · original: .brainme/inbox-procesado/2026-01-10/acta-octubre.md", salida)
        self.assertIn("[[decision-sala]] · sin origen", salida)
        self.assertIn("Notas: 6 · 5 sin revisar contra su original", self.brain("estado"))
        self.assertIn("Por revisar: 3 notas", self.brain("jardin", "--hecho", "decision-sala", "[[aforo-del-taller]]"))
        self.assertNotIn("[[decision-sala]]", self.brain("jardin"))
        # Una nota que cambia vuelve a la lista
        self.escribir("02_decisions/decision-sala.md", NOTAS["02_decisions/decision-sala.md"] + "Otra línea.\n")
        self.assertIn("[[decision-sala]]", self.brain("jardin"))
        self.brain("jardin", "--hecho", "decision-sala", "aforo-del-taller", "publico-jubilado", "pregunta-precio",
                   "pregunta-horario")
        self.assertIn("Por revisar: 0 notas", self.brain("jardin"))
        self.assertNotIn("sin revisar", self.brain("estado"))

    def test_leer_con_original(self):
        salida = self.brain("leer", "--original", "aforo-del-taller", "aforo-del-taller")
        self.assertEqual(salida.count("=== .brainme/inbox-procesado/2026-01-10/acta-octubre.md"), 1)
        self.assertIn("· original de [[aforo-del-taller]]", salida)
        self.assertIn("admite 35 personas en la sala azul", salida)
        self.assertNotIn("sala azul.\n", self.brain("leer", "aforo-del-taller"))  # sin --original, solo la ruta

    def test_tablero_largo(self):
        self.escribir("tablero.md", "---\nactualizado: 2026-01-01\n---\n\n" + "".join("- paso %d\n" % i for i in range(45)))
        self.assertIn("El tablero tiene 45 líneas (máximo 40)", self.brain("comprueba", "--todo"))

    def test_buscar_pone_lo_vigente_primero(self):
        self.escribir("02_decisions/decision-sala-roja.md", nota(
            "decision", "Se usa la sala roja.", "Cambia la sala. [[aforo-del-taller]]", estado="tomada",
            decidido_por='"la administradora"', reemplaza_a='"[[decision-sala]]"'))
        salida = self.brain("buscar", "sala")
        self.assertLess(salida.index("[[decision-sala-roja]]"), salida.index("[[decision-sala]] [reemplazada"))

    def test_bitacora(self):
        self.env["XDG_CONFIG_HOME"] = os.path.join(self.tmp.name, "sin-autor")
        self.assertIn("Falta el autor", self.brain("bitacora", "Algo", codigo=2))
        self.env["XDG_CONFIG_HOME"] = os.path.join(self.tmp.name, "config")
        ayer = time.time() - 86400
        os.utime(os.path.join(self.raiz, "tablero.md"), (ayer, ayer))
        salida = self.brain("bitacora", "Procesé el inbox", "--sigue", "Llamar a Rosa")
        self.assertIn("Tablero sin cambios hoy", salida)
        os.utime(os.path.join(self.raiz, "tablero.md"))
        self.assertNotIn("Tablero", self.brain("bitacora", "Otra cosa"))
        texto = self.leer("bitacora.md")
        self.assertIn("## %s\n\n- " % HOY, texto)
        self.assertIn("· Ana P. · Procesé el inbox **Sigue:** Llamar a Rosa\n- ", texto)
        self.escribir(".brainme/handoff.md", "**Objetivo:** probar.\n**Siguiente paso:** uno.")
        self.assertIn("Handoff guardado", self.brain("bitacora", "--handoff", ".brainme/handoff.md"))
        self.assertIn("**Siguiente paso:** uno.", self.brain("bitacora", "--handoff-ultimo"))
        self.assertIn("Handoff · Ana P.", self.brain("bitacora", "--ultimas", "1"))
        self.assertEqual(self.leer("bitacora.md").count("## %s" % HOY), 1)

    def test_leer_y_revisar_no_cambian_nada(self):
        self.escribir("00_inbox/acta.md", "Reunión.\n")
        antes = self.huellas()
        for args in (["estado"], ["buscar", "sala"], ["leer", "aforo-del-taller"], ["comprueba"], ["comprueba", "--todo"],
                     ["inbox"], ["bitacora", "--ultimas", "3"], ["autor"]):
            self.brain(*args)
        self.assertEqual(self.huellas(), antes)

    def test_comandos_viejos(self):
        for viejo, nuevo in (("texto", "brainme leer"), ("verificar", "comprueba --todo"), ("guia", "references/"),
                             ("inventario", "brainme ordenar inventario"), ("mover", "brainme ordenar mover")):
            self.assertIn(nuevo, self.brain(viejo, "x", codigo=2))


class Multiproyecto(Base):
    def setUp(self):
        super().setUp()
        self.brain("crear", "--multiproyecto", "--trata", "Un estudio inventado")
        self.brain("autor", "Ana P.")

    def test_crear(self):
        claude = self.leer("CLAUDE.md")
        self.assertIn("## brainme · multiproyecto", claude)
        self.assertIn("**Contexto general:** `general/`", claude)
        self.assertIn("**De qué trata:** Un estudio inventado", claude)
        self.assertIn("## brainme\n", self.leer("general/CLAUDE.md"))
        self.assertIn("Un proyecto de una carpeta multiproyecto necesita --prefijo",
                      self.brain("crear", "proyectos/2026/acme", codigo=2))
        self.assertIn("cada proyecto va en proyectos/<año>/", self.brain("crear", "acme", codigo=2))
        self.brain("crear", "proyectos/2026/acme", "--prefijo", "acme", "--trata", "Precios de Acme")
        ficha = self.leer("proyectos/2026/acme/CLAUDE.md")
        self.assertIn("- **Estado:** activo\n- **Prefijo de notas:** `acme-`", ficha)
        self.assertIn("ya es multiproyecto", self.brain("crear", "--multiproyecto"))

    def test_panorama_y_proyecto(self):
        self.brain("crear", "proyectos/2026/acme", "--prefijo", "acme-", "--trata", "Precios de Acme")
        self.brain("crear", "proyectos/2025/viejo", "--prefijo", "viejo-")
        p = os.path.join(self.raiz, "proyectos/2026/acme")
        ficha = self.leer("proyectos/2025/viejo/CLAUDE.md").replace("**Estado:** activo", "**Estado:** cerrado 2025-12-01")
        self.escribir("proyectos/2025/viejo/CLAUDE.md", ficha)
        self.brain("bitacora", "Abrí el proyecto", "--sigue", "Llamar al cliente", raiz=p)
        salida = self.brain("estado")
        self.assertIn("Carpeta multiproyecto: taller · contexto general: general/", salida)
        self.assertIn("- 2026/acme · Precios de Acme", salida)
        self.assertIn("Abrí el proyecto", salida)
        self.assertIn("Cerrados (1): 2025/viejo", salida)
        # En el proyecto: los enlaces al contexto general funcionan, y las notas llevan el prefijo
        self.escribir("general/01_knowledge/metodo-de-entrevistas.md", nota("conocimiento", "Método.", "Cinco preguntas."))
        self.escribir("01_knowledge/acme-cliente.md", nota("conocimiento", "Paga 3,400.", "Usa [[metodo-de-entrevistas]]."),
                      viejo=False, raiz=p)
        self.escribir("01_knowledge/sin-prefijo.md", nota("conocimiento", "Algo.", "[[acme-cliente]]"), viejo=False, raiz=p)
        salida = self.brain("comprueba", raiz=p)
        self.assertNotIn("rotos", salida)
        self.assertIn("Sin el prefijo acme- (1): [[sin-prefijo]]", salida)
        self.assertIn("prefijo acme-", self.brain("estado", raiz=p))
        self.assertIn("En el contexto general (general/)", self.brain("buscar", "metodo entrevistas", raiz=p))


if __name__ == "__main__":
    unittest.main()


class Ordenar(Base):
    """Una carpeta con avance previo: notas en carpetas propias, wikilinks con ruta, un link
    markdown relativo, una imagen incrustada, un canvas y dos notas con el mismo nombre."""

    ANTES = {
        "Reuniones/2024-05-02 Kickoff.md": "# Kickoff\nSe habló de [[Ideas/precio por uso]] y ver "
                                           "[notas](../Cliente%20A/ideas.md).\n![[diagrama.png]]\n`[[Ideas/precio por uso]]`\n",
        "Ideas/precio por uso.md": "---\ntipo: idea\n---\n# Precio por uso\nVer [[Reuniones/2024-05-02 Kickoff|el kickoff]].\n",
        "Cliente A/ideas.md": "# Ideas A\nNada [[precio por uso]].\n",
        "Ideas/ideas.md": "# Ideas\n",
        "Reuniones/diagrama.png": "PNG",
        "mapa.canvas": '{"nodes": [{"id": "1", "type": "file", "file": "Ideas/precio por uso.md"}], "edges": []}',
    }
    PLAN = {"movimientos": [
        {"de": "Reuniones/2024-05-02 Kickoff.md", "a": "00_inbox/", "tags": ["reuniones"]},
        {"de": "Reuniones/diagrama.png", "a": "00_inbox/"},
        {"de": "Ideas/precio por uso.md", "a": "01_knowledge/precio-por-uso.md", "frontmatter": {"resumen": "Cobrar por uso."},
         "tags": ["ideas"]},
        {"de": "Cliente A/ideas.md", "a": "00_inbox/ideas-cliente-a.md", "tags": ["cliente-a"]},
        {"de": "Ideas/ideas.md", "a": "00_inbox/"},
        {"de": "mapa.canvas", "a": "05_exports/"},
    ]}

    def setUp(self):
        super().setUp()
        self.brain("crear", "--trata", "Un proyecto que ya tenía notas")
        for rel, texto in self.ANTES.items():
            self.escribir(rel, texto)
        os.makedirs(os.path.join(self.raiz, ".obsidian"))

    def plan(self, plan):
        self.escribir(".brainme/plan-orden.json", json.dumps(plan))
        return self.brain("ordenar", "mover", "--plan", ".brainme/plan-orden.json")

    def test_inventario_no_cambia_nada(self):
        antes = self.huellas()
        salida = self.brain("ordenar", "inventario", "--tabla")
        self.assertIn("6 por ordenar", salida)
        self.assertIn("ideas: Cliente A/ideas.md, Ideas/ideas.md", salida)  # mismo nombre
        self.assertIn("Ideas/precio por uso.md | nota | Precio por uso", salida)
        despues = self.huellas()
        self.assertEqual({k: v for k, v in despues.items() if not k.startswith(".brainme")}, antes)

    def test_mover_corrige_enlaces_y_deshacer_los_devuelve(self):
        self.assertIn("Respaldo creado", self.brain("ordenar", "respaldo"))
        salida = self.plan(self.PLAN)
        self.assertIn("Archivos movidos: 6", salida)
        self.assertIn("Enlaces rotos: 0 antes, 0 después", salida)
        kickoff = self.leer("00_inbox/2024-05-02 Kickoff.md")
        self.assertIn("[[precio-por-uso]]", kickoff)
        self.assertIn("[notas](ideas-cliente-a.md)", kickoff)
        self.assertIn("`[[Ideas/precio por uso]]`", kickoff)  # el código no se toca
        self.assertIn("tags: [reuniones]", kickoff)
        precio = self.leer("01_knowledge/precio-por-uso.md")
        self.assertIn("tipo: idea", precio)  # lo que el usuario tenía se conserva
        self.assertIn("resumen: Cobrar por uso.", precio)
        self.assertIn("[[2024-05-02 Kickoff|el kickoff]]", precio)
        self.assertIn("01_knowledge/precio-por-uso.md", self.leer("05_exports/mapa.canvas"))
        for carpeta in ("Ideas", "Reuniones", "Cliente A"):
            self.assertFalse(os.path.exists(os.path.join(self.raiz, carpeta)), carpeta)
        self.assertIn("Archivos movidos: 6", self.brain("ordenar", "deshacer"))
        self.assertIn("[notas](../Cliente%20A/ideas.md)", self.leer("Reuniones/2024-05-02 Kickoff.md"))
        self.assertIn('"file": "Ideas/precio por uso.md"', self.leer("mapa.canvas"))
        self.assertIn("No hay ningún orden que deshacer", self.brain("ordenar", "deshacer"))

    def test_plan_con_error_no_mueve_nada(self):
        antes = self.huellas()
        self.escribir(".brainme/plan-orden.json", json.dumps({"movimientos": [
            {"de": "Ideas/ideas.md", "a": "00_inbox/x.md"}, {"de": "Cliente A/ideas.md", "a": "00_inbox/x.md"},
            {"de": "no-existe.md", "a": "00_inbox/"}, {"de": "mapa.canvas", "a": ".obsidian/"}]}))
        salida = self.brain("ordenar", "mover", "--plan", ".brainme/plan-orden.json", codigo=2)
        self.assertIn("No se movió nada", salida)
        self.assertIn("Varios archivos irían a 00_inbox/x.md", salida)
        self.assertIn("No existe: no-existe.md", salida)
        self.assertIn("Destino no permitido", salida)
        self.assertEqual({k: v for k, v in self.huellas().items() if not k.startswith(".brainme")}, antes)

    def test_wikilinks(self):
        self.assertIn("convertidos a wikilinks: 1", self.brain("ordenar", "wikilinks"))
        self.assertIn("[[Cliente A/ideas|notas]]", self.leer("Reuniones/2024-05-02 Kickoff.md"))

    def test_resumenes(self):
        self.plan(self.PLAN)
        self.assertIn("Todas las notas tienen resumen", self.brain("ordenar", "resumenes"))  # lo del inbox no cuenta
        self.escribir("01_knowledge/vacia.md", '---\ntipo: conocimiento\nresumen: "<la idea>"\n---\n\nVacía.\n')
        self.escribir("01_knowledge/sin-frontmatter.md", "Solo texto.\n")
        salida = self.brain("ordenar", "resumenes")
        self.assertIn("Sin resumen: 2 notas, en 1 lote de hasta 25", salida)
        self.assertIn('"01_knowledge/vacia.md"', self.leer(".brainme/resumenes/lote-01.json"))
        self.escribir(".brainme/resumenes/r.json", json.dumps({
            "05_exports/mapa.canvas": "No es nota.", "01_knowledge/vacia.md": "Una nota: vacía.",
            "01_knowledge/precio-por-uso.md": "Otro resumen.", "../fuera.md": "x", "01_knowledge/larga.md": "x" * 400}))
        salida = self.brain("ordenar", "resumenes", "--poner", ".brainme/resumenes/r.json")
        self.assertIn("Resúmenes escritos: 1. Ya tenían resumen: 1.", salida)
        self.assertIn("Sin escribir (3)", salida)
        vacia = self.leer("01_knowledge/vacia.md")
        self.assertIn('resumen: "Una nota: vacía."', vacia)
        self.assertNotIn("<la idea>", vacia)
        self.assertIn("resumen: Cobrar por uso.", self.leer("01_knowledge/precio-por-uso.md"))  # nunca cambia uno que ya está

    def test_no_ordena_la_raiz_de_un_multiproyecto(self):
        multi = os.path.join(self.tmp.name, "estudio")
        os.makedirs(multi)
        self.brain("crear", "--multiproyecto", raiz=multi)
        self.assertIn("raíz de una carpeta multiproyecto", self.brain("ordenar", "inventario", raiz=multi, codigo=2))
