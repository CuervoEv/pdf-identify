import os
import time
import json
from pathlib import Path
from PIL import Image, ImageDraw
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from typing import List, Optional

# ==========================================
# ESQUEMAS PYDANTIC PARA STRUCTURED OUTPUT
# ==========================================
class CampoDetectado(BaseModel):
    id: str
    tipo: str = Field(description="'texto', 'checkbox', 'numero', 'fecha'")
    x: float = Field(alias="x1")  # Mapeamos x1 a x internamente en post-proceso
    y: float = Field(alias="y1")
    w: float = Field(alias="x2")  # Temporalmente guarda x2, luego calculamos w
    h: float = Field(alias="y2")  # Temporalmente guarda y2, luego calculamos h
    fontSize: float = 9.0
    align: str = "left"

class RespuestaGemini(BaseModel):
    fields: List[CampoDetectado]

class GeminiVisionService:
    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("API KEY no detectada.")
        self.client = genai.Client(api_key=api_key)
        self.model_id = "gemini-2.5-pro"

    # 5 franjas verticales (Y 0–1000)
    FRANJAS = [(0, 240), (190, 430), (380, 620), (570, 810), (760, 1000)]

    def _agregar_grilla_franja(self, image_pil, y_ini, y_fin):
        img  = image_pil.copy().convert("RGB")
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
            if y_val < y_ini or y_val > y_fin: continue
            y_px = int(((y_val - y_ini) / rango) * h)
            if y_val % 100 == 0:
                draw.line([(0, y_px), (w, y_px)], fill=(150, 150, 150), width=2)
                draw.text((2, y_px + 2), str(y_val), fill=(200, 0, 0))
            else:
                draw.line([(0, y_px), (w, y_px)], fill=(210, 210, 210), width=1)
                draw.text((2, y_px + 2), str(y_val), fill=(255, 100, 100))

        return img

    def _anotar_campos_puntos(self, image_pil, fields, y_ini, y_fin):
        # Mantenido intacto (tu lógica de render visual funciona bien)
        img  = image_pil.copy().convert("RGBA")
        draw = ImageDraw.Draw(img, "RGBA")
        w_img, h_img = img.size
        rango = y_fin - y_ini

        for field in fields:
            try:
                fid  = str(field.get("id", ""))
                tipo = str(field.get("tipo", "texto")).lower()
                x = float(field.get("x", 0))
                y = float(field.get("y", 0))
                fw = float(field.get("w", 0))
                fh = float(field.get("h", 0))
                if fw <= 0 or fh <= 0: continue

                x1_px = int((x / 1000) * w_img)
                x2_px = int(((x + fw) / 1000) * w_img)
                y_rel  = (y - y_ini) / rango
                y2_rel = ((y + fh) - y_ini) / rango
                y1_px  = int(y_rel  * h_img)
                y2_px  = int(y2_rel * h_img)
                cy_px  = (y1_px + y2_px) // 2

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

    def _calcular_iou(self, boxA, boxB):
        xA = max(boxA[0], boxB[0])
        yA = max(boxA[1], boxB[1])
        xB = min(boxA[0] + boxA[2], boxB[0] + boxB[2])
        yB = min(boxA[1] + boxA[3], boxB[1] + boxB[3])
        interArea = max(0, xB - xA) * max(0, yB - yA)
        if interArea == 0: return 0.0
        boxAArea = boxA[2] * boxA[3]
        boxBArea = boxB[2] * boxB[3]
        union = float(boxAArea + boxBArea - interArea)
        if union <= 0: return 0.0
        return interArea / union

    def _resolver_colisiones(self, fields_detectados, umbral_iou=0.10):
        campos_validos = []
        def _area_key(f): return float(f.get("w", 0) or 0) * float(f.get("h", 0) or 0)
        fields_ordenados = sorted(fields_detectados, key=_area_key, reverse=True)
        def _box(f): return [float(f.get("x",0)), float(f.get("y",0)), float(f.get("w",0)), float(f.get("h",0))]

        for actual in fields_ordenados:
            box_actual = _box(actual)
            colision = False
            for aprobado in campos_validos:
                box_aprobado = _box(aprobado)
                if self._calcular_iou(box_actual, box_aprobado) > umbral_iou:
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
            if y + h < y_ini or y > y_fin: continue
            
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
            if not fid: continue
            w, h = campo.get("w", 0), campo.get("h", 0)
            if w == 0 and h == 0:
                if fid not in mapa: mapa[fid] = campo
                continue
            area = w * h
            if fid not in mapa:
                mapa[fid] = campo
            else:
                area_actual = mapa[fid].get("w", 0) * mapa[fid].get("h", 0)
                if area > area_actual: mapa[fid] = campo
        return list(mapa.values())

    def _recortar_franja(self, image_pil, y_ini, y_fin):
        w, h   = image_pil.size
        top    = int((y_ini / 1000) * h)
        bottom = int((y_fin  / 1000) * h)
        return image_pil.crop((0, top, w, bottom))

    def _llamar_gemini(self, imagen_pil, prompt, retries=3, delay=2):
        # AHORA USAMOS Pydantic y types.GenerateContentConfig
        for attempt in range(1, retries + 1):
            try:
                return self.client.models.generate_content(
                    model=self.model_id,
                    contents=[prompt, imagen_pil],
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=RespuestaGemini,
                        temperature=0,
                    ),
                )
            except Exception as e:
                err = str(e)
                if ("503" in err or "UNAVAILABLE" in err.upper()) and attempt < retries:
                    print(f"[Gemini] 503 (intento {attempt}/{retries}). Reintentando en {delay}s...")
                    time.sleep(delay)
                else:
                    raise

    def _construir_prompt(self, expected_fields, y_ini, y_fin):
        return f"""
ROL: Eres un sistema OCR especializado en formularios en papel.
Tu ÚNICA función es localizar zonas VACÍAS de escritura, no texto impreso.
TAREA: Localizar coordenadas de llenado para: {expected_fields}

Escala Absoluta (Eje X: 0 a 1000, Eje Y: {y_ini} a {y_fin}).
No toques bloques GRISES.
Devuelve el JSON según el esquema solicitado. Usa x1, y1, x2, y2 reales.
"""

    def _procesar_por_franjas(self, image_pil, expected_fields, debug_dir, page_num):
        todos = []

        for idx, (y_ini, y_fin) in enumerate(self.FRANJAS):
            print(f"[Gemini] Franja {idx+1}/{len(self.FRANJAS)} → y:{y_ini}-{y_fin}")

            recorte            = self._recortar_franja(image_pil, y_ini, y_fin)
            recorte_con_grilla = self._agregar_grilla_franja(recorte, y_ini, y_fin)
            recorte_con_grilla = self._enmascarar_areas_usadas(recorte_con_grilla, todos, y_ini, y_fin)

            Path(debug_dir).mkdir(parents=True, exist_ok=True)
            prompt = self._construir_prompt(expected_fields, y_ini, y_fin)

            try:
                response = self._llamar_gemini(recorte_con_grilla, prompt)
                
                # LA MAGIA DE PYDANTIC: response.parsed ya es un objeto RespuestaGemini
                if not response or not response.parsed:
                    continue
                    
                parsed_data = response.parsed.model_dump()
                fields = parsed_data.get("fields", [])

                fields_validos = []
                for f in fields:
                    # Mapeo de x1,y1,x2,y2 devueltos por el esquema a x,y,w,h
                    x1, y1 = float(f.get("x", 0)), float(f.get("y", 0))
                    x2, y2 = float(f.get("w", 0)), float(f.get("h", 0)) 
                    
                    f["x"], f["y"] = x1, y1
                    f["w"] = max(0, x2 - x1)
                    f["h"] = max(0, y2 - y1)

                    fy, fh = float(f.get("y", 0)), float(f.get("h", 0))
                    if fy < (y_ini - 10) or fy > (y_fin + 10): continue

                    f["y"] = max(y_ini, min(fy, y_fin - 1))
                    f["h"] = min(fh, y_fin - f["y"])
                    fields_validos.append(f)

                todos.extend(fields_validos)

            except Exception as e:
                print(f"❌ [DEBUG FATAL] Franja {idx+1} falló: {str(e)}")
                continue

        sin_dup = self._deduplicar(todos)
        deduplicados = self._resolver_colisiones(sin_dup, umbral_iou=0.30)

        return deduplicados

    def analyze_form_page(self, image_pil, expected_fields, page_num=None, debug_dir="temp"):
        fields = self._procesar_por_franjas(image_pil, expected_fields, debug_dir, page_num)
        return fields