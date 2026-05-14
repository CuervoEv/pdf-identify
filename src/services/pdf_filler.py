"""
Rellenador de PDFs: AcroForm nativo + overlay para planos.
"""

import fitz
import logging
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
        # ------------------------------------------------------------------
    # RECORTE DE MÁRGENES VACÍOS
    # ------------------------------------------------------------------

    def crop_empty_margins(self, page_num: int = 0, margin_pt: float = 20.0):
        """
        Recorta los márgenes vacíos de una página.
        Detecta el contenido real y ajusta el cropbox para eliminar bordes en blanco.
        
        Args:
            page_num: índice de página (base 0)
            margin_pt: margen de seguridad en puntos (default 20pt ≈ 7mm)
        
        Returns:
            dict con las coordenadas del contenido encontrado y el rect original
        """
        if page_num >= len(self.doc):
            return None
        
        page = self.doc[page_num]
        original_rect = page.rect
        
        # Obtener todos los dibujos e imágenes de la página
        content_rects = []
        
        # 1. Buscar rectángulos de texto
        try:
            text_dict = page.get_text("dict")
            for block in text_dict.get("blocks", []):
                if block.get("type") == 1:  # texto
                    bbox = block.get("bbox")
                    if bbox:
                        content_rects.append(fitz.Rect(bbox))
        except:
            pass
        
        # 2. Buscar imágenes
        try:
            for img in page.get_images(full=True):
                bbox = page.get_image_bbox(img)
                if bbox and bbox.width > 0 and bbox.height > 0:
                    content_rects.append(bbox)
        except:
            pass
        
        # 3. Buscar dibujos (paths)
        try:
            drawings = page.get_drawings()
            for d in drawings:
                if d.get("rect"):
                    r = d["rect"]
                    if r.width > 0 and r.height > 0:
                        content_rects.append(r)
        except:
            pass
        
        if not content_rects:
            logger.warning("[Crop] No se encontró contenido. Se mantiene el rect original.")
            return {
                "original": list(original_rect),
                "cropped": list(original_rect),
                "crop_applied": False
            }
        
        # Calcular el bounding box que contiene todo el contenido
        union_rect = content_rects[0]
        for r in content_rects[1:]:
            union_rect = union_rect | r  # unión de rectángulos
        
        # Añadir margen de seguridad
        crop_rect = fitz.Rect(
            max(original_rect.x0, union_rect.x0 - margin_pt),
            max(original_rect.y0, union_rect.y0 - margin_pt),
            min(original_rect.x1, union_rect.x1 + margin_pt),
            min(original_rect.y1, union_rect.y1 + margin_pt)
        )
        
        # Aplicar crop
        page.set_cropbox(crop_rect)
        
        logger.info(f"[Crop] Original: {original_rect.width:.0f}x{original_rect.height:.0f}pt → "
                    f"Crop: {crop_rect.width:.0f}x{crop_rect.height:.0f}pt "
                    f"(recorte: {original_rect.width - crop_rect.width:.0f}x{original_rect.height - crop_rect.height:.0f}pt)")
        
        return {
            "original": list(original_rect),
            "cropped": list(crop_rect),
            "crop_applied": True,
            "content_found": True
        }
    def detect_font_size(self, page_num: int = 0, gemini_service=None, image_pil=None) -> float:
        """
        Detecta el tamaño de fuente predominante en el PDF.
        """
        if page_num >= len(self.doc):
            print(f"[Font Detection] ❌ page_num {page_num} fuera de rango ({len(self.doc)} páginas)")
            return 9.0

        page = self.doc[page_num]
        all_font_sizes = []
        
        print(f"\n{'='*60}")
        print(f"[Font Detection] 📄 Analizando página {page_num+1}")
        print(f"[Font Detection] 📐 Dimensiones: {page.rect.width:.0f}x{page.rect.height:.0f} puntos ({page.rect.height*25.4/72:.0f}mm)")
        print(f"{'='*60}")

        # Método 1: get_text("dict")
        print("\n🔍 Método 1: get_text('dict')")
        try:
            text_dict = page.get_text("dict")
            blocks_texto = 0
            for block in text_dict.get("blocks", []):
                if block.get("type", 0) == 1:
                    for line in block.get("lines", []):
                        for span in line.get("spans", []):
                            font_size = span.get("size", 0)
                            text = span.get("text", "").strip()
                            if font_size > 0 and len(text) > 1:
                                all_font_sizes.append(round(font_size, 1))
                                blocks_texto += 1
                                if blocks_texto <= 5:
                                    print(f"  ✓ '{text[:40]}...' → {font_size}pt (fuente: {span.get('font', '?')})")
            print(f"  📊 Total spans encontrados: {blocks_texto}")
        except Exception as e:
            print(f"  ❌ Falló: {e}")

        # Método 2: get_text("rawdict")
        print("\n🔍 Método 2: get_text('rawdict')")
        try:
            text_rawdict = page.get_text("rawdict")
            blocks_raw = 0
            for block in text_rawdict.get("blocks", []):
                if block.get("type", 0) == 1:
                    for line in block.get("lines", []):
                        for span in line.get("spans", []):
                            font_size = span.get("size", 0)
                            text = span.get("text", "").strip()
                            if font_size > 0 and text.strip():
                                if blocks_raw < 3:
                                    print(f"  ✓ '{text[:40]}' → {font_size}pt")
                                blocks_raw += 1
            print(f"  📊 Total spans (raw): {blocks_raw}")
        except Exception as e:
            print(f"  ❌ Falló: {e}")

        # Método 3: get_text_words()
        print("\n🔍 Método 3: get_text_words()")
        try:
            words = page.get_text_words()
            print(f"  📊 Palabras encontradas: {len(words)}")
            words_with_font = 0
            for i, word in enumerate(words):
                if len(word) > 8:
                    text = word[4]
                    font_size = word[8] if len(word) > 8 else 0
                    if font_size > 0 and text.strip():
                        all_font_sizes.append(round(font_size, 1))
                        words_with_font += 1
                        if i < 5:
                            print(f"  ✓ '{text}' → {font_size}pt")
            print(f"  📊 Palabras con tamaño de fuente: {words_with_font}")
        except Exception as e:
            print(f"  ❌ Falló: {e}")

        # Método 4: get_text("html")
        print("\n🔍 Método 4: get_text('html')")
        try:
            html_text = page.get_text("html")
            import re
            font_sizes_html = re.findall(r'font-size:\s*([\d.]+)pt', html_text)
            if font_sizes_html:
                sizes_set = sorted(set([round(float(s), 1) for s in font_sizes_html]))
                print(f"  ✓ Tamaños en HTML: {sizes_set[:10]}")
                for s in font_sizes_html:
                    all_font_sizes.append(round(float(s), 1))
            else:
                print(f"  ⚠️ No se encontraron tamaños en HTML")
        except Exception as e:
            print(f"  ❌ Falló: {e}")

        # Resultado
        print(f"\n{'='*60}")
        if all_font_sizes:
            from collections import Counter
            size_counter = Counter(all_font_sizes)
            most_common = size_counter.most_common(1)[0]
            print(f"[Font Detection] 📊 Muestras totales: {len(all_font_sizes)}")
            print(f"[Font Detection] 📊 Distribución: {dict(size_counter.most_common(5))}")
            print(f"[Font Detection] ✅ Tamaño más común: {most_common[0]}pt ({most_common[1]} ocurrencias)")
            return most_common[0]
        
        # Si no hay texto digital
        print("[Font Detection] ⚠️ PDF SIN TEXTO DIGITAL (escaneado/imagen)")
        
        if gemini_service and image_pil:
            print("[Font Detection] 🤖 Llamando a Gemini visión...")
            try:
                estimated = gemini_service.estimar_tamano_fuente(
                    image_pil, page.rect.width, page.rect.height
                )
                print(f"[Font Detection] ✅ Gemini estimó: {estimated}pt")
                return estimated
            except Exception as e:
                print(f"[Font Detection] ❌ Gemini falló: {e}")
        else:
            print(f"[Font Detection] ⚠️ No hay gemini_service={gemini_service is not None}, image_pil={image_pil is not None}")
        
        # Fallback
        fallback = 10.0 if page.rect.height > 250 else 9.0
        print(f"[Font Detection] 🔄 Usando fallback: {fallback}pt")
        return fallback

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
                if images_by_page and page_num in images_by_page:
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