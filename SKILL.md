---
name: evskill
description: EvSkill convierte informes de evaluación física KineReach (PDF) a Markdown y JSON, y luego los procesa. Revisa incoherencias del informe, saca el perfil carga-velocidad del VBT, pasa el plan de entrenamiento de 6 semanas a CSV y compara una evaluación con su reevaluación. Úsala siempre que haya que leer, resumir, verificar o usar los datos de un PDF de KineReach o KideoReach, aunque el usuario solo diga "mira esta evaluación", "pásame el informe a texto", "qué trae el programa del PDF", "compara con la evaluación anterior" o quiera programar a partir de un informe. No la uses para PDF que no sean de KineReach ni para escribir un programa desde cero sin informe.
---

# EvSkill

La guía completa está en `README.md`, en la sección "Para la IA", en esta misma carpeta. Este es el resumen operativo.

1. **No leas el PDF.** Convierte, revisa y exporta el plan con un solo comando:
   ```bash
   python <carpeta-de-esta-skill>/evskill.py todo "informe.pdf" --salida <carpeta de trabajo local>
   ```
   Necesita PyMuPDF: `pip install pymupdf`.

2. **Lee `<nombre>.md`.** Trae el informe en tablas y el plan día a día. Si una sección sale en `sin_reconocer`, búscala en el `.txt`.

3. **Lee `<nombre>.revision.md`.**
   - Cuenta los avisos al usuario en el chat, como preguntas para quien evaluó.
   - No corrijas datos en silencio.
   - No pongas la revisión en un entregable.
   - Qué significa cada aviso: `docs/revisiones.md`.

4. **Calcula desde el JSON**, con `docs/esquema-json.md` como guía, o con los subcomandos:
   - `evskill.py vbt <json> -v 1.0 0.8`: kilos para cada velocidad de barra. Usa la mejor repetición, igual que KineReach; `--media` usa la velocidad media.
   - `evskill.py csv <json>`: el plan en CSV.
   - `evskill.py comparar antes.json despues.json`: la evolución entre dos evaluaciones.

5. **Pregunta lo que el informe no trae**, si importa: pierna dominante, protocolo de los tests, calendario y lesiones previas.

Son datos de salud, muchas veces de menores. Las salidas se quedan en local: no las subas a servicios externos ni a repositorios.

Si el conversor falla con un formato nuevo, lee `docs/formato-kinereach.md`.
