"""Pruebas mínimas de scripts/brainme.py. No usan Claude: corren el script sobre un
proyecto de ejemplo armado en una carpeta temporal.

    python3 -m unittest discover tests
"""

import datetime
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
import zipfile

SCRIPT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts", "brainme.py")

# Un proyecto de una versión anterior: sin versión ni resúmenes, con el aviso y los
# archivos de Graphify, una versión vieja de un entregable y una copia en conflicto de iCloud.
ARCHIVOS = {
    "CLAUDE.md": "# viejo\n\n## brainme\n\n**Proyecto:** viejo · **De qué trata:** prueba · "
                 "**Configurado con brainme:** 2026-01-01\n\n## graphify\n\n"
                 "For codebase questions, first run graphify query.\n",
    ".claude/settings.json": json.dumps({"hooks": {"PreToolUse": [{"matcher": "Bash|Grep", "hooks": [
        {"type": "command", "command": "\"$HOME/.local/bin/graphify\" hook-guard search"}]}]}}),
    ".graphifyignore": "graphify-out/\n00_inbox/\n",
    "graphify-out/graph.json": "{}\n",
    "graphify-out/2026-01-01/graph.json": "{}\n",
    "01_knowledge/idea-central.md": "---\ntitulo: \"Idea central\"\ntipo: conocimiento\n---\n\n"
                                    "La idea. Ver [[decision-precio]].\n",
    "01_knowledge/idea-larga.md": "---\ntitulo: \"Larga\"\ntipo: conocimiento\n---\n\n" + "palabra " * 1200,
    "01_knowledge/idea-central 2.md": "copia en conflicto\n",
    "02_decisions/decision-precio.md": "---\ntitulo: \"Precio\"\ntipo: decision\nresumen: \"Cobramos por fase.\"\n"
                                       "---\n\nCuerpo [[idea-central]] [[idea-central]].\n",
    "05_exports/reports/informe-v1.md": "v1\n",
    "05_exports/reports/informe-v2.md": "v2\n",
    "05_exports/presentations/deck-v1.html": "<html></html>\n",
    "05_exports/presentations/deck-v1.md": "---\ntipo: entregable\nresumen: \"Ficha del deck.\"\n---\n\nFicha del deck.\n",
    "05_exports/presentations/deck-v2.html": "<html></html>\n",
    "05_exports/presentations/_versiones/deck-v0.html": "<html></html>\n",
    "05_exports/data/.DS_Store": "",
}


class BrainmeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.raiz = os.path.join(self.tmp.name, "proyecto")
        for rel, texto in ARCHIVOS.items():
            ruta = os.path.join(self.raiz, rel)
            os.makedirs(os.path.dirname(ruta), exist_ok=True)
            with open(ruta, "w", encoding="utf-8") as f:
                f.write(texto)
        self.env = dict(os.environ, XDG_CONFIG_HOME=os.path.join(self.tmp.name, "config"),
                        CLAUDE_CONFIG_DIR=os.path.join(self.tmp.name, "claude"))

    def tearDown(self):
        self.tmp.cleanup()

    def brain(self, *args, codigo=0, raiz=None):
        r = subprocess.run([sys.executable, SCRIPT, "--raiz", raiz or self.raiz] + list(args),
                           capture_output=True, text=True, env=self.env)
        self.assertEqual(r.returncode, codigo, r.stdout + r.stderr)
        return r.stdout

    def leer(self, rel):
        with open(os.path.join(self.raiz, rel), encoding="utf-8") as f:
            return f.read()

    def test_migrar_aplica_y_deshace(self):
        salida = self.brain("migrar")
        self.assertIn("Cambios automáticos (brainme migrar --aplicar): 6", salida)
        self.brain("migrar", "--aplicar")
        claude_md = self.leer("CLAUDE.md")
        self.assertTrue(claude_md.endswith("**Configurado con brainme:** 2026-01-01 · **Versión:** 3.3.0\n\n"
                                           "Lo vigente del proyecto está en su tablero: @tablero.md\n"))
        self.assertIn("## Próximos pasos", self.leer("tablero.md"))
        self.assertNotIn("## graphify", claude_md)
        self.assertEqual(json.loads(self.leer(".claude/settings.json")), {})
        # Los archivos de Graphify quedan como estaban
        self.assertEqual(self.leer(".graphifyignore"), ARCHIVOS[".graphifyignore"])
        self.assertTrue(os.path.exists(os.path.join(self.raiz, "graphify-out/2026-01-01/graph.json")))
        self.assertFalse(os.path.exists(os.path.join(self.raiz, "05_exports/data")))
        self.assertTrue(os.path.exists(os.path.join(self.raiz, "bitacora.md")))
        self.assertIn("No hay cambios automáticos", self.brain("migrar", "--aplicar"))
        # La 3.3 no cambia el formato: un proyecto de la 3.2 no tiene nada que migrar
        with open(os.path.join(self.raiz, "CLAUDE.md"), "w", encoding="utf-8") as f:
            f.write(claude_md.replace("**Versión:** 3.3.0", "**Versión:** 3.2.0"))
        self.assertNotIn("Migración pendiente", self.brain("estado"))
        with open(os.path.join(self.raiz, "CLAUDE.md"), "w", encoding="utf-8") as f:
            f.write(claude_md)
        self.brain("migrar", "--deshacer")
        self.assertEqual(self.leer("CLAUDE.md"), ARCHIVOS["CLAUDE.md"])
        self.assertFalse(os.path.exists(os.path.join(self.raiz, "bitacora.md")))
        self.assertFalse(os.path.exists(os.path.join(self.raiz, "tablero.md")))
        self.assertTrue(os.path.isdir(os.path.join(self.raiz, "05_exports/data")))

    def test_resumenes_por_lotes_sin_tocar_el_texto(self):
        salida = self.brain("sin-resumen", "--lotes", "1")
        self.assertIn("Notas sin resumen: 4, en 4 lotes", salida)
        with open(os.path.join(self.raiz, ".brainme/resumenes/lote-01.json"), encoding="utf-8") as f:
            self.assertEqual(json.load(f), ["01_knowledge/idea-central.md"])  # la más enlazada primero
        with open(os.path.join(self.raiz, "r.json"), "w", encoding="utf-8") as f:
            json.dump({"01_knowledge/idea-central.md": "La idea: precio por fase.",
                       "02_decisions/decision-precio.md": "No debe cambiar."}, f)
        self.assertIn("Resúmenes escritos: 1 · ya tenían: 1", self.brain("poner-resumenes", "--desde", "r.json"))
        nota = self.leer("01_knowledge/idea-central.md")
        self.assertIn('resumen: "La idea: precio por fase."\n---\n\nLa idea. Ver [[decision-precio]].\n', nota)
        self.assertIn('resumen: "Cobramos por fase."', self.leer("02_decisions/decision-precio.md"))

    def test_bitacora_pide_autor_y_guarda_handoff(self):
        self.brain("bitacora", "Algo", codigo=2)
        self.brain("autor", "Ana P.")
        self.brain("bitacora", "Procesé el inbox", "--sigue", "graduar la pregunta")
        with open(os.path.join(self.raiz, "h.md"), "w", encoding="utf-8") as f:
            f.write("**Objetivo:** probar.\n\n- uno\n- dos\n")
        self.brain("bitacora", "--handoff", "h.md")
        self.brain("bitacora", "Después del handoff")
        ultimas = self.brain("bitacora", "--ultimas", "5").strip().split("\n")
        self.assertEqual(len(ultimas), 3)
        self.assertIn("Ana P. · Procesé el inbox **Sigue:** graduar la pregunta", ultimas[0])
        self.assertIn("Handoff · Ana P.", ultimas[1])
        self.assertIn("- uno\n- dos", self.brain("bitacora", "--handoff-ultimo"))

    def test_estado_avisa_lo_nuevo(self):
        salida = self.brain("estado")
        self.assertIn("Migración pendiente", salida)
        self.assertIn("Notas sin resumen: 4", salida)
        self.assertIn("Notas largas (más de 1.000 palabras): 1 -> [[idea-larga]]", salida)
        self.assertIn("Copias en conflicto de iCloud: 1", salida)
        self.assertIn("Entregables por ordenar en 05_exports: 6 archivos", salida)

    def test_mapa_de_enlaces(self):
        with open(os.path.join(self.raiz, "01_knowledge/idea-larga.md"), "a", encoding="utf-8") as f:
            f.write("\nVer [[nota-que-no-existe]].\n")
        salida = self.brain("mapa")
        self.assertIn("Mapa: 6 notas, 1 conexión · 1 isla, 1 enlace roto (revisa el jardín)", salida)
        self.assertIn("[[nota-que-no-existe]] en [[idea-larga]]", salida)
        nota = self.brain("mapa", "--nota", "decision-precio")
        self.assertIn("[[decision-precio]] · Cobramos por fase. (02_decisions)", nota)
        self.assertIn("La enlazan (1):\n  [[idea-central]]", nota)
        camino = self.brain("mapa", "--camino", "idea-central", "decision-precio")
        self.assertIn("[[idea-central]] → [[decision-precio]]", camino)
        # Después de escribir: lo suelto y lo roto de hoy, con nombre; lo viejo, solo en la línea
        ayer = os.path.getmtime(os.path.join(self.raiz, "01_knowledge/idea-larga.md")) - 2 * 86400
        comprueba = self.brain("comprueba")
        self.assertTrue(comprueba.startswith("Mapa: 6 notas"))
        self.assertIn("Escrita hoy, con enlace roto: [[nota-que-no-existe]] en [[idea-larga]]", comprueba)
        self.assertIn("Escritas hoy, sin enlaces a otra nota (1): [[idea-larga]]", comprueba)
        os.utime(os.path.join(self.raiz, "01_knowledge/idea-larga.md"), (ayer, ayer))
        self.assertNotIn("idea-larga", self.brain("comprueba"))
        self.assertIn("Entregables de hoy que no enlazan lo que los sustenta", self.brain("comprueba"))
        self.assertEqual(self.brain("sincroniza"), self.brain("comprueba"))  # nombre hasta la 3.2
        self.assertTrue(os.path.exists(os.path.join(self.raiz, "graphify-out/2026-01-01/graph.json")))
        self.assertNotIn("graphify", self.brain("inventario"))

    def zip_office(self, rel, partes):
        os.makedirs(os.path.dirname(os.path.join(self.raiz, rel)), exist_ok=True)
        with zipfile.ZipFile(os.path.join(self.raiz, rel), "w") as z:
            for nombre, xml in partes.items():
                z.writestr(nombre, xml)

    def test_texto_de_office_y_archivos_sin_ficha(self):
        W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
        self.zip_office("01_knowledge/brief.docx", {"word/document.xml":
            '<w:document %s><w:body><w:p><w:r><w:t>Objetivo:</w:t></w:r><w:r><w:tab/><w:t>bajar costos</w:t>'
            '</w:r></w:p><w:tbl><w:tr><w:tc><w:p><w:r><w:t>Plazo</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r>'
            '<w:t>12 semanas</w:t></w:r></w:p></w:tc></w:tr></w:tbl></w:body></w:document>' % W})
        self.assertEqual(self.brain("texto", "01_knowledge/brief.docx"), "Objetivo:\tbajar costos\nPlazo | 12 semanas\n")

        P = ('xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" '
             'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
             'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"')
        R = 'xmlns="http://schemas.openxmlformats.org/package/2006/relationships"'
        self.zip_office("05_exports/presentations/deck.pptx", {
            "ppt/presentation.xml": '<p:presentation %s><p:sldIdLst><p:sldId id="256" r:id="rId2"/>'
                                    '</p:sldIdLst></p:presentation>' % P,
            "ppt/_rels/presentation.xml.rels": '<Relationships %s><Relationship Id="rId2" Type="x/slide" '
                                               'Target="slides/slide1.xml"/></Relationships>' % R,
            "ppt/slides/slide1.xml": '<p:sld %s><a:p><a:r><a:t>Precio por fase</a:t></a:r></a:p></p:sld>' % P,
            "ppt/slides/_rels/slide1.xml.rels": '<Relationships %s><Relationship Id="rId1" Type="x/notesSlide" '
                                                'Target="../notesSlides/notesSlide1.xml"/></Relationships>' % R,
            "ppt/notesSlides/notesSlide1.xml": '<p:notes %s><p:sp><p:nvSpPr><p:nvPr><p:ph type="body"/></p:nvPr>'
                                               '</p:nvSpPr><a:p><a:r><a:t>Decirlo al final</a:t></a:r></a:p></p:sp>'
                                               '<p:sp><p:nvSpPr><p:nvPr><p:ph type="sldNum"/></p:nvPr></p:nvSpPr>'
                                               '<a:p><a:r><a:t>1</a:t></a:r></a:p></p:sp></p:notes>' % P})
        self.assertEqual(self.brain("texto", "05_exports/presentations/deck.pptx"),
                         "## Diapositiva 1\nPrecio por fase\nNotas: Decirlo al final\n")

        S = ('xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
             'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"')
        filas = "".join('<row r="%d"><c r="A%d" t="inlineStr"><is><t>Fase %d</t></is></c><c r="C%d"><v>%d</v></c></row>'
                        % (i, i, i, i, i * 100) for i in range(2, 5))
        self.zip_office("01_knowledge/precios.xlsx", {
            "xl/workbook.xml": '<workbook %s><sheets><sheet name="Precios" sheetId="1" r:id="rId1"/></sheets>'
                               '</workbook>' % S,
            "xl/_rels/workbook.xml.rels": '<Relationships %s><Relationship Id="rId1" Type="x/worksheet" '
                                          'Target="worksheets/sheet1.xml"/></Relationships>' % R,
            "xl/sharedStrings.xml": '<sst %s><si><t>Fase</t></si><si><t>Monto</t></si></sst>' % S,
            "xl/worksheets/sheet1.xml": '<worksheet %s><sheetData><row r="1"><c r="A1" t="s"><v>0</v></c>'
                                        '<c r="C1" t="s"><v>1</v></c></row>%s</sheetData></worksheet>' % (S, filas)})
        self.assertEqual(self.brain("texto", "01_knowledge/precios.xlsx", "--filas", "2"),
                         "## Hoja: Precios\nFase |  | Monto\nFase 2 |  | 200\n(2 filas más: --filas 0 las muestra todas)\n")
        self.assertIn("Fase 4 |  | 400", self.brain("texto", "01_knowledge/precios.xlsx"))
        self.assertIn("textutil", self.brain("texto", "01_knowledge/idea-central.md", codigo=2))

        # Sin ficha: lo que ninguna nota enlaza, incrusta ni nombra en archivo o pdf
        for rel in ("01_knowledge/foto.png", "01_knowledge/diagrama.png",
                    "04_sources/literature/perez-2023.pdf", "05_exports/diagrams/journey/journey-v2.png"):
            os.makedirs(os.path.dirname(os.path.join(self.raiz, rel)), exist_ok=True)
            with open(os.path.join(self.raiz, rel), "wb") as f:
                f.write(b"x")
        archivos = {"01_knowledge/idea-central.md": "\n![[diagrama.png]]\n",
                    "04_sources/literature/perez-2023-onboarding.md": "---\ntipo: literatura\npdf: \"perez-2023.pdf\"\n---\n",
                    "05_exports/diagrams/journey/journey.md": "---\ntipo: entregable\n---\n"}
        for rel, texto in archivos.items():
            with open(os.path.join(self.raiz, rel), "a", encoding="utf-8") as f:
                f.write(texto)
        linea = [l for l in self.brain("estado").split("\n") if l.startswith("Archivos sin ficha")]
        self.assertEqual(linea, ["Archivos sin ficha: 1 imagen, 2 archivos de Office, 1 presentación -> "
                                 "brief.docx, foto.png, precios.xlsx, deck.pptx (dales ficha o enlázalos desde una nota)"])

    def test_multiproyecto_de_una_tesis(self):
        self.probar_tesis("multiproyecto")

    def test_multiproyecto_con_el_nombre_hasta_la_32(self):
        self.probar_tesis("espacio")

    def probar_tesis(self, nombre):
        tesis = os.path.join(self.tmp.name, "tesis")
        os.makedirs(tesis)
        with open(os.path.join(tesis, "CLAUDE.md"), "w", encoding="utf-8") as f:
            f.write("# Tesis\n\nMis reglas.\n\n## brainme · %s\n\n**%s:** mi tesis · **Contexto general:** "
                    "`marco/` · **Versión:** 3.0.0\n\n" % (nombre, nombre.capitalize()) + "### Ficha de cada proyecto\n\n- **Estado:** activo\n"
                    "- **Prefijo de notas:**\n- **Pregunta del estudio:**\n")
        self.brain("crear", "marco", "--trata", "Marco teórico común", raiz=tesis)
        marco = os.path.join(tesis, "marco")
        self.brain("crear", "proyectos/estudio-docentes", "--prefijo", "ed", raiz=marco, codigo=1)  # sin año
        self.brain("crear", "proyectos/2026/estudio-docentes", raiz=marco, codigo=1)  # sin prefijo
        salida = self.brain("crear", "proyectos/2026/estudio-docentes", "--prefijo", "ed", raiz=marco)
        self.assertIn("Ficha por completar: Pregunta del estudio", salida)
        estudio = os.path.join(tesis, "proyectos", "2026", "estudio-docentes")
        with open(os.path.join(estudio, "CLAUDE.md"), encoding="utf-8") as f:
            ficha = f.read()
        self.assertIn("## Proyecto\n\n- **Estado:** activo\n- **Prefijo de notas:** `ed-`\n", ficha)
        with open(os.path.join(estudio, "01_knowledge", "hallazgo.md"), "w", encoding="utf-8") as f:
            f.write("Sin prefijo.\n")
        self.assertIn("Notas sin el prefijo ed-: 1 -> [[hallazgo]]", self.brain("estado", raiz=estudio))
        self.assertIn("- 2026/estudio-docentes · ed- · ", self.brain(nombre, raiz=tesis))
        self.assertIn("Multiproyecto: mi tesis · contexto general: marco/", self.brain(nombre, raiz=tesis))
        self.assertIn("Multiproyecto: mi tesis", self.brain("estado", raiz=estudio))
        with open(os.path.join(estudio, "tablero.md"), encoding="utf-8") as f:
            tablero = f.read()
        with open(os.path.join(estudio, "tablero.md"), "w", encoding="utf-8") as f:
            f.write(tablero.replace("- <el siguiente paso concreto, y quién lo da>", "- Entrevistar a 5 docentes"))
        self.assertIn("sigue (tablero): Entrevistar a 5 docentes", self.brain(nombre, raiz=tesis))
        with open(os.path.join(estudio, "CLAUDE.md"), "w", encoding="utf-8") as f:
            f.write(ficha.replace("**Estado:** activo", "**Estado:** cerrado 2026-12-01"))
        self.assertIn("Cerrados (1): 2026/estudio-docentes", self.brain(nombre, raiz=tesis))

    def test_tablero_se_crea_se_carga_y_avisa(self):
        nuevo = os.path.join(self.tmp.name, "nuevo")
        os.makedirs(nuevo)
        self.brain("crear", "--trata", "Prueba", raiz=nuevo)
        with open(os.path.join(nuevo, "CLAUDE.md"), encoding="utf-8") as f:
            self.assertIn("@tablero.md", f.read())
        salida = self.brain("estado", raiz=nuevo)
        self.assertIn("Tablero: 20 líneas · actualizado 20", salida)
        self.assertIn("Tablero por llenar", salida)
        self.assertNotIn("por ordenar): 1", salida)  # tablero.md se queda en la raíz
        with open(os.path.join(nuevo, "tablero.md"), "w", encoding="utf-8") as f:
            f.write("---\nactualizado: 2026-11-21\n---\n\n## Próximos pasos\n- [ ] Llamar a José\n"
                    + "- más\n" * 40)
        salida = self.brain("estado", raiz=nuevo)
        self.assertNotIn("Tablero por llenar", salida)
        self.assertIn("Tablero largo: 46 líneas (máximo 40)", salida)

    def test_jardin_certeza_y_archivar(self):
        notas = {
            "01_knowledge/precio-por-fase.md": "---\ntipo: conocimiento\nfecha: 2026-11-02\ncerteza: supuesto\n"
                                              "como_se_sabe: \"lo dijo José, sin dato\"\n"
                                              "origen: \"reunion-kickoff (inbox, 2026-11-02)\"\n---\n\nIdea.\n",
            "01_knowledge/modelo-precio-por-fase.md": "---\ntipo: conocimiento\nfecha: 2026-11-03\n"
                                                     "certeza: confirmado\n---\n\nLa misma idea.\n",
            "01_knowledge/otra.md": "---\ntipo: conocimiento\nrelacionadas: [\"[[precio-por-fase]]\"]\n---\n\n"
                                    "Ver [[precio-por-fase]] y [[01_knowledge/precio-por-fase|esta]].\n",
            ".brainme/inbox-procesado/2026-11-02/reunion-kickoff.md": "Acta.\n",
            # Mismo hecho, contado distinto en notas de nombres distintos
            "01_knowledge/piloto-dura-8-semanas.md": "---\ntipo: conocimiento\ntags: [piloto]\n---\n\nVer [[otra]].\n",
            "01_knowledge/duracion-del-piloto.md": "---\ntipo: conocimiento\ntags: [piloto]\n---\n\n12 semanas. [[otra]]\n",
        }
        for rel, texto in notas.items():
            os.makedirs(os.path.dirname(os.path.join(self.raiz, rel)), exist_ok=True)
            with open(os.path.join(self.raiz, rel), "w", encoding="utf-8") as f:
                f.write(texto)
        self.assertIn("Supuestos sin confirmar: 1 -> [[precio-por-fase]]", self.brain("estado"))
        self.assertIn("[[precio-por-fase]] (supuesto)", self.brain("mapa", "--nota", "otra"))
        jardin = self.brain("jardin")
        self.assertIn("Jardín: nunca cerrado. Por revisar: 8 notas.", jardin)
        self.assertIn("  [[precio-por-fase]] (2026-11-02) · supuesto: lo dijo José, sin dato · original: ", jardin)
        self.assertIn("original: .brainme/inbox-procesado/2026-11-02/reunion-kickoff.md", jardin)
        self.assertIn("[[modelo-precio-por-fase]] ~ [[precio-por-fase]]", jardin)
        self.assertNotIn("~ [[piloto-dura-8-semanas]]", jardin)  # por nombre no se parecen
        linea = [l for l in jardin.split("\n") if l.startswith("  [[piloto-dura-8-semanas]]")][0]
        self.assertIn("mismo tema: [[duracion-del-piloto]]", linea)

        # Sin --repuntar: los enlaces por nombre siguen llegando; el que tenía ruta pasa a nombre
        self.brain("archivar", "precio-por-fase")
        archivada = self.leer("01_knowledge/archive/precio-por-fase.md")
        self.assertIn("archivada: 20", archivada)
        self.assertIn("Ver [[precio-por-fase]] y [[precio-por-fase|esta]].", self.leer("01_knowledge/otra.md"))
        self.assertIn("Enlaces a la nota archivada [[precio-por-fase]]: en [[otra]]", self.brain("jardin"))
        self.assertNotIn("precio-por-fase", self.brain("verificar").split("Archivos con")[0])  # ninguno roto
        self.brain("archivar", "--deshacer")
        self.assertEqual(self.leer("01_knowledge/otra.md"), notas["01_knowledge/otra.md"])
        self.assertEqual(self.leer("01_knowledge/precio-por-fase.md"), notas["01_knowledge/precio-por-fase.md"])
        self.assertFalse(os.path.exists(os.path.join(self.raiz, "01_knowledge/archive")))

        # Fusionada: los enlaces pasan a la nota que queda, que sigue nombrando a la archivada
        with open(os.path.join(self.raiz, "01_knowledge/modelo-precio-por-fase.md"), "a", encoding="utf-8") as f:
            f.write("\n## Actualizaciones\n- 2026-11-22: recibe [[precio-por-fase]].\n")
        self.brain("archivar", "precio-por-fase", "--por", "modelo-precio-por-fase", "--repuntar")
        otra = self.leer("01_knowledge/otra.md")
        self.assertIn("relacionadas: [\"[[modelo-precio-por-fase]]\"]", otra)
        self.assertIn("Ver [[modelo-precio-por-fase]] y [[modelo-precio-por-fase|esta]].", otra)
        self.assertIn('reemplazada_por: "[[modelo-precio-por-fase]]"',
                      self.leer("01_knowledge/archive/precio-por-fase.md"))
        self.assertIn("(archivada, reemplazada por [[modelo-precio-por-fase]])",
                      self.brain("mapa", "--nota", "precio-por-fase"))
        self.assertIn("recibe [[precio-por-fase]].", self.leer("01_knowledge/modelo-precio-por-fase.md"))
        self.assertNotIn("Enlaces a la nota archivada", self.brain("jardin"))
        self.assertNotIn("Supuestos sin confirmar", self.brain("estado"))

    def test_jardin_por_tandas(self):
        def escribir(nombre, cuerpo):
            with open(os.path.join(self.raiz, "01_knowledge/%s.md" % nombre), "w", encoding="utf-8") as f:
                f.write("---\ntipo: conocimiento\nfecha: 2026-11-21\ncerteza: supuesto\n---\n\n%s\n" % cuerpo)

        def en_tanda(jardin):
            return re.findall(r"^  \[\[([^\]]+)\]\] \(", jardin, re.M)

        self.assertNotIn("toca revisar el jardín", self.brain("estado"))
        for i in range(25):
            escribir("nota-%02d" % i, "Texto [[idea-central]].")
        self.assertIn("Jardín: nunca cerrado, con 28 notas por revisar (toca revisar el jardín)", self.brain("estado"))
        # Los supuestos primero; lo que no cabe en la tanda se anuncia y sigue pendiente
        jardin = self.brain("jardin")
        primera = en_tanda(jardin)
        self.assertEqual(len(primera), 20)
        self.assertTrue(all(n.startswith("nota-") for n in primera))
        self.assertIn("Quedan 8 para las tandas que siguen.", jardin)
        self.assertIn("quedan 28 notas por revisar", self.brain("jardin", "--hecho", codigo=2))
        self.assertIn("no-existe", self.brain("jardin", "--hecho", "nota-00", "no-existe", codigo=2))
        self.assertIn("Revisadas: 20. Por revisar: 8.", self.brain("jardin", "--hecho", *primera))
        jardin = self.brain("jardin")
        segunda = en_tanda(jardin)
        self.assertEqual(len(segunda), 8)
        self.assertFalse(set(primera) & set(segunda))
        self.assertIn("Supuestos ya revisados que siguen sin confirmar (20): [[", jardin)
        self.brain("jardin", "--hecho", *["[[%s]]" % n for n in segunda])
        self.assertIn("Jardín cerrado el 20", self.brain("jardin", "--hecho"))
        self.assertIn("Por revisar: 0 notas", self.brain("jardin"))
        self.assertNotIn("toca revisar el jardín", self.brain("estado"))

        # El mismo día vuelve a la lista lo nuevo o cambiado, también un enlace; mover el enlace, no
        escribir("nota-00", "Otro texto [[idea-central]].")
        escribir("nota-01", "Texto [[decision-precio]].")
        escribir("nota-02", "Texto [[01_knowledge/idea-central]].")
        escribir("nota-03", "Texto [idea-central](idea-central.md).")
        escribir("nueva", "Recién escrita [[idea-central]].")
        self.assertEqual(sorted(en_tanda(self.brain("jardin"))), ["nota-00", "nota-01", "nueva"])
        # La última tanda se anota de una vez, y lo que cambió después de verla no cuenta como revisado antes
        self.assertIn("Revisadas: 3. Por revisar: 0.", self.brain("jardin", "--hecho", "--tanda"))
        self.assertIn("No hay una tanda por anotar", self.brain("jardin", "--hecho", "--tanda", codigo=2))
        # Saltarse lo que falta se llama por su nombre y se dice
        escribir("otra-nueva", "Recién escrita [[idea-central]].")
        self.assertIn("quedan 1 nota por revisar", self.brain("jardin", "--hecho", codigo=2))
        salida = self.brain("jardin", "--hecho", "--sin-revisar")
        self.assertIn("Quedan sin revisar, por decisión del usuario: 1 nota.", salida)
        self.assertIn("Jardín cerrado el 20", salida)
        self.assertIn("Por revisar: 0 notas", self.brain("jardin"))

    def test_buscar(self):
        archivos = {
            "01_knowledge/duracion-del-piloto.md": "---\ntipo: conocimiento\ncerteza: supuesto\nresumen: \"El piloto dura 12 semanas.\"\n"
                                                   "---\n\n# Piloto\n\nSe cerró la decisión de precio en la reunión.\n",
            "01_knowledge/otra-cosa.md": "---\ntipo: conocimiento\n---\n\nLa reunión fue larga.\n",
            "01_knowledge/archive/piloto-viejo.md": "---\ntipo: conocimiento\narchivada: 2026-11-01\n"
                                                    "reemplazada_por: \"[[duracion-del-piloto]]\"\n---\n\nLa decisión: precios fijos.\n",
            ".brainme/inbox-procesado/2026-11-02/acta.md": "Acta.\nDecisión de los precios: por fase.\n",
            ".obsidian/workspace.json": "{\"decision\": \"precio\"}\n",
            "05_exports/reports/informe/versiones/informe-v0.md": "La decisión de precio vieja.\n",
        }
        for rel, texto in archivos.items():
            os.makedirs(os.path.dirname(os.path.join(self.raiz, rel)), exist_ok=True)
            with open(os.path.join(self.raiz, rel), "w", encoding="utf-8") as f:
                f.write(texto)
        # Sin tildes ni plurales; nombre y resumen pesan más; supuestos y archivadas, a la vista
        salida = self.brain("buscar", "decisiones de Precio")
        vigentes, archivadas = salida.split("Archivadas (1):")
        self.assertIn("Notas con: decisiones, precio (", vigentes)
        self.assertIn("  [[duracion-del-piloto]] (supuesto) · El piloto dura 12 semanas. (01_knowledge)\n"
                      "      … Se cerró la decisión de precio en la reunión.", vigentes)
        self.assertLess(vigentes.index("[[decision-precio]]"), vigentes.index("[[duracion-del-piloto]]"))
        self.assertNotIn("otra-cosa", salida)
        self.assertNotIn("workspace", salida)
        self.assertNotIn("informe-v0", salida)
        self.assertIn("[[piloto-viejo]] (archivada, reemplazada por [[duracion-del-piloto]])", archivadas)
        self.assertIn("Originales del inbox (1; con todas las palabras, 1):\n  .brainme/inbox-procesado/2026-11-02/acta.md\n"
                      "      … Decisión de los precios: por fase.", archivadas)
        # Sin todas las palabras, las que tienen algunas; sin ninguna, lo dice
        self.assertIn("Con algunas de esas palabras (", self.brain("buscar", "reunión", "inexistente"))
        self.assertIn("Ninguna nota habla de: helicoptero.", self.brain("buscar", "helicóptero"))
        self.assertIn("[[decision-precio]]", self.brain("buscar", "decisivamente", "precios"))

    def test_las_guias_nombran_lo_que_existe(self):
        repo = os.path.dirname(os.path.dirname(SCRIPT))
        ayuda = self.brain("--help")
        comandos = set(re.search(r"\{([a-z0-9,\-]+)\}", ayuda).group(1).split(","))
        guias = [os.path.join(repo, "SKILL.md"), os.path.join(repo, "README.md"), SCRIPT]
        for carpeta in ("references", "agents", "commands", "templates"):
            guias += [os.path.join(repo, carpeta, n) for n in sorted(os.listdir(os.path.join(repo, carpeta)))]
        for guia in guias:
            with open(guia, encoding="utf-8") as f:
                texto = f.read()
            for rel in re.findall(r"\b((?:references|templates|agents|commands)/[A-Za-z\-]+\.md)\b", texto):
                self.assertTrue(os.path.exists(os.path.join(repo, rel)), "%s nombra %s" % (guia, rel))
            for comando in re.findall(r"`brainme(?: --raiz \S+)?\s+([a-z][a-z\-]+)\b", texto):
                self.assertIn(comando, comandos, "%s usa brainme %s" % (guia, comando))
            self.assertIsNone(re.search(r"flujo \d", texto), "%s cita un flujo por número" % guia)
        with open(os.path.join(repo, "SKILL.md"), encoding="utf-8") as f:
            skill = f.read()
        for n in os.listdir(os.path.join(repo, "references")):
            self.assertIn("references/" + n, skill)  # toda guía se alcanza desde el SKILL

    def escribir(self, rel, texto, raiz=None):
        ruta = os.path.join(raiz or self.raiz, rel)
        os.makedirs(os.path.dirname(ruta), exist_ok=True)
        with open(ruta, "w", encoding="utf-8") as f:
            f.write(texto)

    def test_procesado_nunca_escribe_encima(self):
        hoy = datetime.date.today().isoformat()
        archivo = ".brainme/inbox-procesado/%s/" % hoy
        self.escribir("00_inbox/reunion.md", "primera\n")
        self.assertIn('origen: "reunion.md (inbox, %s)"' % hoy, self.brain("procesado", "reunion.md"))
        self.escribir("00_inbox/Reunion.md", "segunda\n")
        salida = self.brain("procesado", "00_inbox/Reunion.md")
        self.assertIn('origen: "Reunion-2.md (inbox, %s)" (ya había otro' % hoy, salida)
        self.assertEqual(self.leer(archivo + "reunion.md"), "primera\n")
        self.assertEqual(self.leer(archivo + "Reunion-2.md"), "segunda\n")
        # Junto a su nota: los nombres son únicos en todo el proyecto
        self.escribir("02_decisions/contrato.pdf", "viejo")
        self.escribir("00_inbox/contrato.pdf", "nuevo")
        self.assertIn("contrato.pdf -> 01_knowledge/contrato-2.pdf", self.brain("procesado", "contrato.pdf", "--a", "01_knowledge"))
        self.assertEqual(self.leer("02_decisions/contrato.pdf"), "viejo")
        # Una subcarpeta del inbox desaparece cuando queda vacía, y solo entonces
        self.escribir("00_inbox/lote/x.md", "x\n")
        self.escribir("00_inbox/lote/y.md", "y\n")
        self.brain("procesado", "lote/x.md")
        self.assertEqual(self.leer("00_inbox/lote/y.md"), "y\n")
        self.brain("procesado", "lote/y.md")
        self.assertFalse(os.path.exists(os.path.join(self.raiz, "00_inbox/lote")))
        self.assertTrue(os.path.isdir(os.path.join(self.raiz, "00_inbox")))
        # Fuera del inbox o a una carpeta ajena, no mueve nada
        self.escribir("00_inbox/a.md", "a\n")
        self.brain("procesado", "a.md", "01_knowledge/idea-central.md", codigo=2)
        self.brain("procesado", "a.md", "--a", "../fuera", codigo=2)
        self.assertEqual(self.leer("00_inbox/a.md"), "a\n")

    def test_inbox_reserva_los_nombres(self):
        hoy = datetime.date.today().isoformat()
        self.assertIn("El inbox está vacío.", self.brain("inbox"))
        self.escribir(".brainme/inbox-procesado/%s/reunion.md" % hoy, "mañana\n")
        self.escribir("04_sources/contrato.pdf", "viejo")
        for rel, texto in (("a/reunion.md", "primera\n"), ("b/reunion.md", "segunda\n"), ("contrato.pdf", "nuevo"),
                           ("largo.txt", "palabra " * 3100)):
            self.escribir("00_inbox/" + rel, texto)
        salida = self.brain("inbox")
        for linea in ('00_inbox/a/reunion.md · 1 palabra · origen: "reunion-2.md (inbox, %s)"',
                      '00_inbox/b/reunion.md · 1 palabra · origen: "reunion-3.md (inbox, %s)"',
                      '00_inbox/contrato.pdf · pdf · origen: "contrato-2.pdf (inbox, %s)"',
                      '00_inbox/largo.txt · 3100 palabras, largo: al lector · origen: "largo.txt (inbox, %s)"'):
            self.assertIn(linea % hoy, salida)
        # En cualquier orden, cada uno sale con el nombre que se le reservó
        self.brain("procesado", "b/reunion.md")
        self.brain("procesado", "contrato.pdf", "--a", "01_knowledge")
        self.assertIn('reunion-2.md (inbox', self.brain("inbox"))
        self.brain("procesado", "a/reunion.md")
        base = ".brainme/inbox-procesado/%s/" % hoy
        self.assertEqual([self.leer(base + n) for n in ("reunion.md", "reunion-2.md", "reunion-3.md")],
                         ["mañana\n", "primera\n", "segunda\n"])
        self.assertEqual(self.leer("01_knowledge/contrato-2.pdf"), "nuevo")

    def test_guia_trae_lo_que_usa_su_flujo(self):
        salida = self.brain("guia", "inbox", "convenciones")
        for parte in ("# Procesar el inbox", "certeza: <confirmado | supuesto>", "# Cómo escribe brainme",
                      "**Ampliar y corregir:**", "Si el comando brainme no existe: python3 "):
            self.assertIn(parte, salida)
        self.assertEqual(self.brain("guia", "inbox", "guardar").count("# Cómo escribe brainme"), 1)
        self.assertIn("Hay: convenciones, ", self.brain("guia", "nada", codigo=2))
        repo = os.path.dirname(os.path.dirname(SCRIPT))
        with open(SCRIPT, encoding="utf-8") as f:
            guias = f.read().split("GUIAS = {")[1].split("\n\n\n")[0]
        for n in os.listdir(os.path.join(repo, "references")):
            self.assertIn("references/" + n, guias)

    def test_comprueba_revisa_lo_escrito_hoy(self):
        hoy = datetime.date.today().isoformat()
        buena = ('---\ntitulo: "x"\ntipo: conocimiento\nfecha: %s\nresumen: "r"\nautor: "Ana"\norigen: "conversación"\n'
                 'certeza: supuesto\ncomo_se_sabe: "Ana"\n---\n\nTexto [[idea-central]] y <https://a.pe>.\n' % hoy)
        self.escribir("01_knowledge/buena.md", buena)
        self.assertNotIn("[[buena]]", self.brain("comprueba"))
        casos = {"01_knowledge/sin-campos.md": ("---\ntipo: conocimiento\nfecha: %s\n---\n\n[[buena]]\n" % hoy,
                                                "falta resumen, autor, origen, certeza, como_se_sabe"),
                 "01_knowledge/plantilla.md": (buena + "\n<AAAA-MM-DD>: <qué cambió y por qué>\n", "sin llenar"),
                 "01_knowledge/propia.md": (buena + "\nVer [[propia]].\n", "se enlaza a sí misma"),
                 "01_knowledge/raya.md": (buena + "\nUna idea — otra.\n\n> cita — exacta\n", "usa raya"),
                 "01_knowledge/certeza.md": (buena.replace("certeza: supuesto", "certeza: alta"), "certeza «alta»"),
                 "02_decisions/decision-x.md": ("---\ntipo: decision\nfecha: %s\nresumen: \"r\"\nautor: \"Ana\"\norigen: \"c\"\n"
                                                "estado: tomada\n---\n\n[[buena]]\n" % hoy, "falta decidido_por"),
                 "05_exports/reports/suelto-v1.md": ("---\ntipo: informe\nfecha: %s\nresumen: \"r\"\nautor: \"Ana\"\n---\n\n"
                                                     "Según [[buena]].\n" % hoy, "cita supuestos y no lo dice: [[buena]]")}
        for rel, (texto, _) in casos.items():
            self.escribir(rel, texto)
        salida = self.brain("comprueba")
        for rel, (_, falta) in casos.items():
            linea = [l for l in salida.split("\n") if l.startswith("  [[%s]]:" % rel.rsplit("/", 1)[-1][:-3])]
            self.assertTrue(linea and falta in linea[0], (rel, linea))
        suelto = [l for l in salida.split("\n") if "[[suelto-v1]]:" in l][0]
        self.assertIn("tipo «informe»: aquí va entregable", suelto)
        self.assertIn("va en su propia carpeta", suelto)
        # Una nota que no es de hoy no se revisa, aunque el archivo se haya tocado
        self.escribir("01_knowledge/sin-campos.md", "---\ntipo: conocimiento\nfecha: 2026-01-01\n---\n\n[[buena]]\n")
        self.assertNotIn("[[sin-campos]]:", self.brain("comprueba"))

    def test_bitacora_recuerda_el_tablero(self):
        self.brain("autor", "Ana P.")
        self.escribir("tablero.md", "---\nactualizado: 2026-01-01\n---\n\n## Próximos pasos\n- Ana: fijar la fecha\n")
        self.assertIn("Tablero sin cambios hoy. Próximos pasos: Ana: fijar la fecha.", self.brain("bitacora", "Algo"))
        # Si el tablero cambió pero no su fecha, la pone el script; si no cambió, no
        self.escribir("tablero.md", "---\nactualizado: 2026-01-01\n---\n\n## Próximos pasos\n- Ana: llamar\n")
        self.assertIn("Tablero: anoté que se actualizó hoy.", self.brain("bitacora", "Otra"))
        self.assertIn("actualizado: " + datetime.date.today().isoformat(), self.leer("tablero.md"))
        self.assertNotIn("Tablero", self.brain("bitacora", "Otra más"))

    def test_comprueba_cuida_la_historia(self):
        nota = ('---\ntitulo: "x"\ntipo: conocimiento\nfecha: 2026-01-01\nresumen: "r"\nautor: "Ana"\norigen: "%s"\n'
                'certeza: confirmado\ncomo_se_sabe: "Ana"\n---\n\nTexto [[idea-central]].\n\n## Actualizaciones\n%s')
        una, dos = "- 2026-02-01: cambió una cosa\n", "- 2026-03-01: cambió otra\n"
        self.escribir("01_knowledge/hist.md", nota % ("acta.md (inbox, 2026-01-01)", una))
        self.brain("estado")  # antes de escribir
        self.escribir("01_knowledge/hist.md", nota % ("acta.md (inbox, 2026-01-01)", una + dos))
        self.assertNotIn("[[hist]]", self.brain("comprueba"))  # ampliar está bien
        self.escribir("01_knowledge/hist.md", nota % ("otra.md (inbox, 2026-03-01)", "- 2026-02-01: cambió una cosa (vigente)\n"))
        for _ in range(2):  # lo sigue diciendo hasta que se devuelve
            salida = self.brain("comprueba")
            self.assertIn("cambió su origen; devuélvelo (era «acta.md (inbox, 2026-01-01)»)", salida)
            self.assertIn("devuélvela («2026-02-01: cambió una cosa»)", salida)
            self.assertIn("devuélvela («2026-03-01: cambió otra»)", salida)
        self.escribir("01_knowledge/hist.md", nota % ("acta.md (inbox, 2026-01-01)", una + dos))
        self.assertNotIn("[[hist]]", self.brain("comprueba"))
        # Un cambio que el usuario quiso hacer se acepta; una nota vieja sin campos no se revisa, una nueva sí
        self.escribir("01_knowledge/hist.md", nota % ("otra", una))
        self.assertNotIn("[[hist]]", self.brain("comprueba", "--dejar", "hist"))
        self.assertNotIn("[[idea-larga]]:", self.brain("comprueba"))
        self.escribir("01_knowledge/nueva.md", "---\ntipo: conocimiento\n---\n\n[[idea-central]]\n")
        self.assertIn("[[nueva]]: falta resumen, autor, origen", self.brain("comprueba"))

    def test_inventario_sugiere_los_entregables(self):
        for n in ("propuesta-v1.docx", "viejas/Propuesta-v10.docx", "Deck Cliente-v2.pptx", "informe-v3.md", "contrato.pdf", "cafe-con-vista.md"):
            self.escribir(n, "x\n")
        lineas = {l.split(" | ")[0]: l for l in self.brain("inventario", "--tabla").split("\n") if " | " in l}
        self.assertTrue(lineas["propuesta-v1.docx"].endswith(
            "-> entregable con versiones, anterior: 05_exports/data/propuesta/versiones/"))
        self.assertTrue(lineas["viejas/Propuesta-v10.docx"].endswith("-> entregable con versiones: 05_exports/data/propuesta/"))
        self.assertIn("05_exports/presentations/deck-cliente/", lineas["Deck Cliente-v2.pptx"])
        self.assertIn("05_exports/reports/informe/", lineas["informe-v3.md"])
        self.assertNotIn("->", lineas["contrato.pdf"] + lineas["cafe-con-vista.md"])

    def test_mover_avisa_versiones_por_ordenar(self):
        for n in (1, 2):
            self.escribir("propuesta-v%d.docx" % n, "x")
        self.escribir("plan.json", json.dumps({"movimientos": [
            {"de": "propuesta-v%d.docx" % n, "a": "05_exports/data/propuesta/"} for n in (1, 2)]}))
        self.assertIn("con versiones por ordenar: 1 ->", self.brain("mover", "--plan", os.path.join(self.raiz, "plan.json")))

    def test_bitacora_avisa_lo_que_falta(self):
        self.brain("autor", "Ana P.")
        self.brain("estado")
        self.assertNotIn("Antes de terminar", self.brain("bitacora", "Nada nuevo"))
        # Un resumen agregado a una nota vieja no la vuelve «escrita hoy»; un enlace roto sí
        self.escribir("r.json", json.dumps({"01_knowledge/idea-larga.md": "Larga."}))
        self.brain("poner-resumenes", "--desde", "r.json")
        self.assertNotIn("Antes de terminar", self.brain("bitacora", "Resúmenes"))
        self.escribir("tablero.md", "---\nactualizado: 2026-01-01\n---\n\n## Objetivo actual\nVer [[idea central]] y `[[ejemplo]]`.\n")
        salida = self.brain("bitacora", "Tablero")
        self.assertIn("Antes de terminar, corrige:\nEnlace roto en el tablero: [[idea central]] (¿[[idea-central]]?)", salida)
        self.assertNotIn("ejemplo", salida)
        # El tablero que perdió su encabezado lo recupera, también con un handoff
        self.escribir("tablero.md", "# Tablero\n\n## Objetivo actual\nOtro.\n")
        self.escribir("h.md", "**Objetivo:** x\n")
        self.assertIn("Tablero: le devolví su encabezado.", self.brain("bitacora", "--handoff", "h.md"))
        self.assertTrue(self.leer("tablero.md").startswith(
            "---\ntipo: tablero\nactualizado: %s\n---\n\n# Tablero\n" % datetime.date.today().isoformat()))
        self.escribir("01_knowledge/nueva.md", "---\ntipo: conocimiento\n---\n\n[[idea-centrall]]\n")
        for _ in range(2):  # lo dice hasta que se corrige
            salida = self.brain("comprueba")
            self.assertIn("con enlace roto: [[idea-centrall]] en [[nueva]] (¿[[idea-central]]?)", salida)
            self.assertIn("[[nueva]]: falta resumen", salida)

    def test_resumenes_sin_rotulos_y_con_tildes(self):
        casos = {"Decision: se usa la sala azul. Pregunta para encontrarla: cuanto mide la sala?":
                 "Se usa la sala azul. ¿Cuánto mide la sala?",
                 "La decision aumento el aforo. ¿que sala se usa?": "La decisión aumento el aforo. ¿Qué sala se usa?",
                 "Esta sala esta lista, como se dijo.": "Esta sala esta lista, como se dijo.",
                 "La pregunta: cuanto cuesta, sigue abierta.": "La pregunta: cuanto cuesta, sigue abierta."}
        for i, (malo, bueno) in enumerate(casos.items()):
            self.escribir("02_decisions/sala-%d.md" % i, "---\ntitulo: \"x\"\n---\n\nTexto.\n")
            self.escribir("r.json", json.dumps({"02_decisions/sala-%d.md" % i: malo}))
            self.brain("poner-resumenes", "--desde", "r.json")
            self.assertIn(bueno, self.leer("02_decisions/sala-%d.md" % i))

    def test_leer_varias_con_sus_originales(self):
        self.escribir(".brainme/inbox-procesado/2026-01-01/acta.md", "Lo que dice el acta.\n")
        for n in ("a", "b"):
            self.escribir("01_knowledge/%s.md" % n, "---\ntipo: conocimiento\norigen: \"acta.md (inbox, 2026-01-01)\"\n---\n\nNota %s.\n" % n)
        salida = self.brain("leer", "[[a]]", "b", "tablero.md", "no-existe")
        self.assertIn("=== 01_knowledge/a.md", salida)
        self.assertIn("Nota b.", salida)
        self.assertIn("No encuentro no-existe.", salida)
        self.assertNotIn("Lo que dice el acta.", salida)
        self.assertEqual(self.brain("leer", "a", "b", "--originales").count("Lo que dice el acta."), 1)
        self.brain("jardin")
        tanda = self.brain("leer", "--tanda")
        self.assertIn("Nota a.", tanda)
        self.assertIn("=== original: .brainme/inbox-procesado/2026-01-01/acta.md", tanda)
        # Lo que no cabe se dice, con el comando para seguir
        for n in ("a", "b"):
            self.escribir("01_knowledge/%s.md" % n, "---\ntipo: conocimiento\n---\n\n" + "palabra " * 4000)
        self.assertIn("Faltan 1: brainme leer idea-central", self.brain("leer", "a", "idea-central"))
        self.brain("leer", codigo=2)
        self.brain("leer", "../fuera.md", codigo=2)

    def test_llevar_no_deja_pasar_datos_del_proyecto(self):
        raiz = os.path.join(self.tmp.name, "varios")
        self.escribir("CLAUDE.md", "# M\n\n## brainme · multiproyecto\n\n**Multiproyecto:** m · **Contexto general:** `general/`\n\n"
                                   "### Ficha de cada proyecto\n\n- **Estado:** activo\n- **Prefijo de notas:**\n", raiz)
        self.brain("crear", "general", "--trata", "x", raiz=raiz)
        self.brain("crear", "proyectos/2026/uno", "--prefijo", "uno-", raiz=raiz)
        self.brain("autor", "Ana P.")
        uno = os.path.join(raiz, "proyectos/2026/uno")
        self.escribir("01_knowledge/uno-idea.md", "---\ntipo: conocimiento\n---\n\nEn Librería Faro lo vio Ana Torres. Vale.\n\n"
                      "## Actualizaciones\n- 2026-01-01: antes\n\n## Otra\nTexto.\n", uno)

        def llevar(texto, *args, codigo=0):
            self.escribir(".brainme/llevar.md", texto, uno)
            return self.brain("llevar", ".brainme/llevar.md", "--de", "uno-idea", "--tema", "Entrevistas en compra", *args,
                              raiz=uno, codigo=codigo)

        for texto, aviso in (("Lo vio Torres en la tienda.", "nombres: Torres"), ("faro no: Faro sí.", "nombres: Faro"),
                             ("Funcionó con la marca Zeta.", "nombres: Zeta"), ("Fueron 12 entrevistas.", "cifras: 12"),
                             ("Costó 3,400 soles.", "cifras: 3,400"), ("Se vio en septiembre.", "fechas: septiembre"),
                             ("Ver [[uno-idea]].", "enlaces a notas del proyecto: [[uno-idea]]"),
                             ("Escribir a ana@faro.pe.", "correos o webs: ana@faro.pe")):
            self.assertIn(aviso, llevar(texto, "--ok", codigo=2))
        self.assertEqual(os.listdir(os.path.join(raiz, "general/00_inbox")), [])
        bueno = "Entrevistar durante la compra da respuestas más concretas.\n\n1. Primero, observar.\n- Después, preguntar.\n"
        self.assertIn("con su OK, repite con --ok", llevar(bueno))
        self.assertEqual(os.listdir(os.path.join(raiz, "general/00_inbox")), [])
        hoy = datetime.date.today().isoformat()
        nombre = "desde-un-proyecto-%s-entrevistas-en-compra" % hoy
        self.assertIn("general/00_inbox/%s.md, y anotado en [[uno-idea]]" % nombre, llevar(bueno, "--ok"))
        self.assertIn("%s-2.md" % nombre, llevar("Con la marca Zeta también.", "--permitir", "Zeta", "--ok"))
        with open(os.path.join(raiz, "general/00_inbox", nombre + ".md"), encoding="utf-8") as f:
            self.assertEqual(f.read(), '---\nautor: "Ana P."\nfecha: %s\norigen: "un proyecto, con OK del usuario"\n---\n\n%s' % (hoy, bueno))
        with open(os.path.join(uno, "01_knowledge/uno-idea.md"), encoding="utf-8") as f:
            self.assertIn("- 2026-01-01: antes\n- %s: Llevada al contexto general (%s) · Ana P.\n" % (hoy, hoy), f.read())
        llevar("", "--ok", codigo=2)
        self.brain("llevar", "x.md", "--de", "a", "--tema", "b", codigo=2)  # fuera de un multiproyecto

    def test_el_comando_brainme(self):
        comando = os.path.join(os.path.dirname(os.path.dirname(SCRIPT)), "bin", "brainme")
        enlace = os.path.join(self.tmp.name, "enlace")
        os.symlink(comando, enlace)
        for ruta in (comando, enlace):
            r = subprocess.run([ruta, "buscar", "precio fase"], cwd=self.raiz, capture_output=True, text=True, env=self.env)
            self.assertEqual((r.returncode, r.stderr), (0, ""))
            self.assertIn("[[decision-precio]]", r.stdout)

    def test_buscar_varias_a_la_vez(self):
        salida = self.brain("buscar", "precio fase, helicóptero")
        self.assertIn("=== precio fase", salida)
        self.assertIn("=== helicóptero\nNinguna nota habla de: helicoptero.", salida)
        self.assertNotIn("===", self.brain("buscar", "precio"))

    def test_jardin_recuerda_lo_que_se_deja(self):
        for n in ("plan-piloto-lima", "plan-piloto-lima-norte"):
            self.escribir("01_knowledge/%s.md" % n, "---\ntipo: conocimiento\n---\n\nTexto [[idea-central]].\n")
        self.escribir("01_knowledge/sola.md", "---\ntipo: conocimiento\n---\n\nSola.\n")
        jardin = self.brain("jardin")
        self.assertIn("[[plan-piloto-lima-norte]] ~ [[plan-piloto-lima]]", jardin)
        self.escribir("01_knowledge/rota.md", "---\ntipo: conocimiento\n---\n\n[[idea-futura#Sección|x]] [[idea-central]]\n")
        self.assertIn("idea-futura", self.brain("jardin"))
        self.brain("jardin", "--dejar", "idea-futura")
        self.assertNotIn("idea-futura", self.brain("jardin"))
        self.assertIn("[[sola]]", jardin.split("Islas")[1])
        self.brain("jardin", "--dejar", "plan-piloto-lima", "[[plan-piloto-lima-norte]]")
        self.brain("jardin", "--dejar", "sola")
        self.brain("jardin", "--dejar", "no-existe", codigo=2)
        jardin = self.brain("jardin")
        self.assertNotIn(" ~ ", jardin)
        self.assertNotIn("[[sola]]", jardin.split("Islas")[1])
        self.brain("jardin", "--hecho", "--sin-revisar")
        self.assertNotIn(" ~ ", self.brain("jardin"))
        # Cambiar la fiabilidad de una fuente la devuelve a la lista
        self.escribir("04_sources/web/f.md", "---\ntipo: fuente-web\nfiabilidad: baja\n---\n\nX\n")
        self.brain("jardin", "--hecho", "f")
        self.escribir("04_sources/web/f.md", "---\ntipo: fuente-web\nresumen: \"r\"\nfiabilidad: baja\n---\n\nX\n")
        self.assertIn("Por revisar: 0 notas", self.brain("jardin"))
        self.escribir("04_sources/web/f.md", "---\ntipo: fuente-web\nfiabilidad: alta\n---\n\nX\n")
        self.assertIn("Por revisar: 1 nota", self.brain("jardin"))

    def test_buscar_una_pregunta_completa_y_el_contexto_general(self):
        self.escribir(".brainme/inbox-procesado/2026-11-02/acta.md", "El piloto dura doce semanas.\n")
        self.assertIn("acta.md\n      … El piloto dura doce semanas.",
                      self.brain("buscar", "¿cuánto dura el piloto y quién lo aprobó?"))
        # Lo vigente es la última actualización, aunque la frase hallada sea la vieja
        self.escribir("01_knowledge/duracion.md", "---\ntipo: conocimiento\n---\n\nEl piloto dura 8 semanas.\n\n"
                      "## Actualizaciones\n- 2026-11-20: ahora son 12 · origen: acta.md (inbox, 2026-11-02)\n- 2026-11-03: otra cosa\n")
        salida = self.brain("buscar", "¿cuánto va a durar el piloto?")
        self.assertIn("Notas con: durar, piloto (1):\n  [[duracion]] (01_knowledge)\n      … El piloto dura 8 semanas.\n"
                      "      última actualización: 2026-11-20: ahora son 12", salida)
        self.assertIn("acta.md\n      … El piloto dura doce semanas.", salida)
        self.assertIn("acta.md", self.brain("buscar", "piloto", "inexistente"))  # con una, si nada coincide más
        # Lo que está en el inbox sin procesar también sale, y lo que no se pudo leer se dice
        self.escribir("00_inbox/nueva.md", "La apertura es en diciembre.\n")
        self.escribir("04_sources/literature/tesis.pdf", "x")
        self.assertIn("En el inbox, sin procesar (1):\n  00_inbox/nueva.md\n      … La apertura es en diciembre.",
                      self.brain("buscar", "apertura"))
        self.assertIn("Sin leer, porque no tienen ficha (1): tesis.pdf", self.brain("buscar", "helicóptero"))
        self.assertNotIn("tesis.pdf", self.brain("buscar", "piloto"))
        raiz = os.path.join(self.tmp.name, "varios")
        self.escribir("CLAUDE.md", "# M\n\n## brainme · multiproyecto\n\n**Multiproyecto:** m · **Contexto general:** "
                                   "`general/`\n\n### Ficha de cada proyecto\n\n- **Estado:** activo\n"
                                   "- **Prefijo de notas:**\n", raiz)
        self.brain("crear", "general", "--trata", "x", raiz=raiz)
        for n in ("uno", "dos"):
            self.brain("crear", "proyectos/2026/" + n, "--prefijo", n, raiz=raiz)
            self.escribir("proyectos/2026/%s/01_knowledge/%s-secreto.md" % (n, n), "Entrevistas de %s.\n" % n, raiz)
        self.escribir("general/01_knowledge/metodo.md", "El método de las entrevistas.\n", raiz)
        salida = self.brain("buscar", "entrevista", raiz=os.path.join(raiz, "proyectos/2026/uno"))
        self.assertIn("En el contexto general (general/) (1):\n  [[metodo]]", salida)
        self.assertIn("[[uno-secreto]]", salida)
        self.assertNotIn("dos-secreto", salida)  # otro proyecto solo se busca si el usuario lo pide

    def test_jardin_encuentra_el_original(self):
        archivos = {"01_knowledge/contrato.pdf": "x", "04_sources/literature/perez-2023.pdf": "x",
                    "01_knowledge/plazo.md": "---\ntipo: conocimiento\norigen: \"contrato.pdf (inbox, 2026-11-02)\"\n---\n\n"
                                             "Vence en 12 semanas: [[contrato.pdf]]\n",
                    "01_knowledge/monto.md": "---\ntipo: conocimiento\norigen: \"[[contrato.pdf]]\"\n---\n\nMonto.\n",
                    ".brainme/inbox-procesado/2026-11-01/acta1.md": "8", ".brainme/inbox-procesado/2026-11-20/acta2.md": "12",
                    "01_knowledge/ampliada.md": "---\ntipo: conocimiento\norigen: \"acta1.md (inbox, 2026-11-01)\"\n---\n\n8.\n\n"
                                                "## Actualizaciones\n- 2026-11-20: ahora 12. origen: acta2.md (inbox, 2026-11-20)\n",
                    "01_knowledge/charla.md": "---\ntipo: conocimiento\norigen: \"conversación 2026-11-20\"\n---\n\nX.\n",
                    "04_sources/literature/perez-2023-pymes.md": "---\ntipo: literatura\npdf: \"perez-2023.pdf\"\n---\n\nX.\n",
                    "04_sources/web/oecd-pymes.md": "---\ntipo: fuente-web\nsource_url: \"https://oecd.org/x\"\n---\n\nX.\n"}
        for rel, texto in archivos.items():
            os.makedirs(os.path.dirname(os.path.join(self.raiz, rel)), exist_ok=True)
            with open(os.path.join(self.raiz, rel), "w", encoding="utf-8") as f:
                f.write(texto)
        jardin = self.brain("jardin")
        for nota, original in (("plazo", "01_knowledge/contrato.pdf"), ("monto", "01_knowledge/contrato.pdf"),
                               ("perez-2023-pymes", "04_sources/literature/perez-2023.pdf"),
                               ("oecd-pymes", "https://oecd.org/x"),
                               ("ampliada", ".brainme/inbox-procesado/2026-11-01/acta1.md, "
                                            ".brainme/inbox-procesado/2026-11-20/acta2.md")):
            linea = [l for l in jardin.split("\n") if l.startswith("  [[%s]]" % nota)][0]
            self.assertIn("original: " + original, linea)
        self.assertIn("· conversación 2026-11-20, sin original", jardin)

    def test_detecta_multiproyecto_armado_a_mano(self):
        otro = os.path.join(self.tmp.name, "otro")
        os.makedirs(otro)
        for carpeta, texto in ((otro, "## brainme\n"), (self.tmp.name, "# Mi consultora\n")):
            with open(os.path.join(carpeta, "CLAUDE.md"), "w", encoding="utf-8") as f:
                f.write(texto)
        self.assertIn("Carpeta multiproyecto armada a mano: ..", self.brain("estado"))

    def test_cada_entregable_en_su_carpeta(self):
        self.brain("versiones", "--plan", ".brainme/plan.json")
        self.brain("mover", "--plan", os.path.join(self.raiz, ".brainme/plan.json"))
        deck = "05_exports/presentations/deck/"
        for rel in ("05_exports/reports/informe/informe-v2.md", "05_exports/reports/informe/versiones/informe-v1.md",
                    deck + "deck-v2.html", deck + "deck.md", deck + "versiones/deck-v1.html",
                    deck + "versiones/deck-v0.html"):
            self.assertTrue(os.path.exists(os.path.join(self.raiz, rel)), rel)
        self.assertFalse(os.path.exists(os.path.join(self.raiz, "05_exports/presentations/_versiones")))
        nombres = self.brain("nombres")
        self.assertIn("deck", nombres)
        self.assertNotIn("informe-v1", nombres)
        self.assertIn("ya están cada uno en su carpeta", self.brain("versiones"))

    def test_consumo_lee_registros_sin_repetir_mensajes(self):
        carpeta = os.path.join(self.tmp.name, "claude", "projects")
        nombre = "".join(c if c.isascii() and c.isalnum() else "-" for c in self.raiz)
        os.makedirs(os.path.join(carpeta, nombre))
        lineas = []
        for i, ctx in enumerate([100000, 300000]):
            for _ in range(2):  # el mismo mensaje aparece en dos líneas
                lineas.append(json.dumps({"type": "assistant", "timestamp": "2026-10-01T10:00:00Z",
                                          "message": {"id": "m%d" % i, "usage": {
                                              "input_tokens": 10, "cache_read_input_tokens": ctx - 10,
                                              "cache_creation_input_tokens": 0}}}))
        with open(os.path.join(carpeta, nombre, "s1.jsonl"), "w", encoding="utf-8") as f:
            f.write("\n".join(lineas) + "\n")
        salida = self.brain("consumo")
        self.assertIn("1 sesiones, 2 respuestas", salida)
        self.assertIn("promedio 200.000", salida)


if __name__ == "__main__":
    unittest.main()
