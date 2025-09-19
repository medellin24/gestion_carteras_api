"""
Módulo de integración con la API de Gestión de Carteras.

Este módulo proporciona una interfaz para que la aplicación de escritorio
se comunique con la API REST, permitiendo el intercambio de datos y la
sincronización entre diferentes instancias de la aplicación.

Componentes principales:
- APIClient: Cliente directo para comunicación con la API
- HybridManager: Manager que combina API y base de datos local
- OperationMode: Modos de operación (local, API, híbrido)
"""

from .config import api_config
from .client import APIClient, APIError

__all__ = ['api_config', 'APIClient', 'APIError'] 