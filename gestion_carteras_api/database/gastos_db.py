from .connection_pool import DatabasePool
import logging
from datetime import datetime, date
from typing import List, Dict, Optional, Tuple
from decimal import Decimal

logger = logging.getLogger(__name__)

# Tipos de gastos fijos
TIPOS_GASTOS = ['GASOLINA', 'VIATICOS', 'MANTENIMIENTO', 'SALARIO', 'OTROS']

def obtener_tipos_gastos() -> List[Tuple]:
    """Obtiene todos los tipos de gastos disponibles (valores fijos)"""
    return [(i+1, tipo, f'Gastos de {tipo.lower()}') for i, tipo in enumerate(TIPOS_GASTOS)]

def obtener_todos_los_gastos(skip: int = 0, limit: int = 100) -> List[Dict]:
    """Obtiene todos los gastos con paginación"""
    try:
        with DatabasePool.get_cursor() as cursor:
            cursor.execute('''
                SELECT g.id, g.empleado_identificacion, e.nombre as empleado_nombre, 
                       g.tipo, g.valor, g.observacion, g.fecha, g.fecha_creacion
                FROM gastos g
                JOIN empleados e ON g.empleado_identificacion = e.identificacion
                ORDER BY g.fecha_creacion DESC, g.id DESC
                OFFSET %s LIMIT %s
            ''', (skip, limit))
            rows = cursor.fetchall()
            
            # Convertir tuplas a diccionarios para FastAPI
            gastos = []
            for row in rows:
                gasto = {
                    'id': row[0],
                    'empleado_identificacion': row[1],
                    'empleado_nombre': row[2],
                    'tipo': row[3],
                    'valor': row[4],
                    'observacion': row[5],
                    'fecha': row[6],
                    'fecha_creacion': row[7]
                }
                gastos.append(gasto)
            return gastos
            
    except Exception as e:
        logger.error(f"Error al obtener todos los gastos: {e}")
        return []

def obtener_gastos_por_fecha_empleado(fecha: date, empleado_identificacion: str) -> List[Tuple]:
    """Obtiene todos los gastos de un empleado en una fecha específica"""
    try:
        with DatabasePool.get_cursor() as cursor:
            cursor.execute('''
                SELECT id, tipo, valor, observacion, fecha_creacion
                FROM gastos
                WHERE empleado_identificacion = %s AND fecha = %s
                ORDER BY fecha_creacion DESC
            ''', (empleado_identificacion, fecha))
            return cursor.fetchall()
            
    except Exception as e:
        logger.error(f"Error al obtener gastos: {e}")
        return []

def obtener_gasto_por_id(gasto_id: int) -> Optional[Dict]:
    """Obtiene un gasto específico por su ID"""
    try:
        with DatabasePool.get_cursor() as cursor:
            cursor.execute('''
                SELECT id, empleado_identificacion, tipo, valor, observacion, fecha, fecha_creacion
                FROM gastos
                WHERE id = %s
            ''', (gasto_id,))
            result = cursor.fetchone()
            if result:
                return {
                    "id": result[0],
                    "empleado_identificacion": result[1],
                    "tipo": result[2],
                    "valor": result[3],
                    "observacion": result[4],
                    "fecha": result[5],
                    "fecha_creacion": result[6]
                }
            return None
    except Exception as e:
        logger.error(f"Error al obtener gasto por ID: {e}")
        return None

def agregar_gasto(empleado_identificacion: str, tipo: str, valor: Decimal, 
                  fecha: date = None, observacion: str = None) -> Optional[int]:
    """Agrega un nuevo gasto"""
    try:
        # Si no viene fecha, usamos HOY local (por defecto date.today() usa la del servidor)
        if fecha is None:
            fecha = date.today()
        
        # Validar que el tipo sea válido
        if tipo not in TIPOS_GASTOS:
            logger.error(f"Tipo de gasto inválido: {tipo}")
            return None
        
        with DatabasePool.get_cursor() as cursor:
            # Determinamos qué poner en fecha_creacion (TIMESTAMP)
            # Si la fecha es HOY, usamos NOW() para tener la hora exacta real.
            # Si la fecha es diferente a HOY (pasado/futuro), usamos esa fecha a las 12:00:00
            # para evitar que el desfase de zona horaria lo mueva de día.
            
            es_hoy = (fecha == date.today())
            
            if es_hoy:
                ts_creacion_sql = "NOW()"
                params = (empleado_identificacion, tipo, fecha, valor, observacion)
            else:
                # Forzamos una hora segura para evitar que el desfase de zona horaria lo mueva de día.
                # Combinamos la fecha con las 12:00:00.
                from datetime import time as _time
                ts_creacion_val = datetime.combine(fecha, _time(12, 0, 0))
                ts_creacion_sql = "%s"
                params = (empleado_identificacion, tipo, fecha, valor, observacion, ts_creacion_val)

            cursor.execute(f'''
                INSERT INTO gastos (empleado_identificacion, tipo, fecha, valor, observacion, fecha_creacion)
                VALUES (%s, %s, %s, %s, %s, {ts_creacion_sql})
                RETURNING id
            ''', params)
            
            return cursor.fetchone()[0]
            
    except Exception as e:
        logger.error(f"Error al agregar gasto: {e}")
        return None

def actualizar_gasto(gasto_id: int, tipo: str = None, valor: Decimal = None, 
                     observacion: str = None) -> bool:
    """Actualiza un gasto existente"""
    try:
        with DatabasePool.get_cursor() as cursor:
            updates = []
            params = []
            
            if tipo is not None:
                if tipo not in TIPOS_GASTOS:
                    logger.error(f"Tipo de gasto inválido: {tipo}")
                    return False
                updates.append("tipo = %s")
                params.append(tipo)
            if valor is not None:
                updates.append("valor = %s")
                params.append(valor)
            if observacion is not None:
                updates.append("observacion = %s")
                params.append(observacion)
                
            if not updates:
                return False
                
            query = f'''
                UPDATE gastos
                SET {', '.join(updates)}
                WHERE id = %s
                RETURNING id
            '''
            params.append(gasto_id)
            
            cursor.execute(query, params)
            return cursor.fetchone() is not None
            
    except Exception as e:
        logger.error(f"Error al actualizar gasto: {e}")
        return False

def eliminar_gasto(gasto_id: int) -> bool:
    """Elimina un gasto"""
    try:
        with DatabasePool.get_cursor() as cursor:
            cursor.execute('''
                DELETE FROM gastos
                WHERE id = %s
                RETURNING id
            ''', (gasto_id,))
            return cursor.fetchone() is not None
            
    except Exception as e:
        logger.error(f"Error al eliminar gasto: {e}")
        return False

def obtener_total_gastos_fecha_empleado(fecha: date, empleado_identificacion: str) -> Decimal:
    """Obtiene el total de gastos de un empleado en una fecha"""
    try:
        with DatabasePool.get_cursor() as cursor:
            cursor.execute('''
                SELECT COALESCE(SUM(valor), 0)
                FROM gastos
                WHERE empleado_identificacion = %s AND fecha = %s
            ''', (empleado_identificacion, fecha))
            
            result = cursor.fetchone()[0]
            return Decimal(str(result)) if result is not None else Decimal('0')
            
    except Exception as e:
        logger.error(f"Error al calcular total de gastos: {e}")
        return Decimal('0')

def obtener_conteo_gastos_fecha_empleado(fecha: date, empleado_identificacion: str) -> int:
    """Obtiene el número de gastos de un empleado en una fecha"""
    try:
        with DatabasePool.get_cursor() as cursor:
            cursor.execute('''
                SELECT COUNT(*)
                FROM gastos
                WHERE empleado_identificacion = %s AND fecha = %s
            ''', (empleado_identificacion, fecha))
            
            return cursor.fetchone()[0]
            
    except Exception as e:
        logger.error(f"Error al contar gastos: {e}")
        return 0

def obtener_gastos_por_tipo_y_fecha(fecha: date, tipo: str = None) -> List[Tuple]:
    """Obtiene gastos por tipo y fecha (para reportes)"""
    try:
        with DatabasePool.get_cursor() as cursor:
            if tipo:
                cursor.execute('''
                    SELECT empleado_identificacion, tipo, valor, observacion, fecha_creacion
                    FROM gastos
                    WHERE fecha = %s AND tipo = %s
                    ORDER BY fecha_creacion DESC
                ''', (fecha, tipo))
            else:
                cursor.execute('''
                    SELECT empleado_identificacion, tipo, valor, observacion, fecha_creacion
                    FROM gastos
                    WHERE fecha = %s
                    ORDER BY tipo, fecha_creacion DESC
                ''', (fecha,))
            
            return cursor.fetchall()
            
    except Exception as e:
        logger.error(f"Error al obtener gastos por tipo: {e}")
        return []

def obtener_resumen_gastos_por_tipo(fecha: date) -> List[Tuple]:
    """Obtiene un resumen de gastos agrupados por tipo para una fecha"""
    try:
        with DatabasePool.get_cursor() as cursor:
            cursor.execute('''
                SELECT tipo, COUNT(*), SUM(valor)
                FROM gastos
                WHERE fecha = %s
                GROUP BY tipo
                ORDER BY tipo
            ''', (fecha,))
            
            return cursor.fetchall()
            
    except Exception as e:
        logger.error(f"Error al obtener resumen de gastos: {e}")
        return []

# Función simplificada de inicialización (ya no crea tablas, solo verifica)
def inicializar_sistema_gastos():
    """Verifica que el sistema de gastos esté listo"""
    try:
        with DatabasePool.get_cursor() as cursor:
            # Verificar que la tabla gastos existe y tiene las columnas necesarias
            cursor.execute("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'gastos'
                AND column_name IN ('tipo', 'valor', 'observacion')
            """)
            
            columnas = [row[0] for row in cursor.fetchall()]
            columnas_requeridas = ['tipo', 'valor', 'observacion']
            
            if all(col in columnas for col in columnas_requeridas):
                logger.info("Sistema de gastos inicializado correctamente")
                return True
            else:
                faltantes = [col for col in columnas_requeridas if col not in columnas]
                logger.error(f"Faltan columnas en tabla gastos: {faltantes}")
                return False
                
    except Exception as e:
        logger.error(f"Error al verificar sistema de gastos: {e}")
        return False 