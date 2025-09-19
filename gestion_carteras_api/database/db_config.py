import os
from dotenv import load_dotenv

# Cargar variables de entorno desde .env si existe
load_dotenv()

DB_CONFIG = {
    'host': os.getenv('DB_HOST', ''),
    'database': os.getenv('DB_NAME', ''),
    'user': os.getenv('DB_USER', ''),
    'password': os.getenv('DB_PASSWORD', ''),
    'port': os.getenv('DB_PORT', '5432'),
}