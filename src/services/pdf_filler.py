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
        if not field_id:
            return ""
        return str(field_id).strip().lower().replace(" ", "_").replace("-", "_")

    def _calcular_baseline(self, fy, fh, f_size):
        """Baseline centrada en el campo, con margen inferior."""
        y_baseline = fy + (fh / 2) + (f_size / 3)
        y_baseline = min(y_baseline, fy + fh - 1.0)
        return y_baseline

    def fill_page(self, page_num, fields, data, debug=True):
        if page_num >= len(self.doc):
            return

        page = self.doc[page_num]
        
        # --- DIAGNÓSTICO EN CONSOLA ---
        rotation = page.rotation
        rect = page.rect
        # La matriz de rotación inversa para alinear imagen (Gemini) con PDF (PyMuPDF)
        derot_matrix = page.derotation_matrix 

        logger.info(f"[PAGE {page_num}] Rot: {rotation}, Rect: {rect}, Crop: {page.cropbox}")

        scale_x = rect.width / 1000.0
        scale_y = rect.height / 1000.0
        
        normalized_data = {self._normalize_id(k): v for k, v in data.items()}

        for field in fields:
            fid = self._normalize_id(field.get("id", ""))
            value = normalized_data.get(fid)

            if value is None or str(value).strip().lower() in ["none", "null", ""]:
                continue

            try:
                # 1. Coordenadas y dimensiones visuales (escala 0-1000 -> tamaño visible)
                lx = float(field.get("x", 0)) * scale_x
                ly = float(field.get("y", 0)) * scale_y
                fw = float(field.get("w", 0)) * scale_x
                fh = float(field.get("h", 0)) * scale_y
                f_size = float(field.get("fontSize", 8))

                if fw < 1 or fh < 1:
                    continue

                # ==========================================
                # RAMA 1: CHECKBOXES Y MARCAS LÓGICAS
                # ==========================================
                tipo_campo = str(field.get("tipo", "")).lower()
                valor_str = str(value).strip().lower()

                if tipo_campo == "checkbox" or valor_str in ["x", "true", "si", "sí"]:
                    # Calculamos el centro visual
                    cx = lx + (fw / 2)
                    cy = ly + (fh / 2)
                    
                    # MAGIA MATRICIAL: Traducimos el punto visual al lienzo nativo
                    punto_check = fitz.Point(cx, cy) * derot_matrix
                    
                    # Dibujamos la 'X' usando la función dedicada
                    self._draw_mark(page, punto_check.x, punto_check.y, min(fw, fh))
                    continue

                # ==========================================
                # RAMA 2: INSERCIÓN DE TEXTO
                # ==========================================
                # Construimos la caja visual donde Gemini vio el espacio
                caja_visual = fitz.Rect(lx + 1.5, ly, lx + fw - 1.5, ly + fh)

                # MAGIA MATRICIAL: Traducimos la caja entera al espacio nativo del PDF
                caja_real = caja_visual * derot_matrix

                # Insertamos el texto
                page.insert_textbox(
                    caja_real,
                    str(value),
                    fontsize=f_size,
                    fontname="helv",
                    color=(0, 0, 0),
                    align=0,  # 0=Izquierda, 1=Centro, 2=Derecha
                    rotate=rotation  # Compensa la rotación para que se lea horizontalmente
                )

            except Exception as e:
                logger.error(f"Error en campo {fid}: {e}")
                continue
    def _draw_mark(self, page, x, y, size):
        """Dibuja una X centrada en el checkbox."""
        s = min(size * 0.3, 4.0)  # máximo 4pt para no desbordar
        page.draw_line((x - s, y - s), (x + s, y + s), color=(0, 0, 0), width=0.8)
        page.draw_line((x - s, y + s), (x + s, y - s), color=(0, 0, 0), width=0.8)

    def save(self, path_or_buffer):
        try:
            self.doc.save(path_or_buffer, garbage=3, deflate=True)
            self.doc.close()
            logger.info("PDF guardado correctamente.")
        except Exception as e:
            logger.error(f"Error al guardar: {e}")
            raise e
