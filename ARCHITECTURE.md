LlenadoFormulariosAutomaticos/
│
├── 📄 README.md                          # Documentación principal
├── 📄 QUICKSTART.md                      # Guía de inicio rápido
├── 📄 VISION_LOGIC.md                    # Documentación técnica detallada
├── 📄 requirements.txt                   # Dependencias Python
├── 📄 .env.example                       # Template de variables de entorno
├── 📄 .gitignore                         # Archivo de git
│
├── 🐚 run_server.bat                     # Script para iniciar en Windows
├── 🐚 run_server.sh                      # Script para iniciar en Linux/Mac
├── 🧪 test_example.py                    # Ejemplos de testing
│
├── 📁 config/                            # Configuración del proyecto
│   ├── __init__.py
│   └── settings.py                       # Variables de entorno y constantes
│
├── 📁 src/                               # Código fuente principal
│   ├── __init__.py
│   ├── main.py                           # FastAPI app y endpoints
│   │
│   ├── 📁 services/                      # Servicios de procesamiento
│   │   ├── __init__.py
│   │   ├── gemini_service.py             # Análisis visual con Gemini 3 Flash
│   │   ├── pdf_filler.py                 # Inserción de datos en PDF
│   │   └── excel_filler.py               # Inserción de datos en Excel
│   │
│   └── 📁 utils/                         # Utilidades
│       ├── __init__.py
│       ├── image_converter.py            # Conversión PDF/Excel → Imagen
│       └── helpers.py                    # Funciones auxiliares
│
├── 📁 temp/                              # Archivos temporales (gitignore)
│
└── .env                                  # Variables de entorno (No commitear)
                                          # Copiar de .env.example

════════════════════════════════════════════════════════════════

FLUJO DE DATOS:

Entrada (Multipart/form-data)
    ├── file: PDF/XLSX
    └── json_data: {"campo_id": "valor"}
           ↓
    [src/main.py] endpoint POST /fill-document
           ↓
    [Guardar en temp/]
           ↓
    ┌─ Si PDF ─────────────────────────────────┐
    │                                          │
    │ [image_converter.py]                     │
    │   PDF → imágenes (1 por página)         │
    │          ↓                               │
    │ [gemini_service.py]                      │
    │   Análisis visual (detecta campos)      │
    │          ↓                               │
    │ [pdf_filler.py]                          │
    │   Insertar datos (texto + checkmarks)   │
    │          ↓                               │
    │ Guardar PDF modificado                  │
    │                                          │
    └──────────────────────────────────────────┘
    
    ┌─ Si Excel ────────────────────────────────┐
    │                                           │
    │ [image_converter.py]                      │
    │   Excel → imagen (representación visual) │
    │          ↓                                │
    │ [gemini_service.py]                       │
    │   Análisis visual (detecta campos)       │
    │          ↓                                │
    │ [excel_filler.py]                         │
    │   Insertar en celdas (con auto-ajuste)  │
    │          ↓                                │
    │ Guardar XLSX modificado                  │
    │                                           │
    └───────────────────────────────────────────┘
           ↓
    Retornar como StreamingResponse
           ↓
    Cliente recibe archivo modificado

════════════════════════════════════════════════════════════════

COMPONENTES CLAVE:

1. main.py
   └─ FastAPI app
      └─ POST /fill-document
         ├─ Recibe archivo + JSON
         ├─ Valida entrada
         ├─ Delega a _process_pdf() o _process_excel()
         └─ Retorna StreamingResponse

2. gemini_service.py
   └─ GeminiVisionService
      ├─ analyze_form_page()
      │  ├─ Envía imagen a Gemini 3 Flash
      │  └─ Parsea JSON de respuesta
      └─ validate_data_against_fields()
         └─ Verifica que todos los campos tienen datos

3. pdf_filler.py
   └─ PDFFiller
      ├─ fill_page()
      │  ├─ Procesa cada campo
      │  ├─ _insert_text() → auto-ajusta fuente
      │  └─ _insert_checkbox() → dibuja X centrada
      └─ save() → guarda PDF modificado

4. excel_filler.py
   └─ ExcelFiller
      ├─ fill_cells()
      │  └─ Mapea coordenadas → referencias de celda
      ├─ _normalize_to_cell_reference()
      │  └─ Convierte [0-1000] a A1, B2, etc.
      └─ save() → guarda XLSX modificado

5. image_converter.py
   └─ ImageConverter
      ├─ pdf_to_images() → PDF → lista de PNG
      ├─ excel_to_image() → Excel → PNG (visual)
      ├─ image_to_base64() → PNG → base64 (para Gemini)
      └─ get_image_dimensions() → obtiene tamaño

════════════════════════════════════════════════════════════════

DEPENDENCIAS:

Framework:
  - fastapi: Web framework
  - uvicorn: ASGI server
  - python-multipart: Manejo multipart/form-data

IA/Visión:
  - google-generativeai: API Gemini 3 Flash

Procesamiento de Documentos:
  - PyMuPDF (fitz): Lectura y edición de PDF
  - pdf2image: Conversión PDF → imagen
  - openpyxl: Lectura y edición de Excel
  - Pillow: Procesamiento de imágenes

Configuración:
  - python-dotenv: Cargar .env
  - pydantic: Validación de datos

════════════════════════════════════════════════════════════════

VARIABLES DE ENTORNO (.env):

GEMINI_API_KEY=<tu_clave_aqui>

════════════════════════════════════════════════════════════════

CONFIGURACIÓN (config/settings.py):

- TEMP_DIR: Directorio para archivos temporales
- MAX_FILE_SIZE: Tamaño máximo (50MB)
- DEFAULT_FONT_NAME: Arial
- DEFAULT_FONT_SIZE: 12pt
- MIN_FONT_SIZE: 6pt
- MAX_FONT_SIZE: 36pt
- COORDINATE_SCALE: 1000 (normalización Gemini)

════════════════════════════════════════════════════════════════

PROMPT GEMINI (core logic):

"Analiza esta imagen de un formulario/documento y detecta TODOS los campos de entrada.

IMPORTANTE:
- NO proporciones coordenadas de las ETIQUETAS.
- Proporciona las coordenadas del ESPACIO VACÍO.
- El espacio vacío es adyacente a la etiqueta.

Para CADA campo, retorna JSON con:
- id: identificador único
- etiqueta: texto de la etiqueta
- tipo: 'texto' o 'checkbox'
- coordenadas_x: [0-1000]
- coordenadas_y: [0-1000]
- ancho_estimado: [0-1000]
- alto_estimado: [0-1000]

Tipos:
- texto: área de entrada de texto
- checkbox: casilla de verificación

Coordenadas:
- [0,0] = esquina superior izquierda
- [1000,1000] = esquina inferior derecha

Responde SOLO con JSON."

════════════════════════════════════════════════════════════════

ENDPOINTS:

GET /health
  └─ Verifica que el servicio está operativo

POST /fill-document
  ├─ Request:
  │  ├─ file (multipart): PDF o XLSX
  │  └─ json_data (string): JSON con datos
  │
  ├─ Response (200):
  │  └─ File (binary): Documento rellenado
  │
  └─ Errors:
     ├─ 400: Archivo/JSON inválido
     ├─ 413: Archivo muy grande
     └─ 500: Error procesando

════════════════════════════════════════════════════════════════

EJEMPLO DE USO:

$ curl -X POST http://localhost:8000/fill-document \
    -F "file=@formulario.pdf" \
    -F 'json_data={"nombre":"Juan","dni":"123","acepta":"X"}' \
    --output resultado.pdf

✓ resultado.pdf descargado con todos los campos rellenados

════════════════════════════════════════════════════════════════
