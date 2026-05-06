import fitz
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("PDF_FILLER")

class PDFFormFiller:
    def __init__(self, pdf_path):
        try:
            self.doc = fitz.open(pdf_path)
        except Exception as e:
            logger.error(f"Error al abrir el PDF: {e}")
            raise e

    def _normalize_id(self, field_id):
        if not field_id: return ""
        return str(field_id).strip().lower().replace(" ", "_").replace("-", "_")

    def _calcular_baseline(self, fy, fh, f_size):
        """
        Calcula la línea base tipográfica correcta.
        
        En PyMuPDF, insert_text usa la línea base (baseline) como punto Y.
        El texto visible ocupa aproximadamente:
          - 70% del fontSize ENCIMA de la baseline (ascendentes)
          - 30% del fontSize DEBAJO de la baseline (descendentes)
        
        Queremos que el texto quede CENTRADO verticalmente dentro del campo,
        ligeramente bajado para que visualmente descanse sobre la línea.
        """
        # Centro vertical del campo
        centro = fy + (fh / 2)
        # La baseline va al 60% del campo para que el texto quede centrado visualmente
        # (el ojo percibe el texto más centrado cuando la baseline está ligeramente abajo del centro)
        baseline = fy + (fh * 0.72)
        
        # Seguridad: nunca salir del campo
        baseline = min(baseline, fy + fh - 1.0)
        baseline = max(baseline, fy + f_size * 0.7)
        
        return baseline

    def fill_page(self, page_num, fields, data, debug=True):
        if page_num >= len(self.doc):
            return

        page = self.doc[page_num]
        scale_x = page.rect.width / 1000.0
        scale_y = page.rect.height / 1000.0
        normalized_data = {self._normalize_id(k): v for k, v in data.items()}

        for field in fields:
            fid = self._normalize_id(field.get("id", ""))
            value = normalized_data.get(fid)

            if value is None or str(value).strip().lower() in ["none", "null", ""]:
                continue

            try:
                fx = float(field.get("x", 0)) * scale_x
                fy = float(field.get("y", 0)) * scale_y
                fw = float(field.get("w", 0)) * scale_x
                fh = float(field.get("h", 0)) * scale_y
                f_size = float(field.get("fontSize", 8))
            except (ValueError, TypeError):
                continue

            # Ignorar campos que Gemini no encontró (w=0 o h=0)
            if fw < 1 or fh < 1:
                logger.warning(f"Campo '{fid}' ignorado: dimensiones inválidas w={fw} h={fh}")
                continue

            # MODO DEBUG: dos puntos rojos como anclas visuales
            if debug:
                r1 = fitz.Rect(fx - 1.5, fy - 1.5, fx + 1.5, fy + 1.5)
                r2 = fitz.Rect(fx + fw - 1.5, fy - 1.5, fx + fw + 1.5, fy + 1.5)
                page.draw_oval(r1, color=(1, 0, 0), fill=(1, 0, 0))
                page.draw_oval(r2, color=(1, 0, 0), fill=(1, 0, 0))

            # CHECKBOXES
            if field.get("tipo") == "checkbox" or str(value).lower() in ["x", "si", "sí", "true"]:
                cx = fx + (fw / 2)
                cy = fy + (fh / 2)
                self._draw_mark(page, cx, cy, min(fw, fh))
                continue

            # TEXTO — baseline calculada correctamente
            y_baseline = self._calcular_baseline(fy, fh, f_size)

            page.insert_text(
                fitz.Point(fx + 1.5, y_baseline),
                str(value),
                fontsize=f_size,
                fontname="helv",
                color=(0, 0, 0)
            )

    def _draw_mark(self, page, x, y, size):
        """Dibuja una X centrada en el checkbox."""
        s = min(size * 0.3, 4.0)  # máximo 4pt para no desbordar
        page.draw_line((x-s, y-s), (x+s, y+s), color=(0, 0, 0), width=0.8)
        page.draw_line((x-s, y+s), (x+s, y-s), color=(0, 0, 0), width=0.8)

    def save(self, path_or_buffer):
        try:
            self.doc.save(path_or_buffer, garbage=3, deflate=True)
            self.doc.close()
            logger.info("PDF guardado correctamente.")
        except Exception as e:
            logger.error(f"Error al guardar: {e}")
            raise e