import fitz
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("PDF_FILLER")

class PDFFormFiller:
    def __init__(self, pdf_path):
        self.doc = fitz.open(pdf_path)
        # Ajuste vertical global: empuja todo el texto ligeramente hacia arriba
        # desde la línea base para que no toque la raya del cuadro.
        self.BOTTOM_MARGIN = 2 

    def _normalize_id(self, field_id):
        if not field_id: return ""
        return str(field_id).strip().lower().replace(" ", "_").replace("-", "_")

    def fill_page(self, page_num, fields, data):
        if page_num >= len(self.doc): return
        page = self.doc[page_num]
        
        # Dimensiones de la página real
        page_w = page.rect.width
        page_h = page.rect.height
        
        # Gemini devuelve coordenadas normalizadas (0 a 1000). Calculamos factores.
        scale_x = page_w / 1000.0
        scale_y = page_h / 1000.0

        normalized_data = {self._normalize_id(k): v for k, v in data.items()}

        for field in fields:
            fid = self._normalize_id(field.get("id", ""))
            value = normalized_data.get(fid)

            # Si no hay valor o es nulo, saltamos
            if value is None or str(value).strip().lower() in ["none", "null", ""]:
                continue

            # Obtener coordenadas
            try:
                # box_2d viene usualmente como [ymin, xmin, ymax, xmax] de Gemini
                # Asegúrate de cómo tu parser convierte esto a x, y, w, h.
                # Asumiré que en tu 'field' ya tienes x, y, w, h procesados.
                
                fx = float(field.get("x", 0)) * scale_x
                fy = float(field.get("y", 0)) * scale_y
                fw = float(field.get("w", 0)) * scale_x
                fh = float(field.get("h", 0)) * scale_y
            except Exception:
                continue

            # Checkbox
            if field.get("tipo") == "checkbox" or str(value).lower() in ["x", "si", "sí", "true"]:
                # La X sí va centrada geométricamente
                cx = fx + (fw / 2)
                cy = fy + (fh / 2)
                self._draw_mark(page, cx, cy, min(fw, fh))
                continue

            # --- LÓGICA DE TEXTO DEFINITIVA: ANCLAJE INFERIOR ---
            # 1. Calculamos el tamaño de fuente dinámico basado en la altura del renglón.
            #    Usamos el 60% de la altura del cuadro, con un tope máximo de 9pt.
            calc_font_size = fh * 0.6
            font_size = min(max(calc_font_size, 5), 9) 

            # 2. Definimos la coordenada Y. 
            #    En lugar de (fy + fh/2) que es el centro, usamos la BASE del cuadro (fy + fh).
            #    Restamos un margen (BOTTOM_MARGIN) para que no pise la línea.
            y_base = (fy + fh) - self.BOTTOM_MARGIN
            
            # Ajuste de seguridad: Si Gemini detectó el encabezado, el cuadro es muy alto.
            # Forzamos que el texto vaya al tercio inferior.
            if fh > 18: 
                y_base = (fy + fh) - 3

            # 3. Escribimos
            page.insert_text(
                fitz.Point(fx + 2, y_base), # fx + 2 da un pequeño margen izquierdo
                str(value),
                fontsize=font_size,
                fontname="helv",
                color=(0, 0, 0)
            )

    def _draw_mark(self, page, x, y, size):
        # Dibuja una X limpia
        s = size * 0.25
        page.draw_line((x-s, y-s), (x+s, y+s), color=(0,0,0), width=1)
        page.draw_line((x-s, y+s), (x+s, y-s), color=(0,0,0), width=1)

    def save(self, path_or_buffer):
        self.doc.save(path_or_buffer)
        self.doc.close()
        