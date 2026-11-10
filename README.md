# kinereach-md

Convierte informes de evaluación física **KineReach** (PDF) en **Markdown** y **JSON**, y después los procesa:

- revisa incoherencias del informe;
- saca el perfil carga-velocidad del VBT;
- pasa el plan de entrenamiento a CSV;
- compara una evaluación con su reevaluación.

Se puede usar como **skill de Claude Code** o como dos scripts de Python sueltos. Funciona sin red y solo necesita PyMuPDF.

> *English: converts KineReach physical-assessment PDF reports into clean Markdown + structured JSON, checks the report for inconsistencies, fits the load-velocity profile, exports the 6-week training plan to CSV and compares two assessments. Spanish-language reports.*

## Qué resuelve

Un informe KineReach tiene entre 20 y 40 páginas. Gran parte es texto explicativo que se repite en todos los informes, y las tablas salen partidas en columnas. Copiar los números a mano o pedírselos a un modelo leyendo el PDF da errores. Este proyecto:

1. **Extrae** lo que importa en tablas:
   - ficha del atleta, autorreporte y encuadre;
   - movilidad y dinamometría por lado, con la diferencia recalculada;
   - cociente isquios/cuádriceps;
   - saltos (CMJ, SJ, drop jump), sprint por tramos y VBT;
   - el **plan de 6 semanas**, día por día: bloque, ejercicio, dosis, serie extra del lado débil, carga e indicaciones.
2. **Revisa** el informe y avisa de errores reales que aparecen en estos PDF:
   - estatura en metros marcada como cm;
   - totales que no suman izquierda + derecha;
   - drop jumps duplicados;
   - RSI que no cuadra con altura y contacto;
   - parciales de sprint imposibles;
   - un análisis que dice "una sola carga" cuando el VBT tiene cinco;
   - cargas del plan por encima de lo medido.
3. **Procesa** los datos:
   - kilos para cada velocidad de barra;
   - el plan en CSV;
   - comparación antes/después.

## Instalación

```bash
pip install pymupdf
```

**Como skill de Claude Code:** clona el repo dentro de tu carpeta de skills.

```bash
git clone https://github.com/iggtht/kinereach-md ~/.claude/skills/kinereach-md
```

Claude la usará sola cuando le pases un informe KineReach. `SKILL.md` describe el flujo.

**Como scripts sueltos:** clónalo donde quieras y usa `scripts/`.

## Uso

```bash
# 1. PDF → .md + .json + .txt
python scripts/kinereach_md.py "EVALUACION.pdf" --salida trabajo/

# 2. Revisar los datos (escribe EVALUACION.revision.md)
python scripts/procesar.py revisar trabajo/EVALUACION.json

# 3. Procesar
python scripts/procesar.py vbt trabajo/EVALUACION.json -v 1.0 0.8 0.6   # kilos por velocidad
python scripts/procesar.py csv trabajo/EVALUACION.json                  # plan → EVALUACION.plan.csv
python scripts/procesar.py comparar trabajo/inicial.json trabajo/reevaluacion.json
```

Ejemplo de revisión (salida real con el PDF sintético de los tests):

```text
## Biométricos
- La estatura figura como 1.7 cm: casi seguro está en metros; con el peso y el IMC del informe sale 170 cm.
## Sumas
- Empuje Horizontal = 150 kg, pero izq + der de «Empuje horizontal» = 75 + 80 = 155 kg.
## Drop jump
- Cajas 30 y 45 cm con la misma altura y contacto (24.0 cm, 160 ms): dato duplicado.
## VBT
- El análisis del informe dice que hubo una sola carga, pero la tabla de Trap Bar deadlift tiene 3 cargas distintas (40, 60, 80 kg).
## Plan
- Semana 2 LUN: «Peso muerto con barra hexagonal» con 95 kg, por encima de la carga máxima medida (80 kg).
```

Y un día del plan en el `.md`:

| Bloque | Ejercicio | Dosis | Carga / nota |
|---|---|---|---|
| FUERZA PRINCIPAL (VBT) | Peso muerto con barra hexagonal<br>_VBT: mejor repetición 1.00 m/s. Cortar si baja de 0.90 m/s._ | 3 × 5 | 50 kg |
| UNILATERAL | Sentadilla búlgara **(+1 serie IZQ)** | 3 × 8 por lado | Mancuernas, RPE 7 |

## Cómo funciona

- **Texto con posición.** PyMuPDF lee cada línea del PDF con su posición y su tamaño de letra. Se quitan las cabeceras y los pies que se repiten en cada página, y también los sellos de impresión del navegador.
- **Secciones.** El informe se corta en sus secciones numeradas (`01 VISIÓN GENERAL`, `02 BIOMÉTRICOS`…). La numeración cambia según los módulos medidos, así que cada sección se reconoce por su nombre.
- **Datos por sección.** Cada sección tiene su lector: tarjetas IZQ/DER, bloques de salto, tabla de sprint y tabla VBT.
- **Columnas del plan.** El plan se lee por columnas. A la izquierda va el ejercicio y, en letra más pequeña, sus indicaciones; en el centro, la dosis; a la derecha, la carga o la nota.
- **Lo demás.** Lo que no tiene lector (análisis, cierre, informes de vídeo KideoReach) pasa como texto en párrafos.

Probado con exportaciones de septiembre a noviembre de 2026, impresas desde Chrome y desde Safari en iOS. Si KineReach cambia la maqueta, el plan es lo primero que se rompe. El conversor avisa de las secciones que no reconoce y deja el texto completo en el `.txt`.

## Tests

```bash
python -m unittest discover -s tests
```

Los tests fabrican un PDF **sintético** con la maqueta de un informe y datos inventados (`tests/fabricar_demo.py`), con errores sembrados a propósito. En este repo no hay ningún informe real: son datos de salud, muchas veces de menores.

## Aviso

Proyecto independiente, sin relación con KineReach. Solo lee los PDF que el propio usuario exporta. Los avisos de la revisión son preguntas para quien evaluó, no diagnósticos.

## Licencia

MIT
