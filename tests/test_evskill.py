"""Tests con un PDF sintético (tests/fabricar_demo.py). Ejecuta: python -m unittest discover -s tests"""
import csv
import json
import os
import sys
import tempfile
import unittest

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(AQUI, "..", "scripts"))
sys.path.insert(0, AQUI)
sys.path.insert(0, os.path.join(AQUI, ".."))

import fabricar_demo  # noqa: E402
import convertir  # noqa: E402
import procesar  # noqa: E402


class TestDemo(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.pdf = fabricar_demo.fabricar(os.path.join(cls.tmp.name, "demo.pdf"))
        convertir.main([cls.pdf, "--salida", cls.tmp.name])
        cls.json = os.path.join(cls.tmp.name, "demo.json")
        with open(cls.json, encoding="utf-8") as f:
            cls.d = json.load(f)
        with open(os.path.join(cls.tmp.name, "demo.md"), encoding="utf-8") as f:
            cls.md = f.read()

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_portada_y_secciones(self):
        a = self.d["atleta"]
        self.assertEqual(a["nombre"], "Atleta Demo")
        self.assertEqual(a["fecha_evaluacion"], "01/01/2027")
        self.assertEqual(a["edad"], 15)
        self.assertEqual(len(self.d["secciones"]), 9)
        self.assertEqual(self.d["sin_reconocer"], [])

    def test_cabeceras_y_pies_fuera(self):
        self.assertNotIn("Documento confidencial de uso", self.md)
        self.assertNotIn("Página 3 de", self.md)

    def test_autorreporte_y_encuadre(self):
        self.assertEqual(self.d["autorreporte"]["energía"], 2)
        self.assertEqual(self.d["encuadre"]["ESTADO DE MEDICIÓN"], "optimo")

    def test_dinamometria(self):
        din = {p["prueba"]: p for p in self.d["dinamometria"]}
        fr = din["Flexión de rodilla 90°"]
        self.assertEqual((fr["izq"], fr["der"], fr["unidad"]), (15, 20, "kg"))
        self.assertEqual(fr["diferencia_pct"], 25.0)
        self.assertEqual(fr["lado_menor"], "izq")
        self.assertEqual(fr["relativa_der"], 0.33)
        self.assertEqual(self.d["otras_medidas"][0]["valor"], 150)
        self.assertEqual(self.d["cociente_hq"]["izq"], 0.38)

    def test_saltos_drop_sprint(self):
        cmj = self.d["saltos"][0]
        self.assertEqual(cmj["valores"], [24, 27, 30])
        self.assertEqual(cmj["protocolo"], "manos libres")
        self.assertEqual([x["caja_cm"] for x in self.d["drop_jumps"]], [30, 45])
        mejor = [i for i in self.d["sprint"]["intentos"] if i["mejor"]][0]
        self.assertEqual(mejor["parciales_s"], {"10": 1.95, "20": 3.3})

    def test_vbt(self):
        ej = self.d["vbt"][0]
        self.assertEqual(ej["ejercicio"], "Trap Bar deadlift")
        self.assertEqual([s["kg"] for s in ej["series"]], [40, 60, 80])
        self.assertEqual(ej["series"][1]["v_mejor"], 0.85)
        rc = procesar.recta(ej["series"], "v_mejor")
        self.assertAlmostEqual(procesar.kg_para(rc, 0.6), 85.0, places=1)

    def test_plan(self):
        p = self.d["plan"]
        self.assertEqual([s["n"] for s in p["semanas"]], [1, 2])
        lun = p["semanas"][0]["dias"][0]
        self.assertEqual((lun["dia"], lun["fecha"], lun["duracion_min"]), ("LUN", "04/01", 50))
        pm, bulgara, nordic = lun["ejercicios"]
        self.assertEqual(pm["bloque"], "FUERZA PRINCIPAL (VBT)")
        self.assertEqual((pm["dosis"], pm["carga"]), ("3 × 5", "50 kg"))
        self.assertIn("Cortar si baja de 0.90 m/s", pm["indicaciones"])
        self.assertEqual(bulgara["serie_extra"], "+1 serie IZQ")
        self.assertEqual(bulgara["carga"], "Mancuernas, RPE 7")
        self.assertTrue(bulgara["por_lado"])
        self.assertEqual(nordic["carga"], "")
        trineo = p["semanas"][0]["dias"][1]["ejercicios"][1]
        self.assertEqual(trineo["carga"], "Moderada: que no se rompa la postura")

    def test_revisar_encuentra_los_errores_sembrados(self):
        avisos = " ".join(m for _, m in procesar.revisar(self.d))
        for esperado in ("1.7 cm", "Energía 2/5", "150 kg", "duplicado", "una sola carga", "95 kg"):
            self.assertIn(esperado, avisos)

    def test_csv(self):
        filas = procesar.plan_filas(self.d)
        self.assertEqual(len(filas), 6)
        procesar.main(["csv", self.json])
        with open(os.path.join(self.tmp.name, "demo.plan.csv"), encoding="utf-8-sig") as f:
            self.assertEqual(len(list(csv.DictReader(f))), 6)

    def test_comparar_mismo_informe(self):
        texto = procesar.comparar_md(self.d, self.d)
        self.assertIn("Flexión de rodilla 90°", texto)
        self.assertNotIn("atletas distintos", texto)


if __name__ == "__main__":
    unittest.main()


class TestEntradaUnica(unittest.TestCase):
    def test_todo(self):
        import evskill
        with tempfile.TemporaryDirectory() as tmp:
            pdf = fabricar_demo.fabricar(os.path.join(tmp, "demo.pdf"))
            evskill.main(["todo", pdf, "--salida", tmp])
            for ext in (".md", ".json", ".txt", ".revision.md", ".plan.csv"):
                self.assertTrue(os.path.exists(os.path.join(tmp, "demo" + ext)), ext)

    def test_ejemplos_al_dia(self):
        """ejemplos/demo.json tiene que coincidir con lo que sale hoy del PDF sintético."""
        with tempfile.TemporaryDirectory() as tmp:
            pdf = fabricar_demo.fabricar(os.path.join(tmp, "demo.pdf"))
            convertir.main([pdf, "--salida", tmp])
            with open(os.path.join(tmp, "demo.json"), encoding="utf-8") as f:
                nuevo = json.load(f)
        with open(os.path.join(AQUI, "..", "ejemplos", "demo.json"), encoding="utf-8") as f:
            self.assertEqual(nuevo, json.load(f), "regenera ejemplos/: python evskill.py todo ejemplos/demo.pdf")
