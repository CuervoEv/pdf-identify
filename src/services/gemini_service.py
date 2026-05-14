"""
Servicio de visión y mapeo con Gemini.
"""

import os
import time
import json
import re
from pathlib import Path
from typing import Optional, List, Dict, Any
from PIL import Image, ImageDraw
from google import genai
from google.genai import types
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Schemas Pydantic
# ---------------------------------------------------------------------------

class FieldMapping(BaseModel):
    field_id: str = Field(description="Identificador del campo en el formulario")
    field_label: Optional[str] = Field(None, description="Etiqueta humana del campo")
    value: Optional[str] = Field(None, description="Valor asignado desde la base maestra")
    source_key: Optional[str] = Field(None, description="Clave del JSON maestro de donde proviene el valor")
    confidence: float = Field(ge=0.0, le=1.0, description="Confianza del modelo en la asignación (0-1)")
    reasoning: Optional[str] = Field(None, description="Justificación breve de la asignación (para auditoría)")
    needs_human_review: bool = Field(False, description="True si confidence < 0.9 o hay ambigüedad")
    page: Optional[int] = Field(None, description="Número de página (base 0)")
    bbox: Optional[List[float]] = Field(None, description="Coordenadas [x0,y0,x1,y1] en puntos PDF")


class EstimacionFuente(BaseModel):
    estimated_font_size_pt: float = Field(description="Tamaño estimado de la fuente principal en puntos (pt)")


class MappingResponse(BaseModel):
    mappings: List[FieldMapping]
    unmapped_master_keys: List[str] = []
    notes: Optional[str] = None


# ---------------------------------------------------------------------------
# Servicio principal
# ---------------------------------------------------------------------------

class GeminiVisionService:
    def __init__(self, model_id: Optional[str] = None):
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("API KEY no detectada.")
        self.client = genai.Client(api_key=api_key)
        self.model_id = model_id or "gemini-2.5-flash"
        self.model_id_vision = "gemini-2.5-pro"

    FRANJAS = [
        (0, 240),
        (190, 430),
        (380, 620),
        (570, 810),
        (760, 1000),
    ]

    # ------------------------------------------------------------------
    # ESTIMACIÓN DE TAMAÑO DE FUENTE
    # ------------------------------------------------------------------

    def estimar_tamano_fuente(self, image_pil, width_pt: float, height_pt: float) -> float:
        """Estima visualmente el tamaño de la fuente principal."""
        prompt = (
            f"Este es un formulario PDF escaneado de {width_pt:.0f}x{height_pt:.0f} puntos. "
            "Observa el texto impreso y estima el tamaño de fuente en puntos (pt). "
            "Responde SOLO con un número, por ejemplo: 7.5"
        )
        try:
            response = self.client.models.generate_content(
                model="gemini-2.5-flash",
                contents=[prompt, image_pil],
                config=types.GenerateContentConfig(temperature=0.0)
            )
            text = response.text.strip() if response.text else ""
            match = re.search(r'(\d+\.?\d*)', text)
            if match:
                size = float(match.group(1))
                if 4 <= size <= 24:
                    print(f"[Gemini] Tamaño estimado: {size}pt")
                    return size
            print(f"[Gemini] No se pudo extraer tamaño de: '{text[:100]}'")
            return 9.0
        except Exception as e:
            print(f"[Gemini] Error: {e}")
            return 9.0

    # ------------------------------------------------------------------
    # GRILLA Y ANOTACIONES
    # ------------------------------------------------------------------

    def _agregar_grilla_franja(self, image_pil, y_ini, y_fin):
        img = image_pil.copy().convert("RGB")
        draw = ImageDraw.Draw(img)
        w, h = img.size
        rango = y_fin - y_ini

        for x_val in range(0, 1001, 50):
            x_px = int((x_val / 1000) * w)
            if x_val % 100 == 0:
                draw.line([(x_px, 0), (x_px, h)], fill=(150, 150, 150), width=2)
                draw.text((x_px + 2, 2), str(x_val), fill=(200, 0, 0))
            else:
                draw.line([(x_px, 0), (x_px, h)], fill=(210, 210, 210), width=1)
                draw.text((x_px + 2, 2), str(x_val), fill=(255, 100, 100))

        y_start = (y_ini // 20) * 20
        for y_val in range(y_start, y_fin + 1, 20):
            if y_val < y_ini or y_val > y_fin:
                continue
            y_px = int(((y_val - y_ini) / rango) * h)
            if y_val % 100 == 0:
                draw.line([(0, y_px), (w, y_px)], fill=(150, 150, 150), width=2)
                draw.text((2, y_px + 2), str(y_val), fill=(200, 0, 0))
            else:
                draw.line([(0, y_px), (w, y_px)], fill=(210, 210, 210), width=1)
                draw.text((2, y_px + 2), str(y_val), fill=(255, 100, 100))
        return img

    def _anotar_campos_puntos(self, image_pil, fields, y_ini, y_fin):
        img = image_pil.copy().convert("RGBA")
        draw = ImageDraw.Draw(img, "RGBA")
        w_img, h_img = img.size
        rango = y_fin - y_ini
        for field in fields:
            try:
                fid = str(field.get("id", ""))
                tipo = str(field.get("tipo", "texto")).lower()
                x = float(field.get("x", 0))
                y = float(field.get("y", 0))
                fw = float(field.get("w", 0))
                fh = float(field.get("h", 0))
                if fw <= 0 or fh <= 0:
                    continue
                x1_px = int((x / 1000) * w_img)
                x2_px = int(((x + fw) / 1000) * w_img)
                y_rel = (y - y_ini) / rango
                y2_rel = ((y + fh) - y_ini) / rango
                y1_px = int(y_rel * h_img)
                y2_px = int(y2_rel * h_img)
                cy_px = (y1_px + y2_px) // 2
                if tipo == "checkbox":
                    cx_px = (x1_px + x2_px) // 2
                    r = 3
                    draw.ellipse([cx_px - r, cy_px - r, cx_px + r, cy_px + r], fill=(0, 200, 0, 220))
                else:
                    r = 2
                    draw.ellipse([x1_px - r, y1_px - r, x1_px + r, y1_px + r], fill=(255, 0, 0, 220))
                    draw.ellipse([x2_px - r, y1_px - r, x2_px + r, y1_px + r], fill=(255, 0, 0, 220))
                    draw.text((x1_px + 2, y1_px - 9), fid[:10], fill=(200, 0, 0, 200))
            except Exception:
                continue
        return img.convert("RGB")

    # ------------------------------------------------------------------
    # UTILIDADES DE COORDENADAS
    # ------------------------------------------------------------------

    def _calcular_iou(self, boxA, boxB):
        xA, yA = max(boxA[0], boxB[0]), max(boxA[1], boxB[1])
        xB, yB = min(boxA[0] + boxA[2], boxB[0] + boxB[2]), min(boxA[1] + boxA[3], boxB[1] + boxB[3])
        interArea = max(0, xB - xA) * max(0, yB - yA)
        if interArea == 0:
            return 0.0
        boxAArea = boxA[2] * boxA[3]
        boxBArea = boxB[2] * boxB[3]
        union = float(boxAArea + boxBArea - interArea)
        return interArea / union if union > 0 else 0.0

    def _resolver_colisiones(self, fields_detectados, umbral_iou=0.10):
        campos_validos = []
        def _area_key(f):
            try:
                return float(f.get("w", 0) or 0) * float(f.get("h", 0) or 0)
            except (TypeError, ValueError):
                return 0.0
        fields_ordenados = sorted(fields_detectados, key=_area_key, reverse=True)
        def _box(f):
            try:
                return [float(f.get("x", 0) or 0), float(f.get("y", 0) or 0),
                        float(f.get("w", 0) or 0), float(f.get("h", 0) or 0)]
            except (TypeError, ValueError):
                return [0.0, 0.0, 0.0, 0.0]
        for actual in fields_ordenados:
            box_actual = _box(actual)
            colision = False
            for aprobado in campos_validos:
                if self._calcular_iou(box_actual, _box(aprobado)) > umbral_iou:
                    colision = True
                    break
            if not colision:
                campos_validos.append(actual)
        return campos_validos

    def _enmascarar_areas_usadas(self, image_recorte, campos_aprobados, y_ini, y_fin):
        img_mascara = image_recorte.copy().convert("RGBA")
        draw = ImageDraw.Draw(img_mascara, "RGBA")
        w_img, h_img = img_mascara.size
        rango_y = y_fin - y_ini
        for f in campos_aprobados:
            x, y, w, h = float(f.get("x", 0)), float(f.get("y", 0)), float(f.get("w", 0)), float(f.get("h", 0))
            if y + h < y_ini or y > y_fin:
                continue
            x1_px = int((x / 1000) * w_img)
            y1_px = int(((y - y_ini) / rango_y) * h_img)
            x2_px = int(((x + w) / 1000) * w_img)
            y2_px = int(((y + h - y_ini) / rango_y) * h_img)
            draw.rectangle([(x1_px, y1_px), (x2_px, y2_px)], fill=(50, 50, 50, 255))
        return img_mascara.convert("RGB")

    def _deduplicar(self, campos):
        mapa = {}
        for campo in campos:
            fid = campo.get("id")
            if not fid:
                continue
            w, h = campo.get("w", 0), campo.get("h", 0)
            if w == 0 and h == 0:
                if fid not in mapa:
                    mapa[fid] = campo
                continue
            area = w * h
            if fid not in mapa:
                mapa[fid] = campo
            else:
                area_actual = mapa[fid].get("w", 0) * mapa[fid].get("h", 0)
                if area > area_actual:
                    mapa[fid] = campo
        return list(mapa.values())

    def _recortar_franja(self, image_pil, y_ini, y_fin):
        w, h = image_pil.size
        top = int((y_ini / 1000) * h)
        bottom = int((y_fin / 1000) * h)
        return image_pil.crop((0, top, w, bottom))

    # ------------------------------------------------------------------
    # LLAMADAS A GEMINI
    # ------------------------------------------------------------------

    def _llamar_gemini(self, imagen_pil, prompt, retries=3, delay=2, model_id=None):
        model = model_id or self.model_id_vision
        for attempt in range(1, retries + 1):
            try:
                return self.client.models.generate_content(
                    model=model,
                    contents=[prompt, imagen_pil],
                )
            except Exception as e:
                err = str(e)
                if ("503" in err or "UNAVAILABLE" in err.upper()) and attempt < retries:
                    print(f"[Gemini] 503 (intento {attempt}/{retries}). Reintentando en {delay}s...")
                    time.sleep(delay)
                else:
                    raise

    def _llamar_gemini_structured(self, pdf_bytes, prompt, retries=3, delay=2):
        for attempt in range(1, retries + 1):
            try:
                return self.client.models.generate_content(
                    model=self.model_id,
                    contents=[
                        types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf"),
                        prompt,
                    ],
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=MappingResponse,
                        temperature=0,
                    ),
                )
            except Exception as e:
                err = str(e)
                if ("503" in err or "UNAVAILABLE" in err.upper()) and attempt < retries:
                    print(f"[Gemini Structured] 503 (intento {attempt}/{retries}). Reintentando en {delay}s...")
                    time.sleep(delay)
                else:
                    raise

    # ------------------------------------------------------------------
    # PROMPTS
    # ------------------------------------------------------------------

    def _construir_prompt(self, expected_fields, y_ini, y_fin, font_size_pt=9.0):
    # Calcular proporciones dinámicas basadas en el tamaño de la letra
        alto_min = round(font_size_pt + 1.0, 1)
        alto_max = round(font_size_pt + 1.5, 1)
        check_size = round(font_size_pt + 1.0, 1)

        return f"""
ROL: Eres un sistema OCR especializado en formularios en papel.
Tu ÚNICA función es localizar zonas VACÍAS de escritura, no texto impreso.

TAREA: Localizar coordenadas de llenado para: {expected_fields}

═══════════════════════════════════════════════════════════
CALIBRACIÓN DE ESCALA
═══════════════════════════════════════════════════════════
Esta imagen es una FRANJA de la página completa.
La grilla muestra coordenadas ABSOLUTAS reales:
  → Eje X: 0 a 1000
  → Eje Y: {y_ini} a {y_fin}
Usa los números de la grilla directamente.
NUNCA reportes Y fuera de {y_ini}-{y_fin}.
NUNCA reportes X fuera de 0-1000.

═══════════════════════════════════════════════════════════
TAMAÑO DE FUENTE DETECTADO: {font_size_pt}pt
═══════════════════════════════════════════════════════════
El formulario usa letra de {font_size_pt}pt. Ajusta el alto de los campos así:
  → Alto mínimo: {alto_min}
  → Alto máximo: {alto_max}
  → Checkbox: {check_size} de lado

═══════════════════════════════════════════════════════════
REGLA DE EXCLUSIÓN ESPACIAL (¡CRÍTICO!)
═══════════════════════════════════════════════════════════
Los bloques de color GRIS OSCURO SÓLIDO son áreas MUERTAS ya usadas por otros campos. 
ESTÁ ESTRICTAMENTE PROHIBIDO que tus coordenadas toquen, crucen o se superpongan con estas áreas grises.

═══════════════════════════════════════════════════════════
PRINCIPIO FUNDAMENTAL
═══════════════════════════════════════════════════════════
Un campo es SIEMPRE un espacio vacío, nunca texto impreso.

SÍ es un campo:
  → Espacio en blanco tras una etiqueta
  → Línea fina horizontal (_____) 
  → Recuadro con borde fino y vacío
  → Texto gris claro o subrayado

NO es un campo:
  → Texto en negrita o con color → ETIQUETA, ignórala
  → Título de sección o encabezado
  → Línea divisoria entre dos campos

═══════════════════════════════════════════════════════════
CADENA DE RAZONAMIENTO
═══════════════════════════════════════════════════════════
Para cada campo:
  [1] ¿Dónde está la etiqueta?
  [2] ¿Qué hay después o debajo de ella?
  [3] ¿Ese espacio está vacío y libre de bloques grises? → Sí: úsalo. No: busca el siguiente.
  [4] ¿Las coordenadas caen en espacio blanco? → Sí: reporta. No: corrige.

═══════════════════════════════════════════════════════════
REGLAS POR TIPO (AJUSTADAS A {font_size_pt}pt)
═══════════════════════════════════════════════════════════
CHECKBOXES:
  → x1,y1 = esquina superior izquierda de la figura vacía.
  → x2,y2 = esquina inferior derecha.
  → Ancho y Alto entre {check_size}-{check_size + 4}. Nunca más de 22.
  → Grupo en fila → mismo 'y1', distinto 'x1'.

FECHAS:
  → 3 campos separados, mismo 'y1', distinto 'x1'.
  → dd: ancho 30-50 | mm: ancho 30-50 | aaaa: ancho 60-90 | alto: {alto_min}-{alto_max}.

TEXTO CORTO:   ancho 30-80,   alto {alto_min}-{alto_max}
TEXTO MEDIO:   ancho 80-350,  alto {alto_min}-{alto_max}
TEXTO LARGO:   ancho 300-970, alto {alto_min}-{alto_max}
NÚMERO:        ancho 50-200,  alto {alto_min}-{alto_max}

LÍNEAS DIVISORIAS:
  → Si ves una línea fina entre dos campos, NO es un campo.
  → Ignórala completamente.

═══════════════════════════════════════════════════════════
ALINEACIÓN
═══════════════════════════════════════════════════════════
  → Misma fila → mismo 'y1' (±5), distinto 'x1'.
  → Filas distintas → 'y1' diferente (mínimo {alto_min + 2} unidades).
  → Nunca 'x2' > 1000. Nunca 'y2' > {y_fin}.

═══════════════════════════════════════════════════════════
AUTO-REVISIÓN
═══════════════════════════════════════════════════════════
  [A] ¿Algún campo sobre texto en negrita o bloques grises? → muévelo al vacío.
  [B] ¿Checkbox con ancho o alto > 22? → reduce a {check_size}.
  [C] ¿Dos campos con mismo 'y1'? → corrige el segundo.
  [D] ¿'x2'>1000 o 'y2'>{y_fin}? → recorta.
  [E] ¿Y fuera de {y_ini}-{y_fin}? → corrige o descarta.
  [F] ¿Faltan campos? → agrégalos con x1=0, y1=0, x2=0, y2=0.

═══════════════════════════════════════════════════════════
EJEMPLOS
═══════════════════════════════════════════════════════════
'ciudad_solicitud':
  [1] "Ciudad" en negrita → etiqueta.
  [2] Debajo: espacio blanco con línea fina.
  [3] Vacío ✓  [4] Blanco ✓
  → x1:248, y1:128, x2:470, y2:{128 + alto_min}

'solicitud_nuevo_chk':
  [1] "Nuevo" a la izquierda → etiqueta.
  [2] A la derecha: cuadro pequeño con borde.
  [3] Vacío ✓  [4] Blanco ✓
  → x1:574, y1:148, x2:{574 + check_size}, y2:{148 + check_size}

RESPONDE SOLO JSON sin markdown con fontSize={font_size_pt}:
{{
  "fields": [
    {{"id":"nombre","tipo":"texto","x1":100,"y1":200,"x2":250,"y2":{200 + alto_min},"fontSize":{font_size_pt},"align":"left"}}
  ]
}}
"""

    def _construir_prompt_verificacion(self, campos_franja, y_ini, y_fin):
        ids = [f.get("id") for f in campos_franja]
        return f"""
Eres un verificador de precisión de coordenadas en formularios.

En la imagen ves puntos de colores sobre un formulario:
  → Puntos ROJOS = esquinas del campo de texto detectado
  → Punto VERDE  = centro del checkbox detectado

TAREA: Verificar si cada marcador cae sobre ESPACIO VACÍO de escritura.
Si un punto rojo cae sobre texto impreso o negrita → el campo está MAL.
Si un punto verde no está centrado en la figura geométrica → está MAL.

SISTEMA DE COORDENADAS:
  → Eje X: 0 a 1000
  → Eje Y: {y_ini} a {y_fin} (coordenadas absolutas reales)
  → NUNCA reportes valores fuera de estos rangos.

Para cada campo devuelve:
  → CORRECTO: mismas coordenadas sin cambios
  → MAL: coordenadas corregidas al espacio vacío real
  → NO ENCONTRADO: w=0, h=0

Campos a verificar: {ids}

RESPONDE SOLO JSON sin markdown:
{{
  "fields": [
    {{"id":"...","tipo":"...","x":0,"y":0,"w":0,"h":0,"fontSize":9,"align":"left"}}
  ]
}}
"""

    # ------------------------------------------------------------------
    # PROCESAMIENTO POR FRANJAS
    # ------------------------------------------------------------------

    def _procesar_por_franjas(self, image_pil, expected_fields, debug_dir, page_num, font_size_pt=9.0):
        todos = []
        for idx, (y_ini, y_fin) in enumerate(self.FRANJAS):
            print(f"[Gemini] Franja {idx+1}/{len(self.FRANJAS)} → y:{y_ini}-{y_fin}")
            recorte = self._recortar_franja(image_pil, y_ini, y_fin)
            recorte_con_grilla = self._agregar_grilla_franja(recorte, y_ini, y_fin)
            recorte_con_grilla = self._enmascarar_areas_usadas(recorte_con_grilla, todos, y_ini, y_fin)
            Path(debug_dir).mkdir(parents=True, exist_ok=True)
            recorte_con_grilla.save(f"{debug_dir}/franja_{idx+1}_gemini_ve.png")
            prompt = self._construir_prompt(expected_fields, y_ini, y_fin, font_size_pt)
            try:
                response = self._llamar_gemini(recorte_con_grilla, prompt)
                texto_raw = response.text if response else ""
                clean_json = texto_raw.replace("```json", "").replace("```", "").strip()
                parsed = json.loads(clean_json)
                fields = parsed.get("fields", [])
                fields_validos = []
                for f in fields:
                    try:
                        if "x1" in f:
                            x1 = float(f.pop("x1", 0))
                            y1 = float(f.pop("y1", 0))
                            x2 = float(f.pop("x2", 0))
                            y2 = float(f.pop("y2", 0))
                            f["x"] = x1
                            f["y"] = y1
                            f["w"] = max(0, x2 - x1)
                            f["h"] = max(0, y2 - y1)
                        fy = float(f.get("y", 0))
                        fh = float(f.get("h", 0))
                        if fy < (y_ini - 10) or fy > (y_fin + 10):
                            continue
                        f["y"] = max(y_ini, min(fy, y_fin - 1))
                        f["h"] = min(fh, y_fin - f["y"])
                        fields_validos.append(f)
                    except Exception as err_campo:
                        print(f"  [!] Error casteando el campo {f.get('id', 'desconocido')}: {err_campo}")
                        continue
                print(f"[Gemini] Franja {idx+1}: {len(fields_validos)} campos.")
                todos.extend(fields_validos)
                suffix = f"_page_{page_num}" if page_num is not None else ""
                (Path(debug_dir) / f"franja_{idx+1}{suffix}.json").write_text(
                    json.dumps({"fields": fields_validos}, indent=2, ensure_ascii=False),
                    encoding="utf-8"
                )
            except Exception as e:
                print(f"❌ [DEBUG FATAL] Franja {idx+1} falló totalmente: {str(e)}")
                continue

        sin_dup = self._deduplicar(todos)
        print(f"[Gemini] Tras _deduplicar: {len(sin_dup)} campos (desde {len(todos)} raw).")
        deduplicados = self._resolver_colisiones(sin_dup, umbral_iou=0.30)
        print(f"[Gemini] Tras filtro IoU 30%: {len(deduplicados)} campos únicos.")

        page_seguro = page_num if page_num is not None else 1
        suffix = f"_page_{page_seguro}"
        Path(debug_dir).mkdir(parents=True, exist_ok=True)
        ruta_archivo = Path(debug_dir) / f"gemini_response{suffix}.json"
        ruta_archivo.write_text(
            json.dumps({"fields": deduplicados}, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print(f"[DEBUG] Ruta absoluta: {ruta_archivo.resolve()}")
        return deduplicados

    def _verificar_y_corregir_por_franjas(self, image_pil, fields_detectados, debug_dir, page_num):
        todos_corregidos = []
        for idx, (y_ini, y_fin) in enumerate(self.FRANJAS):
            campos_franja = [f for f in fields_detectados if y_ini - 10 <= f.get("y", 0) <= y_fin + 10]
            if not campos_franja:
                continue
            print(f"[Gemini][2pass] Franja {idx+1}: verificando {len(campos_franja)} campos.")
            recorte = self._recortar_franja(image_pil, y_ini, y_fin)
            recorte_anotado = self._anotar_campos_puntos(recorte, campos_franja, y_ini, y_fin)
            prompt_v = self._construir_prompt_verificacion(campos_franja, y_ini, y_fin)
            try:
                response = self._llamar_gemini(recorte_anotado, prompt_v)
                clean = response.text.replace("```json", "").replace("```", "").strip()
                corregidos = json.loads(clean).get("fields", [])
                print(f"[Gemini][2pass] Franja {idx+1}: {len(corregidos)} corregidos.")
                todos_corregidos.extend(corregidos)
            except Exception as e:
                print(f"[Gemini][2pass] Franja {idx+1} falló: {e}")
                todos_corregidos.extend(campos_franja)
        resultado = self._resolver_colisiones(todos_corregidos, umbral_iou=0.10)
        print(f"[Gemini][2pass] Total final: {len(resultado)} campos.")
        Path(debug_dir).mkdir(parents=True, exist_ok=True)
        suffix = f"_page_{page_num}" if page_num is not None else ""
        (Path(debug_dir) / f"gemini_response{suffix}.json").write_text(
            json.dumps({"fields": resultado}, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return resultado

    def analyze_form_page(self, image_pil, expected_fields, page_num=None, debug_dir="temp", font_size_pt=9.0):
        fields = self._procesar_por_franjas(image_pil, expected_fields, debug_dir, page_num, font_size_pt)
        print(f"[Gemini] Final: {len(fields)} campos.")
        return fields

    # ------------------------------------------------------------------
    # MAPEO CON MAESTRO
    # ------------------------------------------------------------------

    def map_fields_with_master(
        self,
        pdf_bytes: bytes,
        master_data: Dict[str, Any],
        extracted_fields: List[Dict[str, Any]],
        pdf_is_acroform: bool = False,
    ) -> MappingResponse:
        prompt = f"""Eres un asistente que mapea campos de un formulario PDF con los datos
de una base maestra. Tu único trabajo es decidir qué valor de la base maestra
corresponde a cada campo del formulario.

REGLAS:
1. Solo asigna un valor si tienes alta confianza (>= 0.7) de que el campo
   se refiere al mismo dato semántico.
2. Si no hay coincidencia clara, asigna value=null y confidence=0.
3. Para fechas, normaliza al formato dd/mm/yyyy.
4. Para checkboxes/radio buttons, value debe ser "true" o "false".
5. NO inventes valores que no estén en la base maestra.
6. Para cada campo asignado, incluye un razonamiento breve (reasoning).
7. Marca needs_human_review=true si confidence < 0.9.

BASE MAESTRA:
{json.dumps(master_data, ensure_ascii=False, indent=2)}

CAMPOS DEL FORMULARIO A MAPEAR:
{json.dumps(extracted_fields, ensure_ascii=False, indent=2)}
"""
        try:
            response = self._llamar_gemini_structured(pdf_bytes, prompt)
            result: MappingResponse = response.parsed
            return result
        except Exception as e:
            print(f"[Gemini] Error en map_fields_with_master: {e}")
            return MappingResponse(
                mappings=[],
                unmapped_master_keys=list(master_data.keys()),
                notes=f"Error: {str(e)}"
            )