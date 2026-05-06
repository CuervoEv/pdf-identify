import os
import time
import json
from pathlib import Path
from google import genai
from google.genai import types

class GeminiVisionService:
    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("API KEY no detectada. Usa GOOGLE_API_KEY o GEMINI_API_KEY.")
        
        self.client = genai.Client(api_key=api_key)
        self.model_id = "gemini-3.0-flash"

    def analyze_form_page(self, image_pil, expected_fields, page_num=None, debug_dir="temp"):
        imagen_limpia = image_pil.convert("RGB")

        prompt = fprompt = f"""
ACTÚA COMO UN MOTOR DE VISIÓN ARTIFICIAL ESTRICTO.
Tu tarea es mapear exclusivamente el ÁREA EN BLANCO de respuesta para estos campos: {expected_fields}.

SISTEMA DE COORDENADAS OBLIGATORIO: Escala 0 a 1000.
x=0 es izquierda, x=1000 es derecha, y=0 es arriba, y=1000 es abajo.
NUNCA uses píxeles absolutos de la imagen. SIEMPRE valores entre 0 y 1000.

REGLAS:

1. CHECKBOXES ('tipo': 'checkbox'):
   - Localiza ÚNICAMENTE la figura geométrica vacía (cuadrado o círculo).
   - PROHIBIDO usar coordenadas de la etiqueta de texto adyacente.
   - El bounding box debe coincidir con los bordes exteriores de la figura vacía.
   - 'w' y 'h' deben ser iguales entre sí y pequeños (entre 12 y 25 unidades).

2. CAMPOS DE TEXTO ('tipo': 'texto'):
   - Localiza la línea de escritura (____) o el interior del recuadro en blanco.
   - El borde inferior del campo (y + h) debe descansar exactamente sobre la línea impresa.
   - PROHIBIDO que el recuadro quede por debajo de la línea base.
   - PROHIBIDO incluir el texto de la pregunta dentro del recuadro.

3. CAMPOS EN LA MISMA FILA HORIZONTAL: mismo 'y' aproximado, distinto 'x'.
   CAMPOS EN FILAS DISTINTAS: 'y' diferente obligatoriamente. 
   Nunca dos campos de filas distintas comparten el mismo 'y'.

4. ATRIBUTOS:
   - 'fontSize': entre 7 y 11 según el alto disponible.
   - 'align': 'left' para texto largo, 'center' para fechas, números o checkboxes.

RESPONDE ÚNICAMENTE CON JSON ESTRICTO, SIN MARKDOWN:
{{
  "fields": [
    {{
      "id": "nombre_del_campo", "tipo": "texto", "x": 100, "y": 200, "w": 50, "h": 15, "fontSize": 9, "align": "left"
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
                        contents=[prompt, imagen_limpia],
                    )
                    break
                except Exception as api_error:
                    err_text = str(api_error)
                    is_503 = "503" in err_text or "UNAVAILABLE" in err_text.upper()
                    if is_503 and attempt < MAX_RETRIES:
                        print(f"[Gemini] 503 recibido (intento {attempt}/{MAX_RETRIES}). Reintentando en {RETRY_DELAY_S}s...")
                        time.sleep(RETRY_DELAY_S)
                        continue
                    raise

            clean_json = response.text.replace('```json', '').replace('```', '').strip()
            parsed = json.loads(clean_json)
            fields = parsed.get("fields", [])

            print("[Gemini] JSON completo recibido:")
            print(json.dumps(parsed, indent=2, ensure_ascii=False))

            Path(debug_dir).mkdir(parents=True, exist_ok=True)
            page_suffix = f"_page_{page_num}" if page_num is not None else ""
            output_path = Path(debug_dir) / f"gemini_response{page_suffix}.json"
            output_path.write_text(json.dumps(parsed, indent=2, ensure_ascii=False), encoding="utf-8")
            print(f"[Gemini] JSON guardado en: {output_path}")
            print(f"[Gemini] Éxito: {len(fields)} campos posicionados dinámicamente.")
            
            return fields

        except Exception as e:
            raise RuntimeError(f"Error crítico en Gemini al analizar página: {e}") from e
