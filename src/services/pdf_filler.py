import fitz
import logging

# Configuración básica de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("PDF_FILLER")

class PDFFormFiller:
    def __init__(self, pdf_path):
        """Inicializa el documento y configura márgenes."""
        try:
            self.doc = fitz.open(pdf_path)
            self.BOTTOM_MARGIN = 1.2 # Ajuste fino para que el texto descanse sobre la línea
        except Exception as e:
            logger.error(f"Error al abrir el PDF: {e}")
            raise e

    def _normalize_id(self, field_id):
        """Estandariza los IDs para coincidir con los datos de entrada."""
        if not field_id: return ""
        return str(field_id).strip().lower().replace(" ", "_").replace("-", "_")

    def fill_page(self, page_num, fields, data, debug=True):
        """Llena los campos detectados en la página especificada."""
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

            # MODO DEBUG: Dibuja los recuadros rojos vistos en tus logs
            if debug:
                rect_debug = fitz.Rect(fx, fy, fx + fw, fy + fh)
                page.draw_rect(rect_debug, color=(1, 0, 0), width=0.3, dashes=[1, 1])

            # Manejo de Checkboxes
            if field.get("tipo") == "checkbox" or str(value).lower() in ["x", "si", "sí", "true"]:
                cx, cy = fx + (fw / 2), fy + (fh / 2)
                self._draw_mark(page, cx, cy, min(fw, fh))
                continue

            # --- LÓGICA DE ALINEACIÓN SEGÚN TIPO DE CAMPO ---
            aspect_ratio = fw / fh if fh > 0 else 1
            
            if fh < 15:
                # Campos de fecha o muy cortos: anclaje casi al fondo
                y_baseline = fy + fh - 1.5 
            elif aspect_ratio > 3.0:
                # Campos largos (Razón Social): bajar texto al 85% de la caja
                y_baseline = fy + (fh * 0.85)
            else:
                # Tablas: forzar al borde inferior para evitar títulos grises
                y_baseline = (fy + fh) - self.BOTTOM_MARGIN

            page.insert_text(
                fitz.Point(fx + 1.5, y_baseline), 
                str(value),
                fontsize=f_size,
                fontname="helv",
                color=(0, 0, 0)
            )

    def _draw_mark(self, page, x, y, size):
        """Dibuja una marca X en las coordenadas indicadas."""
        s = size * 0.25
        page.draw_line((x-s, y-s), (x+s, y+s), color=(0,0,0), width=0.8)
        page.draw_line((x-s, y+s), (x+s, y-s), color=(0,0,0), width=0.8)

    def save(self, path_or_buffer):
        """Guarda el archivo y libera recursos."""
        try:
            self.doc.save(path_or_buffer, garbage=3, deflate=True)
            self.doc.close()
            logger.info("PDF procesado y guardado correctamente.")
        except Exception as e:
            logger.error(f"Error al guardar: {e}")
            raise e