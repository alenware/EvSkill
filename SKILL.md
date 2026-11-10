---
name: kinereach-md
description: Convierte informes de evaluación física KineReach (PDF) a Markdown y JSON, y los procesa después. Revisa incoherencias del informe, saca el perfil carga-velocidad del VBT, pasa el plan de entrenamiento de 6 semanas a CSV y compara una evaluación con su reevaluación. Úsala siempre que haya que leer, resumir, verificar o usar los datos de un PDF de KineReach o KideoReach, aunque el usuario solo diga "mira esta evaluación", "pásame el informe a texto", "qué trae el programa del PDF", "compara con la evaluación anterior" o quiera programar a partir de un informe. No la uses para PDF que no sean de KineReach ni para escribir un programa desde cero sin informe.
---

# kinereach-md

Los informes KineReach son PDF de 20 a 40 páginas. Más o menos la mitad es texto explicativo que se repite en todos ("QUÉ MIDE", "POR QUÉ IMPORTA") y cabeceras de página. Leer el PDF directo gasta contexto y mezcla columnas. Esta skill lo pasa a un Markdown limpio y a un JSON con los datos. Después los procesa con scripts deterministas, así los números no dependen de que el modelo los copie bien.

## Paso 1: convertir

```bash
python <carpeta-de-la-skill>/scripts/kinereach_md.py "informe.pdf" --salida <carpeta de trabajo>
```

- Acepta varios PDF a la vez.
- Escribe tres ficheros por informe:
  - `<nombre>.md`: lo que se lee.
  - `<nombre>.json`: lo que se procesa.
  - `<nombre>.txt`: el texto completo, sin cabeceras ni pies.
- Por pantalla dice qué encontró: secciones, pruebas de movilidad y dinamometría, saltos, VBT y semanas del plan.
- Si una sección no se pudo leer como datos, sale en `sin_reconocer`. Lo que falte se busca en el `.txt`.
- Un PDF que no es de KineReach sale como texto en párrafos, con un aviso.
- Necesita PyMuPDF (`pip install pymupdf`). Funciona sin red.

Lee el `.md`, no el PDF. Ocupa una fracción del original y trae:
- las tablas de lado izquierdo y derecho, con la diferencia recalculada;
- saltos, sprint y VBT;
- el análisis del informe en prosa;
- el plan semana a semana, con bloque, ejercicio, dosis, serie extra del lado débil, carga e indicaciones.

## Paso 2: revisar los datos antes de usarlos

```bash
python <carpeta-de-la-skill>/scripts/procesar.py revisar <nombre>.json
```

Los informes KineReach traen errores con frecuencia. Si se usan sin mirar, acaban en el programa. La revisión comprueba:
- **Estatura:** "1.7 cm" cuando son metros.
- **Sumas:** si el total no coincide con izquierda más derecha.
- **Diferencias y fuerza relativa:** que el valor del informe coincida con el recalculado.
- **Saltos:** CV alto o mal calculado, CMJ menor que SJ.
- **Drop jump:** RSI que no cuadra con altura y contacto, datos duplicados entre cajas.
- **Sprint:** parciales imposibles o intento "mejor" mal marcado.
- **VBT:** el análisis dice "una sola carga" cuando la tabla trae varias; zonas o cargas del plan que no salen de la recta.
- **Autorreporte:** contradicciones, como energía 1/5 con estado "óptimo" o una escala de dolor que parece invertida.
- **Plan:** cargas por encima de lo que el atleta ya movió.

Cuenta los avisos al usuario **en el chat**. Son preguntas para quien evaluó, no correcciones. No corrijas un dato en silencio y no metas la revisión en un entregable para el atleta o el club. Si hay que trabajar con un dato dudoso, di cuál usas y por qué.

Hay cosas que el script no puede comprobar. Pregúntalas si importan:
- la pierna dominante, que casi nunca aparece;
- el protocolo de salida del sprint;
- el calendario real de partidos.

## Paso 3: procesar según lo que se pida

| Pide | Comando | Sale |
|---|---|---|
| Cargas para entrenar por velocidad | `procesar.py vbt <json> -v 1.0 0.8 0.6` | La recta carga-velocidad, su r y los kilos para cada velocidad |
| El plan en hoja de cálculo o para cargarlo en otra app | `procesar.py csv <json>` | `<nombre>.plan.csv`, una fila por ejercicio y día |
| Ver si mejoró en la reevaluación | `procesar.py comparar antes.json despues.json` | `<nombre>.comparacion.md` con la evolución de cada prueba |
| Resumir o explicar el informe | (leer el `.md`) | Un resumen en tus palabras, con los números del JSON |

Sobre el VBT:
- KineReach calcula las zonas y las cargas del plan con la **mejor repetición** de cada serie. `vbt` usa esa misma velocidad por defecto. `--media` usa la velocidad media.
- Si r es menor que 0,9, avisa de que los kilos estimados son poco fiables.
- Nunca propongas cargas por encima de la más alta medida sin decirlo.

Al comparar evaluaciones:
- Un cambio pequeño puede ser solo el error del test. No lo llames mejora si es del orden del CV del salto o de una décima en el sprint.
- Confirma que los dos informes usan el mismo protocolo.

## Cómo está hecho el informe (por si algo falla)

- **Secciones.** El informe se divide en secciones numeradas, como "01 / VISIÓN GENERAL / Resumen de la evaluación". No todos los informes traen las mismas: la numeración cambia según los módulos medidos.
- **Movilidad y dinamometría.** Vienen en tarjetas con este orden: nombre, "Diferencia alta · 18.5%", IZQ, valor, DER, valor y, a veces, "Fuerza relativa".
- **Diferencia entre lados.** Es (lado mayor − lado menor) / lado mayor. KineReach la clasifica así: baja si es menor del 10 %, moderada entre el 10 y el 15 %, alta desde el 15 %.
- **Plan.** El conversor lee la posición del texto en la página para separar las tres columnas:
  - a la izquierda, el ejercicio y sus indicaciones (las indicaciones van en letra más pequeña);
  - en el centro, la dosis ("3 × 8 por lado");
  - a la derecha, la carga o la nota.

  Si KineReach cambia la maqueta, lo primero que se rompe es esto. Compara el `.md` con una página del PDF.
- **PDF impresos desde Safari.** Mezclan los datos de la portada en otras páginas. El conversor lo tolera, pero revisa la ficha del atleta.

## Privacidad

Estos informes son datos de salud, muchas veces de menores:
- No los subas a ningún servicio externo.
- No los copies a un repositorio.
- No pongas nombres reales en ejemplos o en tests.

Los tests de esta skill usan un PDF sintético (`tests/fabricar_demo.py`).
