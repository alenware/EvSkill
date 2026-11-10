#!/usr/bin/env python3
"""Convierte un informe KineReach (PDF) en Markdown legible y en JSON estructurado.

Uso:
    python scripts/convertir.py informe.pdf [otro.pdf ...] [--salida DIR] [--con-texto]

Por cada PDF escribe, en --salida (por defecto, la carpeta del PDF):
    <nombre>.md    el informe limpio: datos en tablas y el plan semana a semana
    <nombre>.json  los mismos datos, listos para procesar (ver procesar.py)
    <nombre>.txt   todo el texto sin cabeceras ni pies, por si algo no se reconoció

Necesita PyMuPDF (pip install pymupdf). No usa red ni servicios externos.
"""
import argparse
import json
import os
import re
import sys
import unicodedata
from collections import Counter

try:
    import fitz  # PyMuPDF
except ImportError:  # pragma: no cover
    sys.exit("Falta PyMuPDF: pip install pymupdf")

# --------------------------------------------------------------------------- utilidades

RUIDO = [
    re.compile(r"^KR$"),
    re.compile(r"^KineReach$"),
    re.compile(r"^KineReach · Documento confidencial"),
    re.compile(r"^Página \d+ de \d+$"),
    re.compile(r"^https?://"),
    re.compile(r"^\d{1,2}/\d{1,2}/\d{2,4},\s*\d{1,2}:\d{2}"),  # sello de impresión del navegador
]
CABECERA = re.compile(r"^(?P<nombre>.+?) · (?P<tipo>.+?) (?P<fecha>\d{2}/\d{2}/\d{4})$")
NUM = re.compile(r"-?\d+(?:[.,]\d+)?")
DIA = re.compile(r"^(LUN|MAR|MIÉ|MIE|JUE|VIE|SÁB|SAB|DOM)$")
DOSIS = re.compile(r"^\d+(?:\s*[–-]\s*\d+)?\s*×")
SEMANA = re.compile(r"^Semana (\d+)$")
LADOS = {"IZQ", "DER", "IZQUIERDO", "DERECHO"}


def limpiar(t):
    t = unicodedata.normalize("NFC", t)
    return re.sub(r"[\u202f\xa0\u2009]", " ", t).strip()


def sin_acentos(t):
    return "".join(c for c in unicodedata.normalize("NFD", t) if unicodedata.category(c) != "Mn")


def num(t):
    if t is None:
        return None
    m = NUM.search(str(t))
    return float(m.group(0).replace(",", ".")) if m else None


def entero_si_puede(x):
    return int(x) if isinstance(x, float) and x.is_integer() else x


def es_mayus(t):
    letras = [c for c in t if c.isalpha()]
    return bool(letras) and t == t.upper() and len(t) <= 70


def valor_unidad(t):
    m = re.match(r"^\s*([≥≈~<>]?\s*-?\d+(?:[.,]\d+)?)\s*(°|kg|cm|mm|m/s|ms|s|N|W|%)?\s*$", t)
    if not m:
        return None, None
    return entero_si_puede(num(m.group(1))), (m.group(2) or "")


def diferencia(a, b):
    if a is None or b is None:
        return None, None
    hi, lo = max(a, b), min(a, b)
    if hi == 0:
        return 0.0, None
    return round(100 * (hi - lo) / hi, 1), (None if a == b else ("izq" if a < b else "der"))


def celda(t):
    if isinstance(t, float) and t.is_integer():
        t = int(t)
    return str(t if t is not None else "").replace("|", "\\|").replace("\n", " ")


def tabla(cab, filas):
    if not filas:
        return ""
    out = ["| " + " | ".join(cab) + " |", "|" + "---|" * len(cab)]
    out += ["| " + " | ".join(celda(c) for c in f) + " |" for f in filas]
    return "\n".join(out) + "\n"


def parrafos(textos):
    """Une líneas cortadas por el ancho de columna en párrafos legibles."""
    out, cur, vistos = [], "", set()
    for t in textos:
        suelta = re.fullmatch(r"(Importancia \w+|[A-ZÁÉÍÓÚ][a-záéíóúñ]+)", t)
        if es_mayus(t) and len(t) < 70:
            if cur:
                out.append(cur)
            if t not in vistos:  # la cabecera se repite al saltar de página
                out.append(f"**{t}**")
            vistos.add(t)
            cur = ""
        elif suelta and len(t) < 25:
            if cur:
                out.append(cur)
            out.append(f"_{t}_")
            cur = ""
        elif cur and (t[:1].islower() or cur.endswith((",", "(", "–", "-", "/", " y", " o", " de", " a", " en"))):
            cur += " " + t
        else:
            if cur:
                out.append(cur)
            cur = t
    if cur:
        out.append(cur)
    return "\n\n".join(out) + "\n"


# --------------------------------------------------------------------------- lectura del PDF

def leer_lineas(ruta):
    """Devuelve las líneas del PDF con su posición y tamaño, sin cabeceras ni pies."""
    doc = fitz.open(ruta)
    crudas = []
    for p, pag in enumerate(doc):
        for b in pag.get_text("dict")["blocks"]:
            for l in b.get("lines", []):
                spans = [s for s in l["spans"] if s["text"].strip()]
                if not spans:
                    continue
                t = limpiar("".join(s["text"] for s in l["spans"]))
                if t:
                    crudas.append({"t": t, "x": round(spans[0]["bbox"][0], 1), "y": round(spans[0]["bbox"][1], 1),
                                   "s": round(spans[0]["size"], 1), "p": p + 1})
    # la cabecera "NOMBRE · Evaluación física dd/mm/aaaa" se repite en cada página
    cands = Counter(l["t"] for l in crudas if CABECERA.match(l["t"]))
    cabecera = cands.most_common(1)[0][0] if cands and cands.most_common(1)[0][1] >= 2 else None
    lineas = [l for l in crudas if l["t"] != cabecera and not any(r.search(l["t"]) for r in RUIDO)]
    es_kinereach = any(l["t"] == "KineReach" for l in crudas[:40])
    return lineas, cabecera, doc.page_count, es_kinereach


def partir_secciones(lineas):
    """Corta en las secciones numeradas del informe: 01 VISIÓN GENERAL, 02 ..."""
    secs, esperado, i = [], 1, 0
    actual = {"n": 0, "etiqueta": "PORTADA", "titulo": "", "lineas": []}
    while i < len(lineas):
        t = lineas[i]["t"]
        if (re.fullmatch(r"\d{2}", t) and int(t) == esperado and i + 2 < len(lineas)
                and es_mayus(lineas[i + 1]["t"]) and not re.fullmatch(r"[\d.,\s]+", lineas[i + 1]["t"])):
            secs.append(actual)
            actual = {"n": esperado, "etiqueta": lineas[i + 1]["t"], "titulo": lineas[i + 2]["t"], "lineas": []}
            esperado += 1
            i += 3
            continue
        actual["lineas"].append(lineas[i])
        i += 1
    secs.append(actual)
    return secs


def tipo_seccion(etiqueta):
    e = sin_acentos(etiqueta).upper()
    for clave, k in [("VISION GENERAL", "vision"), ("ENCUADRE", "encuadre"), ("BIOMETRICOS", "biometricos"),
                     ("MOVILIDAD", "movilidad"), ("FUERZA ISOMETRICA", "dinamometria"), ("POTENCIA", "potencia"),
                     ("VELOCIDAD", "velocidad"), ("VBT", "vbt"), ("PLANIFICACION", "plan"), ("CIERRE", "cierre")]:
        if e.startswith(clave):
            return k
    return "texto"


# --------------------------------------------------------------------------- parsers por sección

def p_portada(textos, todo, cabecera):
    d = {}
    if "Informe de rendimiento" in textos:
        i = textos.index("Informe de rendimiento")
        d["tipo_informe"] = textos[i + 1] if i + 1 < len(textos) else None
        if i + 2 < len(textos):
            d["nombre"] = textos[i + 2].title()
        if i + 3 < len(textos) and "·" in textos[i + 3]:
            d["contexto"] = textos[i + 3]
    if cabecera:
        m = CABECERA.match(cabecera)
        d.setdefault("nombre", m.group("nombre").title())
        d["fecha_evaluacion"] = m.group("fecha")
    else:
        m = re.search(r"(\d{2}/\d{2}/\d{4}) · Documento confidencial", todo)
        if m:
            d["fecha_evaluacion"] = m.group(1)
    for clave, patron in [("edad", r"\n(\d+)\nAños\n"), ("peso_kg", r"\n([\d.,]+)\nkg\n"),
                          ("estatura", r"\n([\d.,]+)\ncm\n"), ("pruebas", r"\n(\d+)\nPruebas\n")]:
        m = re.search(patron, "\n" + todo + "\n")
        if m:
            d[clave] = entero_si_puede(num(m.group(1)))
    return d


def p_vision(textos, contexto=None):
    todo = "\n".join(textos)
    d = {}
    resumen = []
    for t in textos:
        if re.fullmatch(r"[\d.,]+%?", t):
            break
        resumen.append(t)
    d["resumen"] = " ".join(resumen)
    for clave, patron in [("pruebas_registradas", r"(\d+)\nPruebas registradas"),
                          ("capacidades_evaluadas", r"(\d+)\nCapacidades evaluadas"),
                          ("diferencias_15_o_mas", r"(\d+)\nDiferencias entre lados"),
                          ("pruebas_con_dolor", r"(\d+)\nPruebas con dolor")]:
        m = re.search(patron, todo)
        if m:
            d[clave] = int(m.group(1))
    alertas = []

    def ruido_portada(t):  # en PDF impresos desde Safari la portada cae en medio de las alertas
        return (re.fullmatch(r"[\d.,]+", t) or t in ("Años", "kg", "cm", "Pruebas")
                or "Documento confidencial" in t or t == contexto)

    if "ALERTAS PRIORITARIAS" in textos:
        i = textos.index("ALERTAS PRIORITARIAS") + 1
        while i < len(textos) and not textos[i].startswith("ESTADO AL MOMENTO"):
            t = textos[i]
            if ruido_portada(t):
                pass
            elif any(a["titulo"] == t for a in alertas) or (alertas and alertas[-1]["detalle"] == t):
                pass
            elif alertas and not alertas[-1]["detalle"] and not re.search(r"\(\d+%\)$", t):
                alertas[-1]["detalle"] = t
            elif re.search(r"\(\d+%\)$", t) or t.startswith(("Asimetría", "Dolor", "Alerta")) or not alertas or alertas[-1]["detalle"]:
                alertas.append({"titulo": t, "detalle": ""})
            i += 1
    d["alertas"] = alertas
    auto = {}
    for k in ["Sueño", "Energía", "Recuperación", "Estrés", "Fatiga", "Dolor"]:
        m = re.search(rf"(?:^|\n){k}\n(\d)/5", todo)
        if m:
            auto[k.lower()] = int(m.group(1))
    return d, auto


def p_encuadre(textos):
    etiquetas = [t for t in textos if es_mayus(t)]
    valores = [t for t in textos if not es_mayus(t)]
    if etiquetas and len(etiquetas) == len(valores):
        return dict(zip(etiquetas, valores))
    return None


def p_biometricos(textos):
    todo = "\n".join(textos)
    d = {}
    m = re.search(r"([\d.,]+) kg\nPeso", todo)
    if m:
        d["peso_kg"] = entero_si_puede(num(m.group(1)))
    m = re.search(r"([\d.,]+) (cm|m)\nEstatura", todo)
    if m:
        d["estatura"], d["estatura_unidad"] = entero_si_puede(num(m.group(1))), m.group(2)
    m = re.search(r"([\d.,]+)\nIMC", todo)
    if m:
        d["imc"] = num(m.group(1))
    return d


def p_bilateral(textos):
    """Tarjetas 'Prueba / Diferencia alta · 18.5% / IZQ / 27° / DER / 22°' de movilidad y dinamometría."""
    pruebas, otras, grupo = [], [], None
    for i, t in enumerate(textos):
        if es_mayus(t) and t not in LADOS and not re.search(r"\d", t) and len(t) < 30:
            siguiente = textos[i + 1] if i + 1 < len(textos) else ""
            v, u = valor_unidad(siguiente)
            if v is not None and u:  # "MID THIGH PULL / 128.2kg": medida sin lados
                otras.append({"prueba": t.title(), "valor": v, "unidad": u})
            else:
                grupo = t
            continue
        if t == "IZQ" and i + 3 < len(textos) and textos[i + 2] == "DER":
            izq, u1 = valor_unidad(textos[i + 1])
            der, u2 = valor_unidad(textos[i + 3])
            if izq is None or der is None:
                continue
            j, nivel, pct = i - 1, None, None
            m = re.match(r"Diferencia (\w+) · ([\d.,]+)%", textos[j]) if j >= 0 else None
            if m:
                nivel, pct, j = m.group(1), num(m.group(2)), j - 1
            dif, menor = diferencia(izq, der)
            fila = {"grupo": grupo.title() if grupo else None, "prueba": textos[j], "izq": izq, "der": der,
                    "unidad": u1 or u2, "diferencia_pct": dif, "lado_menor": menor,
                    "diferencia_pct_informe": pct, "nivel_informe": nivel}
            if i + 4 < len(textos):
                m = re.match(r"Fuerza relativa: IZQ ([\d.,]+) · DER ([\d.,]+)", textos[i + 4])
                if m:
                    fila["relativa_izq"], fila["relativa_der"] = num(m.group(1)), num(m.group(2))
            pruebas.append(fila)
    return pruebas, otras


def p_hq(todo):
    m = re.search(r"COCIENTE ISQUIOTIBIALES.*?\nIZQ\n([\d.,]+)\n(.*?)\nDER\n([\d.,]+)\n(.*?)(?:\n(?:Comparación|Diferencia)|$)",
                  todo, re.S)
    if not m:
        return None
    return {"izq": num(m.group(1)), "der": num(m.group(3)),
            "detalle_izq": " ".join(m.group(2).split("\n")), "detalle_der": " ".join(m.group(4).split("\n"))}


def p_potencia(textos):
    todo = "\n".join(textos)
    saltos = []
    for i, t in enumerate(textos):
        m = re.match(r"^Promedio ([\d.,]+) ?cm$", t)
        if not m or i < 2 or not re.match(r"^[\d.,]+ ?cm$", textos[i - 1]):
            continue
        k = i - 2
        nombre = textos[k]
        if k >= 1 and re.fullmatch(r"[A-Z]{2,5}", textos[k - 1]):
            nombre = f"{textos[k - 1]} ({textos[k]})"
        s = {"prueba": nombre, "mejor_cm": num(textos[i - 1]), "promedio_cm": num(m.group(1)), "valores": []}
        j = i + 1
        while j < len(textos):
            u = textos[j]
            if u.startswith("CV "):
                s["cv_pct"] = num(u)
            elif u.startswith("Intentos "):
                s["intentos"] = int(num(u))
            elif re.fullmatch(r"[\d.,]+", u) and "intentos" in s and len(s["valores"]) < s["intentos"]:
                s["valores"].append(num(u))
            elif u.startswith("Protocolo"):
                s["protocolo"] = u.split(":", 1)[-1].strip()
                break
            else:
                break
            j += 1
        saltos.append(s)
    dj = [{"caja_cm": int(c), "rsi": num(r), "altura_cm": num(h), "contacto_ms": int(ms),
           "intentos": int(n) if n else None}
          for r, h, ms, c, n in re.findall(
              r"([\d.,]+) RSI\s*Altura ([\d.,]+) cm\s*Contacto (\d+) ms\s*Caja (\d+) cm(?:\s*Intentos (\d+))?", todo)]
    m = re.search(r"RELACIÓN CMJ / SJ\n([\d.,]+)", todo)
    return saltos, sorted(dj, key=lambda x: x["caja_cm"]), (num(m.group(1)) if m else None)


def p_velocidad(textos):
    todo = "\n".join(textos)
    d = {"intentos": [], "referencias": []}
    m = re.search(r"CARRERA DE (\d+) M", todo)
    if m:
        d["distancia_m"] = int(m.group(1))
    if "INTENTO" not in textos:
        return d if d.get("distancia_m") else None
    i = textos.index("INTENTO") + 1
    cols = []
    while i < len(textos) and re.match(r"^(\d+ M|TRAMO .+)$", textos[i]):
        cols.append(textos[i])
        i += 1
    while i < len(textos):
        m = re.fullmatch(r"(\d)( MEJOR)?(?: (.+))?", textos[i])
        if not m:
            break
        if m.group(3):
            celdas, i = re.findall(r"[\d.,]+ s(?: · [\d.,]+ m/s)?", m.group(3)), i + 1
        else:
            celdas, i = textos[i + 1:i + 1 + len(cols)], i + 1 + len(cols)
        fila = {"intento": int(m.group(1)), "mejor": bool(m.group(2)), "parciales_s": {}, "tramos": {}}
        for col, c in zip(cols, celdas):
            if col.startswith("TRAMO"):
                v = re.findall(r"[\d.,]+", c)
                fila["tramos"][col.replace("TRAMO ", "")] = {"s": num(v[0]) if v else None,
                                                             "m_s": num(v[1]) if len(v) > 1 else None}
            else:
                fila["parciales_s"][col.replace(" M", "")] = num(c)
        d["intentos"].append(fila)
    d["referencias"] = sorted(set(re.findall(r"media U\d+: ≈?[\d.,]+ s", todo)))
    return d


CLAVES_VBT = [("SERIE", "serie"), ("CARGA", "kg"), ("REPS", "reps"), ("V MEDIA", "v_media"),
              ("MEJOR", "v_mejor"), ("V PICO", "v_pico"), ("PÉRDIDA", "perdida_pct"), ("POTENCIA", "potencia_w")]


def p_vbt(textos):
    ejercicios = []
    for i, t in enumerate(textos):
        if not re.fullmatch(r"\d+ series", t) or i == 0:
            continue
        ej = {"ejercicio": textos[i - 1], "series": [], "zonas": []}
        j = i + 1
        while j < len(textos) and textos[j] != "SERIE":
            j += 1
        cab = []
        while j < len(textos) and not re.fullmatch(r"[\d.,\s]+", textos[j]):
            if cab and re.fullmatch(r"(m/s|kg|%|W)", textos[j]):
                cab[-1] += " " + textos[j]
            else:
                cab.append(textos[j])
            j += 1
        claves = []
        for c in cab:
            claves.append(next((k for pref, k in CLAVES_VBT if c.upper().startswith(pref)), sin_acentos(c).lower()))
        nums = []
        while j < len(textos) and re.fullmatch(r"[\d.,\s]+", textos[j]):
            nums += [num(x) for x in textos[j].split()]
            j += 1
        if claves:
            for k in range(0, len(nums) - len(claves) + 1, len(claves)):
                fila = dict(zip(claves, nums[k:k + len(claves)]))
                for c in ("serie", "reps", "potencia_w"):
                    if c in fila:
                        fila[c] = entero_si_puede(fila[c])
                ej["series"].append(fila)
        ejercicios.append(ej)
    # zonas: "Fuerza máxima / ≥ 102.5 kg / a 0.40 m/s"
    zonas = []
    for i, t in enumerate(textos):
        if re.match(r"^[≥≈~]?\s*[\d.,]+ kg$", t) and i + 1 < len(textos) and re.match(r"^a [\d.,]+ m/s$", textos[i + 1]):
            zonas.append({"zona": textos[i - 1], "carga": t, "kg": num(t), "v_m_s": num(textos[i + 1])})
    if ejercicios:
        ejercicios[-1]["zonas"] = zonas
    return ejercicios


def p_plan(lineas):
    textos = [l["t"] for l in lineas]
    inicio = next((i for i, t in enumerate(textos) if SEMANA.match(t)), len(textos))
    intro = textos[:inicio]
    plan = {"intro": intro, "semanas": [], "cargas_por_velocidad": []}
    m = re.search(r"Del (\d{2}/\d{2}/\d{4}) al (\d{2}/\d{2}/\d{4})", " ".join(intro))
    if m:
        plan["desde"], plan["hasta"] = m.group(1), m.group(2)
    for i, t in enumerate(intro[:-1]):
        if re.fullmatch(r"[\d.,]+ m/s", t) and re.fullmatch(r"[\d.,]+ kg", intro[i + 1]):
            plan["cargas_por_velocidad"].append({"m_s": num(t), "kg": num(intro[i + 1])})

    semana = dia = ej = None
    bloque, modo = None, None
    x_dosis = x_izq = tam_nombre = None
    for l in lineas[inicio:]:
        t = l["t"]
        m = SEMANA.match(t)
        if m:
            n = int(m.group(1))
            if not semana or semana["n"] != n:
                semana = {"n": n, "fase": None, "objetivo": "", "dias": []}
                plan["semanas"].append(semana)
                modo = "semana"
            else:
                modo = "semana_repetida"
            continue
        if DIA.match(t):
            dia = {"dia": t, "fecha": None, "titulo": None, "descripcion": "", "duracion_min": None, "ejercicios": []}
            semana["dias"].append(dia)
            modo, bloque, ej = "dia", None, None
            continue
        if modo in ("semana", "semana_repetida"):
            if es_mayus(t) and x_izq is not None and abs(l["x"] - x_izq) < 6:
                modo = "cuerpo"  # la página siguió el día anterior sin repetir la cabecera del día
            else:
                if modo == "semana":
                    if semana["fase"] is None:
                        semana["fase"] = t
                    else:
                        semana["objetivo"] = (semana["objetivo"] + " " + t).strip()
                continue
        if modo == "dia":
            if dia["fecha"] is None and re.fullmatch(r"\d{2}/\d{2}", t):
                dia["fecha"] = t
            elif re.fullmatch(r"\d+ min", t):
                dia["duracion_min"] = int(num(t))
                modo = "cuerpo"
            elif dia["titulo"] is None:
                dia["titulo"] = t
            else:
                dia["descripcion"] = (dia["descripcion"] + " " + t).strip()
            continue
        if modo != "cuerpo" or dia is None:
            continue
        if re.match(r"^\+\d+ serie", t):
            if ej:
                ej["serie_extra"] = t
            continue
        if DOSIS.match(t) and ej and not ej["dosis"]:
            ej["dosis"], x_dosis = t, l["x"]
            continue
        if ej and ej["dosis"] and x_dosis is not None and abs(l["x"] - x_dosis) < 12:
            ej["dosis"] += " " + t  # la dosis siguió en otra línea
            continue
        if ej and x_dosis is not None and l["x"] > x_dosis + 60:
            ej["carga"] = (ej["carga"] + " " + t).strip()
            continue
        if es_mayus(t) and (x_dosis is None or l["x"] < x_dosis - 20):
            bloque, ej, x_izq = t, None, l["x"]
            tam_nombre = None
            continue
        # columna izquierda: nombre de ejercicio o indicaciones (letra más pequeña)
        if tam_nombre is None:
            tam_nombre = l["s"]
        if ej and l["s"] < tam_nombre - 0.5:
            ej["indicaciones"] = (ej["indicaciones"] + " " + t).strip()
            continue
        if ej and not ej["dosis"] and not ej["indicaciones"] and abs(l["y"] - ej["_y"]) < 2 * l["s"]:
            ej["nombre"] += " " + t  # nombre largo partido en dos líneas
            ej["_y"] = l["y"]
            continue
        ej = {"bloque": bloque, "nombre": t, "serie_extra": None, "dosis": "", "carga": "", "indicaciones": "",
              "_y": l["y"]}
        dia["ejercicios"].append(ej)
    for s in plan["semanas"]:
        for d in s["dias"]:
            for e in d["ejercicios"]:
                e.pop("_y", None)
                e.update(leer_dosis(e["dosis"]))
    return plan


def leer_dosis(dosis):
    m = re.match(r"^(\d+)(?:\s*[–-]\s*(\d+))?\s*×\s*(.+)$", dosis or "")
    if not m:
        return {"series": None, "reps": None, "por_lado": False}
    series = int(m.group(1)) if not m.group(2) else f"{m.group(1)}-{m.group(2)}"
    return {"series": series, "reps": m.group(3).replace(" por lado", "").strip(),
            "por_lado": "por lado" in m.group(3)}


# --------------------------------------------------------------------------- ensamblado

def convertir(ruta):
    lineas, cabecera, paginas, es_kinereach = leer_lineas(ruta)
    todo = "\n".join(l["t"] for l in lineas)
    secs = partir_secciones(lineas) if es_kinereach else [{"n": 0, "etiqueta": "PORTADA", "titulo": "", "lineas": []}]
    datos = {"fuente": os.path.basename(ruta), "paginas": paginas,
             "secciones": [f'{s["n"]:02d} {s["etiqueta"]}' for s in secs if s["n"]], "sin_reconocer": []}
    datos["atleta"] = p_portada([l["t"] for l in secs[0]["lineas"]], todo, cabecera)
    textos_libres = {}
    for s in secs[1:]:
        textos = [l["t"] for l in s["lineas"]]
        k = tipo_seccion(s["etiqueta"])
        if k == "vision":
            datos["resumen"], datos["autorreporte"] = p_vision(textos, datos["atleta"].get("contexto"))
        elif k == "encuadre":
            enc = p_encuadre(textos)
            if enc:
                datos["encuadre"] = enc
            else:
                textos_libres[s["etiqueta"]] = textos
        elif k == "biometricos":
            datos["biometricos"] = p_biometricos(textos)
        elif k in ("movilidad", "dinamometria"):
            pruebas, otras = p_bilateral(textos)
            datos[k] = pruebas
            if otras:
                datos.setdefault("otras_medidas", []).extend(otras)
            if k == "dinamometria":
                hq = p_hq("\n".join(textos))
                if hq:
                    datos["cociente_hq"] = hq
            if not pruebas:
                datos["sin_reconocer"].append(s["etiqueta"])
        elif k == "potencia":
            datos["saltos"], datos["drop_jumps"], datos["cmj_sj"] = p_potencia(textos)
            if not datos["saltos"] and not datos["drop_jumps"]:
                datos["sin_reconocer"].append(s["etiqueta"])
        elif k == "velocidad":
            v = p_velocidad(textos)
            if v and v["intentos"]:
                datos["sprint"] = v
            else:
                datos["sin_reconocer"].append(s["etiqueta"])
                textos_libres[s["etiqueta"]] = textos
        elif k == "vbt":
            datos["vbt"] = p_vbt(textos)
            # las zonas y el análisis pueden caer en la misma página: el resto se guarda como texto
        elif k == "plan":
            datos["plan"] = p_plan(s["lineas"])
        else:
            textos_libres[f'{s["etiqueta"]} · {s["titulo"]}'] = textos
    datos["textos"] = {k: " \n".join(v) for k, v in textos_libres.items()}
    datos["_textos_lista"] = textos_libres
    return datos, todo


def a_markdown(d, con_texto=False, todo=""):
    a = d.get("atleta", {})
    if not d["secciones"]:  # no es un informe KineReach: se entrega el texto en párrafos
        titulo = os.path.splitext(d["fuente"])[0]
        return (f"# {titulo}\n\n> No parece un informe KineReach: es el texto del PDF sin estructurar.\n\n"
                + parrafos([t for t in todo.split("\n") if t.strip()]))
    md = [f'# {a.get("nombre", "Atleta")} · {a.get("tipo_informe") or "Informe KineReach"}\n']
    ficha = [("Fecha de evaluación", a.get("fecha_evaluacion")), ("Contexto", a.get("contexto")),
             ("Edad", a.get("edad")), ("Peso (kg)", a.get("peso_kg")), ("Estatura", a.get("estatura")),
             ("Pruebas", a.get("pruebas")), ("Fuente", f'{d["fuente"]} ({d["paginas"]} páginas)')]
    md.append(tabla(["Dato", "Valor"], [(k, v) for k, v in ficha if v is not None]))
    md.append("Secciones del informe: " + ", ".join(d["secciones"]) + "\n")

    r = d.get("resumen")
    if r:
        md.append("## Resumen\n")
        md.append(r.get("resumen", "") + "\n")
        nombres = {"pruebas_registradas": "Pruebas registradas", "capacidades_evaluadas": "Capacidades evaluadas",
                   "diferencias_15_o_mas": "Diferencias entre lados ≥ 15 %", "pruebas_con_dolor": "Pruebas con dolor"}
        cont = [(v, r[k]) for k, v in nombres.items() if k in r]
        md.append(tabla(["Indicador", "Valor"], cont))
        if r.get("alertas"):
            md.append("**Alertas del informe**\n")
            md += [f'- {x["titulo"]}' + (f' — {x["detalle"]}' if x["detalle"] else "") for x in r["alertas"]]
            md.append("")
    if d.get("autorreporte"):
        md.append("## Autorreporte (1–5)\n")
        md.append(tabla(list(k.capitalize() for k in d["autorreporte"]), [list(d["autorreporte"].values())]))
    if d.get("encuadre"):
        md.append("## Encuadre\n")
        md.append(tabla(["Campo", "Valor"], list(d["encuadre"].items())))
    if d.get("biometricos"):
        b = d["biometricos"]
        md.append("## Biométricos\n")
        md.append(tabla(["Peso (kg)", "Estatura", "IMC"],
                        [[b.get("peso_kg"), f'{b.get("estatura", "")} {b.get("estatura_unidad", "")}'.strip(), b.get("imc")]]))
    for k, titulo in (("movilidad", "Movilidad"), ("dinamometria", "Dinamometría (fuerza isométrica)")):
        if d.get(k):
            md.append(f"## {titulo}\n")
            filas = []
            for p in d[k]:
                rel = (f'{p["relativa_izq"]} / {p["relativa_der"]}' if "relativa_izq" in p else "")
                filas.append([p["grupo"] or "", p["prueba"], f'{p["izq"]} {p["unidad"]}'.strip(),
                              f'{p["der"]} {p["unidad"]}'.strip(),
                              f'{p["diferencia_pct"]} %' if p["diferencia_pct"] is not None else "",
                              (p["lado_menor"] or "=").upper(), p["nivel_informe"] or ""] + ([rel] if k == "dinamometria" else []))
            cab = ["Grupo", "Prueba", "Izq", "Der", "Diferencia", "Menor", "Nivel (informe)"]
            md.append(tabla(cab + (["×PC izq / der"] if k == "dinamometria" else []), filas))
            md.append("_Diferencia = (lado mayor − lado menor) / lado mayor, recalculada desde los valores._\n")
    if d.get("otras_medidas"):
        md.append("**Otras medidas**\n")
        md.append(tabla(["Prueba", "Valor"], [[o["prueba"], f'{o["valor"]} {o["unidad"]}'] for o in d["otras_medidas"]]))
    if d.get("cociente_hq"):
        h = d["cociente_hq"]
        md.append("**Cociente isquios / cuádriceps (isométrico)**\n")
        md.append(tabla(["Lado", "Cociente", "Detalle"], [["Izq", h["izq"], h["detalle_izq"]], ["Der", h["der"], h["detalle_der"]]]))
    if d.get("saltos") or d.get("drop_jumps"):
        md.append("## Saltos y pliometría\n")
        md.append(tabla(["Prueba", "Mejor (cm)", "Promedio (cm)", "CV %", "Intentos", "Valores", "Protocolo"],
                        [[s["prueba"], s["mejor_cm"], s["promedio_cm"], s.get("cv_pct"), s.get("intentos"),
                          ", ".join(str(v) for v in s["valores"]), s.get("protocolo", "")] for s in d.get("saltos", [])]))
        if d.get("cmj_sj"):
            md.append(f'CMJ ÷ SJ = {d["cmj_sj"]}\n')
        if d.get("drop_jumps"):
            md.append("**Drop jump**\n")
            md.append(tabla(["Caja (cm)", "RSI", "Altura (cm)", "Contacto (ms)", "Intentos"],
                            [[x["caja_cm"], x["rsi"], x["altura_cm"], x["contacto_ms"], x["intentos"]] for x in d["drop_jumps"]]))
    if d.get("sprint"):
        sp = d["sprint"]
        md.append(f'## Sprint{" " + str(sp["distancia_m"]) + " m" if sp.get("distancia_m") else ""}\n')
        parc = sorted({k for f in sp["intentos"] for k in f["parciales_s"]}, key=lambda x: int(x))
        tram = list(dict.fromkeys(k for f in sp["intentos"] for k in f["tramos"]))
        filas = []
        for f in sp["intentos"]:
            fila = [f'{f["intento"]}{" (mejor)" if f["mejor"] else ""}'] + [f["parciales_s"].get(k) for k in parc]
            fila += [f'{f["tramos"][k]["s"]} s · {f["tramos"][k]["m_s"]} m/s' if k in f["tramos"] else "" for k in tram]
            filas.append(fila)
        md.append(tabla(["Intento"] + [f"{k} m (s)" for k in parc] + [f"Tramo {k} m" for k in tram], filas))
        if sp.get("referencias"):
            md.append("Referencias del informe: " + "; ".join(sp["referencias"]) + "\n")
    for ej in d.get("vbt", []):
        md.append(f'## VBT · {ej["ejercicio"]}\n')
        if ej["series"]:
            cab = list(ej["series"][0].keys())
            md.append(tabla(cab, [[s.get(c) for c in cab] for s in ej["series"]]))
        if ej["zonas"]:
            md.append("**Zonas del informe**\n")
            md.append(tabla(["Zona", "Carga", "Velocidad (m/s)"], [[z["zona"], z["carga"], z["v_m_s"]] for z in ej["zonas"]]))
    for titulo, textos in d.get("_textos_lista", {}).items():
        md.append(f"## {titulo.title() if titulo.isupper() else titulo}\n")
        md.append(parrafos(textos))
    if d.get("plan"):
        md.append(plan_md(d["plan"]))
    if d.get("sin_reconocer"):
        md.append("> Secciones que el conversor no pudo leer como datos: " + ", ".join(d["sin_reconocer"]) +
                  ". Revisa el .txt.\n")
    if con_texto:
        md.append("## Anexo: texto completo\n\n```text\n" + todo + "\n```\n")
    return "\n".join(md)


def plan_md(p):
    md = ["## Plan de entrenamiento\n"]
    if p.get("desde"):
        md.append(f'Del {p["desde"]} al {p["hasta"]}.\n')
    if p.get("cargas_por_velocidad"):
        md.append(tabla(["Velocidad (m/s)", "Carga (kg)"], [[c["m_s"], c["kg"]] for c in p["cargas_por_velocidad"]]))
    if p.get("intro"):  # la tabla velocidad → carga ya va arriba
        md.append(parrafos([t for t in p["intro"] if t not in ("VELOCIDAD", "CARGA")
                            and not re.fullmatch(r"[\d.,]+ (m/s|kg)", t)]))
    for s in p["semanas"]:
        md.append(f'### Semana {s["n"]} — {s["fase"] or ""}\n')
        if s["objetivo"]:
            md.append(f'_{s["objetivo"]}_\n')
        for di in s["dias"]:
            dur = f' ({di["duracion_min"]} min)' if di["duracion_min"] else ""
            md.append(f'#### {di["dia"]} {di["fecha"] or ""} · {di["titulo"] or ""}{dur}\n')
            if di["descripcion"]:
                md.append(di["descripcion"] + "\n")
            filas, ultimo = [], None
            for e in di["ejercicios"]:
                nombre = e["nombre"] + (f' **({e["serie_extra"]})**' if e["serie_extra"] else "")
                if e["indicaciones"]:
                    nombre += f'<br>_{e["indicaciones"]}_'
                filas.append([e["bloque"] if e["bloque"] != ultimo else "", nombre, e["dosis"], e["carga"]])
                ultimo = e["bloque"]
            md.append(tabla(["Bloque", "Ejercicio", "Dosis", "Carga / nota"], filas))
    return "\n".join(md)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Informe KineReach (PDF) → Markdown + JSON")
    ap.add_argument("pdf", nargs="+")
    ap.add_argument("--salida", help="carpeta de salida (por defecto, la del PDF)")
    ap.add_argument("--con-texto", action="store_true", help="añade al .md el texto completo como anexo")
    a = ap.parse_args(argv)
    for ruta in a.pdf:
        datos, todo = convertir(ruta)
        carpeta = a.salida or os.path.dirname(os.path.abspath(ruta))
        os.makedirs(carpeta, exist_ok=True)
        base = os.path.join(carpeta, os.path.splitext(os.path.basename(ruta))[0])
        with open(base + ".md", "w", encoding="utf-8") as f:
            f.write(a_markdown(datos, a.con_texto, todo))
        with open(base + ".txt", "w", encoding="utf-8") as f:
            f.write(todo + "\n")
        datos.pop("_textos_lista", None)
        with open(base + ".json", "w", encoding="utf-8") as f:
            json.dump(datos, f, ensure_ascii=False, indent=1)
        if not datos["secciones"]:
            print(f"{os.path.basename(ruta)}: no parece un informe KineReach; solo se extrae el texto")
            print(f"  → {base}.md / .json / .txt")
            continue
        n_ej = sum(len(di["ejercicios"]) for s in datos.get("plan", {}).get("semanas", []) for di in s["dias"])
        print(f'{os.path.basename(ruta)}: {len(datos["secciones"])} secciones, '
              f'{len(datos.get("movilidad", []))} movilidad, {len(datos.get("dinamometria", []))} dinamometría, '
              f'{len(datos.get("saltos", []))} saltos, {len(datos.get("vbt", []))} VBT, '
              f'{len(datos.get("plan", {}).get("semanas", []))} semanas de plan ({n_ej} ejercicios)'
              + (f' · sin reconocer: {", ".join(datos["sin_reconocer"])}' if datos["sin_reconocer"] else ""))
        print(f"  → {base}.md / .json / .txt")


if __name__ == "__main__":
    sys.exit(main())
