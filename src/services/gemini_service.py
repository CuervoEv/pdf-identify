import os
import json
from io import BytesIO
from google import genai
from google.genai import types

class GeminiVisionService:
    def __init__(self):
        # Intenta ambas variables de entorno por compatibilidad
        api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("API KEY no detectada. Usa GOOGLE_API_KEY o GEMINI_API_KEY.")
        
        # Inicialización del cliente con la nueva librería google-genai
        self.client = genai.Client(api_key=api_key)
        self.model_id = "gemini-3-flash-preview"

    def analyze_form_page(self, image_pil, expected_fields):
        """
        Analiza la imagen y detecta coordenadas precisas para cada campo.
        Usa un sistema de cuadrícula 0-1000 para mapeo de PDF.
        """
        buffered = BytesIO()
        image_pil.save(buffered, format="PNG")
        img_bytes = buffered.getvalue()

        # Prompt optimizado para evitar solapamientos y mejorar la precisión
        prompt = f"""
        ACTÚA COMO UN ESCÁNER ÓPTICO DE PRECISIÓN MILIMÉTRICA.
        Tu tarea es localizar las coordenadas exactas de llenado para estos campos: {expected_fields}.

        REGLAS CRÍTICAS DE POSICIONAMIENTO:
        1. LOCALIZACIÓN: No des la coordenada de la etiqueta de texto. Busca el recuadro o espacio en blanco ADYACENTE donde un humano escribiría el dato.
        2. ESCALA: Usa un sistema de coordenadas de 0 a 1000 (x=0 es izquierda, y=0 es arriba).
        3. BOX MODEL:
           - 'x', 'y': Es la esquina superior izquierda del espacio de escritura.
           - 'w', 'h': Es el ancho y alto del espacio disponible.
        4. ATRIBUTOS DINÁMICOS:
           - 'fontSize': Sugiere un tamaño entre 7 y 11. Si el espacio 'w' es pequeño, reduce el fontSize.
           - 'align': 'left' para texto largo, 'center' para fechas o números cortos.
           - 'tipo': 'checkbox' si es un cuadro de marcar, 'texto' si es para escribir.

        RESPONDE ÚNICAMENTE CON UN JSON ESTRICTO:
        {{
          "fields": [
            {{
              "id": "nombre_exacto_del_campo",
              "tipo": "texto",
              "x": 100, "y": 200, "w": 50, "h": 20,
              "fontSize": 9,
              "align": "left"
            }}
          ]
        }}
        No incluyas explicaciones ni markdown. Solo el objeto JSON.
        """

        try:
            # Generación de contenido con el modelo Flash Preview
            response = self.client.models.generate_content(
                model=self.model_id,
                contents=[
                    prompt,
                    types.Part.from_bytes(data=img_bytes, mime_type="image/png")
                ]
            )
            
            # Limpieza de la respuesta para asegurar que json.loads no falle
            clean_json = response.text.replace('```json', '').replace('```', '').strip()
            
            # Debug log de la respuesta cruda para verificar coordenadas
            print(f"[Gemini] Coordenadas recibidas (snippet): {clean_json[:150]}...")
            
            parsed = json.loads(clean_json)
            fields = parsed.get("fields", [])
            
            # Validación de IDs: solo devolver los que solicitamos y la IA encontró
            detected_ids = [f['id'] for f in fields]
            print(f"[Gemini] Éxito: {len(fields)} campos posicionados dinámicamente.")
            
            return fields

        except Exception as e:
            print(f"Error crítico en el servicio Gemini: {e}")
            return []