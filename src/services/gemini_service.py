import os
import time
import json
from pathlib import Path
from PIL import Image, ImageDraw
from google import genai
from src.utils.image_annotator import agregar_grilla


class GeminiVisionService:
    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("API KEY no detectada. Usa GOOGLE_API_KEY o GEMINI_API_KEY.")
        self.client = genai.Client(api_key=api_key)
        self.model_id = "gemini-3-flash-preview"

    # ─────────────────────────────────────────────
    # GRILLA CON COORDENADAS ABSOLUTAS DE LA FRANJA
    # ─────────────────────────────────────────────

    def _agregar_grilla_franja(self, image_pil, y_ini, y_fin):
        """
        Dibuja una grilla sobre el recorte mostrando los valores
        REALES de coordenadas absolutas de la página completa.
        Eje X: siempre 0-1000.
        Eje Y: valores reales entre y_ini y y_fin.
        """
        img  = image_pil.copy().convert("RGB")
        draw = ImageDraw.Draw(img)
        w, h = img.size
        rango = y_fin - y_ini

        for i in range(0, 1001, 100):
            # Eje X
            x_px = int((i / 1000) * w)
            draw.line([(x_px, 0), (x_px, h)], fill=(180, 180, 180), width=1)
            draw.text((x_px + 2, 2), str(i), fill=(220, 50, 50))

            # Eje Y — valor absoluto real
            y_px   = int((i / 1000) * h)
            y_real = round(y_ini + (i / 1000) * rango)
            draw.line([(0, y_px), (w, y_px)], fill=(180, 180, 180), width=1)
            draw.text((2, y_px + 2), str(y_real), fill=(220, 50, 50))

        return img

    # ─────────────────────────────────────────────
    # UTILIDADES
    # ─────────────────────────────────────────────

    def _deduplicar(self, campos):
        """Conserva una sola ocurrencia por id, priorizando la de mayor área."""
        mapa = {}
        for campo in campos:
            fid = campo.get("id")
            if not fid:
                continue
            if campo.get("w", 0) == 0 and campo.get("h", 0) == 0:
                continue
            area_nueva  = campo.get("w", 0) * campo.get("h", 0)
            area_actual = mapa[fid].get("w", 0) * mapa[fid].get("h", 0) if fid in mapa else -1
            if fid not in mapa or area_nueva > area_actual:
                mapa[fid] = campo
        return list(mapa.values())

    def _recortar_franja(self, image_pil, y_ini, y_fin):
        """Recorta la imagen entre y_ini y y_fin (escala 0-1000 → píxeles)."""
        w, h   = image_pil.size
        top    = int((y_ini / 1000) * h)
        bottom = int((y_fin  / 1000) * h)
        return image_pil.crop((0, top, w, bottom))

    def _llamar_gemini(self, imagen_pil, prompt, retries=3, delay=2):
        """Llama a Gemini con reintentos ante errores 503."""
        for attempt in range(1, retries + 1):
            try:
                return self.client.models.generate_content(
                    model=self.model_id,
                    contents=[prompt, imagen_pil],
                )
            except Exception as e:
                err = str(e)
                if ("503" in err or "UNAVAILABLE" in err.upper()) and attempt < retries:
                    print(f"[Gemini] 503 (intento {attempt}/{retries}). Reintentando en {delay}s...")
                    time.sleep(delay)
                else:
                    raise

    # ─────────────────────────────────────────────
    # FRANJAS con solapamiento de 100 unidades y rangos de 200
    # ─────────────────────────────────────────────

    FRANJAS = [
        (0, 200),
        (100, 300),
        (200, 400),
        (300, 500),
        (400, 600),
        (500, 700),
        (600, 800),
        (700, 900),
        (800, 1000),
    ]

    def _procesar_por_franjas(self, image_pil, expected_fields, debug_dir, page_num):
        todos_los_campos = []

        for idx, (y_ini, y_fin) in enumerate(self.FRANJAS):
            print(f"[Gemini] Franja {idx+1}/{len(self.FRANJAS)} → y:{y_ini}-{y_fin}")

            recorte = self._recortar_franja(image_pil, y_ini, y_fin)
            recorte_con_grilla = self._agregar_grilla_franja(recorte, y_ini, y_fin)

            prompt = self._construir_prompt(expected_fields, y_ini, y_fin)

            try:
                response   = self._llamar_gemini(recorte_con_grilla, prompt)
                clean_json = response.text.replace("```json", "").replace("```", "").strip()
                parsed     = json.loads(clean_json)
                fields     = parsed.get("fields", [])

                # Filtrar campos fuera del rango de la franja
                fields_validos = []
                for f in fields:
                    fy  = f.get("y", 0)
                    fh  = f.get("h", 0)
                    if fy < y_ini or (fy + fh) > y_fin:
                        # Corregir si está ligeramente fuera por redondeo
                        f["y"] = max(y_ini, min(fy, y_fin - 1))
                        f["h"] = min(fh, y_fin - f["y"])
                    fields_validos.append(f)

                print(f"[Gemini] Franja {idx+1}: {len(fields_validos)} campos.")
                todos_los_campos.extend(fields_validos)

                # Guardar JSON de cada franja para debug
                Path(debug_dir).mkdir(parents=True, exist_ok=True)
                suffix = f"_page_{page_num}" if page_num is not None else ""
                franja_path = Path(debug_dir) / f"franja_{idx+1}{suffix}.json"
                franja_path.write_text(
                    json.dumps(parsed, indent=2, ensure_ascii=False), encoding="utf-8"
                )

            except Exception as e:
                print(f"[Gemini] Franja {idx+1} falló: {e}")
                continue

        deduplicados = self._deduplicar(todos_los_campos)
        print(f"[Gemini] Total tras deduplicar: {len(deduplicados)} campos únicos.")

        # Guardar JSON consolidado
        output_path = Path(debug_dir) / f"gemini_response_page_{page_num}.json"
        output_path.write_text(
            json.dumps({"fields": deduplicados}, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )

        return deduplicados

    # ─────────────────────────────────────────────
    # PROMPT con contexto de franja
    # ─────────────────────────────────────────────

    def _construir_prompt(self, expected_fields, y_ini, y_fin):
        return f"""
ROL: Eres un sistema OCR especializado en formularios en papel.
Tu ÚNICA función es localizar zonas VACÍAS de escritura, no texto impreso.

TAREA: Localizar las coordenadas de llenado para estos campos: {expected_fields}

═══════════════════════════════════════════════════════════
CALIBRACIÓN DE ESCALA — LEE ESTO ANTES DE CUALQUIER COSA
═══════════════════════════════════════════════════════════
Esta imagen es una FRANJA de la página completa.
La grilla visible tiene números rojos que muestran coordenadas ABSOLUTAS reales:
  → Eje X: 0 a 1000 (izquierda a derecha de la página completa)
  → Eje Y: {y_ini} a {y_fin} (posición real dentro de la página completa)

USA los números de la grilla directamente como tus coordenadas.
NUNCA reportes Y fuera del rango {y_ini}-{y_fin}.
NUNCA reportes X fuera del rango 0-1000.

═══════════════════════════════════════════════════════════
PRINCIPIO FUNDAMENTAL
═══════════════════════════════════════════════════════════
Un campo de llenado es SIEMPRE un espacio vacío, nunca texto impreso.

SEÑALES de que SÍ es un campo:
  → Espacio en blanco después de una etiqueta
  → Línea fina horizontal impresa (_____)
  → Recuadro con borde fino y vacío por dentro
  → Texto gris claro o subrayado (placeholder)

SEÑALES de que NO es un campo:
  → Texto en negrita o con color → es una ETIQUETA, ignórala
  → Título de sección o encabezado de columna
  → Texto ya impreso dentro de un recuadro

═══════════════════════════════════════════════════════════
CADENA DE RAZONAMIENTO — APLICA A CADA CAMPO
═══════════════════════════════════════════════════════════
  [1] ¿Dónde está la etiqueta de este campo en la imagen?
  [2] ¿Qué hay inmediatamente DESPUÉS o DEBAJO de esa etiqueta?
  [3] ¿Ese espacio está vacío? → Sí: úsalo. No: busca el siguiente vacío.
  [4] ¿Las coordenadas caen sobre espacio blanco? → Sí: reporta. No: corrige.

═══════════════════════════════════════════════════════════
REGLAS POR TIPO
═══════════════════════════════════════════════════════════
CHECKBOXES:
  → x,y = esquina superior izquierda de la figura vacía (cuadrado o círculo).
  → w = h, entre 12 y 20. Nunca más de 22.
  → Grupo en fila → mismo 'y', distinto 'x'.

FECHAS (dd / mm / aaaa):
  → 3 campos separados, mismo 'y', distinto 'x'.
  → dd: w 30-50 | mm: w 30-50 | aaaa: w 60-90 | h: 10-16.
  → (y + h) toca la línea base impresa.

TEXTO CORTO:   w 30-80,   h 10-18
TEXTO MEDIO:   w 80-350,  h 10-20
TEXTO LARGO:   w 300-970, h 10-22
NÚMERO:        w 50-200,  h 10-18

═══════════════════════════════════════════════════════════
ALINEACIÓN
═══════════════════════════════════════════════════════════
  → Misma fila → mismo 'y' (±5), distinto 'x'.
  → Filas distintas → 'y' diferente (mínimo 10 unidades).
  → Nunca (x + w) > 1000.
  → Nunca (y + h) > {y_fin}.

═══════════════════════════════════════════════════════════
AUTO-REVISIÓN ANTES DE RESPONDER
═══════════════════════════════════════════════════════════
  [A] ¿Algún campo cae sobre texto en negrita? → muévelo al vacío adyacente.
  [B] ¿Algún checkbox con w o h > 22? → reduce a máximo 20.
  [C] ¿Dos campos distintos con mismo 'y'? → corrige el segundo.
  [D] ¿Algún (x+w) > 1000 o (y+h) > {y_fin}? → recorta.
  [E] ¿Algún campo con 'y' fuera de {y_ini}-{y_fin}? → corrige o descarta.
  [F] ¿Faltan campos de {expected_fields}? → agrégalos con w=0, h=0.

═══════════════════════════════════════════════════════════
EJEMPLO CORRECTO
═══════════════════════════════════════════════════════════
Campo 'ciudad_solicitud':
  [1] Etiqueta "Ciudad" en negrita → es la etiqueta, no el campo.
  [2] Debajo hay espacio en blanco con línea fina.
  [3] Vacío ✓  [4] Cae en blanco ✓
  → x:248, y:128, w:222, h:25

Campo 'solicitud_nuevo_chk':
  [1] Etiqueta "Nuevo" a la izquierda del cuadro.
  [2] A la derecha hay cuadro pequeño con borde fino vacío.
  [3] Vacío ✓  [4] Cae en blanco ✓
  → x:574, y:148, w:17, h:17

═══════════════════════════════════════════════════════════
RESPONDE SOLO CON JSON, sin markdown, sin texto adicional:
═══════════════════════════════════════════════════════════
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

    # ─────────────────────────────────────────────
    # TWO-PASS: VERIFICACIÓN
    # ─────────────────────────────────────────────

    def _verificar_y_corregir(self, image_pil, fields_detectados):
        try:
            img_anotada  = image_pil.copy().convert("RGBA")
            draw         = ImageDraw.Draw(img_anotada, "RGBA")
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
                    fill    = (0, 180, 0, 70)  if tipo == "checkbox" else (220, 30, 30, 70)
                    outline = (0, 160, 0, 255) if tipo == "checkbox" else (220, 30, 30, 255)
                    draw.rectangle([(x1, y1), (x2, y2)], fill=fill, outline=outline, width=2)
                    draw.text((x1 + 2, y1 + 2), fid[:12], fill=(255, 255, 255, 255))
                except Exception:
                    continue

            prompt_v = f"""
Eres un verificador de coordenadas en formularios.
Rectángulos rojos = campo de texto. Verdes = checkbox.

Verifica si cada rectángulo cubre ÚNICAMENTE espacio vacío de escritura.
Si cubre texto impreso o etiqueta en negrita → está MAL.

Para cada campo:
- CORRECTO → mismas coordenadas
- MAL → coordenadas corregidas al espacio vacío real
- NO ENCONTRADO → w=0, h=0

Coordenadas 0-1000. NUNCA fuera de rango.
Campos: {[f.get('id') for f in fields_detectados]}

JSON estricto sin markdown:
{{
  "fields": [
    {{"id":"...","tipo":"...","x":0,"y":0,"w":0,"h":0,"fontSize":9,"align":"left"}}
  ]
}}
"""
            response   = self._llamar_gemini(img_anotada.convert("RGB"), prompt_v)
            clean      = response.text.replace("```json", "").replace("```", "").strip()
            corregidos = json.loads(clean).get("fields", [])
            print(f"[Gemini][2pass] {len(corregidos)} campos verificados.")
            return corregidos if isinstance(corregidos, list) and corregidos else fields_detectados

        except Exception as e:
            print(f"[Gemini][2pass] Falló, usando detección original: {e}")
            return fields_detectados

    # ─────────────────────────────────────────────
    # PUNTO DE ENTRADA PRINCIPAL
    # ─────────────────────────────────────────────

    def analyze_form_page(self, image_pil, expected_fields, page_num=None, debug_dir="temp"):
        # Paso 1: detección por franjas
        fields = self._procesar_por_franjas(image_pil, expected_fields, debug_dir, page_num)

        # Paso 2: two-pass verificación sobre imagen completa
        fields = self._verificar_y_corregir(image_pil, fields)
        print(f"[Gemini] Final: {len(fields)} campos tras verificación.")

        return fields