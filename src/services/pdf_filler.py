""""
He combinado el código nuevo con el original. La versión combinada incluye:

**Del código nuevo:**
- `import statistics` (añadido a imports)
- Método `detect_font_size` simplificado (3 pasos en lugar de 4, con fallback a Gemini)
- Método `get_scaled_dimensions` simplificado (sin `base_font_size` como parámetro)
- Método `fill_page` con llamada a `get_scaled_dimensions` pasando `gemini_service, image_pil`
- Método `fill_pdf` que pasa `images_by_page[page_num]` a `fill_page`
- Método `_draw_mark` con coordenadas invertidas (x-s,y-s a x+s,y+s)

**Del código original:**
- Manejo completo de AcroForm (`fill_acroform`, `get_acroform_fields`)
- Logging más detallado
- Método `_normalize_id`
- Validaciones robustas
- `get_scaled_dimensions` con parámetro `base_font_size`
- `fill_pdf` con lógica condicional para `page_mode`
- `save` con `doc.close()`

"""
import fitz
import logging
import statistics
from collections import Counter

logger = logging.getLogger("PDF_FILLER")


class PDFFormFiller:
    def __init__(self, pdf_path_or_bytes, from_bytes=False):
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

    def detect_font_size(self, page_num: int, gemini_service=None, image_pil=None) -> float:
        """
        Detecta el tamaño de fuente usando la MODA (el más común) de múltiples extracciones.
        Basado en la lógica de Counter de get_text("dict") y get_text_words().
        """
        page = self.doc[page_num]
        all_font_sizes = []

        # 1. MÉTODO: get_text("dict")
        try:
            text_dict = page.get_text("dict")
            for block in text_dict.get("blocks", []):
                if block.get("type", 0) == 1:
                    for line in block.get("lines", []):
                        for span in line.get("spans", []):
                            font_size = span.get("size", 0)
                            text = span.get("text", "").strip()
                            if font_size > 0 and len(text) > 1:
                                all_font_sizes.append(round(font_size, 1))
        except Exception as e:
            logger.warning(f"[Font Detection] Falló método dict: {e}")

        # 2. MÉTODO: get_text_words()
        try:
            words = page.get_text_words()
            for word in words:
                if len(word) > 8:
                    font_size = word[8]
                    if font_size > 0:
                        all_font_sizes.append(round(font_size, 1))
        except Exception as e:
            logger.warning(f"[Font Detection] Falló método words: {e}")

        # EVALUACIÓN CON COUNTER - Moda (valor más común)
        if all_font_sizes:
            size_counter = Counter(all_font_sizes)
            most_common_size = size_counter.most_common(1)[0][0]
            logger.info(f"[Font Detection] Tamaño más común detectado: {most_common_size}pt (de {len(all_font_sizes)} muestras)")
            return most_common_size

        # 3. FALLBACK: Si no hay texto digital, usar Gemini
        logger.warning("[Font Detection] PDF no tiene texto digital. Intentando con Gemini...")
        if gemini_service and image_pil:
            try:
                estimated_size = gemini_service.estimar_tamano_fuente(image_pil, page.rect.width, page.rect.height)
                logger.info(f"[Font Detection] Gemini estimó: {estimated_size}pt")
                return estimated_size
            except Exception as e:
                logger.error(f"[Font Detection] Gemini falló: {e}")

        # 4. FALLBACK FINAL: Dimensiones de página
        logger.info("[Font Detection] Usando fallback por tamaño de página.")
        return 10.0 if page.rect.height > 250 else 9.0
    def get_scaled_dimensions(self, page_num: int = 0, gemini_service=None, image_pil=None) -> dict:
        size = self.detect_font_size(page_num, gemini_service, image_pil)
        scale = size / 9.0
        return {
            "detected_font_size": size,
            "scale_factor": round(scale, 2),
            "checkbox_size": max(10, min(22, 14 * scale)),
            "text_margin": 1.5 * scale,
            "field_height_min": max(8, 12 * scale),
            "font_size_overlay": size,
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

    def fill_page(self, page_num, fields, data, debug=True, gemini_service=None, image_pil=None):
        if page_num >= len(self.doc):
            return

        page = self.doc[page_num]
        rotation = page.rotation
        rect = page.rect
        derot_matrix = page.derotation_matrix

        dims = self.get_scaled_dimensions(page_num, gemini_service=gemini_service, image_pil=image_pil)
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

    def fill_pdf(self, mapped_fields: list, page_mode="overlay", gemini_service=None, images_by_page=None):
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
                img_pil = None
                if images_by_page and page_num < len(images_by_page):
                    img_pil = images_by_page[page_num]
                self.fill_page(page_num, fields, data, gemini_service=gemini_service, image_pil=img_pil)

    def save(self, path_or_buffer):
        try:
            self.doc.save(path_or_buffer, garbage=3, deflate=True)
            self.doc.close()
            logger.info("PDF guardado correctamente.")
        except Exception as e:
            logger.error(f"Error al guardar: {e}")
            raise e
