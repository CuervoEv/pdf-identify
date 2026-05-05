import fitz
import json
from PIL import Image, ImageDraw

def detectar_escala_gemini(campos):
    """
    Detecta automáticamente si Gemini devolvió píxeles o escala 0-1000.
    Si el valor máximo supera 1000, son píxeles absolutos.
    """
    max_x = max((c["x"] + c.get("w", 0)) for c in campos)
    max_y = max((c["y"] + c.get("h", 0)) for c in campos)
    return max_x, max_y  # Si > 1000 → son px reales; si ≤ 1000 → escala normalizada

def generar_imagen_mapeada(pdf_original, archivo_json, imagen_salida, num_pagina=0, dpi=150):
    doc = fitz.open(pdf_original)
    pagina = doc[num_pagina]
    pix = pagina.get_pixmap(dpi=dpi)

    modo = "RGBA" if pix.alpha else "RGB"
    imagen = Image.frombytes(modo, [pix.width, pix.height], pix.samples)
    dibujo = ImageDraw.Draw(imagen)

    img_w, img_h = imagen.size
    print(f"📐 Imagen renderizada: {img_w} × {img_h} px")

    with open(archivo_json, "r", encoding="utf-8") as f:
        datos = json.load(f)

    campos = datos.get("fields", [])
    if not campos:
        print("❌ No hay campos en el JSON")
        return

    # Detectar qué escala usó Gemini
    max_x, max_y = detectar_escala_gemini(campos)
    print(f"🔍 Valor máximo detectado: x={max_x:.0f}, y={max_y:.0f}")

    if max_x > 1000 or max_y > 1000:
        # Gemini devolvió píxeles de la imagen que recibió
        div_x, div_y = max_x, max_y
        print(f"⚠️  Modo PÍXELES detectado → divisor: {div_x:.0f} × {div_y:.0f}")
    else:
        # Gemini obedeció la escala 0-1000
        div_x, div_y = 1000.0, 1000.0
        print("✅ Modo 0-1000 detectado")

    for campo in campos:
        x0 = (campo["x"] / div_x) * img_w
        y0 = (campo["y"] / div_y) * img_h
        w  = (campo["w"] / div_x) * img_w
        h  = (campo["h"] / div_y) * img_h
        x1, y1 = x0 + w, y0 + h

        color = (0, 180, 0) if campo.get("tipo") == "checkbox" else (220, 30, 30)
        dibujo.rectangle([x0, y0, x1, y1], outline=color, width=2)
        dibujo.text((x0 + 2, y0 + 1), campo.get("id", "?")[:15], fill=color)

    imagen.save(imagen_salida)
    doc.close()
    print(f"✅ Imagen guardada: {imagen_salida}")

generar_imagen_mapeada("Prueba.pdf", "mapa.txt", "Prueba_Mapeada.png", num_pagina=0)