FROM python:3.11-slim

# Evitar prompts interactivos y buffers de Python
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Instalar dependencias del sistema mínimas
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copiar requerimientos e instalarlos
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el código de la aplicación
COPY . .

# Crear directorio de datos persistente si no existe
RUN mkdir -p /data

# Exponer el puerto
EXPOSE 8000

# Variables de entorno por defecto
ENV PORT=8000 \
    DATABASE_PATH=/data/ygo_data.db

# Ejecutar con Gunicorn WSGI
CMD ["gunicorn", "wsgi:app", "--bind", "0.0.0.0:8000", "--workers", "2", "--threads", "4", "--timeout", "120"]
