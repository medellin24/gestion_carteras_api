from .connection_pool import DatabasePool
import logging
from typing import List, Dict, Optional
from datetime import datetime, date

logger = logging.getLogger(__name__)

def buscar_cliente_por_cedula(identificacion: str) -> Optional[Dict]:
    """
    Busca un cliente por número de identificación y retorna sus datos
    junto con un resumen de su historial
    """
    try:
        with DatabasePool.get_cursor() as cursor:
            query = '''
                SELECT 
                    identificacion, nombre, apellido,
                    telefono, direccion, observaciones,
                    COALESCE(historial_crediticio, '[]'::jsonb),
                    COALESCE(score_global, 100)
                FROM clientes 
                WHERE identificacion = %s
            '''
            cursor.execute(query, (identificacion,))
            result = cursor.fetchone()
            
            if not result:
                return None
                
            from datetime import date
            return {
                'identificacion': result[0],
                'nombre': result[1],
                'apellido': result[2],
                'telefono': result[3],
                'direccion': result[4],
                'observaciones': result[5],
                'historial_crediticio': result[6],
                'score_global': result[7],
                'fecha_creacion': date.today()
            }
            
    except Exception as e:
        logger.error(f"Error al buscar cliente por cédula: {e}")
        return None

def obtener_cliente_por_identificacion(identificacion: str) -> Optional[Dict]:
    """
    Obtiene un cliente por su identificación
    """
    return buscar_cliente_por_cedula(identificacion)

def obtener_historial_cliente(cliente_id: int) -> List[Dict]:
    """Obtiene el historial de tarjetas y pagos del cliente"""
    try:
        with DatabasePool.get_cursor() as cursor:
            query = '''
                SELECT 
                    t.id, t.codigo, t.estado,
                    t.fecha_creacion, t.fecha_cancelacion,
                    t.monto, t.interes, t.cuotas,
                    COALESCE(SUM(a.monto), 0) as total_abonado,
                    e.nombre as empleado_nombre
                FROM tarjetas t
                LEFT JOIN abonos a ON t.id = a.tarjeta_id
                LEFT JOIN empleados e ON t.empleado_id = e.id
                WHERE t.cliente_id = %s
                GROUP BY t.id, e.nombre
                ORDER BY t.fecha_creacion DESC
            '''
            cursor.execute(query, (cliente_id,))
            return [
                {
                    'tarjeta_id': row[0],
                    'codigo': row[1],
                    'estado': row[2],
                    'fecha_creacion': row[3],
                    'fecha_cancelacion': row[4],
                    'monto': row[5],
                    'interes': row[6],
                    'cuotas': row[7],
                    'total_abonado': row[8],
                    'empleado_nombre': row[9]
                }
                for row in cursor.fetchall()
            ]
            
    except Exception as e:
        logger.error(f"Error al obtener historial del cliente: {e}")
        return []

def crear_cliente(identificacion: str, nombre: str, apellido: str, 
                 telefono: str = None, direccion: str = None, 
                 observaciones: str = None) -> Optional[Dict]:
    """Crea un nuevo cliente y retorna sus datos como diccionario"""
    try:
        # Normalizar a MAYÚSCULAS los campos de texto relevantes
        nombre = (nombre or '').upper()
        apellido = (apellido or '').upper()
        direccion = (direccion or None)
        if direccion:
            direccion = direccion.upper()
        if observaciones:
            observaciones = observaciones.upper()
        with DatabasePool.get_cursor() as cursor:
            query = '''
                INSERT INTO clientes (
                    identificacion, nombre, apellido,
                    telefono, direccion, observaciones
                ) VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING identificacion, nombre, apellido, telefono, direccion, observaciones, CURRENT_DATE as fecha_creacion
            '''
            cursor.execute(query, (
                identificacion, nombre, apellido,
                telefono, direccion, observaciones
            ))
            row = cursor.fetchone()
            if not row:
                return None
            return {
                'identificacion': row[0],
                'nombre': row[1],
                'apellido': row[2],
                'telefono': row[3],
                'direccion': row[4],
                'observaciones': row[5],
                'fecha_creacion': row[6]
            }
            
    except Exception as e:
        logger.error(f"Error al crear cliente: {e}")
        return False

def actualizar_cliente(identificacion: str, nombre: str, apellido: str,
                      telefono: str = None, direccion: str = None,
                      observaciones: str = None) -> Optional[Dict]:
    """Actualiza los datos de un cliente y retorna el registro actualizado"""
    try:
        # Normalizar a MAYÚSCULAS los campos de texto relevantes
        nombre = (nombre or '').upper()
        apellido = (apellido or '').upper()
        if direccion:
            direccion = direccion.upper()
        if observaciones:
            observaciones = observaciones.upper()
        with DatabasePool.get_cursor() as cursor:
            query = '''
                UPDATE clientes 
                SET nombre = %s, 
                    apellido = %s, 
                    telefono = %s, 
                    direccion = %s, 
                    observaciones = %s
                WHERE identificacion = %s
                RETURNING identificacion, nombre, apellido, telefono, direccion, observaciones, CURRENT_DATE as fecha_creacion
            '''
            cursor.execute(query, (
                nombre, apellido, telefono,
                direccion, observaciones, identificacion
            ))
            
            # Limpiar caché de tarjetas para que se actualice la vista
            from .tarjetas_db import _cache
            _cache.clear()
            row = cursor.fetchone()
            if not row:
                return None
            return {
                'identificacion': row[0],
                'nombre': row[1],
                'apellido': row[2],
                'telefono': row[3],
                'direccion': row[4],
                'observaciones': row[5],
                'fecha_creacion': row[6]
            }
            
    except Exception as e:
        logger.error(f"Error al actualizar cliente: {e}")
        return False

def eliminar_cliente(identificacion: str) -> bool:
    try:
        with DatabasePool.get_cursor() as cursor:
            query = 'DELETE FROM clientes WHERE identificacion = %s RETURNING identificacion'
            cursor.execute(query, (identificacion,))
            return cursor.fetchone() is not None
    except Exception as e:
        logger.error(f"Error al eliminar cliente: {e}")
        return False

def obtener_clientes(offset: int = 0, limit: int = 50) -> List[Dict]:
    try:
        with DatabasePool.get_cursor() as cursor:
            query = '''
                SELECT 
                    identificacion, nombre, apellido,
                    telefono, direccion, observaciones,
                    COALESCE(score_global, 100)
                FROM clientes 
                ORDER BY nombre, apellido
                OFFSET %s LIMIT %s
            '''
            cursor.execute(query, (offset, limit))
            clientes = cursor.fetchall()
            
            from datetime import date
            return [{
                'identificacion': cliente[0],
                'nombre': cliente[1],
                'apellido': cliente[2],
                'telefono': cliente[3],
                'direccion': cliente[4],
                'observaciones': cliente[5],
                'score_global': cliente[6],
                'fecha_creacion': date.today()
            } for cliente in clientes]
    except Exception as e:
        logger.error(f"Error al obtener clientes: {e}")
        return []

def actualizar_score_historial(identificacion: str, score: int, historial: List[Dict]) -> bool:
    """Actualiza el score y el historial compactado del cliente"""
    try:
        import json
        historial_json = json.dumps(historial)
        with DatabasePool.get_cursor() as cursor:
            query = '''
                UPDATE clientes 
                SET score_global = %s,
                historial_crediticio = %s::jsonb
                WHERE identificacion = %s
            '''
            cursor.execute(query, (score, historial_json, identificacion))
            return True
    except Exception as e:
        logger.error(f"Error al actualizar score/historial: {e}")
        return False

def listar_clientes_por_empleado(empleado_id: str, solo_activos: bool = False) -> List[Dict]:
    """Lista clientes asociados a un empleado, opcionalmente filtrando solo los activos."""
    try:
        with DatabasePool.get_cursor() as cursor:
            # Usamos DISTINCT para evitar duplicados si un cliente tiene varias tarjetas
            if solo_activos:
                query = '''
                    SELECT DISTINCT c.identificacion, c.nombre, c.apellido, c.telefono, c.direccion
                    FROM clientes c
                    JOIN tarjetas t ON c.identificacion = t.cliente_identificacion
                    WHERE t.empleado_identificacion = %s AND t.estado = 'activas'
                    ORDER BY c.nombre, c.apellido
                '''
            else:
                # "Todos": clientes que tengan o hayan tenido tarjetas con este empleado
                query = '''
                    SELECT DISTINCT c.identificacion, c.nombre, c.apellido, c.telefono, c.direccion
                    FROM clientes c
                    JOIN tarjetas t ON c.identificacion = t.cliente_identificacion
                    WHERE t.empleado_identificacion = %s
                    ORDER BY c.nombre, c.apellido
                '''
            cursor.execute(query, (empleado_id,))
            rows = cursor.fetchall()
            return [
                {
                    'identificacion': row[0],
                    'nombre': row[1],
                    'apellido': row[2],
                    'telefono': row[3],
                    'direccion': row[4]
                } for row in rows
            ]
    except Exception as e:
        logger.error(f"Error al listar clientes por empleado: {e}")
        return []

def buscar_datos_clavo(identificacion: str) -> Optional[Dict]:
    """
    Busca cliente por identificación y obtiene sus datos personales
    más la fecha de su última tarjeta (activa o no).
    """
    try:
        with DatabasePool.get_cursor() as cursor:
            # Datos del cliente
            query_cliente = '''
                SELECT identificacion, nombre, apellido, telefono, direccion
                FROM clientes
                WHERE identificacion = %s
            '''
            cursor.execute(query_cliente, (identificacion,))
            cliente = cursor.fetchone()
            
            if not cliente:
                return None
            
            # Última tarjeta (fecha de creación más reciente)
            # Buscamos en todas las tarjetas de este cliente
            query_tarjeta = '''
                SELECT fecha_creacion
                FROM tarjetas
                WHERE cliente_identificacion = %s
                ORDER BY fecha_creacion DESC
                LIMIT 1
            '''
            cursor.execute(query_tarjeta, (identificacion,))
            tarjeta = cursor.fetchone()
            fecha_ultima = tarjeta[0] if tarjeta else None
            
            # Asegurar que sea date (no datetime) para evitar error de validación Pydantic
            if isinstance(fecha_ultima, datetime):
                fecha_ultima = fecha_ultima.date()

            return {
                'identificacion': cliente[0],
                'nombre': cliente[1],
                'apellido': cliente[2],
                'telefono': cliente[3],
                'direccion': cliente[4],
                'fecha_ultima_tarjeta': fecha_ultima
            }
    except Exception as e:
        logger.error(f"Error al buscar clavo: {e}")
        return None
