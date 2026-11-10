"""Fabrica un PDF con la maqueta de un informe KineReach y datos INVENTADOS, para los tests.

No hay ningún informe real en este repositorio: los informes llevan datos de salud de personas,
muchas veces menores. Este PDF imita solo la disposición del texto (secciones numeradas,
tarjetas IZQ/DER, tablas y columnas del plan) y trae errores sembrados a propósito para que
procesar.py revisar los encuentre.

    python fabricar_demo.py salida.pdf
"""
import sys

import fitz

CAB = "ATLETA DEMO · Evaluación física 01/01/2027"

# (x, y, texto, tamaño). Cada página empieza en y=40; el pie se añade solo.
PAGINAS = [
    [(47, 40, "KR", 6.4), (65, 60, "KineReach", 9.8), (60, 120, "Informe de rendimiento", 10),
     (60, 140, "Evaluación física integral", 12), (60, 170, "ATLETA DEMO", 24),
     (60, 200, "Futbol · extremo · Sub15 · Club Demo", 10),
     (60, 240, "15", 18), (60, 260, "Años", 9), (140, 240, "60", 18), (140, 260, "kg", 9),
     (220, 240, "170", 18), (220, 260, "cm", 9), (300, 240, "20", 18), (300, 260, "Pruebas", 9),
     (60, 700, "01/01/2027 · Documento confidencial", 9)],
    [(45, 80, "01", 40), (105, 90, "VISIÓN GENERAL", 8.6), (105, 110, "Resumen de la evaluación", 22),
     (105, 140, "Evaluación de prueba con datos inventados. Muestra una diferencia alta entre", 10),
     (105, 155, "lados en la flexión de rodilla.", 10),
     (60, 190, "20", 18), (60, 210, "Pruebas registradas", 9), (200, 190, "3", 18), (200, 210, "Capacidades evaluadas", 9),
     (60, 240, "ALERTAS PRIORITARIAS", 8), (60, 255, "Asimetría bilateral > 15% en ROD. FLEXIÓN 90° (25%)", 9),
     (60, 268, "Evaluar causa. No progresar carga hasta clarificar.", 9),
     (60, 300, "ESTADO AL MOMENTO DE MEDIR · AUTORREPORTE 1–5", 8),
     (60, 315, "Sueño", 9), (60, 328, "4/5", 9), (120, 315, "Energía", 9), (120, 328, "2/5", 9),
     (180, 315, "Recuperación", 9), (180, 328, "3/5", 9), (260, 315, "Estrés", 9), (260, 328, "3/5", 9),
     (320, 315, "Fatiga", 9), (320, 328, "3/5", 9), (380, 315, "Dolor", 9), (380, 328, "1/5", 9),
     (45, 380, "02", 40), (105, 390, "ENCUADRE", 8.6), (105, 410, "Contexto de la evaluación", 22),
     (60, 440, "OBJETIVO", 8), (200, 440, "CARGA RECIENTE", 8), (60, 455, "inicio programa", 9),
     (200, 455, "descansado", 9), (60, 480, "ESTADO DE MEDICIÓN", 8), (60, 495, "optimo", 9),
     (45, 540, "03", 40), (105, 550, "BIOMÉTRICOS", 8.6), (105, 570, "Antropometría", 22),
     (60, 600, "60 kg", 14), (60, 618, "Peso", 9), (160, 600, "1.7 cm", 14), (160, 618, "Estatura", 9),
     (260, 600, "20.8", 14), (260, 618, "IMC", 9)],
    [(45, 80, "04", 40), (105, 90, "FUERZA ISOMÉTRICA", 8.6), (105, 110, "Dinamometría", 22),
     (60, 150, "RODILLA", 8), (60, 165, "Flexión de rodilla 90°", 9.4), (60, 178, "Diferencia alta · 25%", 8),
     (60, 191, "IZQ", 8), (60, 204, "15 kg", 10), (160, 191, "DER", 8), (160, 204, "20 kg", 10),
     (60, 217, "Fuerza relativa: IZQ 0.25 · DER 0.33 ×PC", 8),
     (60, 240, "Extensión de rodilla 60°", 9.4), (60, 253, "Diferencia baja · 5%", 8),
     (60, 266, "IZQ", 8), (60, 279, "40 kg", 10), (160, 266, "DER", 8), (160, 279, "38 kg", 10),
     (60, 292, "Fuerza relativa: IZQ 0.67 · DER 0.63 ×PC", 8),
     (60, 320, "GENERAL", 8), (60, 335, "Empuje horizontal", 9.4), (60, 348, "Diferencia baja · 6.3%", 8),
     (60, 361, "IZQ", 8), (60, 374, "75 kg", 10), (160, 361, "DER", 8), (160, 374, "80 kg", 10),
     (60, 400, "OTROS", 8), (60, 415, "EMPUJE HORIZONTAL", 9), (60, 428, "150kg", 10),
     (60, 460, "COCIENTE ISQUIOTIBIALES / CUÁDRICEPS · ISOMÉTRICO", 8),
     (60, 475, "IZQ", 8), (60, 488, "0.38", 12), (60, 501, "Flexión 15 kg ÷ extensión 40 kg (promedio de ángulos)", 8),
     (300, 475, "DER", 8), (300, 488, "0.53", 12), (300, 501, "Flexión 20 kg ÷ extensión 38 kg (promedio de ángulos)", 8),
     (60, 520, "Comparación interna entre lados y en el tiempo.", 7)],
    [(45, 80, "05", 40), (105, 90, "POTENCIA", 8.6), (105, 110, "Saltos y pliometría", 22),
     (60, 150, "CMJ", 10), (60, 163, "Cv alto", 8), (60, 180, "30 cm", 16), (60, 198, "Promedio 27 cm", 8),
     (60, 211, "CV 12%", 8), (60, 224, "Intentos 3", 8), (60, 237, "24", 8), (60, 250, "27", 8), (60, 263, "30", 8),
     (60, 276, "Protocolo: manos libres", 8),
     (60, 310, "DROP JUMP", 8), (60, 323, "Reactivo", 8), (60, 336, "1.5 RSI", 14), (60, 352, "Altura 24 cm", 8),
     (60, 365, "Contacto 160 ms", 8), (60, 378, "Caja 30 cm", 8), (60, 391, "Intentos 1", 8),
     (260, 310, "DROP JUMP", 8), (260, 323, "Reactivo", 8), (260, 336, "1.5 RSI", 14), (260, 352, "Altura 24 cm", 8),
     (260, 365, "Contacto 160 ms", 8), (260, 378, "Caja 45 cm", 8), (260, 391, "Intentos 1", 8),
     (45, 440, "06", 40), (105, 450, "VELOCIDAD", 8.6), (105, 470, "Sprint y cambio de dirección", 22),
     (60, 500, "CARRERA DE 20 M · TIEMPOS ACUMULADOS", 8), (60, 515, "INTENTO", 8), (140, 515, "10 M", 8),
     (220, 515, "20 M", 8), (60, 530, "1", 9), (140, 530, "2.00 s", 9), (220, 530, "3.40 s", 9),
     (60, 545, "2 MEJOR", 9), (140, 545, "1.95 s", 9), (220, 545, "3.30 s", 9)],
    [(45, 80, "07", 40), (105, 90, "VBT", 8.6), (105, 110, "Entrenamiento basado en velocidad", 22),
     (63, 150, "Trap Bar deadlift", 14), (480, 150, "3 series", 9),
     (60, 180, "SERIE", 8), (120, 180, "CARGA kg", 8), (200, 180, "REPS", 8), (240, 180, "V MEDIA m/s", 8),
     (310, 180, "MEJOR REP.", 8), (310, 192, "m/s", 8), (370, 180, "V PICO m/s", 8),
     (60, 210, "1", 9.8), (120, 210, "40", 9.8), (200, 210, "5", 9.8), (240, 210, "0.95", 9.8), (310, 210, "1.05", 9.8), (370, 210, "1.60", 9.8),
     (60, 230, "2", 9.8), (120, 230, "60", 9.8), (200, 230, "4", 9.8), (240, 230, "0.75", 9.8), (310, 230, "0.85", 9.8), (370, 230, "1.30", 9.8),
     (60, 250, "3", 9.8), (120, 250, "80", 9.8), (200, 250, "3", 9.8), (240, 250, "0.55", 9.8), (310, 250, "0.65", 9.8), (370, 250, "1.00", 9.8),
     (60, 290, "Fuerza acelerativa", 9), (60, 303, "85 kg", 9), (60, 316, "a 0.60 m/s", 8),
     (45, 360, "08", 40), (105, 370, "PLANIFICACIÓN", 8.6), (105, 390, "Plan de 6 semanas", 22),
     (60, 420, "Del 04/01/2027 al 14/02/2027. Contenido de prueba.", 9),
     (60, 445, "VELOCIDAD", 8), (160, 445, "CARGA", 8), (60, 460, "1.00 m/s", 9), (160, 460, "50 kg", 9)],
    [(60, 92, "Semana 1", 12), (400, 94, "Base · Carga", 9), (60, 124, "Aprender los patrones con volumen bajo.", 9.4),
     (73, 163, "LUN", 7.9), (67, 175, "04/01", 11.2), (114, 160, "Fuerza básica", 11.2),
     (114, 177, "Barra hexagonal guiada por velocidad.", 9), (504, 163, "50 min", 8.6),
     (71, 206, "FUERZA PRINCIPAL (VBT)", 7.9),
     (71, 227, "Peso muerto con barra hexagonal", 9.4), (71, 242, "VBT: mejor repetición 1.00 m/s. Cortar si baja de", 8.2),
     (71, 254, "0.90 m/s.", 8.2), (332, 228, "3 × 5", 9), (500, 228, "50 kg", 9),
     (71, 280, "UNILATERAL", 7.9),
     (71, 301, "Sentadilla búlgara", 9.4), (160, 302, "+1 serie IZQ", 7.9), (332, 302, "3 × 8 por lado", 9),
     (457, 302, "Mancuernas, RPE", 9), (521, 314, "7", 9),
     (71, 336, "Nordic curl (isquiotibiales)", 9.4), (332, 337, "2 × 4", 9),
     (73, 380, "MIÉ", 7.9), (67, 392, "06/01", 11.2), (114, 377, "Velocidad", 11.2),
     (114, 394, "Aceleración corta.", 9), (504, 380, "40 min", 8.6),
     (71, 420, "SPRINT", 7.9), (71, 441, "Sprint de aceleración", 9.4), (332, 442, "4 × 10 m", 9),
     (71, 466, "Empuje de trineo", 9.4), (332, 467, "3 × 10 m", 9), (457, 467, "Moderada: que no", 9),
     (457, 479, "se rompa la postura", 9)],
    [(60, 92, "Semana 2", 12), (400, 94, "Base · Carga", 9), (60, 124, "Más volumen.", 9.4),
     (73, 163, "LUN", 7.9), (67, 175, "11/01", 11.2), (114, 160, "Fuerza básica", 11.2),
     (114, 177, "Barra hexagonal guiada por velocidad.", 9), (504, 163, "50 min", 8.6),
     (71, 206, "FUERZA PRINCIPAL (VBT)", 7.9), (71, 227, "Peso muerto con barra hexagonal", 9.4),
     (332, 228, "4 × 5", 9), (500, 228, "95 kg", 9),
     (45, 300, "09", 40), (105, 310, "CIERRE", 8.6), (105, 330, "Plan de acción", 22),
     (60, 360, "Solo una carga evaluada en VBT; completar el perfil.", 9),
     (60, 375, "Reevaluar en 6 semanas.", 9)],
]


def fabricar(ruta):
    doc = fitz.open()
    total = len(PAGINAS)
    for n, lineas in enumerate(PAGINAS, 1):
        pag = doc.new_page(width=595, height=842)
        if n > 1:
            pag.insert_text((47, 40), "KR", fontsize=6.4)
            pag.insert_text((65, 40), "KineReach", fontsize=9.8)
            pag.insert_text((360, 40), CAB, fontsize=8.6)
        for x, y, texto, tam in lineas:
            pag.insert_text((x, y + tam), texto, fontsize=tam, fontname="helv")
        pag.insert_text((45, 815), "KineReach · Documento confidencial de uso clínico y deportivo", fontsize=7.9)
        pag.insert_text((500, 815), f"Página {n} de {total}", fontsize=7.9)
    doc.save(ruta)
    return ruta


if __name__ == "__main__":
    fabricar(sys.argv[1] if len(sys.argv) > 1 else "demo.pdf")
