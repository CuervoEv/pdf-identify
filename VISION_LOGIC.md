# Documentación Técnica - Lógica de Visión y Razonamiento Espacial

## 1. Flujo de Detección de Campos (Gemini 3 Flash)

### 1.1 Proceso General

```
Documento Original (PDF/Excel)
    ↓
Conversión a Imagen (1 página/imagen)
    ↓
Envío a Gemini 3 Flash + Prompt Especializado
    ↓
Análisis Visual (Etiquetas vs Espacios Vacíos)
    ↓
Retorno JSON con Campos Detectados
    ↓
Validación contra JSON de Datos
    ↓
Inserción en Documento Original
```

### 1.2 Prompt de Visión (Specializado)

**Objetivo**: Que Gemini distinga entre:
1. **Etiquetas** (ej: "Nombre:", "DNI:")
2. **Espacios vacíos** (donde va la respuesta)
3. **Tipos de campo** (texto o checkbox)

**Prompt Actual** (en `src/services/gemini_service.py`):

```
Analiza esta imagen de un formulario/documento y detecta TODOS los campos de entrada.

IMPORTANTE:
- NO proporciones coordenadas de las ETIQUETAS (ej. "Nombre:").
- Proporciona las coordenadas del ESPACIO VACÍO donde debe insertarse la respuesta.
- El espacio vacío es adyacente a la etiqueta (a la derecha o debajo).

Para CADA campo detectado, retorna un JSON con esta estructura:
{
  "campos": [
    {
      "id": "campo_identificador_único",
      "etiqueta": "texto de la etiqueta",
      "tipo": "texto" o "checkbox",
      "coordenadas_x": número entre 0-1000,
      "coordenadas_y": número entre 0-1000,
      "ancho_estimado": número entre 0-1000,
      "alto_estimado": número entre 0-1000
    }
  ]
}
```

**Parámetros de Generación**:
- `temperature`: 0.2 (bajo = determinístico)
- `top_p`: 0.9
- `top_k`: 40

### 1.3 Normalización de Coordenadas

Las coordenadas se normalizan a escala **[0, 1000]** para independencia de resolución:

```
[0, 0]     ─────────── [1000, 0]
  ┌─────────────────────────┐
  │                         │
  │    Documento/Página     │
  │                         │
  └─────────────────────────┘
[0, 1000]  ─────────── [1000, 1000]
```

**Ventajas**:
- Independiente de DPI de la imagen
- Fácil de rescalar a cualquier dimensión
- Precisión consistente

## 2. Detección de Espacios Vacíos vs Etiquetas

### 2.1 Lógica Visual

El prompt instruye a Gemini para:

1. **Identificar etiqueta**
   - Buscar texto seguido de ":" o similar
   - Ejemplo: "Nombre:", "Teléfono:"

2. **Localizar espacio vacío adyacente**
   - Puede estar **a la derecha** (formularios horizontales)
   - O **debajo** (formularios verticales)
   - Identificar por: línea en blanco, caja, o área vacía clara

3. **Calcular coordenadas del espacio**
   - NO de la etiqueta
   - DEL ESPACIO VACÍO (esquina superior izquierda)

### 2.2 Ejemplos de Detección

#### Ejemplo 1: Formulario Horizontal
```
┌─────────────────────────────────────────┐
│ Nombre: ┌──────────────────────────┐   │
│         │  [ESPACIO VACÍO]         │   │
│         └──────────────────────────┘   │
└─────────────────────────────────────────┘

Gemini debe retornar:
- etiqueta: "Nombre:"
- coordenadas_x: 150 (inicio del espacio)
- coordenadas_y: 100 (inicio del espacio)
```

#### Ejemplo 2: Formulario Vertical
```
┌──────────────────────────────┐
│ Nombre:                      │
│ ┌─────────────────────────┐  │
│ │   [ESPACIO VACÍO]       │  │
│ └─────────────────────────┘  │
│                              │
│ Teléfono:                    │
│ ┌─────────────────────────┐  │
│ │   [ESPACIO VACÍO]       │  │
│ └─────────────────────────┘  │
└──────────────────────────────┘

Gemini retorna múltiples campos con coordenadas Y distintas
```

#### Ejemplo 3: Checkbox
```
┌────────────────────────────────┐
│ ☐ Acepta términos y condiciones│
│                                │
│ ☐ Recibir newsletter           │
└────────────────────────────────┘

Gemini identifica:
- tipo: "checkbox"
- coordenadas_x: 120, coordenadas_y: 50 (centro del recuadro)
```

## 3. Tipos de Campo

### 3.1 Campo de Texto

**Características**:
- Áreas vacías rectangulares
- Pueden tener bordes o estar en blanco
- Altura generalmente de 20-50 píxeles para una línea
- Múltiples líneas si es de gran altura

**Inserción**:
- Convertir coordenadas [0-1000] a píxeles PDF
- Auto-ajustar fuente si el texto es muy largo
- Respetar márgenes internos (padding)

**Auto-ajuste de fuente**:
```python
def _calculate_font_size(text, width, height):
    font_size = 12  # Default
    
    if len(text) > 40:
        font_size -= 2
    if len(text) > 80:
        font_size -= 4
    if len(text) > 150:
        font_size -= 6
    
    return max(6, min(font_size, 36))
```

### 3.2 Campo Checkbox

**Características**:
- Pequeños recuadros (generalmente 15-30 píxeles)
- Pueden tener marca (☑) o vacío (☐)
- Generalmente cuadrados

**Inserción**:
- Calcular **centro** del recuadro
- Dibujar "X" diagonal (dos líneas)
- Tamaño de X = 80% del recuadro
- Grosor = 2px

**Fórmula del Centro**:
```
center_x = x_inicio + (ancho / 2)
center_y = y_inicio + (alto / 2)

x_size = min(ancho, alto) * 0.4

Línea 1: (center_x - x_size, center_y - x_size) a (center_x + x_size, center_y + x_size)
Línea 2: (center_x - x_size, center_y + x_size) a (center_x + x_size, center_y - x_size)
```

## 4. Conversión de Coordenadas

### 4.1 PDF: De Imagen a PDF

```
Imagen (150 DPI):
- Width: 1200px, Height: 1600px
- Coordenadas Gemini: [250, 150] (normalizadas)

Conversión:
1. norm_x = 250 / 1000 = 0.25
2. norm_y = 150 / 1000 = 0.15

3. pdf_x = 0.25 * page_width
4. pdf_y = 0.15 * page_height

Ejemplo (page_width=595pt, page_height=842pt):
- pdf_x = 0.25 * 595 = 148.75pt
- pdf_y = 0.15 * 842 = 126.3pt
```

### 4.2 Excel: De Imagen a Celda

```
Imagen:
- Coordenadas Gemini: [250, 150]

Conversión (heurística):
1. col_index = (250 / 1000) * 26 + 1 = 7.5 → 7 (columna G)
2. row_index = (150 / 1000) * 100 + 1 = 16 (fila 16)

Resultado: "G16"
```

## 5. Validación de Datos

### 5.1 Validación en Tiempo de Detección

```python
for campo in campos_detectados:
    # Validar estructura
    assert 'id' in campo
    assert 'tipo' in campo
    assert campo['tipo'] in ['texto', 'checkbox']
    
    # Validar coordenadas
    assert 0 <= campo['coordenadas_x'] <= 1000
    assert 0 <= campo['coordenadas_y'] <= 1000
```

### 5.2 Validación de Datos Proporcionados

```python
field_ids = {campo['id'] for campo en campos}
data_ids = set(json_data.keys())

missing = field_ids - data_ids

if missing:
    raise Error(f"Campos faltantes: {missing}")
```

## 6. Flujo Completo Ejemplo

### Entrada: Formulario PDF

```
┌────────────────────────────────┐
│ FORMULARIO DE REGISTRO         │
├────────────────────────────────┤
│ Nombre:  ┌──────────────────┐  │
│          │                  │  │
│          └──────────────────┘  │
│                                │
│ DNI:     ┌──────────────────┐  │
│          │                  │  │
│          └──────────────────┘  │
│                                │
│ ☐ Acepta términos              │
└────────────────────────────────┘
```

### Paso 1: Convertir a Imagen
```
formulario.pdf → página1.png (1200x1600 @ 150 DPI)
```

### Paso 2: Enviar a Gemini
```json
{
  "image": "data:image/png;base64,...",
  "prompt": "Analiza esta imagen..."
}
```

### Paso 3: Respuesta Gemini
```json
{
  "campos": [
    {
      "id": "nombre",
      "etiqueta": "Nombre:",
      "tipo": "texto",
      "coordenadas_x": 300,
      "coordenadas_y": 150,
      "ancho_estimado": 450,
      "alto_estimado": 30
    },
    {
      "id": "dni",
      "etiqueta": "DNI:",
      "tipo": "texto",
      "coordenadas_x": 300,
      "coordenadas_y": 300,
      "ancho_estimado": 450,
      "alto_estimado": 30
    },
    {
      "id": "acepta",
      "etiqueta": "Acepta términos",
      "tipo": "checkbox",
      "coordenadas_x": 150,
      "coordenadas_y": 450,
      "ancho_estimado": 30,
      "alto_estimado": 30
    }
  ]
}
```

### Paso 4: Validar Datos JSON
```json
{
  "nombre": "Juan Pérez",
  "dni": "12345678A",
  "acepta": "X"
}
```

✓ Todos los campos tienen datos

### Paso 5: Insertar en PDF

```python
# Campo "nombre"
pdf_x = 0.3 * 595 = 178.5pt
pdf_y = 0.15 * 842 = 126.3pt
texto = "Juan Pérez"
fuente = 12pt
→ Insertar en PDF

# Campo "dni"
pdf_x = 0.3 * 595 = 178.5pt
pdf_y = 0.3 * 842 = 252.6pt
texto = "12345678A"
fuente = 12pt
→ Insertar en PDF

# Campo "acepta" (checkbox)
center_x = (150/1000 * 595) + 15 = 104.25pt
center_y = (450/1000 * 842) + 15 = 391.9pt
→ Dibujar X centrada
```

### Paso 6: Guardar y Retornar
```
formulario_rellenado.pdf → Cliente (StreamingResponse)
```

## 7. Casos Edge y Manejo

### 7.1 Texto Muy Largo

**Problema**: Texto no cabe en el área detectada

**Solución**:
```
1. Medir ancho del área (ancho_estimado)
2. Si texto > 40 char → font_size -= 2
3. Si texto > 80 char → font_size -= 4
4. Si texto > 150 char → font_size -= 6
5. Mínimo: 6pt, Máximo: 36pt
6. Si aún no cabe → insertar con salto de línea
```

### 7.2 Checkbox Muy Pequeño

**Problema**: Área detectada es muy pequeña para X

**Solución**:
```
x_size = min(ancho, alto) * 0.4  # Escalar proporcionalmente
Si x_size < 5px → usar mínimo 5px
```

### 7.3 Campo No Detectado

**Problema**: Gemini no detecta un campo presente

**Solución**:
1. Validación lanza error
2. Usuario debe revisar formulario o prompt
3. Opción: ajustar prompt para campos específicos

### 7.4 Coordenadas Fuera de Rango

**Problema**: Gemini retorna coordenadas > 1000

**Solución**:
```python
# Validación
if coordenadas_x > 1000 or coordenadas_x < 0:
    raise ValueError("Coordenada X fuera de rango")
```

## 8. Optimizaciones Futuras

1. **Machine Learning para precisión**: Entrenar modelo con formularios reales
2. **Cache de análisis**: Memorizar resultados de Gemini
3. **OCR nativo**: Extraer texto preexistente para completar automáticamente
4. **Análisis de patrón**: Detectar patrón de formulario (grillas, columnas)
5. **Firma digital**: Integración con herramientas de firma

## 9. Referencia: Métodos Clave

| Módulo | Método | Responsabilidad |
|--------|--------|-----------------|
| `gemini_service.py` | `analyze_form_page()` | Envía imagen a Gemini, parsea respuesta |
| `gemini_service.py` | `validate_data_against_fields()` | Valida que datos cubren todos campos |
| `pdf_filler.py` | `fill_page()` | Orquesta inserción en página PDF |
| `pdf_filler.py` | `_insert_text()` | Inserta texto con auto-ajuste fuente |
| `pdf_filler.py` | `_insert_checkbox()` | Dibuja X en checkbox |
| `pdf_filler.py` | `_calculate_font_size()` | Calcula fuente óptima |
| `excel_filler.py` | `fill_cells()` | Inserta en celdas Excel |
| `excel_filler.py` | `_normalize_to_cell_reference()` | Convierte [0-1000] a celda |

