# Este archivo contendrá la lógica de la base de datos para las bases.
# Por favor, copie aquí el contenido de 'database/bases_db.py'.

import psycopg2
from .connection_pool import DatabasePool
import logging
from typing import Optional, Tuple, Dict
from datetime import date
from decimal import Decimal

logger = logging.getLogger(__name__)

def insertar_base(empleado_id: str, fecha: date, monto: Decimal) -> Optional[int]:
    try:
        with DatabasePool.get_cursor() as cursor:
            cursor.execute('''
                INSERT INTO bases (empleado_id, fecha, monto)
                VALUES (%s, %s, %s)
                RETURNING id
            ''', (empleado_id, fecha, monto))
            return cursor.fetchone()[0]
    except Exception as e:
        logger.error(f"Error al insertar base: {e}")
        return None

def obtener_base(empleado_id: str, fecha: date) -> Optional[Dict]:
    try:
        with DatabasePool.get_cursor() as cursor:
            cursor.execute('''
                SELECT b.id, b.empleado_id, b.fecha, b.monto, e.nombre 
                FROM bases b
                JOIN empleados e ON e.identificacion = b.empleado_id
                WHERE b.empleado_id = %s AND b.fecha = %s
            ''', (empleado_id, fecha))
            row = cursor.fetchone()
            if not row:
                return None
            return {
                'id': row[0],
                'empleado_id': str(row[1]),
                'fecha': row[2],
                'monto': float(row[3]) if row[3] is not None else 0.0,
                'empleado_nombre': row[4]
            }
    except Exception as e:
        logger.error(f"Error al obtener base: {e}")
        return None

def actualizar_base(empleado_id: str, fecha: date, nuevo_monto: Decimal) -> bool:
    try:
        with DatabasePool.get_cursor() as cursor:
            cursor.execute('''
                UPDATE bases 
                SET monto = %s
                WHERE empleado_id = %s AND fecha = %s
                RETURNING id
            ''', (nuevo_monto, empleado_id, fecha))
            return cursor.fetchone() is not None
    except Exception as e:
        logger.error(f"Error al actualizar base: {e}")
        return False

def eliminar_base(empleado_id: str, fecha: date) -> bool:
    try:
        with DatabasePool.get_cursor() as cursor:
            cursor.execute('''
                DELETE FROM bases 
                WHERE empleado_id = %s AND fecha = %s
                RETURNING id
            ''', (empleado_id, fecha))
            return cursor.fetchone() is not None
    except Exception as e:
        logger.error(f"Error al eliminar base: {e}")
        return False 

def obtener_base_por_id(base_id: int) -> Optional[Dict]:
    try:
        with DatabasePool.get_cursor() as cursor:
            cursor.execute('''
                SELECT b.id, b.empleado_id, b.fecha, b.monto, e.nombre 
                FROM bases b
                JOIN empleados e ON e.identificacion = b.empleado_id
                WHERE b.id = %s
            ''', (base_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return {
                'id': row[0],
                'empleado_id': str(row[1]),
                'fecha': row[2],
                'monto': float(row[3]) if row[3] is not None else 0.0,
                'empleado_nombre': row[4]
            }
    except Exception as e:
        logger.error(f"Error al obtener base por id: {e}")
        return None

def actualizar_base_por_id(base_id: int, nuevo_monto: Decimal) -> bool:
    try:
        with DatabasePool.get_cursor() as cursor:
            cursor.execute('''
                UPDATE bases
                SET monto = %s
                WHERE id = %s
                RETURNING id
            ''', (nuevo_monto, base_id))
            return cursor.fetchone() is not None
    except Exception as e:
        logger.error(f"Error al actualizar base por id: {e}")
        return False

def eliminar_base_por_id(base_id: int) -> bool:
    try:
        with DatabasePool.get_cursor() as cursor:
            cursor.execute('''
                DELETE FROM bases
                WHERE id = %s
                RETURNING id
            ''', (base_id,))
            return cursor.fetchone() is not None
    except Exception as e:
        logger.error(f"Error al eliminar base por id: {e}")
        return False