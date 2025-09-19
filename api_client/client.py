import json
import time
import logging
from typing import Dict, List, Optional, Any, Union
from datetime import date, datetime
from decimal import Decimal

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

# Asumimos que la configuración de la API está en un archivo config.py dentro de este paquete.
# Si no es así, esta importación podría necesitar ajuste.
from .config import api_config

logger = logging.getLogger(__name__)

class APIError(Exception):
    """Excepción personalizada para errores de la API"""
    def __init__(self, message: str, status_code: Optional[int] = None, response_data: Optional[Dict] = None):
        self.message = message
        self.status_code = status_code
        self.response_data = response_data
        super().__init__(self.message)

class APIClient:
    """Cliente para comunicarse con la API de Gestión de Carteras"""
    
    def __init__(self):
        if not REQUESTS_AVAILABLE:
            raise ImportError("La librería 'requests' es necesaria. Por favor, instálala con: pip install requests")
        
        self.config = api_config
        self.session = requests.Session()
        self.session.headers.update(self.config.default_headers)
        self.session.timeout = self.config.timeout
    
    def _make_request(self, method: str, endpoint: str, data: Optional[Dict] = None, params: Optional[Dict] = None) -> Union[Dict, List]:
        """Realiza una petición HTTP con manejo de errores y reintentos"""
        url = self.config.get_endpoint_url(endpoint)
        
        for attempt in range(self.config.max_retries + 1):
            try:
                logger.debug(f"Realizando {method} request a {url} (intento {attempt + 1})")
                
                response = self.session.request(method=method, url=url, json=data, params=params)
                
                if 200 <= response.status_code < 300:
                    if not response.content:
                        return {}
                    # Intentar parsear JSON de forma segura
                    try:
                        return response.json()
                    except ValueError:
                        # No es JSON; devolver texto crudo encapsulado
                        return {"raw": response.text}
                
                # Manejo de errores específicos
                # Intentar parsear JSON; si falla, usar texto
                error_data: Dict[str, Any] = {}
                error_message = 'Error desconocido del servidor.'
                if response.content:
                    try:
                        error_data = response.json()
                        error_message = error_data.get('detail', error_message)
                    except ValueError:
                        # HTML o texto plano
                        error_message = response.text[:300] if response.text else error_message
                
                if response.status_code == 404:
                    raise APIError(f"Recurso no encontrado: {endpoint}", response.status_code, error_data)
                elif response.status_code == 400:
                    raise APIError(f"Error de validación: {error_message}", response.status_code, error_data)
                else:
                    raise APIError(f"Error HTTP {response.status_code}: {error_message}", response.status_code, error_data)
                    
            except requests.exceptions.ConnectionError as e:
                logger.warning(f"Error de conexión, reintentando... (intento {attempt + 1})")
                if attempt == self.config.max_retries:
                    raise APIError(f"No se pudo conectar con la API después de {self.config.max_retries + 1} intentos.")
                time.sleep(1)
            except requests.exceptions.Timeout as e:
                logger.warning(f"Timeout, reintentando... (intento {attempt + 1})")
                if attempt == self.config.max_retries:
                     raise APIError(f"Timeout al conectar con la API después de {self.config.max_retries + 1} intentos.")
                time.sleep(1)
            except requests.exceptions.RequestException as e:
                raise APIError(f"Error en la petición HTTP: {e}")

    # --- Autenticación ---
    def login(self, username: str, password: str) -> Dict:
        payload = {"username": username, "password": password}
        tokens = self._make_request('POST', '/auth/login', data=payload)
        access = tokens.get('access_token')
        if not access:
            raise APIError("Login fallido: token no recibido")
        # Guardar tokens y actualizar headers
        self.config.auth_token = access
        self.session.headers['Authorization'] = f"Bearer {access}"
        self._refresh_token = tokens.get('refresh_token')
        self._role = tokens.get('role')
        return tokens

    def refresh(self) -> Dict:
        if not hasattr(self, '_refresh_token') or not self._refresh_token:
            raise APIError("No hay refresh token disponible")
        tokens = self._make_request('POST', '/auth/refresh', data={'refresh_token': self._refresh_token})
        access = tokens.get('access_token')
        if not access:
            raise APIError("Refresh fallido: token no recibido")
        self.config.auth_token = access
        self.session.headers['Authorization'] = f"Bearer {access}"
        self._refresh_token = tokens.get('refresh_token')
        self._role = tokens.get('role')
        return tokens

    # --- Registro público (signup/trial o con plan) ---
    def signup_public(self, nombre_negocio: str, email: str, password_admin: str, plan_max_empleados: Optional[int] = None) -> Dict:
        payload = {
            "nombre_negocio": nombre_negocio,
            "email": email,
            "password_admin": password_admin,
        }
        if plan_max_empleados is not None:
            payload["plan_max_empleados"] = int(plan_max_empleados)
        return self._make_request('POST', '/public/signup', data=payload)

    # --- Admin: límites y creación de cobradores ---
    def get_admin_limits(self) -> Dict:
        return self._make_request('GET', '/admin/limits')

    def create_cobrador(self, username: str, password: str, empleado_identificacion: str) -> Dict:
        payload = {
            "username": username,
            "password": password,
            "empleado_identificacion": empleado_identificacion,
        }
        return self._make_request('POST', '/admin/users/cobradores', data=payload)

    def deactivate_cobrador(self, empleado_identificacion: str) -> Dict:
        return self._make_request('POST', f"/admin/users/cobradores/{empleado_identificacion}/deactivate")

    def activate_cobrador(self, empleado_identificacion: str) -> Dict:
        return self._make_request('POST', f"/admin/users/cobradores/{empleado_identificacion}/activate")

    # --- Cobradores: credenciales y permisos (NUEVA LÓGICA SIMPLE) ---
    def get_cobrador_credentials(self, empleado_identificacion: str) -> Dict:
        return self._make_request('GET', f"/admin/users/cobradores/{empleado_identificacion}/credentials")

    def upsert_cobrador_credentials(self, empleado_identificacion: str, username: str, password: str) -> Dict:
        payload = {"username": username, "password": password}
        return self._make_request('POST', f"/admin/users/cobradores/{empleado_identificacion}/upsert", data=payload)

    def get_permisos_empleado(self, empleado_identificacion: str) -> Dict:
        """
        Obtiene los permisos del empleado basado en empleados.descargar/subir/fecha_accion
        Lógica simple: puede descargar si descargar=TRUE Y fecha_accion < hoy
        """
        return self._make_request('GET', f"/admin/users/cobradores/{empleado_identificacion}/permissions")

    def rehabilitar_permisos(self, empleado_identificacion: str, descargar: bool = False, subir: bool = False) -> Dict:
        """
        Re-habilita permisos desde escritorio para casos de error.
        Lógica: pone descargar/subir en TRUE y fecha_accion en ayer para permitir hoy.
        """
        payload = {"descargar": bool(descargar), "subir": bool(subir)}
        return self._make_request('POST', f"/admin/users/cobradores/{empleado_identificacion}/permissions/rehabilitar", data=payload)

    def usar_permisos(self, empleado_identificacion: str, descargar: bool = False, subir: bool = False) -> Dict:
        """
        Usa permisos desde app móvil.
        Lógica: 
        - Al descargar: descargar=FALSE, subir=TRUE, fecha_accion=igual
        - Al subir: descargar=TRUE, subir=FALSE, fecha_accion=hoy
        """
        payload = {"descargar": bool(descargar), "subir": bool(subir)}
        return self._make_request('POST', f"/admin/users/cobradores/{empleado_identificacion}/permissions/usar", data=payload)

    def _convert_types_for_json(self, data: Dict) -> Dict:
        """Convierte tipos como Decimal y date a formatos compatibles con JSON."""
        if not isinstance(data, dict):
            return data
        
        converted = {}
        for key, value in data.items():
            if isinstance(value, (datetime, date)):
                converted[key] = value.isoformat()
            elif isinstance(value, Decimal):
                converted[key] = float(value)
            # Recursividad para diccionarios y listas anidadas
            elif isinstance(value, dict):
                converted[key] = self._convert_types_for_json(value)
            elif isinstance(value, list):
                converted[key] = [self._convert_types_for_json(item) if isinstance(item, dict) else item for item in value]
            else:
                converted[key] = value
        return converted

    # --- Métodos para Empleados ---
    def list_empleados(self) -> List[Dict]:
        return self._make_request('GET', '/empleados/')

    def create_empleado(self, empleado_data: Dict) -> Dict:
        payload = self._convert_types_for_json(empleado_data)
        return self._make_request('POST', '/empleados/', data=payload)
        
    def update_empleado(self, identificacion: str, empleado_data: Dict) -> Dict:
        payload = self._convert_types_for_json(empleado_data)
        return self._make_request('PUT', f'/empleados/{identificacion}', data=payload)
        
    def delete_empleado(self, identificacion: str) -> Dict:
        return self._make_request('DELETE', f'/empleados/{identificacion}')

    def transferir_tarjetas_empleado(self, empleado_origen: str, empleado_destino: str) -> Dict:
        """Transfiere todas las tarjetas de un empleado a otro empleado."""
        payload = {
            "empleado_destino": empleado_destino,
            "confirmar_transferencia": True
        }
        return self._make_request('POST', f'/empleados/{empleado_origen}/transferir-tarjetas', data=payload)

    def eliminar_empleado_forzado(self, identificacion: str) -> Dict:
        """Elimina un empleado y opcionalmente todas sus tarjetas asociadas."""
        payload = {
            "confirmar_eliminacion": True,
            "eliminar_tarjetas": True
        }
        return self._make_request('DELETE', f'/empleados/{identificacion}/forzar-eliminacion', data=payload)

    # --- Métodos para Bases ---
    def get_base_by_empleado_fecha(self, empleado_id: str, fecha: str) -> Optional[Dict]:
        try:
            return self._make_request('GET', f'/bases/{empleado_id}/{fecha}')
        except APIError as e:
            # Si no existe, devolver None para que la UI muestre la opción de asignar base
            if e.status_code == 404:
                return None
            raise

    def create_base(self, base_data: Dict) -> Dict:
        payload = self._convert_types_for_json(base_data)
        return self._make_request('POST', '/bases/', data=payload)
        
    def update_base(self, base_id: int, base_data: Dict) -> Dict:
        payload = self._convert_types_for_json(base_data)
        # El endpoint podría variar, ej: /bases/{id} o /bases/{empleado_id}/{fecha}
        # Asumiendo que es por ID de base.
        return self._make_request('PUT', f'/bases/{base_id}', data=payload)
        
    def delete_base(self, base_id: int) -> Dict:
        return self._make_request('DELETE', f'/bases/{base_id}')
    
    def list_bases_by_empleado(self, empleado_id: str, fecha: Optional[Union[str, date]] = None, skip: int = 0, limit: int = 100) -> List[Dict]:
        """Lista bases por empleado, opcionalmente filtradas por fecha"""
        params = {'skip': skip, 'limit': limit}
        if fecha:
            if isinstance(fecha, date):
                fecha = fecha.isoformat()
            params['fecha'] = fecha
        return self._make_request('GET', f'/empleados/{empleado_id}/bases/', params=params)
    
    def list_bases(self, fecha: Optional[Union[str, date]] = None, skip: int = 0, limit: int = 100) -> List[Dict]:
        """Lista todas las bases, opcionalmente filtradas por fecha"""
        params = {'skip': skip, 'limit': limit}
        if fecha:
            if isinstance(fecha, date):
                fecha = fecha.isoformat()
            params['fecha'] = fecha
        return self._make_request('GET', '/bases/', params=params)
    
    # --- Métodos para Gastos ---

    def list_tipos_gastos(self) -> List[Dict]:
        """Obtiene la lista de tipos de gastos desde la API."""
        return self._make_request('GET', '/gastos/tipos')
    
    def create_gasto(self, gasto_data: Dict) -> Dict:
        """Crea un nuevo gasto"""
        data = self._convert_types_for_json(gasto_data)
        return self._make_request('POST', '/gastos/', data=data)
    
    def get_gasto(self, gasto_id: int) -> Dict:
        """Obtiene un gasto por ID"""
        return self._make_request('GET', f'/gastos/{gasto_id}')
    
    def update_gasto(self, gasto_id: int, gasto_data: Dict) -> Dict:
        """Actualiza un gasto"""
        data = self._convert_types_for_json(gasto_data)
        return self._make_request('PUT', f'/gastos/{gasto_id}', data=data)
    
    def delete_gasto(self, gasto_id: int) -> Dict:
        """Elimina un gasto"""
        return self._make_request('DELETE', f'/gastos/{gasto_id}')
    
    def list_gastos_by_empleado_fecha(self, empleado_id: str, fecha: Union[str, date]) -> List[Dict]:
        """Lista gastos por empleado y fecha"""
        if isinstance(fecha, date):
            fecha = fecha.isoformat()
        return self._make_request('GET', f'/empleados/{empleado_id}/gastos/{fecha}')
    
    def get_resumen_gastos_by_empleado_fecha(self, empleado_id: str, fecha: Union[str, date]) -> List[Dict]:
        """Obtiene resumen de gastos por empleado y fecha"""
        if isinstance(fecha, date):
            fecha = fecha.isoformat()
        return self._make_request('GET', f'/empleados/{empleado_id}/gastos/{fecha}/resumen')
    
    def list_gastos(self, empleado_id: Optional[str] = None, fecha: Optional[Union[str, date]] = None, 
                   tipo: Optional[str] = None, skip: int = 0, limit: int = 100) -> List[Dict]:
        """Lista gastos con filtros opcionales"""
        if empleado_id and fecha:
            # Gastos específicos por empleado y fecha
            if isinstance(fecha, date):
                fecha = fecha.isoformat()
            return self._make_request('GET', f'/empleados/{empleado_id}/gastos/{fecha}')
        elif fecha and tipo:
            # Gastos por fecha y tipo
            params = {'tipo': tipo}
            return self._make_request('GET', f'/gastos/fecha/{fecha}', params=params)
        elif fecha:
            # Gastos por fecha (todos los tipos)
            return self._make_request('GET', f'/gastos/fecha/{fecha}')
        else:
            # Lista general de gastos
            params = {'skip': skip, 'limit': limit}
            return self._make_request('GET', '/gastos/', params=params)
    
    # --- Métodos para Tarjetas ---
    
    def list_tarjetas(self, empleado_id: Optional[str] = None, estado: str = 'activas', skip: int = 0, limit: int = 100) -> List[Dict]:
        """Lista tarjetas, opcionalmente filtradas por empleado y estado"""
        if empleado_id:
            # Si se especifica empleado, usar endpoint específico
            params = {'estado': estado, 'skip': skip, 'limit': limit}
            return self._make_request('GET', f'/empleados/{empleado_id}/tarjetas/', params=params)
        else:
            # Si no se especifica empleado, usar endpoint general
            params = {'estado': estado, 'skip': skip, 'limit': limit}
            return self._make_request('GET', '/tarjetas/', params=params)
    
    def list_targetas(self, empleado_id: Optional[str] = None, estado: str = 'activas', skip: int = 0, limit: int = 100) -> List[Dict]:
        """Alias para list_tarjetas (compatibilidad)"""
        return self.list_tarjetas(empleado_id, estado, skip, limit)
    
    def create_tarjeta(self, tarjeta_data: Dict) -> Dict:
        """Crea una nueva tarjeta"""
        payload = self._convert_types_for_json(tarjeta_data)
        return self._make_request('POST', '/tarjetas/', data=payload)
    
    def get_tarjeta(self, codigo: str) -> Dict:
        """Obtiene una tarjeta por código"""
        return self._make_request('GET', f'/tarjetas/{codigo}')
    
    def update_tarjeta(self, codigo: str, tarjeta_data: Dict) -> Dict:
        """Actualiza una tarjeta"""
        payload = self._convert_types_for_json(tarjeta_data)
        return self._make_request('PUT', f'/tarjetas/{codigo}', data=payload)
    
    def delete_tarjeta(self, codigo: str) -> Dict:
        """Elimina una tarjeta"""
        return self._make_request('DELETE', f'/tarjetas/{codigo}')
    
    def update_estado_tarjeta(self, codigo: str, estado: str) -> Dict:
        """Actualiza el estado de una tarjeta"""
        return self._make_request('PUT', f'/tarjetas/{codigo}/estado', data={'estado': estado})
    
    def mover_tarjeta(self, codigo: str, nuevo_empleado_id: str) -> Dict:
        """Mueve una tarjeta a otro empleado"""
        return self._make_request('PUT', f'/tarjetas/{codigo}/mover', data={'nuevo_empleado_id': nuevo_empleado_id})
    
    # --- Métodos para Abonos ---
    
    def list_abonos_by_tarjeta(self, tarjeta_codigo: str) -> List[Dict]:
        """Lista todos los abonos de una tarjeta específica"""
        return self._make_request('GET', f'/tarjetas/{tarjeta_codigo}/abonos/')
    
    def get_abono(self, abono_id: int) -> Dict:
        """Obtiene un abono por ID"""
        return self._make_request('GET', f'/abonos/{abono_id}')
    
    def create_abono(self, abono_data: Dict) -> Dict:
        """Registra un nuevo abono"""
        payload = self._convert_types_for_json(abono_data)
        return self._make_request('POST', '/abonos/', data=payload)
    
    def update_abono(self, abono_id: int, abono_data: Dict) -> Dict:
        """Actualiza un abono existente"""
        payload = self._convert_types_for_json(abono_data)
        return self._make_request('PUT', f'/abonos/{abono_id}', data=payload)
    
    def delete_abono(self, abono_id: int) -> Dict:
        """Elimina un abono"""
        return self._make_request('DELETE', f'/abonos/{abono_id}')
    
    def delete_ultimo_abono(self, tarjeta_codigo: str) -> Dict:
        """Elimina el último abono de una tarjeta"""
        return self._make_request('DELETE', f'/tarjetas/{tarjeta_codigo}/abonos/ultimo')
    
    # --- Métodos para Liquidación ---
    
    def get_liquidacion_diaria(self, empleado_id: str, fecha: Union[str, date]) -> Dict:
        """Obtiene la liquidación diaria de un empleado"""
        if isinstance(fecha, date):
            fecha = fecha.isoformat()
        return self._make_request('GET', f'/liquidacion/{empleado_id}/{fecha}')
    
    def get_resumen_financiero(self, fecha: Union[str, date]) -> Dict:
        """Obtiene el resumen financiero del día"""
        if isinstance(fecha, date):
            fecha = fecha.isoformat()
        return self._make_request('GET', f'/liquidacion/resumen/{fecha}')

    def get_tarjeta_resumen(self, tarjeta_codigo: str) -> Dict:
        """Obtiene el resumen de una tarjeta por código"""
        return self._make_request('GET', f'/tarjetas/{tarjeta_codigo}/resumen')

    # --- Permisos por empleado (columnas descargar/subir/fecha_accion) ---
    def get_empleado_permissions(self, empleado_identificacion: str) -> Dict:
        """Obtiene descargar, subir y fecha_accion para un empleado"""
        return self._make_request('GET', f'/empleados/{empleado_identificacion}/permissions')

    def set_empleado_permissions(self, empleado_identificacion: str, descargar: Optional[bool] = None,
                                 subir: Optional[bool] = None, fecha_accion: Optional[Union[str, date]] = None) -> Dict:
        """Actualiza permisos de empleado. Acepta descargar/subir y fecha_accion (YYYY-MM-DD o date)."""
        payload: Dict[str, Union[bool, str]] = {}
        if descargar is not None:
            payload['descargar'] = bool(descargar)
        if subir is not None:
            payload['subir'] = bool(subir)
        if fecha_accion is not None:
            if isinstance(fecha_accion, date):
                payload['fecha_accion'] = fecha_accion.isoformat()
            else:
                payload['fecha_accion'] = str(fecha_accion)
        if not payload:
            return {}
        return self._make_request('POST', f'/empleados/{empleado_identificacion}/permissions', data=payload)

    # --- Métodos para gestión de suscripciones ---
    
    def renew_subscription(self, max_empleados: int, dias: int, es_renovacion: bool = True) -> Dict:
        """Renueva o cambia el plan de suscripción."""
        payload = {
            "max_empleados": max_empleados,
            "dias": dias,
            "es_renovacion": es_renovacion
        }
        return self._make_request('POST', '/admin/billing/renew', data=payload)

    def activate_available_cobradores(self) -> Dict:
        """Activa todos los usuarios cobrador disponibles hasta llenar el cupo del plan."""
        return self._make_request('POST', '/admin/users/cobradores/activate-available')

    def get_cobradores_activos(self) -> Dict:
        """Obtiene la lista de empleados que tienen usuario cobrador activo."""
        return self._make_request('GET', '/admin/users/cobradores/activos')

    # --- Detalles para liquidación ---
    def list_tarjetas_canceladas_del_dia(self, empleado_id: str, fecha: Union[str, date]) -> List[Dict]:
        if isinstance(fecha, date):
            fecha = fecha.isoformat()
        return self._make_request('GET', f'/empleados/{empleado_id}/tarjetas/canceladas/{fecha}')

    def list_tarjetas_nuevas_del_dia(self, empleado_id: str, fecha: Union[str, date]) -> List[Dict]:
        if isinstance(fecha, date):
            fecha = fecha.isoformat()
        return self._make_request('GET', f'/empleados/{empleado_id}/tarjetas/nuevas/{fecha}')

    def list_abonos_del_dia(self, empleado_id: str, fecha: Union[str, date]) -> List[Dict]:
        if isinstance(fecha, date):
            fecha = fecha.isoformat()
        return self._make_request('GET', f'/empleados/{empleado_id}/abonos/{fecha}')

    # --- Métodos para Clientes ---

    def get_cliente(self, identificacion: str) -> Dict:
        return self._make_request('GET', f'/clientes/{identificacion}')

    def create_cliente(self, cliente_data: Dict) -> Dict:
        payload = self._convert_types_for_json(cliente_data)
        return self._make_request('POST', '/clientes/', data=payload)

    def update_cliente(self, identificacion: str, cliente_data: Dict) -> Dict:
        payload = self._convert_types_for_json(cliente_data)
        return self._make_request('PUT', f'/clientes/{identificacion}', data=payload)

    def get_cliente_historial(self, identificacion: str) -> List[Dict]:
        return self._make_request('GET', f'/clientes/{identificacion}/historial')

    def get_cliente_estadisticas(self, identificacion: str) -> Dict:
        return self._make_request('GET', f'/clientes/{identificacion}/estadisticas')

# Instancia global del cliente
api_client = APIClient() 