#!/bin/bash

# Script para iniciar rápidamente el servidor en Linux/Mac

echo ""
echo "=========================================="
echo "Llenado Inteligente de Documentos"
echo "FastAPI Microservicio"
echo "=========================================="
echo ""

# Verificar si .env existe
if [ ! -f ".env" ]; then
    echo "Error: .env no encontrado"
    echo "Ejecuta: cp .env.example .env"
    echo "Y luego edita .env con tu GEMINI_API_KEY"
    exit 1
fi

# Crear venv si no existe
if [ ! -d "venv" ]; then
    echo "Creando entorno virtual..."
    python3 -m venv venv
fi

# Activar venv
source venv/bin/activate

# Instalar dependencias
echo ""
echo "Verificando dependencias..."
pip install -r requirements.txt -q

# Iniciar servidor
echo ""
echo "Iniciando servidor en http://localhost:8000"
echo "Presiona CTRL+C para detener"
echo ""

python -m uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
