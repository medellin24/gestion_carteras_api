from .connection_pool import DatabasePool
import logging
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from decimal import Decimal

logger = logging.getLogger(__name__)

def obtener_abonos_tarjeta(tarjeta_codigo: str) -> List[Tuple]:
    """Obtiene todos los abonos de una tarjeta específica"""
    try:
        with DatabasePool.get_cursor() as cursor:
            query = '''
                SELECT id, fecha, monto, indice_orden, metodo_pago
                FROM abonos
                WHERE tarjeta_codigo = %s
                ORDER BY fecha DESC, indice_orden DESC
            '''
            cursor.execute(query, (tarjeta_codigo,))
            return cursor.fetchall()
            
    except Exception as e:
        logger.error(f"Error al obtener abonos: {e}")
        return []

def obtener_abono_por_id(abono_id: int) -> Optional[Dict]:
    """Obtiene un abono específico por su ID"""
    try:
        with DatabasePool.get_cursor() as cursor:
            query = '''
                SELECT id, tarjeta_codigo, fecha, monto, indice_orden, metodo_pago
                FROM abonos
                WHERE id = %s
            '''
            cursor.execute(query, (abono_id,))
            result = cursor.fetchone()
            if result:
                return {
                    "id": result[0],
                    "tarjeta_codigo": result[1],
                    "fecha": result[2],
                    "monto": result[3],
                    "indice_orden": result[4],
                    "metodo_pago": result[5]
                }
            return None
    except Exception as e:
        logger.error(f"Error al obtener abono por ID: {e}")
        return None

def registrar_abono(tarjeta_codigo: str, monto: Decimal, metodo_pago: str = 'efectivo') -> Optional[int]:
    """
    Registra un nuevo abono para una tarjeta
    Retorna el ID del abono creado o None si hay error
    """
    try:
        with DatabasePool.get_cursor() as cursor:
            # Obtener el siguiente índice de orden
            cursor.execute('''
                SELECT COALESCE(MAX(indice_orden), 0) + 1
                FROM abonos
                WHERE tarjeta_codigo = %s
            ''', (tarjeta_codigo,))
            indice_orden = cursor.fetchone()[0]
            
            # Insertar el abono usando fecha/hora local
            query = '''
                INSERT INTO abonos (tarjeta_codigo, fecha, monto, indice_orden, metodo_pago)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id
            '''
            cursor.execute(query, (tarjeta_codigo, datetime.now(), monto, indice_orden, metodo_pago))
            return cursor.fetchone()[0]
            
    except Exception as e:
        logger.error(f"Error al registrar abono: {e}")
        return None

def obtener_total_abonado(tarjeta_codigo: str) -> Decimal:
    """Calcula el total abonado en una tarjeta"""
    try:
        with DatabasePool.get_cursor() as cursor:
            query = '''
                SELECT COALESCE(SUM(monto), 0)
                FROM abonos
                WHERE tarjeta_codigo = %s
            '''
            cursor.execute(query, (tarjeta_codigo,))
            return cursor.fetchone()[0]
            
    except Exception as e:
        logger.error(f"Error al calcular total abonado: {e}")
        return Decimal('0')

def obtener_saldo_tarjeta(tarjeta_codigo: str) -> Optional[Decimal]:
    """Calcula el saldo pendiente de una tarjeta (monto total - total abonado)"""
    try:
        from .tarjetas_db import obtener_tarjeta_por_codigo
        
        # Obtener la tarjeta para calcular el monto total
        tarjeta = obtener_tarjeta_por_codigo(tarjeta_codigo)
        if not tarjeta:
            return None
            
        monto = Decimal(str(tarjeta.get('monto', 0)))
        interes = Decimal(str(tarjeta.get('interes', 0)))
        
        # Calcular monto total con interés
        monto_total = monto * (1 + interes / 100)
        
        # Obtener total abonado
        total_abonado = obtener_total_abonado(tarjeta_codigo)
        
        # Calcular saldo pendiente
        saldo_pendiente = monto_total - total_abonado
        
        return saldo_pendiente
        
    except Exception as e:
        logger.error(f"Error al calcular saldo de tarjeta: {e}")
        return None

def eliminar_ultimo_abono(tarjeta_codigo: str) -> bool:
    """Elimina el último abono registrado de una tarjeta"""
    try:
        with DatabasePool.get_cursor() as cursor:
            query = '''
                DELETE FROM abonos
                WHERE id = (
                    SELECT id
                    FROM abonos
                    WHERE tarjeta_codigo = %s
                    ORDER BY fecha DESC, indice_orden DESC
                    LIMIT 1
                )
                RETURNING id
            '''
            cursor.execute(query, (tarjeta_codigo,))
            return cursor.fetchone() is not None
            
    except Exception as e:
        logger.error(f"Error al eliminar último abono: {e}")
        return False

def eliminar_abono_por_id(abono_id: int) -> bool:
    """Elimina un abono específico por su ID"""
    try:
        with DatabasePool.get_cursor() as cursor:
            query = '''
                DELETE FROM abonos
                WHERE id = %s
                RETURNING id
            '''
            cursor.execute(query, (abono_id,))
            return cursor.fetchone() is not None
            
    except Exception as e:
        logger.error(f"Error al eliminar abono por ID: {e}")
        return False

def actualizar_abono(
    abono_id: int,
    monto: Optional[Decimal] = None,
    fecha: Optional[datetime] = None,
    metodo_pago: Optional[str] = None
) -> bool:
    """Actualiza un abono existente"""
    try:
        with DatabasePool.get_cursor() as cursor:
            updates = []
            params = []
            
            if monto is not None:
                updates.append("monto = %s")
                params.append(monto)
            if fecha is not None:
                updates.append("fecha = %s")
                params.append(fecha)
            if metodo_pago is not None:
                updates.append("metodo_pago = %s")
                params.append(metodo_pago)
                
            if not updates:
                return False
                
            query = f'''
                UPDATE abonos
                SET {', '.join(updates)}
                WHERE id = %s
                RETURNING id
            '''
            params.append(abono_id)
            cursor.execute(query, params)
            return cursor.fetchone() is not None
    except Exception as e:
        logger.error(f"Error al actualizar abono: {e}")
        return False

def obtener_abonos_por_fecha(
    fecha: datetime,
    empleado_identificacion: Optional[str] = None
) -> List[Tuple]:
    """Obtiene abonos por fecha y empleado opcional"""
    try:
        with DatabasePool.get_cursor() as cursor:
            query = '''
                SELECT a.id, a.fecha, a.monto, t.codigo,
                       c.nombre, c.apellido
                FROM abonos a
                JOIN tarjetas t ON a.tarjeta_codigo = t.codigo
                JOIN clientes c ON t.cliente_identificacion = c.identificacion
                WHERE DATE(a.fecha) = %s
                AND (CASE WHEN %s IS NULL THEN TRUE 
                         ELSE t.empleado_identificacion = %s END)
                ORDER BY a.fecha DESC
            '''
            cursor.execute(query, (fecha, empleado_identificacion, empleado_identificacion))
            return cursor.fetchall()
    except Exception as e:
        logger.error(f"Error al obtener abonos por fecha: {e}")
        return [] 