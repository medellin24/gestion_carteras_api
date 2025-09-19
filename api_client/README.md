API Client (Escritorio)

Configuración de entorno
- Crea un archivo `.env` en la raíz del proyecto de escritorio con:
```
API_BASE_URL=http://127.0.0.1:8000
API_TIMEOUT=30
API_MAX_RETRIES=3
```

Uso
- El cliente lee automáticamente `API_BASE_URL` para apuntar a la API.
- Si no hay `.env`, usará `http://localhost:8000` por defecto.

Requisitos
- requests
- (Opcional) python-dotenv, si quieres cargar `.env` automáticamente.

