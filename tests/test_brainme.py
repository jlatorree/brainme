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

SCRIPT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts", "brainme.py")

# Un proyecto de una versión anterior: sin versión ni resúmenes, con el aviso de
# Graphify, una versión vieja de un entregable y una copia en conflicto de iCloud.
ARCHIVOS = {
    "CLAUDE.md": "# viejo\n\n## brainme\n\n**Proyecto:** viejo · **De qué trata:** prueba · "
                 "**Configurado con brainme:** 2026-01-01\n\n## graphify\n\n"
                 "For codebase questions, first run graphify query.\n",
    ".claude/settings.json": json.dumps({"hooks": {"PreToolUse": [{"matcher": "Bash|Grep", "hooks": [
        {"type": "command", "command": "\"$HOME/.local/bin/graphify\" hook-guard search"}]}]}}),
    ".graphifyignore": "graphify-out/\n00_inbox/\n",
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
        self.assertTrue(claude_md.endswith("**Configurado con brainme:** 2026-01-01 · **Versión:** 3.1.0\n"))
        self.assertNotIn("## graphify", claude_md)
        self.assertEqual(json.loads(self.leer(".claude/settings.json")), {})
        self.assertIn("05_exports/**/versiones/", self.leer(".graphifyignore"))
        self.assertFalse(os.path.exists(os.path.join(self.raiz, "05_exports/data")))
        self.assertTrue(os.path.exists(os.path.join(self.raiz, "bitacora.md")))
        self.assertIn("No hay cambios automáticos", self.brain("migrar", "--aplicar"))
        self.brain("migrar", "--deshacer")
        self.assertEqual(self.leer("CLAUDE.md"), ARCHIVOS["CLAUDE.md"])
        self.assertFalse(os.path.exists(os.path.join(self.raiz, "bitacora.md")))
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

    def test_mapa_sin_graphify(self):
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
        with open(os.path.join(estudio, "CLAUDE.md"), "w", encoding="utf-8") as f:
            f.write(ficha.replace("**Estado:** activo", "**Estado:** cerrado 2026-12-01"))
        self.assertIn("Cerrados (1): 2026/estudio-docentes", self.brain("espacio", raiz=tesis))

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
