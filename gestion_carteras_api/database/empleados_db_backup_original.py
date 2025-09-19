from database.connection_pool import DatabasePool
import logging
from typing import List, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

def obtener_empleados():
    try:
        with DatabasePool.get_cursor() as cursor:
            cursor.execute('''
                SELECT identificacion, nombre as nombre_completo, telefono, direccion 
                FROM empleados 
                ORDER BY nombre
            ''')
            return cursor.fetchall()
    except Exception as e:
        logger.error(f"Error al obtener empleados: {e}")
        return []

def insertar_empleado(identificacion: str, nombre: str, telefono: str, direccion: str) -> Optional[str]:
    try:
        with DatabasePool.get_cursor() as cursor:
            # La inserción sigue usando la columna 'nombre'
            cursor.execute('''
                INSERT INTO empleados (identificacion, nombre, telefono, direccion)
                VALUES (%s, %s, %s, %s)
                RETURNING identificacion
            ''', (identificacion, nombre, telefono, direccion))
            return cursor.fetchone()[0]
    except Exception as e:
        logger.error(f"Error al insertar empleado: {e}")
        return None

def actualizar_empleado(identificacion: str, nombre: str, telefono: str, direccion: str) -> bool:
    try:
        with DatabasePool.get_cursor() as cursor:
            # La actualización sigue usando la columna 'nombre'
            cursor.execute('''
                UPDATE empleados 
                SET nombre = %s, telefono = %s, direccion = %s
                WHERE identificacion = %s
                RETURNING identificacion
            ''', (nombre, telefono, direccion, identificacion))
            return cursor.fetchone() is not None
    except Exception as e:
        logger.error(f"Error al actualizar empleado: {e}")
        return False

def eliminar_empleado(identificacion: str) -> bool:
    try:
        with DatabasePool.get_cursor() as cursor:
            cursor.execute('DELETE FROM empleados WHERE identificacion = %s RETURNING identificacion', 
                         (identificacion,))
            return cursor.fetchone() is not None
    except Exception as e:
        logger.error(f"Error al eliminar empleado: {e}")
        return False

def buscar_empleado_por_identificacion(identificacion: str) -> Optional[Dict]:
    try:
        with DatabasePool.get_cursor() as cursor:
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