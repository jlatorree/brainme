"""Pruebas de scripts/brainme.py. No usan Claude: corren el script sobre proyectos de ejemplo
armados en una carpeta temporal.

    python3 -m unittest discover tests
"""

import datetime
import hashlib
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
                                          estado="tomada"),
    "03_open_questions/pregunta-precio.md": nota("pregunta", "¿Cuánto cobrar?", "Falta decidir. [[aforo-del-taller]]",
                                                 estado="abierta", prioridad="alta"),
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
        self.assertIn("Preguntas abiertas: 2\n  [alta] [[pregunta-precio]]\n  [baja] [[pregunta-horario]]", salida)
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
        self.escribir("01_knowledge/buena.md", nota("conocimiento", "Buena.", "Ver [[aforo-del-taller]] y [[contrato.pdf]]."),
                      viejo=False)
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
        for viejo, nuevo in (("texto", "brainme leer"), ("jardin", "comprueba --todo"), ("guia", "references/")):
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
