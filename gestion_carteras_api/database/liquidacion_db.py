from .connection_pool import DatabasePool
import logging
from datetime import datetime, date, timezone
from zoneinfo import ZoneInfo
from typing import Dict, Optional
from decimal import Decimal

logger = logging.getLogger(__name__)

def obtener_datos_liquidacion(empleado_identificacion: str, fecha: date, tz_name: str = 'UTC') -> Dict:
    """
    Obtiene todos los datos necesarios para la liquidación diaria de un empleado
    
    Returns:
        Dict con todas las métricas de liquidación
    """
    try:
        datos = {
            'empleado': empleado_identificacion,
            'fecha': fecha,
            'tarjetas_activas': 0,
            'tarjetas_canceladas': 0,
            'tarjetas_nuevas': 0,
            'total_registros': 0,
            'total_recaudado': Decimal('0'),
            'base_dia': Decimal('0'),
            'prestamos_otorgados': Decimal('0'),
            'total_gastos': Decimal('0'),
            'subtotal': Decimal('0'),
            'total_final': Decimal('0')
        }
        
        # Calcular límites UTC del día local y la fecha local (DATE)
        try:
            tz = ZoneInfo(tz_name or 'UTC')
        except Exception:
            tz = ZoneInfo('UTC')
        start_local = datetime(fecha.year, fecha.month, fecha.day, 0, 0, 0, tzinfo=tz)
        end_local = datetime(fecha.year, fecha.month, fecha.day, 23, 59, 59, 999000, tzinfo=tz)
        start_utc = start_local.astimezone(timezone.utc)
        end_utc = end_local.astimezone(timezone.utc)
        # Para columnas timestamp sin zona, comparar con límites UTC sin tz (naive)
        start_naive = start_utc.replace(tzinfo=None)
        end_naive = end_utc.replace(tzinfo=None)
        fecha_local = fecha
        # debug removido

        with DatabasePool.get_cursor() as cursor:
            # 1. Contar tarjetas activas (todas las activas)
            cursor.execute('''
                SELECT COUNT(*) 
                FROM tarjetas 
                WHERE empleado_identificacion = %s AND estado = 'activas'
            ''', (empleado_identificacion,))
            
            datos['tarjetas_activas'] = cursor.fetchone()[0]
            
            # 2. Contar tarjetas canceladas EN LA FECHA local (fecha_cancelacion es DATE)
            cursor.execute('''
                SELECT COUNT(*) 
                FROM tarjetas 
                WHERE empleado_identificacion = %s 
                AND estado = 'cancelada'
                AND fecha_cancelacion = %s
            ''', (empleado_identificacion, fecha_local))
            
            datos['tarjetas_canceladas'] = cursor.fetchone()[0]
            # debug removido
            
            # 3. Contar tarjetas nuevas del día
            cursor.execute('''
                SELECT COUNT(*) 
                FROM tarjetas 
                WHERE empleado_identificacion = %s 
                  AND fecha_creacion >= %s AND fecha_creacion <= %s
            ''', (empleado_identificacion, start_naive, end_naive))
            
            datos['tarjetas_nuevas'] = cursor.fetchone()[0]
            # debug removido
            
            # 4. Total de registros (abonos del día)
            cursor.execute('''
                SELECT COUNT(*) 
                FROM abonos a
                JOIN tarjetas t ON a.tarjeta_codigo = t.codigo
                WHERE t.empleado_identificacion = %s 
                  AND a.fecha >= %s AND a.fecha <= %s
            ''', (empleado_identificacion, start_naive, end_naive))
            
            total_registros = cursor.fetchone()[0]
            datos['total_registros'] = total_registros
            logger.info(f"Abonos del día encontrados: {total_registros} para {empleado_identificacion} en {fecha}")
            
            # 5. Total recaudado (suma de abonos del día)
            cursor.execute('''
                SELECT COALESCE(SUM(a.monto), 0)
                FROM abonos a
                JOIN tarjetas t ON a.tarjeta_codigo = t.codigo
                WHERE t.empleado_identificacion = %s 
                  AND a.fecha >= %s AND a.fecha <= %s
            ''', (empleado_identificacion, start_naive, end_naive))
            
            result = cursor.fetchone()[0]
            datos['total_recaudado'] = Decimal(str(result)) if result else Decimal('0')
            logger.info(f"Total recaudado: ${datos['total_recaudado']} para {empleado_identificacion} en {fecha}")
            
            # 6. Base del día (desde tabla bases)
            cursor.execute('''
                SELECT COALESCE(SUM(monto), 0)
                FROM bases
                WHERE empleado_id = %s 
                AND fecha = %s
            ''', (empleado_identificacion, fecha))
            
            result = cursor.fetchone()[0]
            datos['base_dia'] = Decimal(str(result)) if result else Decimal('0')
            
            # 7. Préstamos otorgados el día (monto de tarjetas nuevas)
            cursor.execute('''
                SELECT COALESCE(SUM(monto), 0)
                FROM tarjetas 
                WHERE empleado_identificacion = %s 
                  AND fecha_creacion >= %s AND fecha_creacion <= %s
            ''', (empleado_identificacion, start_naive, end_naive))
            
            result = cursor.fetchone()[0]
            datos['prestamos_otorgados'] = Decimal(str(result)) if result else Decimal('0')
            logger.info(f"Préstamos otorgados: ${datos['prestamos_otorgados']} para {empleado_identificacion} en {fecha}")
            
            # 8. Total de gastos del día
            # Total gastos del día local (usar fecha_creacion entre límites UTC)
            cursor.execute('''
                SELECT COALESCE(SUM(valor), 0)
                FROM gastos
                WHERE empleado_identificacion = %s
                  AND fecha_creacion >= %s AND fecha_creacion <= %s
            ''', (empleado_identificacion, start_naive, end_naive))
            result = cursor.fetchone()[0]
            datos['total_gastos'] = Decimal(str(result)) if result is not None else Decimal('0')
            
            # 9. Calcular totales
            # Subtotal = Recaudado + Base - Préstamos
            datos['subtotal'] = (datos['total_recaudado'] + 
                               datos['base_dia'] - 
                               datos['prestamos_otorgados'])
            
            # Total final = Subtotal - Gastos
            datos['total_final'] = datos['subtotal'] - datos['total_gastos']
            
            logger.info(f"Liquidación calculada para {empleado_identificacion} - {fecha}")
            return datos
            
    except Exception as e:
        logger.error(f"Error al obtener datos de liquidación: {e}")
        return datos

def obtener_base_empleado_fecha(empleado_identificacion: str, fecha: date) -> Decimal:
    """Obtiene la base asignada a un empleado en una fecha específica"""
    try:
        with DatabasePool.get_cursor() as cursor:
            cursor.execute('''
                SELECT COALESCE(SUM(monto), 0)
                FROM bases
                WHERE empleado_id = %s AND fecha = %s
            ''', (empleado_identificacion, fecha))
            
            result = cursor.fetchone()[0]
            return Decimal(str(result)) if result else Decimal('0')
            
    except Exception as e:
        logger.error(f"Error al obtener base del empleado: {e}")
        return Decimal('0')

def crear_tabla_bases():
    """Crea la tabla de bases si no existe"""
    try:
        with DatabasePool.get_cursor() as cursor:
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS bases (
                    id SERIAL PRIMARY KEY,
                    empleado_id VARCHAR(20) NOT NULL,
                    fecha DATE NOT NULL,
                    monto NUMERIC(10,2) NOT NULL,
                    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(empleado_id, fecha)
                );
            ''')
            
            # Índice para optimizar consultas
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_bases_empleado_fecha 
                ON bases(empleado_id, fecha);
            ''')
            
            logger.info("Tabla de bases creada correctamente")
            return True
            
    except Exception as e:
        logger.error(f"Error al crear tabla de bases: {e}")
        return False

def asignar_base_empleado(empleado_identificacion: str, fecha: date, monto: Decimal) -> bool:
    """Asigna o actualiza la base de un empleado para una fecha"""
    try:
        with DatabasePool.get_cursor() as cursor:
            cursor.execute('''
                INSERT INTO bases (empleado_id, fecha, monto)
                VALUES (%s, %s, %s)
                ON CONFLICT (empleado_id, fecha) 
                DO UPDATE SET 
                    monto = EXCLUDED.monto
            ''', (empleado_identificacion, fecha, monto))
            
            logger.info(f"Base asignada: {empleado_identificacion} - {fecha} - ${monto}")
            return True
            
    except Exception as e:
        logger.error(f"Error al asignar base: {e}")
        return False

def obtener_resumen_financiero_fecha(fecha: date) -> Dict:
    """Obtiene un resumen financiero de todos los empleados para una fecha"""
    try:
        resumen = {
            'fecha': fecha,
            'total_recaudado_todos': Decimal('0'),
            'total_bases_asignadas': Decimal('0'),
            'total_prestamos_otorgados': Decimal('0'),
            'total_gastos_todos': Decimal('0'),
            'empleados_activos': 0
        }
        
        with DatabasePool.get_cursor() as cursor:
            # Total recaudado por todos los empleados
            cursor.execute('''
                SELECT COALESCE(SUM(a.monto), 0)
                FROM abonos a
                WHERE DATE(a.fecha) = %s
            ''', (fecha,))
            
            result = cursor.fetchone()[0]
            resumen['total_recaudado_todos'] = Decimal(str(result)) if result else Decimal('0')
            
            # Total bases asignadas
            cursor.execute('''
                SELECT COALESCE(SUM(monto), 0)
                FROM bases
                WHERE fecha = %s
            ''', (fecha,))
            
            result = cursor.fetchone()[0]
            resumen['total_bases_asignadas'] = Decimal(str(result)) if result else Decimal('0')
            
            # Total préstamos otorgados
            cursor.execute('''
                SELECT COALESCE(SUM(monto), 0)
                FROM tarjetas
                WHERE DATE(fecha_creacion) = %s
            ''', (fecha,))
            
            result = cursor.fetchone()[0]
            resumen['total_prestamos_otorgados'] = Decimal(str(result)) if result else Decimal('0')
            
            # Total de gastos de todos los empleados
            cursor.execute('''
                SELECT COALESCE(SUM(valor), 0)
                FROM gastos
                WHERE fecha = %s
            ''', (fecha,))
            
            result = cursor.fetchone()[0]
            resumen['total_gastos_todos'] = Decimal(str(result)) if result else Decimal('0')

            # Empleados que trabajaron ese día
            cursor.execute('''
                SELECT COUNT(DISTINCT empleado_id)
                FROM bases
                WHERE fecha = %s
            ''', (fecha,))
            
            resumen['empleados_activos'] = cursor.fetchone()[0]
            
        return resumen
        
    except Exception as e:
        logger.error(f"Error al obtener resumen financiero: {e}")
        # Devuelve el objeto de resumen con los valores por defecto en caso de error
        return resumen 