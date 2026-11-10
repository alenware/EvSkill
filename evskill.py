#!/usr/bin/env python3
"""EvSkill: un solo punto de entrada para convertir y procesar informes KineReach.

    python evskill.py todo        informe.pdf [...] [--salida DIR]   convierte + revisa + plan a CSV
    python evskill.py convertir   informe.pdf [...] [--salida DIR] [--con-texto]
    python evskill.py revisar     informe.json
    python evskill.py vbt         informe.json [-v 1.0 0.8 0.6] [--media]
    python evskill.py csv         informe.json
    python evskill.py comparar    antes.json despues.json

`todo` es lo que hay que usar casi siempre. El resto existe para repetir un paso suelto.
Ver README.md (guía para la IA) y docs/.
"""
import json
import os
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(AQUI, "scripts"))

import convertir  # noqa: E402
import procesar  # noqa: E402


def todo(args):
    salida = None
    if "--salida" in args:
        i = args.index("--salida")
        salida = args[i + 1]
    pdfs = [a for a in args if a.lower().endswith(".pdf")]
    if not pdfs:
        sys.exit("Uso: python evskill.py todo informe.pdf [...] [--salida DIR]")
    convertir.main(args)
    for pdf in pdfs:
        carpeta = salida or os.path.dirname(os.path.abspath(pdf))
        base = os.path.join(carpeta, os.path.splitext(os.path.basename(pdf))[0])
        with open(base + ".json", encoding="utf-8") as f:
            datos = json.load(f)
        if not datos.get("secciones"):
            continue  # no es KineReach: solo hay texto
        avisos = procesar.revisar(datos)
        with open(base + ".revision.md", "w", encoding="utf-8") as f:
            f.write(procesar.revision_md(datos, avisos))
        hechos = [base + ".revision.md"]
        if procesar.plan_filas(datos):
            procesar.main(["csv", base + ".json"])
            hechos.append(base + ".plan.csv")
        print(f"  revisión: {len(avisos)} avisos → {hechos[0]}")
        if len(hechos) > 1:
            print(f"  plan → {hechos[1]}")


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if not argv or argv[0] in ("-h", "--help", "ayuda"):
        print(__doc__)
        return 0
    cmd, resto = argv[0], argv[1:]
    if cmd == "todo":
        todo(resto)
    elif cmd == "convertir":
        convertir.main(resto)
    elif cmd in ("revisar", "vbt", "csv", "comparar"):
        procesar.main([cmd] + resto)
    else:
        sys.exit(f"Subcomando desconocido: {cmd}. Usa: todo, convertir, revisar, vbt, csv, comparar")
    return 0


if __name__ == "__main__":
    sys.exit(main())
