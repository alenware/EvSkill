# Cómo está hecho un PDF de KineReach (para mantener el conversor)

Lee esto solo si el conversor falla con un informe nuevo o vas a tocar `scripts/convertir.py`.

## Lectura

`leer_lineas()` usa PyMuPDF (`page.get_text("dict")`) y guarda cada línea con su texto, `x`, `y`, tamaño de letra y página. Luego quita el ruido:

- la cabecera "NOMBRE · Evaluación física dd/mm/aaaa", que es la línea de ese patrón que más se repite;
- los pies "KineReach · Documento confidencial…" y "Página N de M";
- las URL y los sellos de fecha que añade el navegador al imprimir.

Es un informe KineReach si una de las primeras 40 líneas es exactamente `KineReach`.

## Secciones

Cada sección empieza con tres líneas seguidas: el número de dos cifras, una etiqueta en mayúsculas y el título.

```
04
FUERZA ISOMÉTRICA
Dinamometría
```

`partir_secciones()` exige que los números vayan en orden (01, 02, 03…). Así ignora otros "01" que aparecen dentro del texto, como los puntos del cierre. La numeración cambia según los módulos medidos, así que el tipo se decide por la etiqueta (`tipo_seccion()`):

| Etiqueta | Lector |
|---|---|
| VISIÓN GENERAL | `p_vision`: resumen, contadores, alertas, autorreporte |
| ENCUADRE | `p_encuadre`: etiquetas en mayúsculas emparejadas en orden con los valores |
| BIOMÉTRICOS | `p_biometricos` |
| MOVILIDAD, FUERZA ISOMÉTRICA | `p_bilateral` (tarjetas) y `p_hq` |
| POTENCIA | `p_potencia`: saltos, drop jumps, CMJ/SJ |
| VELOCIDAD | `p_velocidad` |
| VBT | `p_vbt`: tabla de series y zonas |
| PLANIFICACIÓN | `p_plan`, que lee por posición |
| el resto | texto en párrafos (`parrafos()`) |

## Tarjetas bilaterales

```
Flexión de rodilla 45°          ← nombre
Diferencia alta · 18.8%         ← opcional
IZQ
35.1 kg
DER
28.5 kg
Fuerza relativa: IZQ 0.49 · DER 0.40 ×PC   ← opcional, solo dinamometría
```

Un nombre en mayúsculas seguido de un valor con unidad ("MID THIGH PULL / 128.2kg") es una medida sin lados y va a `otras_medidas`.

## Plan: columnas

En la página del plan, las coordenadas x típicas (A4 de 595 pt) son estas:

| Elemento | x | Tamaño |
|---|---|---|
| Cabecera de semana "Semana N" | 60 | 12 |
| Día (LUN, MAR…) y fecha | ~70 | 7.9 / 11.2 |
| Título y descripción del día | 114 | 11.2 / 9 |
| Bloque (MAYÚSCULAS) | 71 | 7.9 |
| Ejercicio | 71 | 9.4 |
| Indicaciones del ejercicio | 71 | 8.2 (más pequeño que el ejercicio) |
| "+1 serie IZQ/DER" | variable | 7.9 |
| Dosis "3 × 8 por lado" | 332 | 9 |
| Carga o nota | > 440 | 9 |

`p_plan()` no usa valores fijos. Deduce cada cosa así:
- la columna de la dosis, de la primera línea que empieza por "N ×";
- la columna derecha, de lo que queda a más de 60 pt a la derecha de la dosis;
- el tamaño del nombre del ejercicio, de la primera línea que sigue a cada bloque.

Las cabeceras de semana se repiten en cada página y se ignoran si el número de semana no cambia.

## Variantes conocidas

- **Chrome (Skia/PDF):** la maqueta de arriba. Es la más limpia.
- **Safari en iOS (Quartz PDFContext):** cada página impresa trae dos pies (el del informe y el del navegador). Los datos de la portada (edad, kg, cm) caen dentro de las alertas de la página 2, y `p_vision` los filtra.
- **KideoReach (análisis de vídeo):** otras secciones ("ANÁLISIS A · fecha"). Sale como texto.
- **Informes sin plan:** no tienen la sección PLANIFICACIÓN.

## Cuando aparezca un formato nuevo

1. Mira las líneas con su posición:
   ```bash
   python -c "import fitz,sys; d=fitz.open(sys.argv[1]); [print(round(s['size'],1), round(s['bbox'][0]), s['text']) for b in d[int(sys.argv[2])].get_text('dict')['blocks'] for l in b.get('lines',[]) for s in l['spans'] if s['text'].strip()]" informe.pdf 18
   ```
2. Ajusta el lector correspondiente.
3. Añade el caso a `tests/fabricar_demo.py`, con datos inventados, y su test.
