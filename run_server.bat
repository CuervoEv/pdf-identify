@echo off
REM Script para iniciar rápidamente el servidor en Windows

echo.
echo ==========================================
echo Llenado Inteligente de Documentos
echo FastAPI Microservicio
echo ==========================================
echo.

REM Verificar si .env existe
if not exist ".env" (
    echo Error: .env no encontrado
    echo Ejecuta: copy .env.example .env
    echo Y luego edita .env con tu GEMINI_API_KEY
    pause
    exit /b 1
)

REM Crear venv si no existe
if not exist "venv" (
    echo Creando entorno virtual...
    python -m venv venv
)

REM Activar venv
call venv\Scripts\activate.bat

REM Instalar dependencias
echo.
echo Verificando dependencias...
pip install -r requirements.txt -q

REM Iniciar servidor
echo.
echo Iniciando servidor en http://localhost:8000
echo Presiona CTRL+C para detener
echo.

python -m uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

pause
