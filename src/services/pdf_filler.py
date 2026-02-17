import fitz
from config import settings

class PDFFormFiller:
    def __init__(self, pdf_path):
        self.doc = fitz.open(pdf_path)
        self.scale_x = None
        self.scale_y = None
        # CALIBRACIÓN: -2 o -3 suele ser el punto dulce para subir el texto
        self.Y_TWEAK = -2 

    def _normalize_id(self, field_id):
        if not field_id: return ""
        return str(field_id).strip().lower().replace(" ", "_").replace("-", "_")

    def fill_page(self, page_num, fields, data):
        if page_num >= len(self.doc): return
        page = self.doc[page_num]
        
        if self.scale_x is None or self.scale_y is None:
            width, height = page.rect.width, page.rect.height
            self.scale_x = width / 1000.0
            self.scale_y = height / 1000.0

        normalized_data = {self._normalize_id(k): v for k, v in data.items()}

        for field in fields:
            fid = self._normalize_id(field.get("id", ""))
            value = normalized_data.get(fid)
            
            if value is None or str(value).strip().lower() in ["none", "null", ""]:
                continue

            # 1. Coordenadas base escaladas
            x_pdf = (float(field.get("x", 0)) * self.scale_x) + 3 # +3 de margen izquierdo
            y_top = (float(field.get("y", 0)) * self.scale_y)
            h_pdf = float(field.get("h", 15)) * self.scale_y
            w_pdf = float(field.get("w", 20)) * self.scale_x

            is_checkbox = field.get("tipo") == "checkbox" or str(value).lower() in ["x", "1", "si", "sí", "true"]

            if is_checkbox:
                # Centro exacto para la X
                self._draw_mark(page, x_pdf + (w_pdf/2) - 3, y_top + (h_pdf/2), w_pdf, h_pdf)
            else:
                # 2. CÁLCULO DE PRECISIÓN VERTICAL
                # En lugar de usar un porcentaje fijo, calculamos el baseline
                # para que el texto quede centrado verticalmente.
                f_size = float(field.get("fontSize", 9))
                
                # Fórmula: Top + (Altura del cuadro / 2) + (Tamaño fuente / 3) + Ajuste Global
                # Esto sitúa la base de la letra justo donde debe estar para que se vea centrada.
                y_baseline = y_top + (h_pdf / 2) + (f_size / 3) + self.Y_TWEAK

                self._draw_text(page, x_pdf, y_baseline, str(value), f_size)

    def _draw_text(self, page, x, y, text, font_size):
        """Dibuja el texto de forma directa y visible."""
        page.insert_text(
            fitz.Point(x, y),
            text,
            fontsize=font_size,
            fontname="helv",
            color=(0, 0, 0),
            overlay=True # Asegura que el texto esté por encima de cualquier capa
        )

    def _draw_mark(self, page, x, y, w, h):
        """Dibuja una X centrada."""
        size = min(w, h) * 0.35
        page.draw_line((x - size, y - size), (x + size, y + size), color=(0,0,0), width=1.3)
        page.draw_line((x - size, y + size), (x + size, y - size), color=(0,0,0), width=1.3)

    def save(self, path_or_buffer):
        self.doc.save(path_or_buffer, garbage=3, deflate=True, clean=True)
        self.doc.close()
        