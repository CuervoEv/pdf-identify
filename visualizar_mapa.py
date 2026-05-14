import fitz
import json
import sys
from pathlib import Path
from PIL import Image, ImageDraw

SCRIPT_DIR = Path(__file__).resolve().parent
TEMP_DIR = SCRIPT_DIR / "temp"


def detectar_escala_gemini(campos):
    derechas = []
    bajos = []
    for c in campos:
        try:
            x = float(c.get("x", 0))
            y = float(c.get("y", 0))
            w = float(c.get("w", 0))
            h = float(c.get("h", 0))
        except (TypeError, ValueError):
            continue
        derechas.append(x + w)
        bajos.append(y + h)
    if not derechas or not bajos:
        return 1000.0, 1000.0
    return max(derechas), max(bajos)


def generar_imagen_mapeada(pdf_path, archivo_json, imagen_salida, num_pagina=0, dpi=150):
    doc = fitz.open(pdf_path)
    
    if num_pagina >= len(doc):
        print(f"❌ El PDF solo tiene {len(doc)} páginas. No existe la página {num_pagina + 1}.")
        doc.close()
        return
    
    pagina = doc[num_pagina]
    pix = pagina.get_pixmap(dpi=dpi)

    modo = "RGBA" if pix.alpha else "RGB"
    imagen = Image.frombytes(modo, [pix.width, pix.height], pix.samples)
    dibujo = ImageDraw.Draw(imagen)

    img_w, img_h = imagen.size
    print(f"📐 Imagen renderizada: {img_w} × {img_h} px")

    raw = Path(archivo_json).read_text(encoding="utf-8").strip()
    if not raw:
        print(f"❌ El JSON está vacío: {archivo_json}")
        doc.close()
        return
    try:
        datos = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"❌ JSON inválido en {archivo_json}: {e}")
        doc.close()
        return

    campos = datos.get("fields", [])
    if not campos:
        print("❌ No hay campos en el JSON")
        doc.close()
        return

    max_x, max_y = detectar_escala_gemini(campos)
    print(f"🔍 Valor máximo detectado: x={max_x:.0f}, y={max_y:.0f}")

    if max_x > 1000 or max_y > 1000:
        div_x, div_y = float(img_w), float(img_h)
        print(f"⚠️  Modo PÍXELES detectado → divisores: {div_x:.0f} × {div_y:.0f}")
    else:
        div_x, div_y = 1000.0, 1000.0
        print("✅ Modo 0-1000 detectado")

    for campo in campos:
        try:
            cx = float(campo.get("x", 0))
            cy = float(campo.get("y", 0))
            cw = float(campo.get("w", 0))
            ch = float(campo.get("h", 0))
        except (TypeError, ValueError):
            continue
        if cw <= 0 or ch <= 0:
            continue
        x0 = (cx / div_x) * img_w
        y0 = (cy / div_y) * img_h
        w = (cw / div_x) * img_w
        h = (ch / div_y) * img_h
        x1, y1 = x0 + w, y0 + h

        color = (0, 180, 0) if campo.get("tipo") == "checkbox" else (220, 30, 30)
        dibujo.rectangle([x0, y0, x1, y1], outline=color, width=2)
        dibujo.text((x0 + 2, y0 + 1), campo.get("id", "?")[:15], fill=color)

    imagen.save(imagen_salida)
    doc.close()
    print(f"✅ Imagen guardada: {imagen_salida}")


def main():
    print("\n=== VISUALIZADOR DE COORDENADAS ===")
    
    # Pedir nombre del PDF
    nombre_pdf = input("Nombre del PDF (ej: prueba-1.pdf): ").strip()
    pdf_path = SCRIPT_DIR / nombre_pdf
    
    if not pdf_path.is_file():
        print(f"❌ No existe: {pdf_path}")
        sys.exit(1)
    
    doc = fitz.open(pdf_path)
    total_paginas = len(doc)
    doc.close()
    
    print(f"📄 PDF: {pdf_path.name} ({total_paginas} páginas)")
    
    # Pedir número de página
    try:
        num_pagina = int(input(f"Número de página (1-{total_paginas}): ").strip())
    except ValueError:
        print("❌ Debe ser un número.")
        sys.exit(1)
    
    if num_pagina < 1 or num_pagina > total_paginas:
        print(f"❌ La página debe estar entre 1 y {total_paginas}.")
        sys.exit(1)
    
    # El JSON mantiene relación con el número de página
    json_path = TEMP_DIR / f"gemini_response_page_{num_pagina}.json"
    
    if not json_path.is_file():
        print(f"❌ No existe el JSON: {json_path}")
        print("   Asegúrate de haber ejecutado /get-map para esta página.")
        sys.exit(1)
    
    # Salida
    salida = SCRIPT_DIR / f"{pdf_path.stem}_mapeada_pagina{num_pagina}.png"
    
    print(f"\n📋 JSON: {json_path.name}")
    print(f"🖼️  Salida: {salida.name}\n")
    
    generar_imagen_mapeada(
        str(pdf_path),
        str(json_path),
        str(salida),
        num_pagina=num_pagina - 1,  # base 0
    )


if __name__ == "__main__":
    main()