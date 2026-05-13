import fitz
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw

SCRIPT_DIR = Path(__file__).resolve().parent
TEMP_DIR = SCRIPT_DIR / "temp"

PDFS = {
    1: SCRIPT_DIR / "Prueba-1.pdf",
    2: SCRIPT_DIR / "Prueba-2.pdf",
    3: SCRIPT_DIR / "Prueba-3.pdf",
}


def detectar_escala_gemini(campos):
    """
    Detecta automáticamente si Gemini devolvió píxeles o escala 0-1000.
    Si el valor máximo supera 1000, se asume espacio en píxeles del raster de página.
    """
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


def generar_imagen_mapeada(pdf_original, archivo_json, imagen_salida, num_pagina=0, dpi=150):
    doc = fitz.open(pdf_original)
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

    # Detectar qué escala usó Gemini
    max_x, max_y = detectar_escala_gemini(campos)
    print(f"🔍 Valor máximo detectado: x={max_x:.0f}, y={max_y:.0f}")

    if max_x > 1000 or max_y > 1000:
        # Coordenadas en píxeles del mismo tamaño de página que esta imagen
        div_x, div_y = float(img_w), float(img_h)
        print(f"⚠️  Modo PÍXELES detectado → divisores: {div_x:.0f} × {div_y:.0f} (tamaño imagen)")
    else:
        # Escala normalizada 0-1000 del pipeline
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
    """
    Cada PDF de prueba es de una sola página física.
    La opción N enlaza Prueba-N.pdf con temp/gemini_response_page_N.json
    (mapeo generado para esa «página» en el pipeline, no hojas extra en el PDF).
    Siempre se renderiza la única página del PDF (índice 0) con las coords del JSON elegido.
    """
    print("\n=== Elegir visualización (1 = PDF + JSON mismo índice) ===")
    for k, p in PDFS.items():
        existe_pdf = p.is_file()
        json_path = TEMP_DIR / f"gemini_response_page_{k}.json"
        existe_json = json_path.is_file()
        estado_pdf = "✓" if existe_pdf else "(falta PDF)"
        estado_json = "✓" if existe_json else "(falta JSON)"
        print(
            f"  {k}) {p.name}  {estado_pdf}  +  temp/gemini_response_page_{k}.json  {estado_json}"
        )

    raw = input("\nElige (1, 2 o 3): ").strip()
    if raw not in ("1", "2", "3"):
        print("❌ Opción inválida. Debe ser 1, 2 o 3.")
        sys.exit(1)
    n = int(raw)
    pdf_path = PDFS[n]
    json_path = TEMP_DIR / f"gemini_response_page_{n}.json"

    if not pdf_path.is_file():
        print(f"❌ No existe el archivo: {pdf_path}")
        sys.exit(1)
    if not json_path.is_file():
        print(f"❌ No existe el archivo: {json_path}")
        sys.exit(1)

    doc = fitz.open(pdf_path)
    n_pages = len(doc)
    doc.close()
    if n_pages < 1:
        print("❌ El PDF no tiene páginas.")
        sys.exit(1)

    # PDFs de una sola página: siempre la primera hoja; el JSON trae coords de esa vista.
    num_pagina_pdf = 0

    salida = SCRIPT_DIR / f"{pdf_path.stem}_mapeada_page{n}.png"
    print(f"\n📄 PDF (página renderizada: 1 de {n_pages}): {pdf_path.name}")
    print(f"📋 JSON (página lógica {n}): {json_path.relative_to(SCRIPT_DIR)}")
    print(f"🖼️  Salida: {salida.name}\n")

    generar_imagen_mapeada(
        str(pdf_path),
        str(json_path),
        str(salida),
        num_pagina=num_pagina_pdf,
    )


if __name__ == "__main__":
    main()
