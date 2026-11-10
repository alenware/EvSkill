# EvSkill

Herramienta para **leer, verificar y procesar informes de evaluación física KineReach (PDF)**:

- pasa cada PDF a Markdown limpio y a JSON con los datos;
- revisa las incoherencias del informe;
- calcula las cargas del VBT;
- exporta el plan de 6 semanas a CSV;
- compara una evaluación con su reevaluación.

Funciona sin red y solo necesita Python 3.9+ y PyMuPDF.

> *English: tools for AI agents and humans to convert KineReach assessment PDFs (Spanish) into clean Markdown + structured JSON, check them for data errors, fit the VBT load-velocity profile, export the training plan to CSV and compare assessments.*

Este README está escrito **para que un agente de IA** (Claude, Codex, GPT…) sepa usar la herramienta sin explorar el código. Si eres una persona, también te sirve.

---

## Para la IA: lo esencial

**Cuándo usarla:** siempre que tengas que leer, resumir, verificar o usar datos de un PDF de KineReach o KideoReach, o programar entrenamiento a partir de uno.

**Regla 1. No leas el PDF directamente.** Ejecuta esto y lee el `.md`:

```bash
python evskill.py todo "ruta/al/informe.pdf" --salida "carpeta/de/trabajo"
```

Ese comando hace todo de una vez:

| Fichero | Para qué |
|---|---|
| `<nombre>.md` | **Léelo tú.** El informe en tablas, sin texto repetido y con el plan día a día |
| `<nombre>.json` | Los datos para calcular. Esquema en [docs/esquema-json.md](docs/esquema-json.md) |
| `<nombre>.revision.md` | **Avisos de datos dudosos.** Cuéntaselos al usuario |
| `<nombre>.plan.csv` | El plan, una fila por ejercicio y día (solo si el informe trae plan) |
| `<nombre>.txt` | Todo el texto del PDF, por si algo no se reconoció |

**Regla 2. Revisa antes de usar.** Los informes KineReach traen errores reales: estatura en metros marcada como cm, sumas que no cuadran, drop jumps duplicados, un análisis que contradice su propia tabla de VBT… Abre `<nombre>.revision.md` y comunica los avisos **en el chat**, como preguntas para quien evaluó. No corrijas datos en silencio y no pongas la revisión en un entregable. Qué significa cada aviso: [docs/revisiones.md](docs/revisiones.md).

**Regla 3. Los números salen del JSON, no de tu memoria.** Para calcular, lee el `.json` o usa los subcomandos. No copies cifras del PDF a ojo.

**Regla 4. Privacidad.** Son datos de salud, muchas veces de menores. No subas los informes ni sus salidas a servicios externos ni a repositorios. Usa siempre una `--salida` local.

### Subcomandos

| Necesitas | Comando |
|---|---|
| Todo de una vez (lo normal) | `python evskill.py todo informe.pdf [...] --salida DIR` |
| Solo convertir | `python evskill.py convertir informe.pdf [...] --salida DIR [--con-texto]` |
| Solo revisar | `python evskill.py revisar DIR/informe.json` |
| Kilos para entrenar por velocidad | `python evskill.py vbt DIR/informe.json -v 1.0 0.8 0.6` |
| El plan en CSV | `python evskill.py csv DIR/informe.json` |
| Evolución entre dos evaluaciones | `python evskill.py comparar DIR/inicial.json DIR/reevaluacion.json` |

Con `python evskill.py` sin argumentos ves la ayuda.

### Cómo interpretar las salidas

- **Diferencia entre lados** = (lado mayor − lado menor) / lado mayor. Se considera baja si es menor del 10 %, moderada entre el 10 y el 15 % y alta desde el 15 %. El script la **recalcula**: usa `diferencia_pct`, no la del informe.
- **VBT:** KineReach calcula las zonas y las cargas del plan con la **mejor repetición** de cada serie, y `vbt` hace lo mismo por defecto (`--media` usa la velocidad media).
  - Si r < 0,9, los kilos estimados son poco fiables.
  - No propongas cargas por encima de la más alta medida sin decirlo.
- **Comparar:** un cambio del orden del error del test (CV del salto, una décima en el sprint) no es una mejora. Confirma también que se usó el mismo protocolo.
- **`secciones` vacío** en el JSON = el PDF no es de KineReach. Solo tienes el texto.
- **`sin_reconocer` con elementos:** esa sección está en el `.txt`, no en el `.md`.

### Lo que la herramienta no sabe (pregúntalo si importa)

- la pierna dominante;
- el protocolo de los tests;
- el calendario de partidos;
- el historial de lesiones.

### Flujo típico

```
Usuario: "mira la evaluación de X y hazle el programa"
 1. python evskill.py todo "X.pdf" --salida trabajo/
 2. leer trabajo/X.md → diagnóstico (asimetrías, saltos, sprint, VBT)
 3. leer trabajo/X.revision.md → contar los avisos y preguntar lo dudoso
 4. con datos confirmados: python evskill.py vbt trabajo/X.json -v ... para las cargas
 5. programar (fuera de esta herramienta)
```

Ejemplos reales de todas las salidas, generados con un PDF sintético, en [`ejemplos/`](ejemplos/).

---

## Instalación

```bash
git clone https://github.com/iggtht/EvSkill
pip install -r EvSkill/requirements.txt
```

**Como skill de Claude Code:** clónalo dentro de tu carpeta de skills. Claude lo usará solo cuando le pases un informe KineReach (entra por [`SKILL.md`](SKILL.md)).

```bash
git clone https://github.com/iggtht/EvSkill ~/.claude/skills/EvSkill
```

**Otros agentes (Codex, Cursor…):** apúntalos a este README o copia la sección "Para la IA" a su fichero de instrucciones (`AGENTS.md` o similar).

## Estructura

```
EvSkill/
├── evskill.py              ← punto de entrada único (todo, convertir, revisar, vbt, csv, comparar)
├── SKILL.md                ← entrada para Claude Code (corta; remite aquí)
├── README.md               ← esta guía
├── scripts/
│   ├── convertir.py        ← PDF → .md + .json + .txt
│   └── procesar.py         ← revisar, vbt, csv, comparar sobre el JSON
├── docs/
│   ├── esquema-json.md     ← todas las claves del JSON
│   ├── revisiones.md       ← qué detecta cada aviso y qué hacer
│   └── formato-kinereach.md← cómo está hecho el PDF (para mantener el conversor)
├── ejemplos/               ← PDF sintético y todas sus salidas
├── tests/
│   ├── fabricar_demo.py    ← fabrica el PDF sintético (datos inventados, errores sembrados)
│   └── test_evskill.py
├── requirements.txt
└── .github/workflows/tests.yml
```

## Tests

```bash
python -m unittest discover -s tests
```

Los tests fabrican un PDF **sintético** con la maqueta de un informe KineReach y datos inventados, con errores sembrados a propósito para que `revisar` los encuentre. En este repo no hay ningún informe real.

## Limitaciones

- Probado con exportaciones de septiembre a noviembre de 2026, impresas desde Chrome y desde Safari en iOS. Si KineReach cambia la maqueta, el plan es lo primero que se rompe: compara el `.md` con el PDF y mira [docs/formato-kinereach.md](docs/formato-kinereach.md).
- Los informes de vídeo (KideoReach) y el análisis en prosa salen como texto, no como datos.

## Aviso

Proyecto independiente, sin relación con KineReach. Solo procesa los PDF que exporta el propio usuario. Los avisos de la revisión no son diagnósticos.

## Licencia

MIT
