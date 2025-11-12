FROM python:3.11-slim

WORKDIR /app

# Dependencias del sistema (útil para psycopg2 si luego usas Postgres)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev && rm -rf /var/lib/apt/lists/*

# Copiar requirements primero
COPY requirements.txt ./

# Instalar dependencias
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copiar el resto (tu main.py y los estáticos)
COPY main.py ./main.py
COPY static/ ./static/

# Variables que tu app lee
ENV IS_DOCKER=true
# DATABASE_URL se define en runtime si usas Postgres (o dejas SQLite)

EXPOSE 8000
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
