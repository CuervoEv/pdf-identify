
# Guía de Inicio Rápido

## ✅ Prerrequisitos
- Python 3.11.9
- pip
- Clave de API de Google Gemini (obtener en: https://ai.google.dev)
- Poppler (para PDF en Windows)

## 🚀 Inicio Rápido (5 minutos)

### 1. Obtener API Key de Gemini
```bash
# Ir a: https://ai.google.dev
# 1. Sign in con tu cuenta Google
# 2. Create API Key
# 3. Copiar la clave
```

### 2. Configurar Proyecto
```bash
# Windows (PowerShell)
cd C:\Users\cmamartinez\Desktop\MicroServicios\LlenadoFormulariosAutomaticos

# Copiar template de .env
copy .env.example .env

# Editar .env y pegar tu API Key
# Abrir .env con tu editor favorito y cambiar:
# GEMINI_API_KEY=tu_clave_aqui
```

### 3. Instalar Poppler (Solo Windows)
```powershell
# Con Chocolatey
choco install poppler

# O descargar manualmente de:
# https://github.com/oschwartz10612/poppler-windows/releases/
# Agregar al PATH del sistema
```

### 4. Crear Entorno Virtual e Instalar Dependencias
```bash
# Crear venv
python -m venv venv

# Activar venv
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# Instalar dependencias
pip install -r requirements.txt
```

### 5. Iniciar Servidor
```bash
# Opción 1: Script automático (Windows)
run_server.bat

# Opción 2: Script automático (Linux/Mac)
chmod +x run_server.sh
./run_server.sh

# Opción 3: Manual
python -m uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

**Resultado esperado:**
```
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     Application startup complete
```

### 6. Probar Servidor
```bash
# En otra terminal, prueba health check:
curl http://localhost:8000/health

# Respuesta esperada:
# {"status":"ok","message":"Servicio operativo"}
```

## 📋 Estructura de Datos - JSON de Entrada

El JSON que envías debe tener el formato:
```json
{
  "campo_id_1": "valor 1",
  "campo_id_2": "valor 2",
  "campo_checkbox": "X"
}
```

**Los IDs de campo deben coincidir con los que Gemini detecta en el formulario.**

## 🧪 Testear con cURL

```bash
# Preparar JSON
$data = '{
  "nombre": "Juan Pérez",
  "dni": "12345678",
  "email": "juan@example.com"
}'

# Llamar endpoint (reemplaza tu_archivo.pdf)
curl -X POST http://localhost:8000/fill-document `
  -F "file=@tu_archivo.pdf" `
  -F "json_data=$data" `
  --output resultado.pdf
```

## 🐍 Testear con Python

```python
import requests
import json

# Datos a rellenar
data = {
    "nombre": "Juan Pérez",
    "dni": "12345678",
    "email": "juan@example.com"
}

# Enviar request
with open("formulario.pdf", "rb") as f:
    files = {"file": f}
    form_data = {"json_data": json.dumps(data)}
    
    response = requests.post(
        "http://localhost:8000/fill-document",
        files=files,
        data=form_data
    )

# Guardar resultado
if response.status_code == 200:
    with open("resultado.pdf", "wb") as out:
        out.write(response.content)
    print("✓ PDF rellenado guardado!")
else:
    print(f"Error {response.status_code}: {response.text}")
```

## 📊 Testear con Postman

1. Abrir Postman
2. Crear nuevo POST request
3. URL: `http://localhost:8000/fill-document`
4. Tab "Body" → form-data
5. Campos:
   - Key: `file` → Type: File → Seleccionar PDF
   - Key: `json_data` → Type: Text → Pegar JSON
6. Click "Send"
7. En respuesta, click "Save response" para guardar PDF

## 🔍 Solucionar Problemas

### "ModuleNotFoundError: No module named 'google'"
```bash
pip install google-generativeai
```

### "No module named 'fitz'"
```bash
pip install --upgrade pymupdf
```

### "poppler not found" (Windows)
```powershell
# Instalar poppler
choco install poppler

# O descargar: https://github.com/oschwartz10612/poppler-windows/releases/
# Agregar carpeta bin al PATH
```

### "GEMINI_API_KEY not set"
```bash
# Verificar que .env existe y tiene la clave
type .env  # Windows
cat .env   # Linux/Mac

# Si está vacío, editar y agregar:
# GEMINI_API_KEY=tu_clave_aqui
```

### "Error from Google Generative AI API"
- Verificar que la API Key es válida
- Verificar que la API está habilitada en Google Cloud
- Verificar que tienes cuota disponible

## 📚 Documentación Completa

- [README.md](README.md) - Documentación completa
- [VISION_LOGIC.md](VISION_LOGIC.md) - Detalles técnicos de detección
- [test_example.py](test_example.py) - Ejemplos de testing

## 🎯 Próximos Pasos

1. **Crear un formulario de prueba** (PDF o Excel)
2. **Ejecutar el servidor**
3. **Rellenar el formulario** usando el endpoint
4. **Revisar resultado**
5. **Iterar** si es necesario ajustar campos

## 💡 Tips

- Los IDs de campo deben ser descriptivos (ej: `campo_nombre` no `f1`)
- El JSON es sensible a mayúsculas/minúsculas
- Para checkboxes, usa cualquier valor no vacío (ej: "X", "1", "true")
- Revisa los logs del servidor para debugging

## 🆘 Support

Si encuentras problemas:
1. Revisa [VISION_LOGIC.md](VISION_LOGIC.md)
2. Prueba health check: `curl http://localhost:8000/health`
3. Revisa logs del servidor (ventana de terminal)
4. Verifica que archivo es PDF/XLSX válido
5. Asegúrate que JSON es válido

## 📝 Ejemplo Completo

**Archivo: formulario_ejemplo.pdf**
```
┌────────────────────────────────┐
│ FORMULARIO                     │
│ Nombre: [_____________]        │
│ DNI: [_____________]           │
│ ☐ Acepta términos              │
└────────────────────────────────┘
```

**Comando:**
```bash
curl -X POST http://localhost:8000/fill-document \
  -F "file=@formulario_ejemplo.pdf" \
  -F 'json_data={"nombre":"Juan Pérez","dni":"12345678A","acepta":"X"}' \
  --output resultado.pdf
```

**Resultado: resultado.pdf con todos los campos rellenados ✓**

---

¡Listo! Ya estás listo para usar el microservicio. 🚀
