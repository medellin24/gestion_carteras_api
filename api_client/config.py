import os
import sys
from typing import Optional

def _load_env_flexible() -> None:
    """Carga variables desde .env buscando en varias ubicaciones razonables.

    Orden de carga (la primera que exista se carga primero; las siguientes complementan sin sobrescribir):
    1) Carpeta del ejecutable (PyInstaller) o del script actual.
    2) %APPDATA%/SIRC/.env (Windows) o ~/.config/sirc/.env (otros).
    3) El .env hallado por find_dotenv() desde el cwd.
    """
    try:
        from dotenv import load_dotenv, find_dotenv  # type: ignore
    except Exception:
        return

    # 1) Directorio del ejecutable/script
    exe_dir = os.path.dirname(getattr(sys, 'executable', sys.argv[0])) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(sys.argv[0]))
    env_paths = [os.path.join(exe_dir, '.env')]

    # 2) Ubicación de configuración del usuario
    if os.name == 'nt':
        appdata = os.getenv('APPDATA')
        if appdata:
            env_paths.append(os.path.join(appdata, 'SIRC', '.env'))
    else:
        home = os.path.expanduser('~')
        env_paths.append(os.path.join(home, '.config', 'sirc', '.env'))

    # 3) find_dotenv desde cwd
    found = find_dotenv(usecwd=True)
    if found:
        env_paths.append(found)

    loaded = set()
    for p in env_paths:
        if p and os.path.isfile(p) and p not in loaded:
            load_dotenv(dotenv_path=p, override=False)
            loaded.add(p)

_load_env_flexible()

class APIConfig:
    """Configuración para la comunicación con la API"""
    
    def __init__(self):
        # URL base de la API (configurable via variable de entorno)
        self.base_url = os.getenv('API_BASE_URL', 'http://127.0.0.1:8000')
        
        # Timeout para requests (en segundos)
        self.timeout = int(os.getenv('API_TIMEOUT', '30'))
        
        # Número de reintentos para requests fallidos
        self.max_retries = int(os.getenv('API_MAX_RETRIES', '3'))
        
        # Token de autenticación (opcional, para futuras implementaciones)
        self.auth_token: Optional[str] = os.getenv('API_AUTH_TOKEN')
        
        # Headers por defecto
        self.default_headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        
        if self.auth_token:
            self.default_headers['Authorization'] = f'Bearer {self.auth_token}'
    
    def get_endpoint_url(self, endpoint: str) -> str:
        """Construye la URL completa para un endpoint"""
        return f"{self.base_url.rstrip('/')}/{endpoint.lstrip('/')}"

# Instancia global de configuración
api_config = APIConfig() 