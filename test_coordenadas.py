from pathlib import Path

import fitz  # PyMuPDF


PDF_PATH = Path(__file__).resolve().parent / "Prueba.pdf"
TARGET_LABELS = ["Razón Social", "Persona Natural", "SI"]


def print_text_blocks(page: fitz.Page, labels: list[str], page_num: int) -> None:
    print(f"\n=== BUSQUEDA DE TEXTO (page.get_text('blocks')) | pagina={page_num} ===")
    blocks = page.get_text("blocks")
    for label in labels:
        found = False
        for block in blocks:
            x0, y0, x1, y1, text, *_ = block
            if label.lower() in (text or "").lower():
                print(
                    f"[blocks][pagina={page_num}] '{label}' -> x0={x0:.2f}, y0={y0:.2f}, "
                    f"x1={x1:.2f}, y1={y1:.2f}"
                )
                found = True
                break
        if not found:
            print(f"[blocks][pagina={page_num}] '{label}' -> NO ENCONTRADO")


def print_text_dict(page: fitz.Page, labels: list[str], page_num: int) -> None:
    print(f"\n=== BUSQUEDA DE TEXTO (page.get_text('dict')) | pagina={page_num} ===")
    text_dict = page.get_text("dict")
    for label in labels:
        found = False
        for block in text_dict.get("blocks", []):
            if "lines" not in block:
                continue
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    span_text = span.get("text", "")
                    if label.lower() in span_text.lower():
                        x0, y0, x1, y1 = span.get("bbox", (0, 0, 0, 0))
                        print(
                            f"[dict][pagina={page_num}] '{label}' -> x0={x0:.2f}, y0={y0:.2f}, "
                            f"x1={x1:.2f}, y1={y1:.2f}"
                        )
                        found = True
                        break
                if found:
                    break
            if found:
                break
        if not found:
            print(f"[dict][pagina={page_num}] '{label}' -> NO ENCONTRADO")


def print_drawings(page: fitz.Page, page_num: int) -> None:
    print(f"\n=== ELEMENTOS VECTORIALES (page.get_drawings()) | pagina={page_num} ===")
    drawings = page.get_drawings()
    rect_count = 0
    line_count = 0

    for idx, drawing in enumerate(drawings):
        drawing_rect = drawing.get("rect")
        items = drawing.get("items", [])
        for item in items:
            op = item[0]

            # Rectangulos (potenciales checkboxes vacios)
            if op == "re":
                rect = item[1]
                width = rect.width
                height = rect.height
                if width <= 25 and height <= 25:
                    rect_count += 1
                    print(
                        f"[rect {rect_count}][pagina={page_num}] draw#{idx} -> "
                        f"x0={rect.x0:.2f}, y0={rect.y0:.2f}, "
                        f"x1={rect.x1:.2f}, y1={rect.y1:.2f}, "
                        f"w={width:.2f}, h={height:.2f}"
                    )

            # Lineas (potenciales subrayados o campos horizontales)
            elif op == "l":
                p0 = item[1]
                p1 = item[2]
                if abs(p0.y - p1.y) <= 0.5:
                    line_count += 1
                    print(
                        f"[linea {line_count}][pagina={page_num}] draw#{idx} -> "
                        f"x0={p0.x:.2f}, y0={p0.y:.2f}, "
                        f"x1={p1.x:.2f}, y1={p1.y:.2f}, "
                        f"longitud={abs(p1.x - p0.x):.2f}"
                    )

        # Algunos dibujos traen bbox util aunque no tengan "re"/"l" directos
        if drawing_rect and rect_count < 5:
            pass

    print(f"\n[pagina={page_num}] Total rectangulos tipo checkbox detectados: {rect_count}")
    print(f"[pagina={page_num}] Total lineas horizontales detectadas: {line_count}")


def main() -> None:
    print(f"PDF: {PDF_PATH}")
    if not PDF_PATH.exists():
        raise FileNotFoundError(f"No se encontro el PDF en: {PDF_PATH}")

    doc = fitz.open(PDF_PATH)
    try:
        print(f"Paginas del documento: {doc.page_count}")
        for page_index in range(doc.page_count):
            page = doc[page_index]
            page_num = page_index + 1
            print("\n" + "=" * 70)
            print(f"Analizando pagina {page_num}...")
            print_text_blocks(page, TARGET_LABELS, page_num)
            print_text_dict(page, TARGET_LABELS, page_num)
            print_drawings(page, page_num)
    finally:
        doc.close()


if __name__ == "__main__":
    main()
