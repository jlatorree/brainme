"""Pruebas mínimas de scripts/brainme.py. No usan Claude: corren el script sobre un
proyecto de ejemplo armado en una carpeta temporal.

    python3 -m unittest discover tests
"""

import json
import os
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
        self.assertIn("Cambios automáticos (BRAIN migrar --aplicar): 6", salida)
        self.brain("migrar", "--aplicar")
        claude_md = self.leer("CLAUDE.md")
        self.assertTrue(claude_md.endswith("**Configurado con brainme:** 2026-01-01 · **Versión:** 3.2.0\n\n"
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
        # Sin Graphify: sincroniza solo da la línea del mapa y deja graphify-out/ como estaba
        self.assertTrue(self.brain("sincroniza").startswith("Mapa: 6 notas"))
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

    def test_espacio_de_una_tesis(self):
        tesis = os.path.join(self.tmp.name, "tesis")
        os.makedirs(tesis)
        with open(os.path.join(tesis, "CLAUDE.md"), "w", encoding="utf-8") as f:
            f.write("# Tesis\n\nMis reglas.\n\n## brainme · espacio\n\n**Espacio:** tesis · **Contexto general:** "
                    "`marco/` · **Versión:** 3.0.0\n\n### Ficha de cada proyecto\n\n- **Estado:** activo\n"
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
        self.assertIn("- 2026/estudio-docentes · ed- · ", self.brain("espacio", raiz=tesis))
        with open(os.path.join(estudio, "tablero.md"), encoding="utf-8") as f:
            tablero = f.read()
        with open(os.path.join(estudio, "tablero.md"), "w", encoding="utf-8") as f:
            f.write(tablero.replace("- <el siguiente paso concreto, y quién lo da>", "- Entrevistar a 5 docentes"))
        self.assertIn("sigue (tablero): Entrevistar a 5 docentes", self.brain("espacio", raiz=tesis))
        with open(os.path.join(estudio, "CLAUDE.md"), "w", encoding="utf-8") as f:
            f.write(ficha.replace("**Estado:** activo", "**Estado:** cerrado 2026-12-01"))
        self.assertIn("Cerrados (1): 2026/estudio-docentes", self.brain("espacio", raiz=tesis))

    def test_tablero_se_crea_se_carga_y_avisa(self):
        nuevo = os.path.join(self.tmp.name, "nuevo")
        os.makedirs(nuevo)
        self.brain("crear", "--trata", "Prueba", raiz=nuevo)
        with open(os.path.join(nuevo, "CLAUDE.md"), encoding="utf-8") as f:
            self.assertIn("@tablero.md", f.read())
        salida = self.brain("estado", raiz=nuevo)
        self.assertIn("Tablero: 21 líneas · actualizado 20", salida)
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
        self.assertIn("Jardín: nunca revisado.", jardin)
        self.assertIn("[[precio-por-fase]] · cómo se sabe: lo dijo José, sin dato", jardin)
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

        # Fusionada: los enlaces pasan a la nota que queda
        self.brain("archivar", "precio-por-fase", "--por", "modelo-precio-por-fase", "--repuntar")
        otra = self.leer("01_knowledge/otra.md")
        self.assertIn("relacionadas: [\"[[modelo-precio-por-fase]]\"]", otra)
        self.assertIn("Ver [[modelo-precio-por-fase]] y [[modelo-precio-por-fase|esta]].", otra)
        self.assertIn('reemplazada_por: "[[modelo-precio-por-fase]]"',
                      self.leer("01_knowledge/archive/precio-por-fase.md"))
        self.assertIn("(archivada, reemplazada por [[modelo-precio-por-fase]])",
                      self.brain("mapa", "--nota", "precio-por-fase"))
        self.assertNotIn("Supuestos sin confirmar", self.brain("estado"))

        # Cadencia: con 15 notas nuevas desde el último jardín, estado lo sugiere
        self.assertNotIn("toca revisar el jardín", self.brain("estado"))
        for i in range(15):
            with open(os.path.join(self.raiz, "01_knowledge/nota-%d.md" % i), "w", encoding="utf-8") as f:
                f.write("---\nfecha: 2026-11-0%d\n---\n\nTexto [[otra]].\n" % (i % 9 + 1))
        self.assertIn("Jardín: nunca revisado, con", self.brain("estado"))
        self.brain("jardin", "--hecho")
        self.assertNotIn("toca revisar el jardín", self.brain("estado"))
        self.assertIn("Jardín: último el 20", self.brain("jardin"))

    def test_detecta_espacio_armado_a_mano(self):
        otro = os.path.join(self.tmp.name, "otro")
        os.makedirs(otro)
        for carpeta, texto in ((otro, "## brainme\n"), (self.tmp.name, "# Mi consultora\n")):
            with open(os.path.join(carpeta, "CLAUDE.md"), "w", encoding="utf-8") as f:
                f.write(texto)
        self.assertIn("Espacio armado a mano: ..", self.brain("estado"))

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
