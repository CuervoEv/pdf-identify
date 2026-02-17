# Ejemplos de Payloads

## 📋 Ejemplo 1: Formulario Simple de Registro

### Formulario PDF:
```
┌──────────────────────────────────┐
│     FORMULARIO DE REGISTRO       │
├──────────────────────────────────┤
│ Nombre completo: _____________   │
│                                  │
│ Correo electrónico: _____________│
│                                  │
│ Teléfono: _____________          │
│                                  │
│ DNI/Cédula: _____________        │
│                                  │
│ ☐ Acepto términos y condiciones │
│                                  │
│ ☐ Deseo recibir ofertas         │
└──────────────────────────────────┘
```

### JSON de Entrada:
```json
{
  "nombre": "Juan Carlos Pérez García",
  "correo": "juan.perez@example.com",
  "telefono": "+34 555-123-456",
  "dni": "12345678-A",
  "acepta_terminos": "X",
  "recibir_ofertas": ""
}
```

### cURL:
```bash
curl -X POST http://localhost:8000/fill-document \
  -F "file=@formulario_registro.pdf" \
  -F 'json_data={"nombre":"Juan Carlos Pérez García","correo":"juan.perez@example.com","telefono":"+34 555-123-456","dni":"12345678-A","acepta_terminos":"X","recibir_ofertas":""}' \
  --output resultado_registro.pdf
```

### Python:
```python
import requests
import json

data = {
    "nombre": "Juan Carlos Pérez García",
    "correo": "juan.perez@example.com",
    "telefono": "+34 555-123-456",
    "dni": "12345678-A",
    "acepta_terminos": "X",
    "recibir_ofertas": ""
}

with open("formulario_registro.pdf", "rb") as f:
    files = {"file": f}
    form_data = {"json_data": json.dumps(data)}
    response = requests.post(
        "http://localhost:8000/fill-document",
        files=files,
        data=form_data
    )
    
    if response.status_code == 200:
        with open("resultado_registro.pdf", "wb") as out:
            out.write(response.content)
        print("✓ PDF rellenado")
    else:
        print(f"✗ Error: {response.status_code}")
```

---

## 📋 Ejemplo 2: Solicitud Comercial

### Formulario PDF:
```
┌──────────────────────────────────────────┐
│    SOLICITUD DE COTIZACIÓN COMERCIAL    │
├──────────────────────────────────────────┤
│ Empresa: _____________________________   │
│                                          │
│ Contacto: _____________________________  │
│                                          │
│ Teléfono: _____________________________  │
│                                          │
│ Email: _____________________________     │
│                                          │
│ Dirección: _____________________________│
│                                          │
│ Cantidad solicitada: _____________________
│                                          │
│ Descripción de necesidad:                │
│ _____________________________________    │
│ _____________________________________    │
│ _____________________________________    │
│                                          │
│ ☐ Presupuesto urgente (< 24h)           │
│                                          │
│ ☐ Conozco el producto                   │
└──────────────────────────────────────────┘
```

### JSON de Entrada:
```json
{
  "empresa": "Tech Solutions SPA",
  "contacto": "María López Jiménez",
  "telefono": "+56 9 1234 5678",
  "email": "maria.lopez@techsolutions.cl",
  "direccion": "Calle Principal 456, Edificio A, Piso 3",
  "cantidad": "500 unidades",
  "descripcion": "Necesitamos cables de red Cat6 para expansión de oficinas",
  "presupuesto_urgente": "X",
  "conoce_producto": "X"
}
```

### cURL:
```bash
curl -X POST http://localhost:8000/fill-document \
  -F "file=@solicitud_comercial.pdf" \
  -F 'json_data={"empresa":"Tech Solutions SPA","contacto":"María López Jiménez","telefono":"+56 9 1234 5678","email":"maria.lopez@techsolutions.cl","direccion":"Calle Principal 456, Edificio A, Piso 3","cantidad":"500 unidades","descripcion":"Necesitamos cables de red Cat6 para expansión de oficinas","presupuesto_urgente":"X","conoce_producto":"X"}' \
  --output resultado_solicitud.pdf
```

---

## 📋 Ejemplo 3: Formulario de Excel

### Estructura Excel:
```
┌─────────────────────────────────┐
│ A             │ B               │
├─────────────────────────────────┤
│ Nombre        │ [       ]       │
│ Compañía      │ [       ]       │
│ Posición      │ [       ]       │
│ Email         │ [       ]       │
│ Región        │ [       ]       │
│ Ventas (M$)   │ [       ]       │
└─────────────────────────────────┘
```

### JSON de Entrada:
```json
{
  "nombre": "Roberto Martínez",
  "compania": "Global Consulting Inc.",
  "posicion": "Director de Ventas",
  "email": "rmartinez@globalconsulting.com",
  "region": "Sudamérica",
  "ventas": "2.5"
}
```

### cURL:
```bash
curl -X POST http://localhost:8000/fill-document \
  -F "file=@ventas_report.xlsx" \
  -F 'json_data={"nombre":"Roberto Martínez","compania":"Global Consulting Inc.","posicion":"Director de Ventas","email":"rmartinez@globalconsulting.com","region":"Sudamérica","ventas":"2.5"}' \
  --output resultado_report.xlsx
```

---

## 📋 Ejemplo 4: Contrato Simple

### JSON de Entrada (texto largo):
```json
{
  "fecha": "12/02/2026",
  "nombre_parte_a": "Juan Carlos Empresa S.A.",
  "direccion_parte_a": "Avenida Principal 123, Oficina 45, Código Postal 28001",
  "nombre_parte_b": "Servicios Profesionales y Consultoría Ltda.",
  "direccion_parte_b": "Calle Secundaria 456, Código Postal 28002",
  "objeto_contrato": "Prestación de servicios de consultoría en transformación digital, incluyendo análisis de procesos, diseño de soluciones tecnológicas e implementación de sistemas",
  "duracion": "12 meses",
  "monto": "$15.000.000 CLP",
  "acepta_terminos": "X",
  "testigo_1": "",
  "testigo_2": ""
}
```

**Nota sobre auto-ajuste de fuente**: 
- "objeto_contrato" es muy largo
- El sistema automáticamente reducirá la fuente para que encaje
- De 12pt → 10pt → 8pt si es necesario

---

## 📋 Ejemplo 5: Múltiples Checkboxes

### JSON (Solo se marca lo que tiene valor):
```json
{
  "tipo_cliente": "empresa",
  "industria_tecnologia": "X",
  "industria_finanzas": "",
  "industria_manufactura": "",
  "industria_retail": "X",
  "servicio_consultoria": "X",
  "servicio_implementacion": "X",
  "servicio_soporte": "",
  "soporte_24_7": "",
  "soporte_horario_laboral": "X"
}
```

**Lógica**: 
- Si tiene cualquier valor no vacío → se marca con X
- Si está vacío o no existe → no se marca

---

## 📋 Ejemplo 6: Manejo de Errores

### Error 400: Archivo no proporcionado
```bash
curl -X POST http://localhost:8000/fill-document \
  -F 'json_data={"test":"data"}'

# Respuesta:
# {"detail":"No file provided"}
```

### Error 400: JSON inválido
```bash
curl -X POST http://localhost:8000/fill-document \
  -F "file=@formulario.pdf" \
  -F 'json_data={json_invalido}'

# Respuesta:
# {"detail":"JSON inválido: Expecting value: line 1 column 1"}
```

### Error 400: Tipo de archivo no soportado
```bash
curl -X POST http://localhost:8000/fill-document \
  -F "file=@documento.txt" \
  -F 'json_data={"test":"data"}'

# Respuesta:
# {"detail":"Tipo de archivo no soportado: .txt. Use PDF o XLSX"}
```

### Error 413: Archivo muy grande
```bash
# Si el archivo excede 50MB

# Respuesta:
# {"detail":"Archivo muy grande. Máximo: 50MB"}
```

### Error 500: Campos faltantes
```bash
curl -X POST http://localhost:8000/fill-document \
  -F "file=@formulario.pdf" \
  -F 'json_data={"nombre":"Juan"}'

# Si el formulario también tiene campo "dni" detectado por Gemini:

# Respuesta:
# {"detail":"Error al procesar documento: Campos detectados pero sin datos en JSON: dni"}
```

---

## 🔗 Endpoints Disponibles

### 1. Health Check
```bash
GET /health

# Respuesta 200:
{"status":"ok","message":"Servicio operativo"}
```

### 2. Rellenar Documento
```bash
POST /fill-document

Content-Type: multipart/form-data

Parámetros:
- file: archivo PDF o XLSX (requerido)
- json_data: string JSON con datos (requerido)

# Respuesta 200:
<binary archivo rellenado>

# Headers de respuesta:
Content-Type: application/octet-stream
Content-Disposition: attachment; filename=filled_original_name.pdf
```

---

## 💾 Respuesta JSON de Gemini (Interno)

Cuando Gemini analiza el formulario, retorna:

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
      "alto_estimado": 35
    },
    {
      "id": "correo",
      "etiqueta": "Correo:",
      "tipo": "texto",
      "coordenadas_x": 300,
      "coordenadas_y": 250,
      "ancho_estimado": 450,
      "alto_estimado": 35
    },
    {
      "id": "acepta_terminos",
      "etiqueta": "Acepta términos",
      "tipo": "checkbox",
      "coordenadas_x": 200,
      "coordenadas_y": 400,
      "ancho_estimado": 30,
      "alto_estimado": 30
    }
  ]
}
```

Los IDs retornados por Gemini deben coincidir con las claves en json_data.

---

## 🧪 Script Python de Testing

```python
#!/usr/bin/env python
"""Script para testing del microservicio"""

import requests
import json
from pathlib import Path

BASE_URL = "http://localhost:8000"

def test_form(pdf_path: str, data: dict) -> bool:
    """Prueba el endpoint con un PDF y JSON"""
    
    print(f"Procesando: {pdf_path}")
    print(f"Datos: {json.dumps(data, indent=2)}")
    
    with open(pdf_path, "rb") as f:
        files = {"file": f}
        form_data = {"json_data": json.dumps(data)}
        
        try:
            response = requests.post(
                f"{BASE_URL}/fill-document",
                files=files,
                data=form_data,
                timeout=60
            )
            
            if response.status_code == 200:
                output = f"resultado_{Path(pdf_path).stem}.pdf"
                with open(output, "wb") as out:
                    out.write(response.content)
                print(f"✓ Éxito: {output}\n")
                return True
            else:
                print(f"✗ Error {response.status_code}: {response.text}\n")
                return False
        
        except Exception as e:
            print(f"✗ Excepción: {str(e)}\n")
            return False

# Ejemplos
if __name__ == "__main__":
    # Test 1: Registro
    test_form("formulario_registro.pdf", {
        "nombre": "Juan Pérez",
        "correo": "juan@example.com",
        "telefono": "555-1234",
        "dni": "12345678",
        "acepta_terminos": "X"
    })
    
    # Test 2: Comercial
    test_form("solicitud_comercial.pdf", {
        "empresa": "Tech Solutions",
        "contacto": "María López",
        "cantidad": "100",
        "presupuesto_urgente": "X"
    })
```

---

## 📊 Resumen Campos Soportados

| Tipo | Ejemplo | Valor | Resultado |
|------|---------|-------|-----------|
| Texto | nombre | "Juan Pérez" | "Juan Pérez" insertado |
| Texto largo | descripción | "Este es un texto muy largo..." | Fuente auto-ajustada |
| Checkbox vacío | acepta | "" | No se marca |
| Checkbox marcado | acepta | "X" | Se marca con X |
| Número | cantidad | "100" | "100" insertado |
| Email | email | "user@domain.com" | "user@domain.com" insertado |
| Fecha | fecha | "12/02/2026" | "12/02/2026" insertado |
| Teléfono | telefono | "+34 555-1234" | "+34 555-1234" insertado |
| Dirección | direccion | "Calle 123, Apt 4" | "Calle 123, Apt 4" insertado |

---

¡Ya tienes todos los ejemplos para comenzar a usar el microservicio!
