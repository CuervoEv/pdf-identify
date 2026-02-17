# Llenado Inteligente de Documentos - FastAPI Microservicio

Microservicio que automáticamente rellena formularios PDF y Excel usando visión por IA (Gemini 3 Flash).

## Características

- 🤖 **Análisis Visual Inteligente**: Detecta campos de entrada usando Gemini 3 Flash
- 📄 **Soporte Multi-formato**: PDF y Excel (XLSX)
- 🎯 **Razonamiento Espacial**: Identifica espacio de respuesta (no etiquetas)
- ✅ **Campos Flexibles**: Texto multilínea con auto-ajuste de fuente + checkmarks
- ⚡ **Rápido y Escalable**: Procesamiento por página, coordinadas normalizadas

## Arquitectura

```
LlenadoFormulariosAutomaticos/
├── src/
│   ├── main.py                 # Aplicación FastAPI
│   ├── services/
│   │   ├── gemini_service.py  # Análisis visual con Gemini
│   │   ├── pdf_filler.py       # Inserción en PDF (PyMuPDF)
│   │   └── excel_filler.py     # Inserción en Excel (openpyxl)
│   └── utils/
│       ├── image_converter.py  # Conversión de formatos
│       └── helpers.py          # Funciones auxiliares
├── config/
│   └── settings.py            # Configuración (env variables)
├── temp/                      # Archivos temporales
├── requirements.txt           # Dependencias Python
├── .env                       # Variables de entorno (GEMINI_API_KEY)
└── README.md                  # Este archivo
```

## Instalación

### Requisitos Previos
- Python 3.11.9
- pip o conda
- Clave de API de Google Gemini

### Pasos

1. **Clonar o descargar el proyecto**
   ```bash
   cd LlenadoFormulariosAutomaticos
   ```

2. **Crear entorno virtual** (recomendado)
   ```bash
   python -m venv venv
   # Windows
   venv\Scripts\activate
   # Linux/Mac
   source venv/bin/activate
   ```

3. **Instalar dependencias**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configurar variables de entorno**
   ```bash
   # Copiar template
   cp .env.example .env
   
   # Editar .env y agregar tu GEMINI_API_KEY
   # GEMINI_API_KEY=tu_clave_aqui
   ```

5. **Instalar poppler (requerido para pdf2image en Windows)**
   ```bash
   # Windows (con choco)
   choco install poppler
   
   # O descargar desde: https://github.com/oschwartz10612/poppler-windows/releases/
   # Y agregar al PATH
   ```

## Uso

### Iniciar Servidor

```bash
python -m uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

El servidor estará disponible en: `http://localhost:8000`

### API Endpoints

#### Health Check
```http
GET /health
```

Response:
```json
{
  "status": "ok",
  "message": "Servicio operativo"
}
```

#### Rellenar Documento
```http
POST /fill-document
Content-Type: multipart/form-data

file: <archivo PDF o XLSX>
json_data: {"campo_id": "valor", ...}
```

**Ejemplo con cURL:**

```bash
curl -X POST http://localhost:8000/fill-document \
  -F "file=@formulario.pdf" \
  -F 'json_data={"nombre": "Juan Pérez", "dni": "12345678", "acepta_terminos": "X"}' \
  --output resultado.pdf
```

**Ejemplo con Python:**

```python
import requests
import json

with open("formulario.pdf", "rb") as f:
    files = {"file": f}
    data = {
        "json_data": json.dumps({
            "nombre": "Juan Pérez",
            "dni": "12345678",
            "acepta_terminos": "X"
        })
    }
    response = requests.post("http://localhost:8000/fill-document", files=files, data=data)
    
    if response.status_code == 200:
        with open("resultado.pdf", "wb") as out:
            out.write(response.content)
```

## Flujo de Procesamiento

### PDF
1. Convertir cada página a imagen (PDF → PNG)
2. Enviar imagen a Gemini 3 Flash
3. Gemini detecta campos: etiqueta, tipo (texto/checkbox), coordenadas normalizadas [0-1000]
4. Validar que todos los campos tienen datos en JSON
5. Redimensionar coordenadas a escala PDF
6. Insertar texto con auto-ajuste de fuente
7. Insertar "X" centrada en checkboxes
8. Guardar PDF modificado
9. Retornar como StreamingResponse

### Excel
1. Convertir hoja a imagen
2. Enviar a Gemini (mismo análisis)
3. Convertir coordenadas a referencias de celda (A1, B2, etc.)
4. Priorizar celdas combinadas si existen
5. Insertar valor e insertar altura/ancho automáticamente
6. Guardar XLSX
7. Retornar como StreamingResponse

## Detalles Técnicos

### Detección de Campos (Gemini Prompt)

El prompt instruye a Gemini para:
- Identificar **etiquetas** (ej: "Nombre:")
- Localizar el **espacio vacío adyacente** (respuesta del usuario)
- Clasificar como **"texto"** o **"checkbox"**
- Retornar coordenadas **normalizadas [0-1000]**

Respuesta JSON esperada:
```json
{
  "campos": [
    {
      "id": "campo_nombre",
      "etiqueta": "Nombre:",
      "tipo": "texto",
      "coordenadas_x": 250,
      "coordenadas_y": 100,
      "ancho_estimado": 400,
      "alto_estimado": 30
    },
    {
      "id": "campo_acepta",
      "etiqueta": "¿Acepta términos?",
      "tipo": "checkbox",
      "coordenadas_x": 150,
      "coordenadas_y": 400,
      "ancho_estimado": 30,
      "alto_estimado": 30
    }
  ]
}
```

### Auto-ajuste de Fuente (PDF)

Para campos de texto largos:
- Fuente inicial: 12pt
- Si texto > 40 caracteres: reduce -2pt
- Si texto > 80 caracteres: reduce -4pt
- Si texto > 150 caracteres: reduce -6pt
- Mínimo: 6pt, Máximo: 36pt

Implementación: `src/services/pdf_filler.py` → `_calculate_font_size()`

### Checkmarks (PDF)

- Identifica **centro** del checkbox
- Dibuja **"X"** con líneas diagonales
- Tamaño: 80% del recuadro
- Grosor: 2px

Implementación: `src/services/pdf_filler.py` → `_insert_checkbox()`

### Excel - Mapeo de Coordenadas

Convierte [0-1000] a referencias de celda:
- Eje X (0-1000) → Columnas (A-Z)
- Eje Y (0-1000) → Filas (1+)

Ejemplo:
- X=250, Y=100 → Columna F, Fila 10 → "F10"

Ajusta ancho de columna automáticamente según contenido.

## Manejo de Errores

| Código | Descripción |
|--------|------------|
| 400 | Archivo no proporcionado, JSON inválido, tipo no soportado |
| 413 | Archivo excede tamaño máximo (50MB) |
| 500 | Error procesando documento (Gemini, conversión, I/O) |

## Limitaciones Actuales

1. **Excel a imagen**: Implementación simplificada (dibuja grid + contenido). En producción, usar LibreOffice headless.
2. **Rotación**: Los formularios deben estar rectos (sin ángulos)
3. **Múltiples checkboxes**: Cada checkbox se considera independiente
4. **Campos opcionales**: Actualmente todos los campos detectados son obligatorios

## Mejoras Futuras

- [ ] Soporte para campos opcionales
- [ ] OCR para rellenar automáticamente si hay datos preexistentes
- [ ] Detección de tablas multi-fila
- [ ] Generación automática de IDs de campo
- [ ] Caché de análisis Gemini
- [ ] Webhook para procesamiento asincrónico
- [ ] Soporte para firmas digitales

## Dependencias

- **fastapi**: Framework web
- **uvicorn**: Servidor ASGI
- **google-generativeai**: API Gemini
- **pdf2image**: Conversión PDF → imagen
- **pymupdf (fitz)**: Edición de PDF
- **openpyxl**: Edición de Excel
- **pillow**: Procesamiento de imágenes
- **python-dotenv**: Cargar variables de entorno

## Troubleshooting

### "ModuleNotFoundError: No module named 'poppler'"
```bash
# Windows con Chocolatey
choco install poppler

# Alternativamente, descargar desde:
# https://github.com/oschwartz10612/poppler-windows/releases/
```

### "google.generativeai.types.generation_types.StopCandidateException"
- Verificar que GEMINI_API_KEY es válida
- Verificar cuota de API en Google Cloud Console

### "RuntimeError: Error while finding fitz"
- Reinstalar pymupdf: `pip install --upgrade pymupdf`

## Licencia

Proyecto de demostración. Usar según necesidades.

## Contacto

Para preguntas o reportes, crear un issue en el repositorio.
