#!/bin/bash

# Script de inicio para Render.com

echo "🚀 Iniciando Habit Tracker Backend..."

# Activar entorno virtual (si existe)
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Instalar dependencias si es necesario
if [ ! -d "venv" ] && [ -f "requirements.txt" ]; then
    echo "📦 Instalando dependencias..."
    pip install -r requirements.txt
fi

# Ejecutar la aplicación
echo "🌐 Iniciando servidor en puerto ${PORT}..."
exec uvicorn main:app --host 0.0.0.0 --port ${PORT} --workers 1