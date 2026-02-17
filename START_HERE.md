# 👋 ¡BIENVENIDO! - EMPIEZA AQUÍ

## 🎯 ¿Qué es esto?

Un **microservicio FastAPI profesional** que automáticamente rellena formularios PDF y Excel usando **Inteligencia Artificial (Gemini 3 Flash)**.

Simplemente:
1. Envía un PDF/Excel + JSON con datos
2. IA detecta campos visualmente
3. Inserta datos automáticamente
4. Recibes documento rellenado

---

## ⚡ Inicio en 5 Minutos

### Paso 1: Configurar (2 min)
```bash
# Windows
copy .env.example .env

# Linux/Mac
cp .env.example .env
```

Luego edita `.env` y agrega tu GEMINI_API_KEY:
```
GEMINI_API_KEY=tu_clave_aqui
```

### Paso 2: Instalar (2 min)
```bash
python -m venv venv

# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate

pip install -r requirements.txt
```

### Paso 3: Ejecutar (1 min)
```bash
python -m uvicorn src.main:app --reload
```

**¡Listo! El servidor está en http://localhost:8000**

### Paso 4: Probar (sin esperar)
```bash
curl http://localhost:8000/health
# Deberías ver: {"status":"ok","message":"Servicio operativo"}
```

---

## 📝 Ejemplo Simple

```bash
curl -X POST http://localhost:8000/fill-document \
  -F "file=@tu_formulario.pdf" \
  -F 'json_data={"nombre":"Juan Pérez","dni":"12345678"}' \
  --output resultado.pdf
```

**¡El PDF rellenado estará en resultado.pdf!**

---

## 📚 Documentación por Tipo de Usuario

### 👤 Soy Principiante
**→ Lee [QUICKSTART.md](QUICKSTART.md)**
- Instalación paso a paso
- Primeros ejemplos
- Comandos básicos

### 👨‍💻 Soy Desarrollador
**→ Lee [ARCHITECTURE.md](ARCHITECTURE.md)**
- Estructura del código
- Cómo funciona
- Flujos de datos

### 🔬 Quiero Entender la IA
**→ Lee [VISION_LOGIC.md](VISION_LOGIC.md)**
- Cómo detecta campos
- Razonamiento espacial
- Detalles técnicos

### 🚀 Voy a Producción
**→ Lee [DEPLOYMENT.md](DEPLOYMENT.md)**
- Docker
- Google Cloud
- AWS
- Instrucciones paso a paso

### 📋 Necesito Ejemplos
**→ Lee [EXAMPLES.md](EXAMPLES.md)**
- 6 ejemplos completos
- Payloads JSON
- cURL y Python

### 🔍 Busco Algo Específico
**→ Lee [INDEX.md](INDEX.md)**
- Índice completo de documentación
- Búsqueda rápida por tema

---

## 🗂️ ¿Qué Archivos Hay?

```
LlenadoFormulariosAutomaticos/
├── 📚 Documentación
│   ├── QUICKSTART.md          ← Empieza aquí
│   ├── README.md              ← Guía completa
│   ├── EXAMPLES.md            ← Ejemplos
│   └── 6 documentos más...
├── 💻 Código
│   ├── src/main.py            ← FastAPI app
│   ├── src/services/          ← Servicios
│   └── src/utils/             ← Utilidades
├── 🐳 Docker
│   ├── Dockerfile
│   └── docker-compose.yml
├── ⚙️ Configuración
│   ├── requirements.txt
│   ├── .env.example
│   └── .gitignore
└── 🚀 Scripts
    ├── run_server.bat
    └── run_server.sh
```

---

## 🎯 Necesitas...

| Necesidad | Ir a |
|-----------|------|
| Instalar rápido | [QUICKSTART.md](QUICKSTART.md) |
| Información completa | [README.md](README.md) |
| Ver ejemplos | [EXAMPLES.md](EXAMPLES.md) |
| Entender la IA | [VISION_LOGIC.md](VISION_LOGIC.md) |
| Comandos rápidos | [COMMANDS.md](COMMANDS.md) |
| Desplegar en producción | [DEPLOYMENT.md](DEPLOYMENT.md) |
| Navegación general | [INDEX.md](INDEX.md) |
| Checklist de lo hecho | [COMPLETION_CHECKLIST.md](COMPLETION_CHECKLIST.md) |

---

## ✨ Características Principales

🤖 **Inteligencia Artificial**
- Usa Gemini 3 Flash
- Detecta campos visualmente
- Identifica etiquetas y espacios vacíos
- Diferencia texto de checkboxes

📄 **Procesamiento de Documentos**
- PDF: conversión, análisis, inserción
- Excel: análisis, inserción en celdas
- Auto-ajuste de fuente y dimensiones

⚡ **Rápido y Fácil**
- API REST simple
- Multipart/form-data
- Streaming de respuesta
- Manejo de errores completo

🔒 **Seguro**
- Variables de entorno
- Validación de entrada
- Limites de tamaño
- Archivos temporales limpios

---

## 🚀 Casos de Uso

✅ Rellenar formularios masivos automáticamente  
✅ Automatizar procesos de administración  
✅ Procesar solicitudes en lote  
✅ Extraer e insertar datos de aplicaciones  
✅ Integrar con tus sistemas  

---

## 🔧 Stack Tecnológico

- **Backend**: FastAPI + Uvicorn
- **IA**: Google Gemini 3 Flash
- **PDF**: PyMuPDF (fitz)
- **Excel**: openpyxl
- **Imágenes**: Pillow
- **Config**: python-dotenv
- **Deployment**: Docker, Docker Compose

---

## 🆘 Problemas Comunes

**"ModuleNotFoundError"**
→ Ejecuta: `pip install -r requirements.txt`

**"poppler not found" (Windows)**
→ Ejecuta: `choco install poppler`

**"GEMINI_API_KEY not set"**
→ Edita `.env` con tu clave

**"Port 8000 already in use"**
→ Busca [COMMANDS.md](COMMANDS.md) "Port 8000 in use"

---

## 📞 Ayuda Rápida

1. **¿Cómo empiezo?**
   → [QUICKSTART.md](QUICKSTART.md)

2. **¿Cómo lo uso?**
   → [EXAMPLES.md](EXAMPLES.md)

3. **¿Cómo funciona?**
   → [ARCHITECTURE.md](ARCHITECTURE.md)

4. **¿Cómo despliego?**
   → [DEPLOYMENT.md](DEPLOYMENT.md)

5. **¿Tengo un error?**
   → [COMMANDS.md](COMMANDS.md)

---

## 🎓 Aprende Más

**Después de instalar y probar:**

1. Lee [README.md](README.md) para entender todo
2. Revisa [EXAMPLES.md](EXAMPLES.md) para ver ejemplos reales
3. Estudia [VISION_LOGIC.md](VISION_LOGIC.md) para detalles de IA
4. Consulta [DEPLOYMENT.md](DEPLOYMENT.md) cuando vayas a producción

---

## ✅ Checklist Rápido

- [ ] Copié `.env.example` a `.env`
- [ ] Agregué mi `GEMINI_API_KEY`
- [ ] Instalé dependencias con `pip install -r requirements.txt`
- [ ] Ejecuté el servidor
- [ ] Probé con `curl http://localhost:8000/health`
- [ ] Leí [QUICKSTART.md](QUICKSTART.md)
- [ ] Probé con un formulario real

---

## 🎊 ¡Próximos Pasos!

1. **Haz los pasos de "Inicio en 5 Minutos" arriba** ↑

2. **Lee [QUICKSTART.md](QUICKSTART.md)** para más detalles

3. **Prueba con tus propios formularios**

4. **Lee [EXAMPLES.md](EXAMPLES.md)** para casos de uso

5. **Personaliza según tus necesidades**

---

## 📌 Información de Contacto / Soporte

- **Documentación**: Ver carpeta `docs/` del proyecto
- **Ejemplos**: [EXAMPLES.md](EXAMPLES.md)
- **Referencia**: [README.md](README.md)
- **Troubleshooting**: [COMMANDS.md](COMMANDS.md)

---

**¿Listo? ¡Comienza con [QUICKSTART.md](QUICKSTART.md) ahora!** 🚀

**Última actualización**: 12/02/2026  
**Versión**: 1.0.0  
**Python**: 3.11.9  
**IA**: Gemini 3 Flash
