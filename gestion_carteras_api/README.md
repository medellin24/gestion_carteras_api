Gestión de Carteras API (Standalone)

Requisitos
- Python 3.10+
- PostgreSQL

Instalación
```bash
# Crear venv (Windows)
python -m venv venv
venv\Scripts\activate

# Instalar dependencias
pip install -r requirements.txt
```

Configuración
1. Copia `.env.example` a `.env` y edita tus valores:
```
DB_HOST=...
DB_NAME=...
DB_USER=...
DB_PASSWORD=...
DB_PORT=5432
JWT_SECRET_KEY=...
```
2. Ejecuta migraciones y seed:
```bash
python -m gestion_carteras_api.scripts.setup_db
```

Ejecutar API
Desde la raíz del repo de la API (directorio padre de `gestion_carteras_api`):
```bash
venv\Scripts\python -m uvicorn gestion_carteras_api.main:app --reload --host 127.0.0.1 --port 8000
```

Autenticación
- POST `/auth/login` -> tokens (admin/cobrador)
- GET `/billing/quote` -> requiere admin

Notas
- Este proyecto es independiente de la app de escritorio. Consume base de datos propia y variables por `.env`.

