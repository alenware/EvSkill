# Esquema del JSON

`convertir.py` escribe un `<nombre>.json` por informe. Las claves de nivel superior solo aparecen si el informe trae esa sección: **comprueba que existan antes de usarlas**. Las unidades van en el nombre del campo (`_kg`, `_cm`, `_s`, `_ms`, `_pct`, `_m_s`) o en `unidad`.

Ejemplo completo: [`ejemplos/demo.json`](../ejemplos/demo.json).

## Metadatos

| Clave | Tipo | Qué es |
|---|---|---|
| `fuente` | str | Nombre del PDF |
| `paginas` | int | Páginas del PDF |
| `secciones` | list[str] | Secciones encontradas, p. ej. `"04 FUERZA ISOMÉTRICA"`. **Vacía = no es un informe KineReach**: solo vale el `.txt` |
| `sin_reconocer` | list[str] | Secciones que existen pero no se pudieron leer como datos → buscar en el `.txt` |
| `textos` | dict[str, str] | Secciones sin lector propio (análisis, cierre, vídeo…) como texto plano |

## Atleta y estado

| Clave | Contenido |
|---|---|
| `atleta` | `nombre`, `tipo_informe`, `contexto` ("Futbol · extremo · Sub15 · Club"), `fecha_evaluacion` (dd/mm/aaaa), `edad`, `peso_kg`, `estatura` (de la portada), `pruebas` |
| `resumen` | `resumen` (texto), `pruebas_registradas`, `capacidades_evaluadas`, `diferencias_15_o_mas`, `pruebas_con_dolor`, `alertas`: lista de `{titulo, detalle}` |
| `autorreporte` | `{sueño, energía, recuperación, estrés, fatiga, dolor}`, escala 1–5. La dirección de "dolor" es ambigua: ver docs/revisiones.md |
| `encuadre` | Campos tal cual del informe, p. ej. `{"OBJETIVO": "inicio programa", "ESTADO DE MEDICIÓN": "optimo"}` |
| `biometricos` | `peso_kg`, `estatura`, `estatura_unidad` ("cm" o "m"), `imc` |

## Pruebas bilaterales: `movilidad` y `dinamometria`

Lista de objetos, uno por prueba:

```json
{"grupo": "Rodilla", "prueba": "Flexión de rodilla 90°", "izq": 15, "der": 20, "unidad": "kg",
 "diferencia_pct": 25.0, "lado_menor": "izq",
 "diferencia_pct_informe": 25.0, "nivel_informe": "alta",
 "relativa_izq": 0.25, "relativa_der": 0.33}
```

- `diferencia_pct` la recalcula el script: (mayor − menor) / mayor × 100. **Usa esta**, no la del informe.
- `lado_menor`: `"izq"`, `"der"` o `null` si son iguales.
- `relativa_*` (× peso corporal) solo en dinamometría y si el informe la trae.
- `unidad` puede ser `""` si el informe no la pone (pasa en algunos tests de tobillo y en el ASLR).

Relacionado:
- `otras_medidas`: medidas sin lados, como `{"prueba": "Mid Thigh Pull", "valor": 128.2, "unidad": "kg"}`.
- `cociente_hq`: `{izq, der, detalle_izq, detalle_der}`, el cociente isquios / cuádriceps isométrico.

## Potencia

- `saltos`: `{prueba: "CMJ (Cv alto)", mejor_cm, promedio_cm, cv_pct, intentos, valores: [..], protocolo}`. El nombre empieza por `CMJ` o `SJ`. Lo que va entre paréntesis es la etiqueta del informe.
- `drop_jumps`: `{caja_cm, rsi, altura_cm, contacto_ms, intentos}`, ordenados por caja.
- `cmj_sj`: el cociente CMJ ÷ SJ del informe, o `null`.

## Sprint: `sprint`

```json
{"distancia_m": 20,
 "intentos": [{"intento": 2, "mejor": true,
               "parciales_s": {"10": 1.95, "20": 3.3},
               "tramos": {"0–10": {"s": 1.95, "m_s": 5.13}}}],
 "referencias": ["media U17: 1,92 s"]}
```

- `parciales_s` son tiempos **acumulados**, con la distancia en metros como clave (texto).
- `tramos` solo aparece si el informe trae la tabla por tramos.

## VBT: `vbt`

Lista, una entrada por ejercicio:

```json
{"ejercicio": "Trap Bar deadlift",
 "series": [{"serie": 1, "kg": 40, "reps": 5, "v_media": 0.95, "v_mejor": 1.05, "v_pico": 1.6,
             "perdida_pct": 18.9, "potencia_w": 1545}],
 "zonas": [{"zona": "Fuerza acelerativa", "carga": "≈ 85 kg", "kg": 85, "v_m_s": 0.6}]}
```

`perdida_pct` y `potencia_w` solo aparecen en los informes que traen esas columnas.

## Plan: `plan`

```json
{"desde": "04/01/2027", "hasta": "14/02/2027",
 "cargas_por_velocidad": [{"m_s": 1.0, "kg": 50}],
 "intro": ["…líneas de texto de la introducción del plan…"],
 "semanas": [{"n": 1, "fase": "Base · Carga", "objetivo": "Aprender los patrones…",
   "dias": [{"dia": "LUN", "fecha": "04/01", "titulo": "Fuerza básica", "descripcion": "…",
             "duracion_min": 50,
             "ejercicios": [{"bloque": "UNILATERAL", "nombre": "Sentadilla búlgara",
                             "serie_extra": "+1 serie IZQ", "dosis": "3 × 8 por lado",
                             "series": 3, "reps": "8", "por_lado": true,
                             "carga": "Mancuernas, RPE 7", "indicaciones": ""}]}]}]}
```

- `series` puede ser un rango en texto (`"4-5"`).
- `reps` es texto porque mezcla repeticiones, tiempos y distancias: `"8"`, `"30 s"`, `"10 m"`, `"3 intentos de 30 m"`.
- `serie_extra`: la serie de más para el lado débil. KineReach la quita en la descarga.
- `carga`: la columna derecha. Trae kilos, RPE o una nota ("Sin carga o liviano").
- `indicaciones`: texto pequeño bajo el ejercicio (tempo, velocidad objetivo, cuándo cortar la serie).
