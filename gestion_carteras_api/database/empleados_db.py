from .connection_pool import DatabasePool
import logging
from typing import List, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

def obtener_empleados(cuenta_id: int):
    try:
        with DatabasePool.get_cursor() as cursor:
            cursor.execute('''
                SELECT identificacion, nombre as nombre_completo, telefono, direccion 
                FROM empleados 
                WHERE cuenta_id = %s
                ORDER BY nombre
            ''', (cuenta_id,))
            rows = cursor.fetchall()
            # Convertir tuplas a diccionarios para FastAPI
            empleados = []
            for row in rows:
                empleado = {
                    'identificacion': row[0],
                    'nombre_completo': row[1],
                    'telefono': row[2],
                    'direccion': row[3]
                }
                empleados.append(empleado)
            return empleados
    except Exception as e:
        logger.error(f"Error al obtener empleados: {e}")
        return []

def insertar_empleado(identificacion: str, nombre: str, telefono: str, direccion: str, cuenta_id: int) -> Optional[str]:
    try:
        with DatabasePool.get_cursor() as cursor:
            # La inserción sigue usando la columna 'nombre'
            cursor.execute('''
                INSERT INTO empleados (identificacion, nombre, telefono, direccion, cuenta_id)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING identificacion
            ''', (identificacion, nombre, telefono, direccion, cuenta_id))
            return cursor.fetchone()[0]
    except Exception as e:
        logger.error(f"Error al insertar empleado: {e}")
        return None

def actualizar_empleado(identificacion: str, nombre: str, telefono: str, direccion: str, cuenta_id: int) -> bool:
    try:
        with DatabasePool.get_cursor() as cursor:
            # La actualización sigue usando la columna 'nombre'
            cursor.execute('''
                UPDATE empleados 
                SET nombre = %s, telefono = %s, direccion = %s
                WHERE identificacion = %s AND cuenta_id = %s
                RETURNING identificacion
            ''', (nombre, telefono, direccion, identificacion, cuenta_id))
            return cursor.fetchone() is not None
    except Exception as e:
        logger.error(f"Error al actualizar empleado: {e}")
        return False

def eliminar_empleado(identificacion: str, cuenta_id: int) -> bool:
    try:
        with DatabasePool.get_cursor() as cursor:
            cursor.execute('DELETE FROM empleados WHERE identificacion = %s AND cuenta_id = %s RETURNING identificacion', 
                         (identificacion, cuenta_id))
            return cursor.fetchone() is not None
    except Exception as e:
        logger.error(f"Error al eliminar empleado: {e}")
        return False

def buscar_empleado_por_identificacion(identificacion: str, cuenta_id: Optional[int] = None) -> Optional[Dict]:
    try:
        with DatabasePool.get_cursor() as cursor:
            if cuenta_id is not None:
                cursor.execute('''
                    SELECT identificacion, nombre as nombre_completo, telefono, direccion
                    FROM empleados
                    WHERE identificacion = %s AND cuenta_id = %s
                ''', (identificacion, cuenta_id))
            else:
                cursor.execute('''
                    SELECT identificacion, nombre as nombre_completo, telefono, direccion
                    FROM empleados
                    WHERE identificacion = %s
                ''', (identificacion,))
            result = cursor.fetchone()
            
            if result:
                return {
                    'identificacion': result[0],
                    'nombre_completo': result[1],
                    'telefono': result[2],
                    'direccion': result[3]
                }
            return None
    except Exception as e:
        logger.error(f"Error al buscar empleado: {e}")
        return None

def verificar_empleado_tiene_tarjetas(identificacion: str) -> Tuple[bool, int]:
    """
    Verifica si un empleado tiene tarjetas asociadas.
    Retorna: (tiene_tarjetas: bool, cantidad_tarjetas: int)
    """
    try:
        with DatabasePool.get_cursor() as cursor:
            cursor.execute('''
                SELECT COUNT(*) 
                FROM tarjetas 
                WHERE empleado_identificacion = %s
            ''', (identificacion,))
            count = cursor.fetchone()[0]
            return count > 0, count
    except Exception as e:
        logger.error(f"Error al verificar tarjetas del empleado: {e}")
        return False, 0

def obtener_tarjetas_empleado(identificacion: str) -> List[Dict]:
    """
    Obtiene todas las tarjetas asociadas a un empleado.
    """
    try:
        with DatabasePool.get_cursor() as cursor:
            cursor.execute('''
                SELECT codigo, estado, monto, cliente_identificacion
                FROM tarjetas 
                WHERE empleado_identificacion = %s
                ORDER BY codigo
            ''', (identificacion,))
            rows = cursor.fetchall()
            tarjetas = []
            for row in rows:
                tarjeta = {
                    'codigo': row[0],
                    'estado': row[1],
                    'monto': row[2],
                    'cliente_identificacion': row[3]
                }
                tarjetas.append(tarjeta)
            return tarjetas
    except Exception as e:
        logger.error(f"Error al obtener tarjetas del empleado: {e}")
        return [] 