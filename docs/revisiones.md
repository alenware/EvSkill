# Qué revisa `revisar` y qué hacer con cada aviso

`python evskill.py revisar informe.json` (y también `todo`) escribe `<nombre>.revision.md`, con los avisos agrupados por categoría.

**Regla general:** un aviso es una **pregunta para quien evaluó**, no una corrección.

- Cuéntaselo al usuario en el chat.
- No cambies el dato en silencio.
- No metas la revisión en un documento para el atleta o el club.
- Si hay que trabajar con un dato dudoso, di cuál usas y por qué.

| Categoría | Qué detecta | Qué hacer |
|---|---|---|
| Biométricos | Estatura < 100 "cm": está en metros. IMC que no cuadra con peso y estatura | Usa la estatura que sale del IMC y dilo |
| Autorreporte | Energía ≤ 2 con estado "óptimo". Dolor 5/5 con 0 pruebas con dolor (escala invertida). Todos los ítems iguales (sin rellenar) | Pregunta el estado real. No asumas el sentido de la escala de dolor |
| Diferencias entre lados | La % del informe no coincide con la recalculada | Usa `diferencia_pct` (la recalculada) |
| Fuerza relativa | ×PC que no coincide con kg ÷ peso | Recalcula con el peso del informe |
| Sumas | Un total ("Empuje horizontal 129 kg") ≠ izq + der | Pregunta cuál es el valor bueno |
| Cociente H/Q | El cociente no sale de los kilos que el propio informe da | Recalcula |
| Saltos | Mejor o promedio mal copiados; CV mal calculado; **CV > 10 %** (gesto inconsistente); CMJ < SJ | Con CV alto, toma el valor con cautela y propón repetir el test |
| Drop jump | RSI ≠ altura ÷ contacto (suele ser una etiqueta equivocada); dos cajas con datos idénticos (duplicado); cajas sin intentos | No uses los duplicados para elegir la altura de caja |
| Sprint | Intento "mejor" mal marcado; parcial que no aumenta; tramo > 9,5 m/s pasados los 10 m (poco creíble); tramo mucho más lento que el anterior (fotocélula) | Usa solo los tramos creíbles; propón repetir el test |
| VBT | Una sola carga (no hay perfil); el análisis dice "una carga" y la tabla trae varias; la velocidad sube con la carga; r < 0,9; zonas o cargas del plan que no salen de ninguna recta | Los kilos estimados se usan con cautela. KineReach calcula con la mejor repetición |
| Plan | Ejercicio sin dosis; carga del plan por encima de la máxima medida | Señálalo antes de cargar el plan en otra aplicación |
| Conversión | Secciones que no se pudieron leer | Lee esa parte en el `.txt` |

## Lo que el script no puede comprobar (pregúntalo si importa)

- **Pierna dominante.** Casi nunca viene en el informe, y cambia cómo se lee una asimetría.
- **Protocolo.** Tipo de salida del sprint, encoder del VBT y si los saltos son con manos libres.
- **Calendario.** Días de partido y días disponibles. No lo supongas: el plan de KineReach suele asumir partido el fin de semana.
- **Historial de lesiones.** Una asimetría con lesión previa se lee distinto.
