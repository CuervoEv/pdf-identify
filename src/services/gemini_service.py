import os
import time
import json
from pathlib import Path
from PIL import ImageDraw
from google import genai
from src.utils.image_annotator import agregar_grilla

class GeminiVisionService:
    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("API KEY no detectada. Usa GOOGLE_API_KEY o GEMINI_API_KEY.")
        
        self.client = genai.Client(api_key=api_key)
        self.model_id = "gemini-3-flash-preview"

    def _verificar_y_corregir(self, image_pil, fields_detectados):
        try:
            img_anotada = image_pil.copy().convert("RGBA")
            draw = ImageDraw.Draw(img_anotada, "RGBA")
            w_img, h_img = img_anotada.size

            for field in fields_detectados:
                try:
                    fid  = str(field.get("id", ""))
                    tipo = str(field.get("tipo", "texto")).lower()
                    x = float(field.get("x", 0))
                    y = float(field.get("y", 0))
                    w = float(field.get("w", 0))
                    h = float(field.get("h", 0))
                    if w <= 0 or h <= 0:
                        continue
                    x1 = max(0, int((x / 1000) * w_img))
                    y1 = max(0, int((y / 1000) * h_img))
                    x2 = min(w_img - 1, int(((x + w) / 1000) * w_img))
                    y2 = min(h_img - 1, int(((y + h) / 1000) * h_img))
                    fill    = (0, 180, 0, 70)    if tipo == "checkbox" else (220, 30, 30, 70)
                    outline = (0, 160, 0, 255)   if tipo == "checkbox" else (220, 30, 30, 255)
                    draw.rectangle([(x1, y1), (x2, y2)], fill=fill, outline=outline, width=2)
                    draw.text((x1 + 2, y1 + 2), fid[:12], fill=(255, 255, 255, 255))
                except Exception:
                    continue

            prompt_verificacion = f"""
Eres un verificador de precisión de coordenadas en formularios.

En la imagen ves rectángulos de colores sobre un formulario:
- Rojo = campo de texto detectado
- Verde = checkbox detectado

TAREA: Revisar si cada rectángulo está posicionado sobre el ESPACIO VACÍO 
de escritura (no sobre texto impreso, etiquetas en negrita ni títulos).

REGLA CLAVE: Un rectángulo correcto cubre únicamente el área en blanco 
donde un humano escribiría. Si cubre texto impreso, está mal.

Para cada campo devuelve:
- CORRECTO → mismas coordenadas sin cambios
- MAL POSICIONADO → coordenadas corregidas al espacio vacío real
- NO ENCONTRADO → w=0 y h=0

SISTEMA DE COORDENADAS: 0 a 1000. x=0 izquierda, y=0 arriba.
NUNCA valores fuera de 0-1000.

Campos a verificar: {[f.get('id') for f in fields_detectados]}

Responde SOLO con JSON estricto, sin markdown:
{{
  "fields": [
    {{
      "id": "nombre_campo",
      "tipo": "texto",
      "x": 100, "y": 200, "w": 150, "h": 14,
      "fontSize": 9,
      "align": "left"
    }}
  ]
}}
"""
            response = self.client.models.generate_content(
                model=self.model_id,
                contents=[prompt_verificacion, img_anotada.convert("RGB")],
            )
            clean = response.text.replace("```json", "").replace("```", "").strip()
            corregidos = json.loads(clean).get("fields", [])
            print(f"[Gemini][2pass] {len(corregidos)} campos verificados.")
            return corregidos if isinstance(corregidos, list) and corregidos else fields_detectados

        except Exception as e:
            print(f"[Gemini][2pass] Falló verificación, usando detección original: {e}")
            return fields_detectados

    def analyze_form_page(self, image_pil, expected_fields, page_num=None, debug_dir="temp"):
        imagen_con_grilla = agregar_grilla(image_pil)

        prompt = f"""
ROL: Eres un sistema OCR especializado en formularios en papel. 
Tu ÚNICA función es localizar zonas vacías de escritura, no texto impreso.

TAREA: Localiza las coordenadas de las zonas de llenado para: {expected_fields}

▸ CALIBRACIÓN DE ESCALA (obligatorio leer primero):
  La imagen tiene marcadores de grilla visibles (líneas grises con números rojos).
  Esos números son tu sistema de coordenadas: 0 a 1000 horizontal, 0 a 1000 vertical.
  Úsalos como regla de medición. NUNCA reportes valores fuera de 0-1000.

▸ PRINCIPIO FUNDAMENTAL:
  Un campo de llenado es un ESPACIO VACÍO, no texto impreso.
  El texto en NEGRITA o con color es siempre una ETIQUETA — NUNCA es un campo.
  El texto gris claro o subrayado puede ser un placeholder — es un campo.
  Una línea horizontal fina (___) es siempre la base de un campo de texto.
  Un cuadro con borde fino y vacío es siempre un campo o checkbox.

▸ REGLA 1 — CAMPOS DE TEXTO:
  SEÑALES de que SÍ es un campo: espacio en blanco, línea base (___), fondo claro sin texto bold.
  SEÑALES de que NO es un campo: texto en negrita, texto con color, título de sección.
  POSICIÓN: el campo está siempre DESPUÉS o DEBAJO de su etiqueta, nunca encima ni sobre ella.
  (y + h) debe quedar exactamente sobre la línea base impresa.

▸ REGLA 2 — CHECKBOXES:
  Localiza ÚNICAMENTE la figura geométrica vacía (cuadrado o círculo con borde).
  x, y apuntan a la esquina superior izquierda de ESA figura, no al texto adyacente.
  w y h iguales entre sí, entre 12 y 20 unidades. Nunca más de 22.
  Grupo de checkboxes en fila → mismo 'y', cada uno con su propia 'x'.

▸ REGLA 3 — FECHAS (dd / mm / aaaa):
  Son 3 campos separados, mismo 'y', distinto 'x'.
  dd → w 30-50 | mm → w 30-50 | aaaa → w 60-90
  h entre 10-16. El campo va ENCIMA de la línea, nunca debajo.

▸ REGLA 4 — ALINEACIÓN:
  Misma fila visual → mismo 'y' (±5), distinto 'x'.
  Filas distintas → 'y' diferente (mínimo 10 unidades de diferencia).
  Nunca (x + w) > 1000. Nunca (y + h) > 1000.

▸ LÍMITES DE TAMAÑO:
  checkbox:        w=h, 12-20
  fecha dd/mm:     w 30-55,   h 10-16
  fecha aaaa:      w 60-90,   h 10-16
  texto corto:     w 30-80,   h 10-18
  texto medio:     w 80-350,  h 10-20
  texto largo:     w 300-970, h 10-22
  número/código:   w 50-200,  h 10-18

▸ COMPLETITUD:
  Reporta TODOS los campos de {expected_fields}.
  Si no encuentras uno → w=0, h=0. Nunca omitas un campo.

RESPONDE SOLO CON JSON, sin markdown, sin texto adicional:
{{
  "fields": [
    {{
      "id": "nombre_campo",
      "tipo": "texto",
      "x": 100, "y": 200, "w": 150, "h": 14,
      "fontSize": 9,
      "align": "left"
    }}
  ]
}}
"""

        try:
            MAX_RETRIES = 3
            RETRY_DELAY_S = 2
            response = None

            for attempt in range(1, MAX_RETRIES + 1):
                try:
                    response = self.client.models.generate_content(
                        model=self.model_id,
                        contents=[prompt, imagen_con_grilla],
                    )
                    break
                except Exception as api_error:
                    err_text = str(api_error)
                    is_503 = "503" in err_text or "UNAVAILABLE" in err_text.upper()
                    if is_503 and attempt < MAX_RETRIES:
                        print(f"[Gemini] 503 (intento {attempt}/{MAX_RETRIES}). Reintentando en {RETRY_DELAY_S}s...")
                        time.sleep(RETRY_DELAY_S)
                        continue
                    raise

            clean_json = response.text.replace("```json", "").replace("```", "").strip()
            parsed = json.loads(clean_json)
            fields = parsed.get("fields", [])

            print(f"[Gemini] Paso 1: {len(fields)} campos detectados.")
            print(json.dumps(parsed, indent=2, ensure_ascii=False))

            Path(debug_dir).mkdir(parents=True, exist_ok=True)
            suffix = f"_page_{page_num}" if page_num is not None else ""
            output_path = Path(debug_dir) / f"gemini_response{suffix}.json"
            output_path.write_text(
                json.dumps(parsed, indent=2, ensure_ascii=False), encoding="utf-8"
            )

            # Two-pass: verificar y corregir con segunda llamada
            fields = self._verificar_y_corregir(image_pil, fields)
            print(f"[Gemini] Paso 2: {len(fields)} campos después de verificación.")

            return fields

        except Exception as e:
            raise RuntimeError(f"Error crítico en Gemini página {page_num}: {e}") from e