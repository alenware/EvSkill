#!/usr/bin/env python3
"""Procesa el JSON que sale de kinereach_md.py.

Subcomandos:
    revisar  datos.json            busca incoherencias del informe (unidades, sumas, CV, sprint, VBT...)
    vbt      datos.json [-v 1 0.8] perfil carga-velocidad: recta, r y kilos para cada velocidad
                                   (con la mejor repetición, como KineReach; --media para la media)
    csv      datos.json            el plan de entrenamiento en CSV, una fila por ejercicio y día
    comparar antes.json despues.json   evaluación inicial contra reevaluación

Cada subcomando imprime el resultado en Markdown y, salvo vbt, lo guarda junto al JSON:
<base>.revision.md, <base>.plan.csv o <base>.comparacion.md.
"""
import argparse
import csv
import json
import math
import os
import re
import sys
import unicodedata


def cargar(ruta):
    with open(ruta, encoding="utf-8") as f:
        return json.load(f)


def base_de(ruta):
    return os.path.splitext(ruta)[0]


def norm(t):
    t = "".join(c for c in unicodedata.normalize("NFD", t or "") if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", t.lower()).strip()


def f(x, nd=2):
    if x is None:
        return ""
    x = round(x, nd)
    return str(int(x)) if float(x).is_integer() else str(x)


# --------------------------------------------------------------------------- perfil carga-velocidad

def recta(series, campo="v_media"):
    pts = [(s["kg"], s[campo]) for s in series if s.get("kg") is not None and s.get(campo) is not None]
    if len({kg for kg, _ in pts}) < 2:
        return None
    n = len(pts)
    mx = sum(p[0] for p in pts) / n
    my = sum(p[1] for p in pts) / n
    sxx = sum((p[0] - mx) ** 2 for p in pts)
    syy = sum((p[1] - my) ** 2 for p in pts)
    sxy = sum((p[0] - mx) * (p[1] - my) for p in pts)
    b = sxy / sxx
    a = my - b * mx
    r = sxy / math.sqrt(sxx * syy) if syy else 0.0
    return {"v0": a, "pendiente": b, "r": r, "n": n, "kg_max": max(p[0] for p in pts)}


def kg_para(rc, v):
    return (v - rc["v0"]) / rc["pendiente"] if rc and rc["pendiente"] else None


# --------------------------------------------------------------------------- revisar

def revisar(d):
    av = []  # (categoría, mensaje)
    add = lambda cat, msg: av.append((cat, msg))
    a, b = d.get("atleta", {}), d.get("biometricos", {})
    peso = b.get("peso_kg") or a.get("peso_kg")
    est, unidad = b.get("estatura", a.get("estatura")), b.get("estatura_unidad", "cm")
    imc = b.get("imc")
    if est is not None and unidad == "cm" and est < 100:
        extra = ""
        if peso and imc:
            extra = f"; con el peso y el IMC del informe sale {math.sqrt(peso / imc) * 100:.0f} cm"
        add("Biométricos", f"La estatura figura como {est} cm: casi seguro está en metros{extra}.")
    elif est and peso and imc:
        h = est / 100 if unidad == "cm" else est
        calc = peso / h ** 2
        if abs(calc - imc) > 0.5:
            add("Biométricos", f"IMC del informe {imc}, calculado {calc:.1f} con {peso} kg y {est} {unidad}.")

    au, enc, res = d.get("autorreporte", {}), d.get("encuadre", {}), d.get("resumen", {})
    estado = next((v for k, v in enc.items() if "ESTADO" in k.upper()), "")
    if au.get("energía") is not None and au["energía"] <= 2 and norm(estado).startswith("optim"):
        add("Autorreporte", f"Energía {au['energía']}/5 pero el estado de medición dice «{estado}».")
    if au.get("dolor") == 5 and res.get("pruebas_con_dolor") == 0:
        add("Autorreporte", "Dolor 5/5 con 0 pruebas con dolor: la escala parece invertida (5 = sin dolor). "
                            "Confírmalo antes de usarlo.")
    if au and len(set(au.values())) == 1:
        add("Autorreporte", f"Todos los ítems valen {list(au.values())[0]}/5: puede que no se haya rellenado.")

    for sec in ("movilidad", "dinamometria"):
        for p in d.get(sec, []):
            if p.get("diferencia_pct_informe") is not None and p["diferencia_pct"] is not None \
                    and abs(p["diferencia_pct"] - p["diferencia_pct_informe"]) > 0.6:
                add("Diferencias entre lados", f'{p["prueba"]}: el informe dice {p["diferencia_pct_informe"]} %, '
                                               f'con {p["izq"]} / {p["der"]} sale {p["diferencia_pct"]} %.')
            if peso and "relativa_izq" in p:
                for lado in ("izq", "der"):
                    calc = p[lado] / peso
                    if abs(calc - p[f"relativa_{lado}"]) > 0.02:
                        add("Fuerza relativa", f'{p["prueba"]} {lado}: informe {p[f"relativa_{lado}"]} ×PC, '
                                               f'calculado {calc:.2f} con {peso} kg.')
    for o in d.get("otras_medidas", []):
        for p in d.get("dinamometria", []):
            n1, n2 = norm(o["prueba"]), norm(p["prueba"])
            if n1 and (n1 in n2 or n2 in n1) and o.get("unidad") == "kg":
                suma = p["izq"] + p["der"]
                if abs(suma - o["valor"]) > 1:
                    add("Sumas", f'{o["prueba"]} = {o["valor"]} kg, pero izq + der de «{p["prueba"]}» '
                                 f'= {p["izq"]} + {p["der"]} = {f(suma)} kg.')
    hq = d.get("cociente_hq")
    if hq:
        for lado in ("izq", "der"):
            m = re.search(r"Flexión ([\d.,]+) kg ÷ extensión ([\d.,]+) kg", hq.get(f"detalle_{lado}", ""))
            if m:
                calc = float(m.group(1)) / float(m.group(2))
                if abs(calc - hq[lado]) > 0.02:
                    add("Cociente H/Q", f"{lado}: informe {hq[lado]}, calculado {calc:.2f}.")

    saltos = d.get("saltos", [])
    for s in saltos:
        vals = s.get("valores") or []
        if vals:
            if abs(max(vals) - s["mejor_cm"]) > 0.15:
                add("Saltos", f'{s["prueba"]}: mejor {s["mejor_cm"]} cm, pero el mayor intento es {max(vals)} cm.')
            media = sum(vals) / len(vals)
            if abs(media - s["promedio_cm"]) > 0.15:
                add("Saltos", f'{s["prueba"]}: promedio {s["promedio_cm"]} cm, calculado {media:.1f} cm.')
            if len(vals) > 1 and s.get("cv_pct") is not None:
                sd_m = math.sqrt(sum((v - media) ** 2 for v in vals) / (len(vals) - 1))
                sd_p = math.sqrt(sum((v - media) ** 2 for v in vals) / len(vals))
                cvs = (100 * sd_m / media, 100 * sd_p / media)
                if min(abs(c - s["cv_pct"]) for c in cvs) > 0.5:
                    add("Saltos", f'{s["prueba"]}: CV {s["cv_pct"]} %, calculado {cvs[0]:.1f} % (muestral).')
        if s.get("cv_pct") and s["cv_pct"] > 10:
            add("Saltos", f'{s["prueba"]}: CV {s["cv_pct"]} %, alto. El mejor intento puede no ser representativo; '
                          f'conviene repetir el test.')
    cmj = next((s for s in saltos if s["prueba"].upper().startswith("CMJ")), None)
    sj = next((s for s in saltos if s["prueba"].upper().startswith("SJ")), None)
    if cmj and sj and cmj["mejor_cm"] < sj["mejor_cm"]:
        add("Saltos", f'CMJ ({cmj["mejor_cm"]} cm) menor que SJ ({sj["mejor_cm"]} cm): raro; revisa la técnica '
                      f'o el registro.')

    vistos = {}
    for x in d.get("drop_jumps", []):
        rsi = x["altura_cm"] / 100 / (x["contacto_ms"] / 1000)
        if abs(rsi - x["rsi"]) > 0.05:
            add("Drop jump", f'Caja {x["caja_cm"]} cm: RSI {x["rsi"]}, con altura y contacto sale {rsi:.2f}.')
        clave = (x["altura_cm"], x["contacto_ms"])
        if clave in vistos:
            add("Drop jump", f'Cajas {vistos[clave]} y {x["caja_cm"]} cm con la misma altura y contacto '
                             f'({x["altura_cm"]} cm, {x["contacto_ms"]} ms): dato duplicado.')
        vistos[clave] = x["caja_cm"]
        if x.get("intentos") is None:
            add("Drop jump", f'Caja {x["caja_cm"]} cm sin número de intentos.')

    sp = d.get("sprint")
    if sp and sp.get("intentos"):
        dists = sorted({int(k) for i in sp["intentos"] for k in i["parciales_s"]})
        if dists:
            final = str(dists[-1])
            con_final = [i for i in sp["intentos"] if i["parciales_s"].get(final)]
            if con_final:
                mejor = min(con_final, key=lambda i: i["parciales_s"][final])
                marcado = next((i for i in sp["intentos"] if i["mejor"]), None)
                if marcado and marcado["intento"] != mejor["intento"]:
                    add("Sprint", f'El informe marca el intento {marcado["intento"]} como mejor, '
                                  f'pero el menor tiempo a {final} m es el {mejor["intento"]}.')
        for i in sp["intentos"]:
            prev_t, prev_d, prev_v = 0.0, 0, None
            for dist in dists:
                t = i["parciales_s"].get(str(dist))
                if t is None:
                    continue
                if t <= prev_t:
                    add("Sprint", f'Intento {i["intento"]}: el parcial de {dist} m ({t} s) no es mayor que el anterior.')
                    break
                v = (dist - prev_d) / (t - prev_t)
                if prev_d >= 10 and v > 9.5:
                    add("Sprint", f'Intento {i["intento"]}, tramo {prev_d}–{dist} m: {v:.1f} m/s, poco creíble; '
                                  f'revisa las fotocélulas.')
                if prev_v and v < prev_v * 0.75:
                    add("Sprint", f'Intento {i["intento"]}, tramo {prev_d}–{dist} m: {v:.1f} m/s, mucho más lento que '
                                  f'el tramo anterior ({prev_v:.1f} m/s). Posible error de cronometraje.')
                prev_t, prev_d, prev_v = t, dist, v

    textos = " ".join((d.get("textos") or {}).values())
    for ej in d.get("vbt", []):
        series = ej.get("series", [])
        cargas = sorted({s["kg"] for s in series if s.get("kg") is not None})
        if len(cargas) < 2:
            add("VBT", f'{ej["ejercicio"]}: una sola carga; no hay perfil carga-velocidad.')
            continue
        if re.search(r"(solo|sólo|única|una sola) (una )?carga|una carga y velocidad", textos, re.I):
            add("VBT", f'El análisis del informe dice que hubo una sola carga, pero la tabla de {ej["ejercicio"]} '
                       f'tiene {len(cargas)} cargas distintas ({", ".join(f(c) for c in cargas)} kg).')
        orden = sorted((s for s in series if s.get("v_media") is not None), key=lambda s: s["kg"])
        for s1, s2 in zip(orden, orden[1:]):
            if s2["kg"] > s1["kg"] and s2["v_media"] > s1["v_media"]:
                add("VBT", f'{ej["ejercicio"]}: con {f(s2["kg"])} kg va más rápido ({s2["v_media"]} m/s) que con '
                           f'{f(s1["kg"])} kg ({s1["v_media"]} m/s).')
        rc = recta(series)
        if rc and abs(rc["r"]) < 0.9:
            add("VBT", f'{ej["ejercicio"]}: la recta carga-velocidad ajusta mal (r = {rc["r"]:.2f}); '
                       f'usa los kilos estimados con cautela.')
        # KineReach calcula zonas y cargas del plan con la mejor repetición; se aceptan las dos rectas
        rectas = {"velocidad media": rc, "mejor repetición": recta(series, "v_mejor")}
        objetivos = [(f'Zona «{z["zona"]}»', z["v_m_s"], z.get("kg")) for z in ej.get("zonas", [])]
        objetivos += [("Plan", c["m_s"], c["kg"]) for c in (d.get("plan") or {}).get("cargas_por_velocidad", [])]
        for nombre, v, kg in objetivos:
            calc = {k: kg_para(r, v) for k, r in rectas.items() if r}
            if kg and calc and all(abs(c - kg) > max(5, 0.1 * kg) for c in calc.values()):
                alt = " o ".join(f"{c:.1f} kg ({k})" for k, c in calc.items())
                add("VBT", f"{nombre}: el informe pone {f(kg)} kg a {v} m/s; con la recta salen {alt}.")

    plan = d.get("plan")
    if plan:
        kg_max = max((s["kg"] for ej in d.get("vbt", []) for s in ej.get("series", []) if s.get("kg")), default=None)
        for s in plan.get("semanas", []):
            for di in s["dias"]:
                for e in di["ejercicios"]:
                    if not e.get("dosis"):
                        add("Plan", f'Semana {s["n"]} {di["dia"]}: «{e["nombre"]}» sin dosis.')
                    kgs = [float(x.replace(",", ".")) for x in re.findall(r"(\d+(?:[.,]\d+)?)\s*kg", e.get("carga", ""))]
                    if kg_max and kgs and max(kgs) > kg_max + 2.5:
                        add("Plan", f'Semana {s["n"]} {di["dia"]}: «{e["nombre"]}» con {f(max(kgs))} kg, por encima de '
                                    f'la carga máxima medida ({f(kg_max)} kg).')
    if d.get("sin_reconocer"):
        add("Conversión", "Secciones no leídas como datos: " + ", ".join(d["sin_reconocer"]) + ". Mira el .txt.")
    return av


def revision_md(d, av):
    a = d.get("atleta", {})
    out = [f'# Revisión de datos · {a.get("nombre", "")} ({a.get("fecha_evaluacion", "")})\n']
    if not av:
        out.append("No se encontraron incoherencias automáticas. Aun así, revisa a mano lo que no se puede "
                   "comprobar solo (pierna dominante, protocolo de los tests, calendario).\n")
        return "\n".join(out)
    out.append(f"{len(av)} avisos. Son para confirmar con quien evaluó, no para corregir en silencio.\n")
    cat_prev = None
    for cat, msg in av:
        if cat != cat_prev:
            out.append(f"\n## {cat}\n")
            cat_prev = cat
        out.append(f"- {msg}")
    return "\n".join(out) + "\n"


# --------------------------------------------------------------------------- vbt

def vbt_md(d, velocidades, campo):
    out = []
    for ej in d.get("vbt", []):
        rc = recta(ej.get("series", []), campo)
        out.append(f'## Perfil carga-velocidad · {ej["ejercicio"]}\n')
        if not rc:
            out.append("Hace falta al menos dos cargas distintas.\n")
            continue
        out.append(f'v = {rc["v0"]:.3f} {"+" if rc["pendiente"] >= 0 else "−"} {abs(rc["pendiente"]):.5f} × kg '
                   f'(r = {rc["r"]:.2f}, {rc["n"]} series, velocidad: {campo})\n')
        out.append("| Velocidad (m/s) | Carga estimada (kg) | Nota |\n|---|---|---|")
        for v in velocidades:
            k = kg_para(rc, v)
            nota = "por encima de lo medido" if k and k > rc["kg_max"] else ""
            out.append(f"| {v} | {f(k, 1)} | {nota} |")
        out.append("\nRedondea a lo que permitan los discos y ajusta en la sesión mirando la velocidad real.\n")
    return "\n".join(out) or "El informe no trae VBT.\n"


# --------------------------------------------------------------------------- csv

CAMPOS_CSV = ["semana", "fase", "dia", "fecha", "sesion", "duracion_min", "orden", "bloque", "ejercicio",
              "serie_extra", "series", "reps", "por_lado", "dosis", "carga_nota", "indicaciones"]


def plan_filas(d):
    filas = []
    for s in d.get("plan", {}).get("semanas", []):
        for di in s["dias"]:
            for n, e in enumerate(di["ejercicios"], 1):
                filas.append({"semana": s["n"], "fase": s["fase"], "dia": di["dia"], "fecha": di["fecha"],
                              "sesion": di["titulo"], "duracion_min": di["duracion_min"], "orden": n,
                              "bloque": e["bloque"], "ejercicio": e["nombre"], "serie_extra": e["serie_extra"] or "",
                              "series": e.get("series"), "reps": e.get("reps"), "por_lado": e.get("por_lado"),
                              "dosis": e["dosis"], "carga_nota": e["carga"], "indicaciones": e["indicaciones"]})
    return filas


# --------------------------------------------------------------------------- comparar

def cambio(a, b, menor_mejor=False):
    if a is None or b is None:
        return ""
    if a == 0:
        return f(b - a)
    pct = 100 * (b - a) / abs(a)
    mejora = (pct < 0) if menor_mejor else (pct > 0)
    return f"{'+' if pct >= 0 else ''}{pct:.1f} %" + (" ✓" if mejora and abs(pct) >= 1 else "")


def comparar_md(a, b):
    na = a.get("atleta", {})
    out = [f'# Comparación · {na.get("nombre", "")}\n',
           f'{a.get("atleta", {}).get("fecha_evaluacion", "?")} → {b.get("atleta", {}).get("fecha_evaluacion", "?")}\n']
    nb = b.get("atleta", {}).get("nombre")
    if norm(na.get("nombre")) != norm(nb):
        out.append(f'> ⚠ Los informes son de atletas distintos ({na.get("nombre")} y {nb}).\n')
    for sec, titulo in (("movilidad", "Movilidad"), ("dinamometria", "Dinamometría")):
        idx = {norm(p["prueba"]): p for p in b.get(sec, [])}
        filas = []
        for p in a.get(sec, []):
            q = idx.get(norm(p["prueba"]))
            if not q:
                continue
            filas.append(f'| {p["prueba"]} | {f(p["izq"])} → {f(q["izq"])} ({cambio(p["izq"], q["izq"])}) | '
                         f'{f(p["der"])} → {f(q["der"])} ({cambio(p["der"], q["der"])}) | '
                         f'{f(p["diferencia_pct"], 1)} % → {f(q["diferencia_pct"], 1)} % |')
        if filas:
            out.append(f"## {titulo}\n\n| Prueba | Izq | Der | Diferencia entre lados |\n|---|---|---|---|")
            out += filas + [""]
    sa = {norm(s["prueba"]).split()[0]: s for s in a.get("saltos", [])}
    sb = {norm(s["prueba"]).split()[0]: s for s in b.get("saltos", [])}
    filas = [f'| {sa[k]["prueba"]} | {f(sa[k]["mejor_cm"])} | {f(sb[k]["mejor_cm"])} | '
             f'{cambio(sa[k]["mejor_cm"], sb[k]["mejor_cm"])} |' for k in sa if k in sb]
    if filas:
        out.append("## Saltos (mejor intento, cm)\n\n| Prueba | Antes | Después | Cambio |\n|---|---|---|---|")
        out += filas + [""]

    def mejor_sprint(d):
        sp = d.get("sprint") or {}
        return next((i for i in sp.get("intentos", []) if i["mejor"]), None)

    ma, mb = mejor_sprint(a), mejor_sprint(b)
    if ma and mb:
        out.append("## Sprint (mejor intento, s)\n\n| Parcial | Antes | Después | Cambio |\n|---|---|---|---|")
        for k in ma["parciales_s"]:
            if k in mb["parciales_s"]:
                out.append(f'| {k} m | {ma["parciales_s"][k]} | {mb["parciales_s"][k]} | '
                           f'{cambio(ma["parciales_s"][k], mb["parciales_s"][k], True)} |')
        out.append("")
    for ea in a.get("vbt", []):
        eb = next((x for x in b.get("vbt", []) if norm(x["ejercicio"]) == norm(ea["ejercicio"])), None)
        ra, rb = recta(ea.get("series", [])), recta(eb.get("series", [])) if eb else None
        if ra and rb:
            out.append(f'## VBT · {ea["ejercicio"]} (kg estimados a cada velocidad)\n\n'
                       f'| Velocidad | Antes | Después | Cambio |\n|---|---|---|---|')
            for v in (1.0, 0.75, 0.5):
                ka, kb = kg_para(ra, v), kg_para(rb, v)
                out.append(f"| {v} m/s | {f(ka, 1)} | {f(kb, 1)} | {cambio(ka, kb)} |")
            out.append("")
    out.append("_Cambios pequeños (menos del error de medida del test) no son mejoras: confírmalos con el "
               "mismo protocolo._\n")
    return "\n".join(out)


# --------------------------------------------------------------------------- main

def guardar(ruta, texto):
    with open(ruta, "w", encoding="utf-8") as fh:
        fh.write(texto)
    print(f"\n→ {ruta}")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Procesa el JSON de un informe KineReach")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("revisar", help="busca incoherencias en los datos")
    p.add_argument("json")
    p = sub.add_parser("vbt", help="perfil carga-velocidad y kilos por velocidad")
    p.add_argument("json")
    p.add_argument("-v", "--velocidades", type=float, nargs="+", default=[1.0, 0.9, 0.8, 0.75, 0.6, 0.5])
    p.add_argument("--media", action="store_true",
                   help="usa la velocidad media de la serie (por defecto, la mejor repetición, como KineReach)")
    p = sub.add_parser("csv", help="plan de entrenamiento a CSV")
    p.add_argument("json")
    p = sub.add_parser("comparar", help="evaluación inicial contra reevaluación")
    p.add_argument("antes")
    p.add_argument("despues")
    a = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    if a.cmd == "revisar":
        d = cargar(a.json)
        texto = revision_md(d, revisar(d))
        print(texto)
        guardar(base_de(a.json) + ".revision.md", texto)
    elif a.cmd == "vbt":
        print(vbt_md(cargar(a.json), a.velocidades, "v_media" if a.media else "v_mejor"))
    elif a.cmd == "csv":
        filas = plan_filas(cargar(a.json))
        if not filas:
            sys.exit("El informe no trae plan de entrenamiento.")
        ruta = base_de(a.json) + ".plan.csv"
        with open(ruta, "w", encoding="utf-8-sig", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=CAMPOS_CSV)
            w.writeheader()
            w.writerows(filas)
        print(f"{len(filas)} filas → {ruta}")
    elif a.cmd == "comparar":
        texto = comparar_md(cargar(a.antes), cargar(a.despues))
        print(texto)
        guardar(base_de(a.despues) + ".comparacion.md", texto)


if __name__ == "__main__":
    sys.exit(main())
