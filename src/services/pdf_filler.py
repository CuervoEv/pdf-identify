"""
Rellenador de PDFs: AcroForm nativo + overlay para planos.

Mejoras alineadas con el documento de investigación:
- Detecta si el PDF es AcroForm (doc.is_form_pdf) y ofrece fill_acroform() para
  rellenar widgets nativos (texto, checkboxes, combos) con widget.field_value.
- El método fill_page (overlay) usa insert_textbox con tamaño de fuente detectado.
- Se añade un método fill_pdf() unificado que decide la estrategia según el tipo.
- Se conserva la lógica de rotación (derotation_matrix) y el dibujo de marcas.
- Nuevo: detección automática de tamaño de fuente (detect_font_size + get_scaled_dimensions).
"""

import fitz
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("PDF_FILLER")


class PDFFormFiller:
    def __init__(self, pdf_path_or_bytes, from_bytes=False):
        """
        Args:
            pdf_path_or_bytes: ruta del archivo o bytes del PDF.
            from_bytes: True si se pasan bytes en lugar de ruta.
        """
        try:
            if from_bytes:
                self.doc = fitz.open(stream=pdf_path_or_bytes, filetype="pdf")
            else:
                self.doc = fitz.open(pdf_path_or_bytes)
            self.is_acroform = self.doc.is_form_pdf
            if self.is_acroform:
                logger.info("PDF AcroForm detectado. Se usará relleno nativo si se solicita.")
            else:
                logger.info("PDF plano. Se usará overlay para el relleno.")
        except Exception as e:
            logger.error(f"Error al abrir el PDF: {e}")
            raise e

    def _normalize_id(self, field_id):
        if not field_id:
            return ""
        return str(field_id).strip().lower().replace(" ", "_").replace("-", "_")

    # ------------------------------------------------------------------
    # DETECCIÓN DE TAMAÑO DE FUENTE
    # ------------------------------------------------------------------

    def detect_font_size(self, page_num: int = 0) -> float:
        """
        Detecta el tamaño de fuente predominante en el PDF.
        
        Estrategia (en orden):
        1. Extraer texto con PyMuPDF y medir alturas reales de glyphs.
        2. Si no hay texto → estimar por dimensiones de la página.
        3. Si falla → devolver 9 (default seguro).
        
        Returns:
            float: tamaño de fuente estimado en puntos.
        """
        if page_num >= len(self.doc):
            return 9.0
        
        page = self.doc[page_num]
        
        # Método 1: Extraer spans con tamaño de fuente explícito
        try:
            blocks = page.get_text("dict", flags=fitz.TEXTFLAGS_TEXT)["blocks"]
            font_sizes = []
            
            for block in blocks:
                if "lines" not in block:
                    continue
                for line in block["lines"]:
                    for span in line["spans"]:
                        size = span.get("size", 0)
                        text = span.get("text", "").strip()
                        if size > 0 and len(text) > 1:
                            font_sizes.append(size)
            
            if font_sizes:
                font_sizes.sort()
                median_size = font_sizes[len(font_sizes) // 2]
                logger.info(f"[Font Detection] Mediana de {len(font_sizes)} spans: {median_size:.1f}pt")
                return round(median_size, 1)
        except Exception as e:
            logger.warning(f"[Font Detection] Falló extracción por dict: {e}")
        
        # Método 2: Calcular altura de texto desde "words"
        try:
            words = page.get_text("words")
            heights = []
            
            for w in words:
                if len(w) >= 5:
                    y0, y1 = w[1], w[3]
                    h = y1 - y0
                    if 2 < h < 50:
                        heights.append(h)
            
            if heights:
                heights.sort()
                median_h = heights[len(heights) // 2]
                estimated_size = round(median_h / 1.2, 1)
                logger.info(f"[Font Detection] Estimado por altura de bbox: {estimated_size:.1f}pt")
                return estimated_size
        except Exception as e:
            logger.warning(f"[Font Detection] Falló extracción por words: {e}")
        
        # Método 3: Estimar por dimensiones de página
        try:
            rect = page.rect
            page_height_mm = rect.height * 25.4 / 72
            
            if page_height_mm > 250:
                estimated_size = 10.0
            elif page_height_mm > 200:
                estimated_size = 9.5
            else:
                estimated_size = 8.0
            
            logger.info(f"[Font Detection] Estimado por página ({page_height_mm:.0f}mm): {estimated_size:.1f}pt")
            return estimated_size
        except Exception as e:
            logger.warning(f"[Font Detection] Falló estimación por página: {e}")
        
        logger.info("[Font Detection] Usando default: 9.0pt")
        return 9.0

    def get_scaled_dimensions(self, page_num: int = 0, base_font_size: float = None) -> dict:
        """
        Calcula dimensiones escaladas para checkboxes y campos de texto.
        """
        if base_font_size is None:
            base_font_size = self.detect_font_size(page_num)
        
        scale = base_font_size / 9.0
        
        return {
            "detected_font_size": base_font_size,
            "scale_factor": round(scale, 2),
            "checkbox_size": max(10, min(22, 14 * scale)),
            "text_margin": 1.5 * scale,
            "field_height_min": max(8, 12 * scale),
            "font_size_overlay": base_font_size,
        }

    # ------------------------------------------------------------------
    # RELLENO NATIVO DE ACROFORM
    # ------------------------------------------------------------------

    def fill_acroform(self, field_values: dict):
        if not self.is_acroform:
            logger.warning("fill_acroform llamado en PDF no AcroForm.")
            return

        for page in self.doc:
            for widget in page.widgets() or []:
                field_name = widget.field_name
                if field_name not in field_values:
                    continue
                value = field_values[field_name]
                try:
                    if widget.field_type_string == "CheckBox":
                        if isinstance(value, bool):
                            widget.field_value = value
                        elif str(value).lower() in ("true", "si", "sí", "x", "1", "yes", "on"):
                            widget.field_value = True
                        else:
                            widget.field_value = False
                    elif widget.field_type_string in ("RadioButton", "ListBox", "ComboBox"):
                        widget.field_value = str(value)
                    else:
                        widget.field_value = str(value)
                    widget.update()
                except Exception as e:
                    logger.error(f"Error rellenando widget {field_name}: {e}")

        self.doc.need_appearances(True)

    def get_acroform_fields(self) -> list:
        campos = []
        for page_index, page in enumerate(self.doc):
            for w in page.widgets() or []:
                campos.append({
                    "page": page_index,
                    "field_name": w.field_name,
                    "field_label": w.field_label or w.field_name,
                    "field_type": w.field_type_string,
                    "rect": list(w.rect),
                    "current_value": w.field_value,
                    "choices": w.choice_values,
                })
        return campos

    # ------------------------------------------------------------------
    # OVERLAY PARA PDFs PLANOS
    # ------------------------------------------------------------------

    def fill_page(self, page_num, fields, data, debug=True):
        if page_num >= len(self.doc):
            return

        page = self.doc[page_num]
        rotation = page.rotation
        rect = page.rect
        derot_matrix = page.derotation_matrix

        dims = self.get_scaled_dimensions(page_num)
        font_size_detected = dims["font_size_overlay"]
        logger.info(f"[PAGE {page_num}] Font size: {font_size_detected:.1f}pt, Scale: {dims['scale_factor']}")

        scale_x = rect.width / 1000.0
        scale_y = rect.height / 1000.0

        normalized_data = {self._normalize_id(k): v for k, v in data.items()}

        for field in fields:
            fid = self._normalize_id(field.get("id", ""))
            value = normalized_data.get(fid)
            if value is None or str(value).strip().lower() in ["none", "null", ""]:
                continue

            try:
                lx = float(field.get("x", 0)) * scale_x
                ly = float(field.get("y", 0)) * scale_y
                fw = float(field.get("w", 0)) * scale_x
                fh = float(field.get("h", 0)) * scale_y
                f_size = float(field.get("fontSize", font_size_detected))

                if fw < 1 or fh < 1:
                    continue

                tipo_campo = str(field.get("tipo", "")).lower()
                valor_str = str(value).strip().lower()

                if tipo_campo == "checkbox" or valor_str in ["x", "true", "si", "sí"]:
                    cx = lx + (fw / 2)
                    cy = ly + (fh / 2)
                    punto_check = fitz.Point(cx, cy) * derot_matrix
                    checkbox_size = min(fw, fh, dims["checkbox_size"])
                    self._draw_mark(page, punto_check.x, punto_check.y, checkbox_size)
                    continue

                caja_visual = fitz.Rect(
                    lx + dims["text_margin"],
                    ly,
                    lx + fw - dims["text_margin"],
                    ly + fh
                )
                caja_real = caja_visual * derot_matrix

                page.insert_textbox(
                    caja_real,
                    str(value),
                    fontsize=f_size,
                    fontname="helv",
                    color=(0, 0, 0),
                    align=0,
                )

            except Exception as e:
                logger.error(f"Error en campo {fid}: {e}")
                continue

    def _draw_mark(self, page, x, y, size):
        s = min(size * 0.3, 4.0)
        page.draw_line((x - s, y - s), (x + s, y + s), color=(0, 0, 0), width=0.8)
        page.draw_line((x - s, y + s), (x + s, y - s), color=(0, 0, 0), width=0.8)

    # ------------------------------------------------------------------
    # MÉTODO UNIFICADO DE RELLENO
    # ------------------------------------------------------------------

    def fill_pdf(self, mapped_fields: list, page_mode="overlay"):
        if page_mode == "acroform" or (page_mode is None and self.is_acroform):
            values = {f.get("field_name", f.get("field_id")): f.get("value")
                      for f in mapped_fields if f.get("value") is not None}
            self.fill_acroform(values)
        else:
            pages_map = {}
            for f in mapped_fields:
                p = f.get("page", 0)
                pages_map.setdefault(p, []).append(f)
            for page_num, fields in pages_map.items():
                data = {f.get("field_id"): f.get("value") for f in fields}
                self.fill_page(page_num, fields, data)

    def save(self, path_or_buffer):
        try:
            self.doc.save(path_or_buffer, garbage=3, deflate=True)
            self.doc.close()
            logger.info("PDF guardado correctamente.")
        except Exception as e:
            logger.error(f"Error al guardar: {e}")
            raise e