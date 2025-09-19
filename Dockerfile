FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Dependencias del sistema mínimas (libpq para psycopg2-binary)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Instalar dependencias Python
COPY gestion_carteras_api/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código del backend
COPY gestion_carteras_api/ ./gestion_carteras_api/

EXPOSE 8000

# Nota: ejecutamos como paquete, acorde a imports relativos
# (uvicorn gestion_carteras_api.main:app)
CMD ["uvicorn", "gestion_carteras_api.main:app", "--host", "0.0.0.0", "--port", "8000"]


