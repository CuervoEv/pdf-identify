# Comandos Rápidos de Referencia

## 🚀 Inicio Rápido

```bash
# Windows
copy .env.example .env
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python -m uvicorn src.main:app --reload

# Linux/Mac
cp .env.example .env
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python -m uvicorn src.main:app --reload
```

## 🧪 Testing

```bash
# Health check
curl http://localhost:8000/health

# Test PDF (PowerShell)
$data = '{"nombre":"Juan","dni":"123"}'
curl -X POST http://localhost:8000/fill-document `
  -F "file=@formulario.pdf" `
  -F "json_data=$data" `
  -o resultado.pdf

# Test PDF (Bash)
curl -X POST http://localhost:8000/fill-document \
  -F "file=@formulario.pdf" \
  -F 'json_data={"nombre":"Juan","dni":"123"}' \
  -o resultado.pdf

# Test con Python
python test_example.py
```

## 📦 Dependencias

```bash
# Instalar todas
pip install -r requirements.txt

# Instalar específicas
pip install fastapi uvicorn
pip install google-generativeai
pip install pdf2image pymupdf pillow
pip install openpyxl
pip install python-dotenv

# Actualizar
pip install --upgrade -r requirements.txt

# Ver instaladas
pip list

# Exportar (después de cambios)
pip freeze > requirements.txt
```

## 🐳 Docker

```bash
# Construir imagen
docker build -t form-filler:latest .

# Ejecutar contenedor
docker run -p 8000:8000 -e GEMINI_API_KEY=tu_clave form-filler:latest

# Con Docker Compose
docker-compose up -d
docker-compose down
docker-compose logs -f

# Ver imágenes y contenedores
docker images
docker ps -a

# Limpiar
docker prune -a
```

## 🔍 Debugging

```bash
# Ver logs detallados
python -m uvicorn src.main:app --reload --log-level debug

# Python debugger
python -m pdb script.py

# Verificar import
python -c "import google.generativeai; print('OK')"

# Validar JSON
python -m json.tool data.json

# Check .env
cat .env
echo %GEMINI_API_KEY%  # Windows
echo $GEMINI_API_KEY   # Linux/Mac
```

## 📁 Archivos Importantes

```bash
# Ver estructura
tree /F  # Windows
tree -L 2  # Linux/Mac

# Listar archivos Python
dir /s *.py  # Windows
find . -name "*.py"  # Linux/Mac

# Ver contenido de archivo
type archivo.py  # Windows
cat archivo.py   # Linux/Mac

# Buscar en archivos
findstr "texto" *.py  # Windows
grep -r "texto" .     # Linux/Mac
```

## 🔧 Mantenimiento

```bash
# Limpiar archivos temporales
del temp\*  # Windows
rm -rf temp/*  # Linux/Mac

# Limpiar cache Python
del __pycache__  # Windows
find . -type d -name __pycache__ -exec rm -r {} +  # Linux/Mac

# Limpiar .pyc
find . -name "*.pyc" -delete

# Reinstalar (limpio)
pip uninstall -r requirements.txt -y
pip install -r requirements.txt
```

## 🔐 Seguridad

```bash
# Verificar vulnerabilidades
pip install safety
safety check

# Check dependencias
pip install pip-audit
pip-audit

# Generar requerimientos seguros
pip freeze > requirements.lock
```

## 📊 Información del Sistema

```bash
# Python version
python --version

# Pip version
pip --version

# Ubicación de Python
where python  # Windows
which python  # Linux/Mac

# Info del entorno
python -c "import sys; print(sys.prefix)"

# Paquetes instalados
pip list --format=json > packages.json
```

## 🚨 Solución Rápida de Problemas

```bash
# Error: "Module not found"
pip install <module>

# Error: "Permission denied"
sudo chown -R $USER venv  # Linux/Mac
icacls venv /grant %USERNAME%:F  # Windows

# Error: "API Key invalid"
# Editar .env y verificar clave

# Error: "Port 8000 in use"
# Windows:
netstat -ano | findstr :8000
taskkill /PID <PID> /F

# Linux/Mac:
lsof -i :8000
kill -9 <PID>

# Error: "poppler not found"
choco install poppler  # Windows
brew install poppler   # Mac
sudo apt-get install poppler-utils  # Linux

# Resetear entorno
deactivate
rm -rf venv
python -m venv venv
source venv/bin/activate  # o venv\Scripts\activate
pip install -r requirements.txt
```

## 📝 Git Workflow

```bash
# Inicializar repo
git init

# Agregar cambios
git add .
git add -A

# Commit
git commit -m "Initial implementation of form filler microservice"

# Ver estado
git status

# Ver cambios
git diff

# Ver logs
git log --oneline

# Ignorar archivos
echo ".env" >> .gitignore
echo "__pycache__/" >> .gitignore
echo "venv/" >> .gitignore
```

## 📚 Documentación Rápida

```bash
# Ver README
type README.md  # Windows
cat README.md   # Linux/Mac

# Ver Quick Start
more QUICKSTART.md

# Ver arquitectura
more ARCHITECTURE.md

# Ver lógica de visión
more VISION_LOGIC.md

# Ver despliegue
more DEPLOYMENT.md
```

## 🎯 Flujo Típico de Desarrollo

```bash
# 1. Crear rama
git checkout -b feature/nueva-feature

# 2. Hacer cambios
# ... editar archivos ...

# 3. Probar localmente
python -m uvicorn src.main:app --reload

# 4. Validar con curl/Postman

# 5. Commit
git add .
git commit -m "Descripción del cambio"

# 6. Push
git push origin feature/nueva-feature

# 7. Pull Request en GitHub
# ... crear PR ...

# 8. Merge a main
git checkout main
git merge feature/nueva-feature

# 9. Deploy
# ... seguir instrucciones en DEPLOYMENT.md ...
```

## 💡 Tips Productividad

```bash
# Crear alias para comandos frecuentes
# Windows (PowerShell):
Set-Alias serve "python -m uvicorn src.main:app --reload"
serve

# Linux/Mac (Bash):
alias serve="python -m uvicorn src.main:app --reload"
serve

# Usar configuración de VS Code
# Crear .vscode/settings.json:
{
  "python.defaultInterpreterPath": "${workspaceFolder}/venv/bin/python",
  "python.linting.enabled": true,
  "python.linting.pylintEnabled": true
}

# Agregar a .vscode/launch.json para debug:
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "FastAPI",
      "type": "python",
      "request": "launch",
      "module": "uvicorn",
      "args": ["src.main:app", "--reload"],
      "jinja": true,
      "justMyCode": true
    }
  ]
}
```

---

## 🆘 Comando Completo para Empezar Desde Cero

```bash
# 1. Navegar al directorio
cd c:\Users\cmamartinez\Desktop\MicroServicios\LlenadoFormulariosAutomaticos

# 2. Copiar env
copy .env.example .env

# 3. IMPORTANTE: Editar .env con tu GEMINI_API_KEY
# Abrir con tu editor favorito y agregar:
# GEMINI_API_KEY=tu_clave_aqui

# 4. Crear venv
python -m venv venv

# 5. Activar venv (Windows)
venv\Scripts\activate
# O si usas Linux/Mac:
# source venv/bin/activate

# 6. Instalar dependencias
pip install -r requirements.txt

# 7. Iniciar servidor
python -m uvicorn src.main:app --reload

# Resultado esperado:
# INFO:     Uvicorn running on http://127.0.0.1:8000
# INFO:     Application startup complete

# 8. En otra terminal, probar:
curl http://localhost:8000/health

# ✓ Éxito si ves: {"status":"ok","message":"Servicio operativo"}
```
