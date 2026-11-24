"""El proyecto de prueba (evals/huerto) con sus 10 preguntas: lo que se puede medir sin Claude.
Para cada pregunta, buscar debe traer sus notas entre las 3 primeras; el jardín debe poner en la
lista la nota con el error sembrado y leer --original, mostrar el original que la corrige.

    python3 -m unittest discover tests
"""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(RAIZ, "scripts", "brainme.py")
EVALS = os.path.join(RAIZ, "evals")


class Huerto(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.raiz = os.path.join(self.tmp.name, "huerto")
        shutil.copytree(os.path.join(EVALS, "huerto"), self.raiz)
        with open(os.path.join(EVALS, "preguntas.json"), encoding="utf-8") as f:
            self.preguntas = json.load(f)

    def tearDown(self):
        self.tmp.cleanup()

    def brain(self, *args):
        r = subprocess.run([sys.executable, SCRIPT, "--raiz", self.raiz] + list(args), capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return r.stdout

    def test_buscar_trae_cada_nota_entre_las_3_primeras(self):
        for q in self.preguntas:
            notas = re.findall(r"^  \[\[([^\]]+)\]\]", self.brain("buscar", q["pregunta"]), re.M)
            for esperada in q["notas"]:
                self.assertIn(esperada, notas[:3], "pregunta %d: %s -> %s" % (q["id"], q["pregunta"], notas[:5]))

    def test_lo_vigente_sale_primero(self):
        notas = re.findall(r"^  \[\[([^\]]+)\]\]", self.brain("buscar", self.preguntas[1]["pregunta"]), re.M)
        self.assertEqual(notas[0], "decision-dia-de-trabajo-domingo")

    def test_el_jardin_encuentra_el_error_sembrado(self):
        q = next(q for q in self.preguntas if q.get("jardin"))
        nota = q["notas"][0]
        self.assertIn("[[%s]]" % nota, self.brain("jardin"))
        salida = self.brain("leer", "--original", nota)
        self.assertIn("abre a las 8", salida)  # lo que dice la nota
        self.assertIn("abre a las 9", salida)  # lo que dice su original

    def test_el_proyecto_esta_completo(self):
        self.assertIn("Supuestos, por si ya se confirmaron (1): [[riego-por-goteo]]", self.brain("comprueba", "--todo"))
        self.assertIn("Inbox sin procesar: 0", self.brain("estado"))
