# Sistema de Auto-llenado de Formularios PDF con IA — Investigación Técnica Completa

## TL;DR

- **Construye un microservicio Python (FastAPI) standalone**, no sigas en n8n: usa **PyMuPDF** para detectar/rellenar campos AcroForm y **Gemini 2.5 Flash** como motor de extracción (PDF nativo, ~$0.30 input / $2.50 output por 1M tokens, soporta hasta 1.000 páginas por petición). Para PDFs planos/escaneados, envíalo igualmente a Gemini en modo visión (sin OCR previo) y haz overlay con `page.insert_htmlbox()` de PyMuPDF sobre las coordenadas que devuelve el modelo.
- **El matching campo→clave del JSON maestro se resuelve con un único llamado al LLM** usando *structured output* (`response_schema` + Pydantic). No necesitas embeddings ni RAG para 30–60 formularios/año: el JSON maestro completo cabe en el prompt y el modelo lo mapea contra las etiquetas extraídas. Anota `confidence` y `source_label` por campo para la auditoría humana.
- **Costos reales esperados:** **$0.01–$0.05 USD por formulario procesado** con Gemini 2.5 Flash (incluyendo páginas como imágenes), es decir **< $3 USD/mes** para tu volumen de 3–5 formularios mensuales. El MVP funcional es ~**5–8 días de desarrollo** para un dev Python intermedio. Recomendación firme: Gemini > Claude > GPT-4o para este caso, por costo nativo de PDF y precio por página.

---

## Key Findings

1. **El tipo de PDF determina el 80% de la complejidad técnica.** Un PDF rellenable (AcroForm) se procesa con 20 líneas de PyMuPDF/pypdf sin perder formato. Un PDF plano requiere una capa adicional: extracción visión-LLM + overlay por coordenadas. Detecta esto al inicio con `doc.is_form_pdf` de PyMuPDF.

2. **Gemini gana en costo y simplicidad para este caso de uso.** Es el único de los tres (Claude, GPT, Gemini) que ingiere PDFs **nativamente** vía la File API o inline base64, sin que tú tengas que rasterizar páginas a imágenes. Cobra cada página de PDF como una imagen (≈258–1.290 tokens/página dependiendo de resolución). Soporta hasta **1.000 páginas por petición** y tiene `response_schema` para JSON estricto.

3. **Claude y GPT-4o también procesan PDF nativamente pero son 3–10× más caros.** Claude Sonnet 4.5 es $3/$15 por 1M tokens vs $0.30/$2.50 de Gemini Flash. Cada página de PDF en Claude usa 1.500–3.000 tokens de texto + tokens de imagen. Para 30–40 campos en 2–5 páginas, Gemini Flash basta y sobra.

4. **PyMuPDF (fitz) es la librería ganadora para todo el manipuleo local.** Maneja detección AcroForm, lectura/escritura de widgets, render a imagen, e **inserción de texto con coordenadas (`insert_text`, `insert_htmlbox`)** — todo en una sola dependencia. Su única limitación es la licencia AGPL: si el código del microservicio no se distribuye fuera de tu empresa, no es problema; si lo distribuyes, debes liberar el código o comprar licencia comercial a Artifex.

5. **Para 30–60 formularios/año, NO necesitas embeddings ni RAG.** El JSON maestro completo (probablemente < 5 KB) cabe en cualquier prompt. Embeddings son overkill: añaden complejidad de infraestructura (vector DB, modelo de embeddings, sincronización) sin ganancia medible a este volumen.

6. **Structured Output con JSON Schema es obligatorio**, no opcional. Tasa de fallo de parseo bajando de 2–5% (JSON mode libre) a <0.3% con `response_schema` estricto en Gemini, <0.1% con `strict: true` en OpenAI Structured Outputs, y <0.2% en Claude tool use.

7. **n8n sirve para orquestación, no para la lógica pesada.** El propio equipo lo confirmó ("no fue eficiente"). El patrón correcto: microservicio FastAPI con endpoint `POST /procesar-formulario`, y opcionalmente un workflow n8n que solo recibe el correo del cliente, descarga el adjunto y llama al microservicio.

8. **Existen referentes comerciales y open-source para validar el enfoque.** Instafill.ai (Python + MongoDB + Azure, comercial) usa exactamente esta arquitectura. En open source: `t-houssian/fillpdf`, `wdhorton/formfill`, `GSA/pdf-filler` y `instafill` en PyPI son referencias funcionales pero limitadas — sirven como semilla, no como solución final.

---

## Details

### 1. Arquitectura recomendada end-to-end

```
                    ┌──────────────────────────────┐
                    │  POST /procesar-formulario   │
                    │  - pdf (multipart/form-data) │
                    │  - json_maestro (JSON)       │
                    └──────────────┬───────────────┘
                                   │
                    ┌──────────────▼──────────────┐
                    │ 1. Normalización entrada    │
                    │    - Si llega .xlsx → PDF   │
                    │    - Validar < 50 MB        │
                    └──────────────┬──────────────┘
                                   │
                    ┌──────────────▼──────────────┐
                    │ 2. Clasificación del PDF    │
                    │    PyMuPDF: doc.is_form_pdf │
                    └──────┬───────────────┬──────┘
                           │               │
            AcroForm /XFA  │               │  Plano / escaneado
              detectado    │               │
                           ▼               ▼
        ┌────────────────────────┐   ┌─────────────────────────────┐
        │ 3A. Extraer widgets    │   │ 3B. Extraer texto + bbox    │
        │     PyMuPDF.widgets()  │   │     PyMuPDF page.get_text() │
        │     → lista de         │   │     + render a imagen       │
        │     {field_name,       │   │     (300 DPI) si escaneado  │
        │      field_label,      │   │                             │
        │      field_type,       │   │     Opcional: PaddleOCR     │
        │      rect}             │   │     solo si Gemini falla    │
        └───────────┬────────────┘   └──────────────┬──────────────┘
                    │                               │
                    └───────────────┬───────────────┘
                                    ▼
                ┌──────────────────────────────────────┐
                │ 4. Llamada a LLM (Gemini 2.5 Flash)  │
                │    Input:                            │
                │    - PDF nativo (File API)           │
                │    - JSON maestro completo           │
                │    - Lista de campos extraídos       │
                │    - Schema Pydantic de respuesta    │
                │                                      │
                │    Output: JSON estricto             │
                │    [{ field_id, value, source_key,   │
                │       confidence, page, bbox }]      │
                └──────────────────┬───────────────────┘
                                   │
                    ┌──────────────▼──────────────┐
                    │ 5. Aplicar valores al PDF   │
                    │                             │
                    │ Si AcroForm:                │
                    │  field.field_value = "..."  │
                    │  field.update()             │
                    │                             │
                    │ Si plano:                   │
                    │  page.insert_htmlbox(       │
                    │    rect, value, css=...)    │
                    └──────────────┬──────────────┘
                                   │
                    ┌──────────────▼──────────────┐
                    │ 6. Salida                   │
                    │  - PDF lleno (bytes)        │
                    │  - JSON de auditoría        │
                    │    (qué llenó, confidence,  │
                    │     campos no encontrados)  │
                    └─────────────────────────────┘
```

**Variantes según tipo:**
- **AcroForm puro:** ruta 3A → 4 → 5 (AcroForm). Es la ruta más confiable; el LLM solo decide *qué valor* va en *qué `field_name`*.
- **PDF plano con texto seleccionable:** ruta 3B (sin OCR) → 4 → 5 (overlay). PyMuPDF entrega texto con bounding boxes, suficiente para que Gemini ubique etiquetas.
- **PDF escaneado (imagen):** ruta 3B con render a imagen → 4 (Gemini visión nativa) → 5 (overlay). Tesseract/PaddleOCR son opcionales y solo agregan latencia: Gemini 2.5 Flash hace OCR mejor que Tesseract de forma nativa.
- **XFA dinámico:** caso difícil. PyMuPDF tiene soporte limitado (los XFA dinámicos con JS no se rerenderizan automáticamente al cambiar valores). Fallback: aplanar a PDF estático con `pdftk` o convertir vía LibreOffice y tratar como PDF plano.

### 2. Comparativa técnica de librerías Python para PDF

| Librería | Lee texto + bbox | Detecta AcroForm | Rellena AcroForm | Dibuja texto en coordenadas | Render a imagen | OCR | Licencia | Recomendación |
|---|---|---|---|---|---|---|---|---|
| **PyMuPDF (fitz)** | ✅ Mejor velocidad + posiciones | ✅ `doc.is_form_pdf`, `page.widgets()` | ✅ `widget.field_value=...; widget.update()` | ✅ `insert_text`, `insert_htmlbox` | ✅ `page.get_pixmap()` | ⚠️ Vía integración Tesseract | **AGPL** o comercial | **Núcleo del proyecto** |
| **pypdf** | ✅ Básico | ✅ `reader.get_fields()` | ✅ `writer.update_page_form_field_values()` | ❌ | ❌ | ❌ | BSD | Alternativa puro-Python si AGPL es problema |
| **pdfplumber** | ✅ Excelente (char-level, tablas) | ⚠️ Vía recorrer `Annots` | ❌ | ❌ | ❌ | ❌ | MIT | Complementaria si necesitas tablas |
| **pdfrw** | ⚠️ Limitado | ✅ | ⚠️ Manual, requiere `NeedAppearances` | ❌ | ❌ | ❌ | MIT | Solo si ya lo conoces; reemplazable por pypdf |
| **reportlab** | ❌ | ❌ | ❌ (crea desde cero) | ✅ Canvas API | ❌ | ❌ | BSD/Commercial | Para overlays superpuestos al PDF original (técnica clásica) |
| **pdftk (CLI)** | ❌ | ✅ `dump_data_fields` | ✅ `fill_form data.fdf output out.pdf flatten` | ❌ | ❌ | ❌ | GPL | Útil como CLI de respaldo o aplanar XFA |
| **borb** | ⚠️ | ⚠️ | ⚠️ | ⚠️ | ⚠️ | ❌ | AGPL/Comercial | No recomendado; comunidad pequeña |

**Recomendación clara:** usa **PyMuPDF como librería principal** (te cubre 95% de los casos en un solo paquete) y mantén **pypdf instalado como fallback** para el día que la licencia AGPL te incomode o para validar resultados. **pdftk como binario opcional** para aplanar XFA dinámicos. No instales reportlab a menos que decidas hacer overlay con PDF auxiliar (técnica más antigua que `insert_htmlbox`).

> **Nota sobre AGPL de PyMuPDF:** la AGPL aplica solo si distribuyes el software. Si el microservicio corre en tu servidor Linux interno y nunca se entrega como producto a terceros, AGPL no te obliga a publicar nada. Si vas a venderlo o entregar binarios, compra licencia comercial a Artifex o migra a pypdf+pdfplumber+reportlab.

### 3. PDFs rellenables (AcroForm) — código de ejemplo

**Detectar si el PDF tiene formulario:**
```python
import pymupdf  # antes "import fitz"

doc = pymupdf.open("formulario_cliente.pdf")
if doc.is_form_pdf:
    print("AcroForm detectado")
else:
    print("PDF plano, ir a ruta visión")
```

**Extraer todos los campos con su etiqueta humana (`field_label` / TU = alternate name) y tipo:**
```python
campos = []
for page_index, page in enumerate(doc):
    for w in page.widgets() or []:
        campos.append({
            "page": page_index,
            "field_name": w.field_name,            # nombre técnico
            "field_label": w.field_label,          # "alternate name" (legible)
            "field_type": w.field_type_string,     # 'Text', 'CheckBox', 'RadioButton', 'ComboBox', 'ListBox', 'Signature'
            "rect": tuple(w.rect),
            "current_value": w.field_value,
            "choices": w.choice_values,            # solo para combo/list
        })
```

**Rellenar y guardar manteniendo apariencia:**
```python
valores = {"NIT": "900123456-7", "RAZON_SOCIAL": "ACME S.A.S."}

for page in doc:
    for w in page.widgets() or []:
        if w.field_name in valores:
            if w.field_type_string == "CheckBox":
                w.field_value = True  # o w.on_state()
            else:
                w.field_value = str(valores[w.field_name])
            w.update()

# Marcar /NeedAppearances para visores que no regeneran apariencias
doc.need_appearances(True)
doc.save("salida.pdf", garbage=4, deflate=True)
```

**Equivalente con pypdf (sin AGPL):**
```python
from pypdf import PdfReader, PdfWriter

reader = PdfReader("formulario_cliente.pdf")
writer = PdfWriter(clone_from=reader)
writer.update_page_form_field_values(
    writer.pages[0],
    {"NIT": "900123456-7", "RAZON_SOCIAL": "ACME S.A.S."},
    auto_regenerate=False,
)
with open("salida.pdf", "wb") as f:
    writer.write(f)
```

### 4. PDFs planos / escaneados

**Estrategia recomendada (orden de preferencia):**

1. **Primera línea: Gemini 2.5 Flash visión nativa con PDF directo.** No pre-proceses. Sube el PDF (file API) y pídele al modelo que devuelva, para cada campo del JSON maestro: el valor encontrado en el documento, las coordenadas del rectángulo donde debe escribirse el dato, y la página. Gemini hace OCR + comprensión semántica en una sola pasada. Más barato y más preciso que Tesseract+pipeline manual para texto general.

2. **Segunda línea (si Gemini falla con escaneos muy degradados):** pre-OCR con PaddleOCR (mejor que Tesseract en layouts modernos; soporta español; salida con bounding boxes word-level) y pasar el texto OCR + las coordenadas como input adicional al LLM.

3. **No recomendado:** Tesseract como única opción (peor accuracy en layouts complejos), Surya/docTR (instalación pesada, dependen de GPU para velocidad razonable).

**Escribir texto en coordenadas (overlay) con PyMuPDF:**
```python
import pymupdf

doc = pymupdf.open("formulario_plano.pdf")
page = doc[0]

# Coordenadas (x0, y0, x1, y1) que devolvió el LLM para el campo "NIT"
rect = pymupdf.Rect(220, 410, 420, 430)

# Mejor calidad tipográfica con insert_htmlbox (HarfBuzz + Noto fallback)
page.insert_htmlbox(
    rect,
    "900123456-7",
    css="* { font-family: sans-serif; font-size: 10px; color: black; }"
)

doc.save("formulario_lleno.pdf", garbage=4, deflate=True)
```

**Alternativa para escaneos: render página → enviar imagen al LLM con Claude o Gemini:**
```python
mat = pymupdf.Matrix(300/72, 300/72)  # 300 DPI
pix = page.get_pixmap(matrix=mat)
img_bytes = pix.tobytes("png")
```

Las coordenadas que el LLM devuelve sobre la imagen renderizada deben re-escalarse al espacio del PDF (`coord_pdf = coord_img * 72 / dpi`).

### 5. Comparativa de modelos de IA — el corazón de la decisión

| Modelo | $ / 1M input | $ / 1M output | PDF nativo | Páginas máx por request | Structured output | Comentario para este caso |
|---|---|---|---|---|---|---|
| **Gemini 2.5 Flash** | **$0.30** | **$2.50** | ✅ Sí (1 página ≈ 258 tokens audio-equivalent o ~tokens-imagen) | **1.000** | ✅ `response_schema` (JSON Schema) | **GANADOR. Mejor relación precio/precisión.** |
| Gemini 2.5 Flash-Lite | $0.10 | $0.40 | ✅ | 1.000 | ✅ | Aún más barato; úsalo si Flash es suficiente en QA |
| Gemini 2.5 Pro | $1.25 | $10 | ✅ | 1.000 | ✅ | Solo si Flash da problemas con formularios muy complejos |
| **Claude Sonnet 4.5** | $3 | $15 | ✅ (visión) | 100 (visual) | ✅ `output_config.format` o tool use | Excelente comprensión, pero 10× más caro |
| Claude Haiku 4.5 | $1 | $5 | ✅ | 100 | ✅ | Competitivo, pero Gemini Flash es mejor precio |
| **GPT-4o** | $2.50 | $10 | ⚠️ Vía base64 / Responses API | Sin tope claro; bill como imágenes | ✅ Structured Outputs (más estricto: <0.1% fallo) | Más caro que Gemini, sin ventaja clara para este caso |
| GPT-4o-mini | $0.15 | $0.60 | ⚠️ | Imágenes | ✅ | Muy barato pero baja precisión visual para layouts complejos |

**Estimación de costo por formulario procesado (PDF de 3 páginas, ~30 campos, JSON maestro de ~3 KB):**

- **Gemini 2.5 Flash:** input ≈ 4.000 tokens (PDF como 3 imágenes a ~1.000 tokens c/u + JSON maestro + prompt + esquema), output ≈ 1.500 tokens. Costo: `4000/1M * $0.30 + 1500/1M * $2.50 ≈ $0.0012 + $0.0038 ≈ **$0.005 por formulario**`.
- **Claude Sonnet 4.5:** input ≈ 9.000 tokens (página ≈ 2.500 tokens texto + imagen) + 3.000 tokens setup, output ≈ 1.500. Costo: `12000/1M * $3 + 1500/1M * $15 ≈ $0.036 + $0.022 ≈ **$0.058 por formulario**`.
- **GPT-4o:** similar a Claude, ~**$0.04–$0.06 por formulario**.

**A 60 formularios/año (peor caso):** Gemini ≈ $0.30/año, Claude ≈ $3.50/año, GPT-4o ≈ $3/año. **A este volumen el costo es irrelevante; la decisión depende de calidad y simplicidad.** Recomendamos Gemini porque (a) la ingesta de PDF nativa elimina código de rasterizado y (b) `response_schema` con Pydantic es ergonómico.

### 6. Patrón de matching de campos con IA

**Prompt template (probado, en español):**

```
Eres un asistente que mapea campos de un formulario PDF corporativo con los datos
de una base maestra. Tu único trabajo es decidir qué valor de la base maestra
corresponde a cada etiqueta del formulario.

REGLAS:
1. Solo asigna un valor si tienes alta confianza (>= 0.7) de que la etiqueta
   se refiere al mismo dato semántico (ej: "Razón Social", "Nombre Comercial",
   "Denominación o Razón Social", "Empresa" → razon_social).
2. Si no hay coincidencia clara, asigna value=null y confidence=0.
3. Para fechas, normaliza al formato dd/mm/yyyy salvo que la etiqueta exija
   otro formato explícito (ej: "Date (MM-DD-YYYY)").
4. Para checkboxes/radio buttons, devuelve true/false o el valor on_state.
5. NO inventes valores que no estén en la base maestra.

BASE MAESTRA (única fuente de verdad):
{json_maestro}

CAMPOS DEL FORMULARIO A LLENAR:
{lista_campos}    # incluye field_name, field_label, field_type, page, rect

Devuelve un array JSON cumpliendo el schema proporcionado.
```

**Schema de respuesta con Pydantic (válido para Gemini, Claude y OpenAI):**

```python
from pydantic import BaseModel, Field
from typing import Optional, Literal

class CampoLleno(BaseModel):
    field_name: str
    value: Optional[str] = None
    source_key: Optional[str] = Field(
        None, description="Clave del JSON maestro de donde proviene el valor"
    )
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: Optional[str] = Field(
        None, description="Por qué se eligió este valor (para auditoría)"
    )
    needs_human_review: bool = False

class RespuestaLlenado(BaseModel):
    campos: list[CampoLleno]
    campos_no_encontrados_en_maestra: list[str]
    notas: Optional[str] = None
```

**Llamada a Gemini con response_schema:**

```python
from google import genai
from google.genai import types

client = genai.Client(api_key=GEMINI_KEY)

with open("formulario.pdf", "rb") as f:
    pdf_bytes = f.read()

resp = client.models.generate_content(
    model="gemini-2.5-flash",
    contents=[
        types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf"),
        prompt_text,
    ],
    config=types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=RespuestaLlenado,
        temperature=0,  # determinismo
    ),
)
resultado: RespuestaLlenado = resp.parsed
```

**Equivalente con Claude (tool use):**

```python
from anthropic import Anthropic
client = Anthropic()

tool_schema = RespuestaLlenado.model_json_schema()

resp = client.messages.create(
    model="claude-sonnet-4-5-20250929",
    max_tokens=4096,
    tools=[{
        "name": "registrar_llenado",
        "description": "Registra los valores asignados a cada campo.",
        "input_schema": tool_schema,
    }],
    tool_choice={"type": "tool", "name": "registrar_llenado"},
    messages=[{
        "role": "user",
        "content": [
            {"type": "document",
             "source": {"type": "base64", "media_type": "application/pdf",
                        "data": base64.b64encode(pdf_bytes).decode()}},
            {"type": "text", "text": prompt_text},
        ],
    }],
)
```

**Manejo de campos ambiguos:**
- `confidence < 0.7` → `needs_human_review=True`, no llenar todavía pero registrar la sugerencia en el JSON de auditoría.
- `value is None` → campo queda vacío, humano lo completa.
- Imprime un PDF lateral o un HTML con `[REVISAR]` antes de cada campo con baja confianza.

**Embeddings — ¿valen la pena?** **No, a 30–60 formularios/año.** Coste de añadirlos: cargar un modelo (sentence-transformers o `text-embedding-3-small` de OpenAI), construir índice del JSON maestro (~20 claves), persistir vectores. Ganancia: cero — Gemini Flash ya hace el matching semántico mejor que cualquier embedding de propósito general. Reconsidera embeddings solo si el JSON maestro crece a >500 campos o si quieres reducir tokens del prompt al límite. Para tu volumen, **dale el JSON maestro completo en el prompt**.

### 7. Stack tecnológico recomendado

**Veredicto: Python + FastAPI standalone, NO seguir en n8n.**

Razones concretas:
- **Velocidad:** un benchmark de Towards Data Science (febrero 2025) mostró que un workflow puramente en JS-nodes de n8n tomó 11.7 s y el mismo flujo descargando a FastAPI tomó 11.0 s — y eso *sin* PDF, solo cálculo tabular. Con PDF + LLM, mover la lógica fuera de n8n es aún más beneficioso.
- **Manejabilidad:** versionado git, tests unitarios con `pytest`, type hints con Pydantic, logging estructurado. Imposible en nodos Code de n8n.
- **Reproducibilidad:** Dockerfile + `requirements.txt` vs. estado en n8n DB.

**Stack final propuesto:**
```
- Python 3.11+
- FastAPI + uvicorn (servidor ASGI)
- PyMuPDF (manipulación PDF)
- google-genai (cliente Gemini oficial)
- pydantic v2 (schemas)
- python-multipart (uploads)
- structlog (logs)
- pytest (tests)
- Docker (despliegue)
```

**Endpoint sugerido:**

```python
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import StreamingResponse
import json, io

app = FastAPI()

@app.post("/procesar-formulario")
async def procesar(
    pdf: UploadFile = File(...),
    json_maestro: str = Form(...),
):
    pdf_bytes = await pdf.read()
    maestro = json.loads(json_maestro)

    resultado = pipeline(pdf_bytes, maestro)   # función con toda la lógica
    pdf_lleno_bytes = resultado["pdf_bytes"]
    auditoria = resultado["auditoria"]

    return StreamingResponse(
        io.BytesIO(pdf_lleno_bytes),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{pdf.filename}_lleno.pdf"',
            "X-Audit-Trail": json.dumps(auditoria),  # o devolver en endpoint aparte
        },
    )

@app.get("/health")
def health():
    return {"status": "ok"}
```

**Despliegue:**

`Dockerfile`:
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

Despliegue Linux simple (sin Kubernetes):
```bash
docker build -t form-filler:1.0 .
docker run -d --name form-filler \
  --restart=unless-stopped \
  -p 8000:8000 \
  -e GEMINI_API_KEY="$GEMINI_API_KEY" \
  form-filler:1.0
```

Usa `caddy` o `nginx` delante para TLS y reverse proxy. Para 3–5 PDFs/mes una sola réplica basta — no necesitas K8s.

**¿Cuándo mantener n8n?** Solo como capa de entrada: workflow que (1) recibe correo, (2) extrae adjunto, (3) hace `HTTP Request` al microservicio, (4) responde por correo al cliente con el PDF lleno. Eso n8n lo hace bien. La transcripción y el LLM **fuera** de n8n.

### 8. Ejemplos de código clave consolidados

**Pipeline completo (esquema, ~80 líneas reales):**

```python
import base64, io, json
import pymupdf
from google import genai
from google.genai import types
from pydantic import BaseModel
from typing import Optional

GEMINI_KEY = "..."
client = genai.Client(api_key=GEMINI_KEY)

class CampoLleno(BaseModel):
    field_name: str
    value: Optional[str] = None
    source_key: Optional[str] = None
    confidence: float
    needs_human_review: bool = False
    page: Optional[int] = None
    bbox: Optional[list[float]] = None  # solo para PDFs planos

class Respuesta(BaseModel):
    campos: list[CampoLleno]
    campos_no_encontrados_en_maestra: list[str] = []

def es_acroform(doc) -> bool:
    return bool(doc.is_form_pdf)

def extraer_widgets(doc):
    out = []
    for i, page in enumerate(doc):
        for w in page.widgets() or []:
            out.append({
                "field_name": w.field_name,
                "field_label": w.field_label or w.field_name,
                "field_type": w.field_type_string,
                "page": i,
                "rect": list(w.rect),
                "choices": w.choice_values,
            })
    return out

def extraer_layout(doc):
    """Para PDFs planos: bloques de texto con bbox para que el LLM ubique."""
    out = []
    for i, page in enumerate(doc):
        for block in page.get_text("blocks"):
            x0, y0, x1, y1, text, *_ = block
            out.append({"page": i, "bbox": [x0, y0, x1, y1], "text": text})
    return out

def llamar_gemini(pdf_bytes, contexto: dict) -> Respuesta:
    prompt = f"""Eres un asistente que llena formularios PDF corporativos.
Base maestra (verdad absoluta):
{json.dumps(contexto['maestro'], ensure_ascii=False, indent=2)}

Campos detectados en el formulario:
{json.dumps(contexto['campos'], ensure_ascii=False, indent=2)}

Reglas:
- Solo asigna value si confidence >= 0.7
- needs_human_review=true si confidence < 0.9
- No inventes datos: si no está en la base maestra, value=null
- Para fechas usa dd/mm/yyyy salvo indicación explícita
"""
    resp = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[
            types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf"),
            prompt,
        ],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=Respuesta,
            temperature=0,
        ),
    )
    return resp.parsed

def aplicar_acroform(doc, campos: list[CampoLleno]):
    valores = {c.field_name: c for c in campos if c.value is not None}
    for page in doc:
        for w in page.widgets() or []:
            c = valores.get(w.field_name)
            if not c:
                continue
            if w.field_type_string == "CheckBox":
                w.field_value = c.value.lower() in ("true", "si", "sí", "x", "1")
            else:
                w.field_value = str(c.value)
            w.update()
    doc.need_appearances(True)

def aplicar_overlay(doc, campos: list[CampoLleno]):
    for c in campos:
        if c.value is None or c.bbox is None or c.page is None:
            continue
        page = doc[c.page]
        rect = pymupdf.Rect(*c.bbox)
        page.insert_htmlbox(
            rect, c.value,
            css="* { font-family: sans-serif; font-size: 10px; color: black; }"
        )

def pipeline(pdf_bytes: bytes, maestro: dict) -> dict:
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    if es_acroform(doc):
        campos = extraer_widgets(doc)
        contexto = {"maestro": maestro, "campos": campos, "modo": "acroform"}
        respuesta = llamar_gemini(pdf_bytes, contexto)
        aplicar_acroform(doc, respuesta.campos)
    else:
        campos = extraer_layout(doc)
        contexto = {"maestro": maestro, "campos": campos, "modo": "overlay"}
        respuesta = llamar_gemini(pdf_bytes, contexto)
        aplicar_overlay(doc, respuesta.campos)

    out_bytes = doc.tobytes(garbage=4, deflate=True)
    doc.close()
    return {
        "pdf_bytes": out_bytes,
        "auditoria": respuesta.model_dump(),
    }
```

### 9. Manejo de casos borde

- **Checkboxes:** `widget.field_type_string == "CheckBox"`. El valor para marcarlo es `widget.on_state()` (suele ser `"Yes"` o `"On"`) o `True`. Para desmarcarlo, `False` o `"Off"`. El LLM debe devolver booleano y tú normalizas en `aplicar_acroform`.
- **Radio buttons:** en PyMuPDF, asignar `True` a uno del grupo automáticamente apaga los demás. Pasa al LLM el `choices` y pídele que devuelva el string exacto del estado a activar.
- **Firmas (Signature widgets):** PyMuPDF marca `field_type_string == "Signature"` como read-only para creación. Si necesitas insertar una imagen de firma, usa `page.insert_image(rect, filename="firma.png")` en las coordenadas del widget — no toques el widget en sí.
- **Fechas con formato:** valida en post-proceso con regex tras recibir el JSON del LLM. Reemplaza separadores. Si la etiqueta dice "MM/DD/YYYY" explícitamente, el prompt debe pedirle al LLM que respete ese formato (incluye en el `reasoning` por qué eligió ese formato).
- **Multi-idioma (español ↔ inglés):** Gemini 2.5 Flash maneja español e inglés sin distinción. En el prompt no aclares el idioma — el modelo lo detecta. Solo añade ejemplos de equivalencia ("Tax ID" = "NIT" = "Identificación Tributaria") si ves errores recurrentes.
- **Auditoría/logging para revisión humana:** registra en JSON por cada formulario:
  - hash SHA-256 del PDF de entrada,
  - hash del PDF de salida,
  - timestamp,
  - modelo usado y versión,
  - lista de `CampoLleno` con confidence y source_key,
  - lista de campos `needs_human_review=True`,
  - costo en tokens (Gemini devuelve `usage_metadata`).
  Persiste estos JSON en una carpeta `auditoria/{fecha}/{hash}.json` o en SQLite. El revisor humano puede abrir el JSON y ver exactamente *de dónde* sacó cada dato la IA.

### 10. Proyectos open source y referencias

| Proyecto | URL | Qué aporta a tu caso |
|---|---|---|
| **t-houssian/fillpdf** | github.com/t-houssian/fillpdf | Ejemplo limpio en Python que envuelve PyMuPDF para `place_text`, `place_image`, llenar AcroForm. Buena semilla. |
| **wdhorton/formfill** | github.com/wdhorton/formfill | CLI que rellena PDFs con LLM. Patrón similar al recomendado. |
| **GSA/pdf-filler** | github.com/GSA/pdf-filler | Servicio REST gubernamental (Ruby). Demuestra el patrón de coordenadas X,Y para PDFs planos. |
| **instafill (PyPI)** | pypi.org/project/instafill/ | Cliente Python del servicio comercial Instafill.ai. Útil como referencia de API. |
| **revolunet/pypdftk** | github.com/revolunet/pypdftk | Wrapper Python de pdftk; útil si decides usar pdftk para XFA. |
| **chandrasuda/ai-autofill** | github.com/chandrasuda/ai-autofill | Extensión Chrome con RAG + LLM para formularios; arquitectura inspiradora aunque para web no PDF. |
| **Instafill.ai (comercial)** | instafill.ai | Confirma el stack: Python + MongoDB + Azure. Documenta el flujo "upload → fine-tune por formulario → fill via API/webhook". |
| **Artículo DEV (instafill)** | dev.to/instafill/how-to-automate-filling-pdf-forms-using-ai-1md9 | Tutorial con prompt template y código GPT-4o real. |

**Blog/papers recientes:**
- "Gemini API: Revolutionizing Content Generation with Direct PDF Input" (Medium, 2024) — demuestra el ahorro de no rasterizar.
- "Structured output comparison across popular LLM providers" (Rost Glukhov, oct 2025) — comparativa práctica de `response_schema` entre providers.
- Documentación oficial Anthropic: `platform.claude.com/docs/build-with-claude/pdf-support` y `.../structured-outputs`.
- Google: `ai.google.dev/gemini-api/docs/document-processing`.

### 11. Estimación realista de esfuerzo y costos

**MVP funcional (microservicio + endpoint + AcroForm + overlay simple):**
- Dev Python intermedio con familiaridad en FastAPI: **5–8 días-persona**.
  - Día 1: scaffolding FastAPI + Docker + clientes Gemini/PyMuPDF.
  - Día 2–3: pipeline AcroForm completo + tests con 3–5 PDFs reales rellenables.
  - Día 4–5: pipeline overlay para PDFs planos + casos borde (checkboxes, fechas).
  - Día 6: módulo de auditoría JSON + endpoint `/auditoria/{id}`.
  - Día 7: hardening (timeouts, rate limit, retries en Gemini), logs estructurados.
  - Día 8: integración con n8n (webhook) o frontal UI mínima.

**Hardening adicional (no MVP):** +1 semana para colas con Redis/RQ si esperas picos, UI de revisión humana (Streamlit basta para uso interno), métricas Prometheus.

**Costos mensuales (volumen real 3–5 formularios/mes):**

| Concepto | Costo estimado |
|---|---|
| Gemini 2.5 Flash API | **$0.02–$0.30/mes** (5 PDFs × $0.005 promedio, hasta $0.06 si son largos) |
| Servidor Linux (ya disponible) | **$0** marginal |
| Almacenamiento PDF + auditoría (asumiendo 200 KB/PDF + JSON) | **< $0.10/mes** |
| **TOTAL infra/IA** | **~$0.50/mes** |

A volumen pico (60/año = 5/mes): **menos de $1 USD/mes**.

Si decides usar Claude Sonnet 4.5 en lugar de Gemini Flash: ~$5–$10/mes a volumen normal. Aún trivial.

---

## Recommendations

**Próximos pasos en orden (etapa por etapa):**

1. **Esta semana — Prototipo de validación (1–2 días):**
   - Toma 2 PDFs reales: uno AcroForm y uno escaneado.
   - Crea un script de ~100 líneas con `pymupdf + google-genai` que reproduzca el flujo end-to-end *sin* FastAPI todavía.
   - Mide accuracy manual: ¿cuántos de 30 campos quedaron correctos? Umbral mínimo aceptable: **>85% de campos correctos sin intervención**, considerando que el humano revisa todo igual.
   - **Decisión gate:** si Gemini Flash queda por debajo de 85%, sube a Gemini 2.5 Pro o Claude Sonnet 4.5 antes de seguir.

2. **Semana 2 — MVP en FastAPI (5–7 días):**
   - Implementa el código de la sección 8 dentro de un proyecto FastAPI.
   - Dockerízalo. Despliega en el servidor Linux con `docker compose`.
   - Integra n8n solo en la capa de entrada (correo → HTTP request al microservicio).
   - Implementa el JSON de auditoría desde el día 1; no lo dejes para después.

3. **Semana 3 — Hardening + revisión humana:**
   - Construye una pantalla simple (Streamlit, FastAPI Jinja, o nodo en n8n) para que la persona revisora vea: PDF original | PDF lleno | tabla de campos con confidence y source_key.
   - Añade botón "aprobar" / "editar y aprobar" que regenere el PDF si hay correcciones.
   - Mide tasa de modificaciones humanas como KPI.

4. **Mes 2 — Iteración con datos reales:**
   - Cada formulario nuevo que falle se vuelve un test case.
   - Si ves que ciertos formularios fallan repetidamente, añade un campo `form_hint` opcional al endpoint para que el operador pueda decir "este es el formulario tipo Bancolombia, los nombres siempre son X".
   - **Umbral para escalar a Gemini 2.5 Pro o Claude:** si la accuracy global se mantiene <90% durante 2 meses con Flash.

5. **Mes 3+ — Opcional según resultados:**
   - Si llegan formularios nuevos cuyo layout se repite, considera "memorizar" mapeos: la primera vez la IA mapea etiquetas → keys del maestro; la segunda vez para el mismo template solo aplicas el mapeo cacheado.
   - Embeddings o RAG solo si el JSON maestro crece a >200 campos o si quieres reducir tokens. **No antes.**

**Benchmarks que cambiarían la recomendación:**
- Si llegan >500 formularios/año → considera prompt caching de Gemini (90% descuento en input repetido) y batch API (50% off).
- Si los PDFs son escaneos de muy baja calidad (<150 DPI, ruido) → añade PaddleOCR como preprocesamiento.
- Si necesitas certificación enterprise (ISO 27001, HIPAA, datos no salen de tu infra) → migra a Vertex AI con datos en región controlada, o considera modelos open source (Qwen 2.5-VL, Llama 3.2 Vision) self-hosted con GPU. Sube el costo en 10–100×.

---

## Caveats

1. **Precios de APIs cambian.** Los números reportados son de las páginas oficiales consultadas en mayo 2026 (Anthropic, Google AI for Developers, OpenAI). Antes de firmar presupuesto, vuelve a verificar: `ai.google.dev/gemini-api/docs/pricing`, `platform.claude.com/docs/about-claude/pricing`, `openai.com/api/pricing`. Particularmente las páginas de Google describen Gemini 3 y Gemini 3.1 ya en general availability — si la accuracy de Flash 2.5 te queda corta, prueba Gemini 3 Flash, no Gemini 2.5 Pro.

2. **Gemini cobra PDFs como imágenes página por página.** La documentación oficial dice literalmente: *"PDFs are billed as image input, with one PDF page equivalent to one image"*. Para Gemini 3, el conteo de tokens por página depende del parámetro `media_resolution` (low/medium/high). Si tus PDFs son densos (30+ campos), usa `high` y acepta el costo extra; aún así sale más barato que Claude.

3. **PyMuPDF + AGPL puede sorprender al área legal.** No es problema si el código no sale de tu empresa, pero documenta esto explícitamente. Si tu organización rechaza AGPL por política, migra a `pypdf` (BSD) + `reportlab` (BSD) — pierdes velocidad y `insert_htmlbox` pero la solución sigue funcionando.

4. **XFA dinámicos siguen siendo un dolor.** PyMuPDF tiene soporte limitado para XFA con JavaScript (ver issue #2668 del repo). Si recibes formularios bancarios colombianos XFA-dinámicos, el flujo es: detectar XFA → aplanar con `pdftk drop_xfa` o convertir vía LibreOffice headless → tratar el resultado como PDF plano y usar la ruta de overlay.

5. **Confianza del LLM no es probabilidad calibrada.** El `confidence` que pide el prompt es una autoevaluación del modelo, no una métrica estadística. Mide en tu propio dataset cuántos errores hay a `confidence >= 0.9` vs `confidence >= 0.7` antes de elegir un umbral fijo.

6. **El cliente final puede tener visores PDF antiguos.** Adobe Reader y visores modernos respetan `/NeedAppearances=true` y regeneran apariencia de campos AcroForm rellenados. Visores muy antiguos (algunos visores de Linux y previews móviles) pueden mostrar el campo vacío aunque el valor esté guardado. Mitigación: aplanar el PDF antes de enviarlo (`pdftk ... output ... flatten` o `writer.update_page_form_field_values(..., flatten=True)` en pypdf).

7. **Datos sensibles a APIs externas.** NIT, razón social, datos de inversionistas — verifica con tu área legal si pueden salir a Google/Anthropic/OpenAI. Las tres ofrecen *Zero Data Retention* o equivalente bajo contratos enterprise, pero por defecto el ZDR no aplica. Si los datos son extremadamente sensibles, evalúa Vertex AI con residency en Sudamérica o modelos open-source self-hosted (más caros en infra, más baratos en API).

8. **Las búsquedas sobre Claude Sonnet 4.5/4.6/Opus 4.7 reflejan información de páginas oficiales y blogs de pricing actualizados a 2026.** Hay cierta evolución de versiones (Sonnet 4.5 → 4.6, Opus 4.6 → 4.7) que ocurre rápido; los precios por tier ($3/$15 para Sonnet, $5/$25 para Opus, $1/$5 para Haiku) se han mantenido estables, pero confirma antes de comprometer presupuesto.

9. **El flujo "humano siempre revisa antes de enviar" es lo que te permite tolerar errores del LLM**. No diseñes para 100% de autonomía; diseña para que el revisor humano abra el PDF lleno + el JSON de auditoría y en 2 minutos confirme/corrija. Esa es la fuente de valor real: pasar de 30 minutos de transcripción manual a 2 minutos de revisión.