from .connection_pool import DatabasePool
import logging
from datetime import datetime, date
from typing import List, Dict, Optional, Tuple
from decimal import Decimal

logger = logging.getLogger(__name__)

# Cache para almacenar resultados frecuentes
_cache = {}
_cache_timeout = 300  # 5 minutos
_modalidad_col_ok: Optional[bool] = None

def _modalidad_column_exists() -> bool:
    global _modalidad_col_ok
    if _modalidad_col_ok is not None:
        return bool(_modalidad_col_ok)
    try:
        with DatabasePool.get_cursor() as cursor:
            cursor.execute(
                """
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = 'public'
                AND table_name = 'tarjetas'
                AND column_name = 'modalidad_pago'
                LIMIT 1
                """
            )
            _modalidad_col_ok = bool(cursor.fetchone())
    except Exception:
        _modalidad_col_ok = False
    return bool(_modalidad_col_ok)

def ensure_modalidad_pago_column():
    """
    Asegura que exista la columna modalidad_pago en la tabla tarjetas.
    - No revienta el arranque si no hay permisos (solo loggea warning).
    """
    try:
        with DatabasePool.get_cursor() as cursor:
            cursor.execute(
                "ALTER TABLE tarjetas "
                "ADD COLUMN IF NOT EXISTS modalidad_pago VARCHAR(20) NOT NULL DEFAULT 'diario'"
            )
        # Si lo logramos (o ya existía), marcar flag
        global _modalidad_col_ok
        _modalidad_col_ok = True
    except Exception as e:
        logger.warning(f"No se pudo asegurar columna modalidad_pago en tarjetas: {e}")

def invalidar_cache_tarjetas(empleado_identificacion: Optional[str] = None):
    """Invalida el caché de tarjetas. Si se especifica empleado, solo invalida ese empleado."""
    global _cache
    if empleado_identificacion:
        # Invalidar solo las entradas de ese empleado
        keys_to_delete = [k for k in _cache.keys() if f"tarjetas_{empleado_identificacion}_" in k]
        for k in keys_to_delete:
            del _cache[k]
        logger.debug(f"Caché de tarjetas invalidado para empleado {empleado_identificacion}")
    else:
        # Invalidar todo el caché
        _cache = {}
        logger.debug("Caché de tarjetas invalidado completamente")

def obtener_todas_las_tarjetas(skip: int = 0, limit: int = 100) -> List[Dict]:
    """Obtiene todas las tarjetas con paginación (para endpoint API)"""
    try:
        with DatabasePool.get_cursor() as cursor:
            modalidad_expr = "COALESCE(t.modalidad_pago, 'diario')" if _modalidad_column_exists() else "'diario'"
            cursor.execute(f'''
                SELECT 
                    t.codigo,
                    t.monto,
                    t.interes,
                    c.nombre, 
                    c.apellido,
                    t.cuotas,
                    t.numero_ruta,
                    t.estado,
                    t.fecha_creacion,
                    t.cliente_identificacion,
                    t.empleado_identificacion,
                    t.observaciones,
                    t.fecha_cancelacion,
                    {modalidad_expr} as modalidad_pago,
                    e.nombre as empleado_nombre
                FROM tarjetas t
                JOIN clientes c ON t.cliente_identificacion = c.identificacion
                JOIN empleados e ON t.empleado_identificacion = e.identificacion
                ORDER BY t.fecha_creacion DESC
                OFFSET %s LIMIT %s
            ''', (skip, limit))
            rows = cursor.fetchall()
            
            # Convertir tuplas a diccionarios para FastAPI con estructura anidada
            tarjetas = []
            for row in rows:
                tarjeta = {
                    'codigo': row[0],
                    'monto': row[1],
                    'interes': row[2],
                    'cliente': {
                        'nombre': row[3],
                        'apellido': row[4],
                        'identificacion': row[9]
                    },
                    'cuotas': row[5],
                    'numero_ruta': row[6],
                    'estado': row[7],
                    'fecha_creacion': row[8],
                    'cliente_identificacion': row[9],
                    'empleado_identificacion': row[10],
                    'observaciones': row[11],
                    'fecha_cancelacion': row[12],
                    'modalidad_pago': row[13] or 'diario',
                    'empleado_nombre': row[14]
                }
                tarjetas.append(tarjeta)
            return tarjetas
            
    except Exception as e:
        logger.error(f"Error al obtener todas las tarjetas: {e}")
        return []

def obtener_tarjetas(empleado_identificacion: Optional[str] = None, 
                    estado: str = 'activas', 
                    offset: int = 0, 
                    limit: int = 200,  # Límite ajustado
                    use_cache: bool = True,
                    fecha_cancelacion_desde: Optional[date] = None) -> List[Tuple]:
                    
    """
    Obtiene las tarjetas según filtros especificados.
    
    Args:
        empleado_identificacion: Identificación del empleado (opcional)
        estado: Estado de las tarjetas ('activas', 'cancelada', 'pendiente')
        offset: Número de registros a saltar
        limit: Número máximo de registros a retornar
        use_cache: Si se debe usar el caché
    """
    cache_key = f"tarjetas_{empleado_identificacion}_{estado}_{offset}_{limit}_{fecha_cancelacion_desde}"
    
    if use_cache and cache_key in _cache:
        return _cache[cache_key]
        
    try:
        with DatabasePool.get_cursor() as cursor:
            modalidad_expr = "COALESCE(t.modalidad_pago, 'diario')" if _modalidad_column_exists() else "'diario'"
            query = f'''
                SELECT 
                    t.codigo,
                    t.monto,
                    t.interes,
                    c.nombre, 
                    c.apellido,
                    t.cuotas,
                    t.numero_ruta,
                    t.estado,
                    t.fecha_creacion,
                    t.cliente_identificacion,
                    t.empleado_identificacion,
                    t.observaciones,
                    t.fecha_cancelacion,
                    {modalidad_expr} as modalidad_pago
                FROM tarjetas t
                JOIN clientes c ON t.cliente_identificacion = c.identificacion
                WHERE t.estado = %s
                AND (CASE WHEN %s IS NULL THEN TRUE 
                         ELSE t.empleado_identificacion = %s END)
            '''
            params: List = [estado, empleado_identificacion, empleado_identificacion]

            # Si se listan canceladas y se pide un "desde", filtrar por fecha_cancelacion (DATE)
            if estado in ('cancelada', 'canceladas') and fecha_cancelacion_desde is not None:
                query += ' AND t.fecha_cancelacion IS NOT NULL AND t.fecha_cancelacion >= %s'
                params.append(fecha_cancelacion_desde)

            query += '''
                ORDER BY t.numero_ruta, t.codigo
                OFFSET %s LIMIT %s
            '''
            params.extend([offset, limit])
            cursor.execute(query, tuple(params))
            result = cursor.fetchall()
            
            if use_cache:
                _cache[cache_key] = result
            return result
            
    except Exception as e:
        logger.error(f"Error al obtener tarjetas: {e}")
        return []

def obtener_tarjeta_por_codigo(codigo: str) -> Optional[Dict]:
    """Obtiene una tarjeta específica por su código"""
    try:
        with DatabasePool.get_cursor() as cursor:
            modalidad_expr = "COALESCE(t.modalidad_pago, 'diario')" if _modalidad_column_exists() else "'diario'"
            query = f'''
                SELECT
                    t.codigo,
                    t.numero_ruta,
                    t.cliente_identificacion,
                    t.empleado_identificacion,
                    t.estado,
                    t.fecha_creacion,
                    t.fecha_cancelacion,
                    t.monto,
                    t.interes,
                    t.cuotas,
                    t.observaciones,
                    {modalidad_expr} as modalidad_pago,
                    c.nombre,
                    c.apellido,
                    c.telefono
                FROM tarjetas t
                JOIN clientes c ON t.cliente_identificacion = c.identificacion
                WHERE t.codigo = %s
            '''
            cursor.execute(query, (codigo,))
            result = cursor.fetchone()
            
            if result:
                return {
                    'codigo': result[0],
                    'numero_ruta': result[1],
                    'cliente_identificacion': result[2],
                    'empleado_identificacion': result[3],
                    'estado': result[4],
                    'fecha_creacion': result[5],
                    'fecha_cancelacion': result[6],
                    'monto': result[7],
                    'interes': result[8],
                    'cuotas': result[9],
                    'observaciones': result[10],
                    'modalidad_pago': result[11] or 'diario',
                    'cliente_nombre': result[12],
                    'cliente_apellido': result[13],
                    'cliente_telefono': result[14]
                }
            return None
            
    except Exception as e:
        logger.error(f"Error al obtener tarjeta por código: {e}")
        return None

def actualizar_estado_tarjeta(tarjeta_codigo: str, nuevo_estado: str) -> bool:
    """Actualiza el estado de una tarjeta"""
    try:
        with DatabasePool.get_cursor() as cursor:
            # Usar fecha local para cancelación
            fecha_cancelacion = date.today() if nuevo_estado == 'cancelada' else None
            
            query = '''
                UPDATE tarjetas 
                SET estado = %s,
                    fecha_cancelacion = %s
                WHERE codigo = %s
                RETURNING codigo
            '''
            cursor.execute(query, (nuevo_estado, fecha_cancelacion, tarjeta_codigo))
            result = cursor.fetchone()
            
            # Limpiar caché relacionado con tarjetas
            _cache.clear()
            
            return result is not None
            
    except Exception as e:
        logger.error(f"Error al actualizar estado de tarjeta: {e}")
        return False

def actualizar_rutas_masivo(updates: List[Tuple[str, Decimal]]) -> bool:
    """
    Actualiza masivamente las rutas de las tarjetas.
    updates: Lista de tuplas (codigo, nuevo_numero_ruta)
    """
    try:
        with DatabasePool.get_cursor() as cursor:
            # executemany es eficiente para actualizaciones por lotes
            query = "UPDATE tarjetas SET numero_ruta = %s WHERE codigo = %s"
            # Invertir el orden para coincidir con la query (ruta, codigo)
            params = [(ruta, codigo) for codigo, ruta in updates]
            cursor.executemany(query, params)
            
            _cache.clear()
            return True
    except Exception as e:
        logger.error(f"Error al actualizar rutas masivamente: {e}")
        return False

def contar_tarjetas_por_estado(empleado_identificacion: Optional[str] = None, 
                              estado: str = 'activas') -> int:
    """Cuenta el número de tarjetas según filtros"""
    try:
        with DatabasePool.get_cursor() as cursor:
            query = '''
                SELECT COUNT(*)
                FROM tarjetas t
                WHERE t.estado = %s
                AND (CASE WHEN %s IS NULL THEN TRUE 
                         ELSE t.empleado_identificacion = %s END)
            '''
            cursor.execute(query, (estado, empleado_identificacion, empleado_identificacion))
            return cursor.fetchone()[0]
            
    except Exception as e:
        logger.error(f"Error al contar tarjetas: {e}")
        return 0 

def obtener_siguiente_numero_ruta(empleado_identificacion: str, posicion_anterior: Optional[Decimal] = None, posicion_siguiente: Optional[Decimal] = None) -> Decimal:
    try:
        with DatabasePool.get_cursor() as cursor:
            # Convertir referencias a enteros (rutas ahora son enteros flexibles hasta 4 dígitos)
            pa = int(posicion_anterior) if posicion_anterior is not None else None
            ps = int(posicion_siguiente) if posicion_siguiente is not None else None

            # Leer todas las rutas del empleado
            cursor.execute("""
                SELECT numero_ruta::int
                FROM tarjetas
                WHERE empleado_identificacion = %s
                ORDER BY numero_ruta::int
            """, (empleado_identificacion,))
            rutas = [r[0] for r in cursor.fetchall()]

            # Si no hay rutas, empezar en 100
            if not rutas:
                return Decimal('100')

            def siguiente_centena(max_ruta: int) -> int:
                c = ((max_ruta // 100) + 1) * 100
                return min(c, 9900)

            # Caso con ambas posiciones: usar exactamente la mitad entera si es posible
            if pa is not None and ps is not None:
                if ps - pa > 1:
                    mitad = (pa + ps) // 2
                    if mitad > pa and mitad < ps and mitad not in rutas:
                        return Decimal(mitad)
                # Sin hueco entero exacto: avanzar a la siguiente centena disponible
                return Decimal(siguiente_centena(max(pa, ps)))

            # Solo anterior: buscar siguiente y aplicar misma estrategia
            if pa is not None:
                # Buscar siguiente existente mayor a pa
                siguientes = [r for r in rutas if r > pa]
                if siguientes:
                    ps2 = siguientes[0]
                    if ps2 - pa > 1:
                        mitad = (pa + ps2) // 2
                        if mitad > pa and mitad < ps2 and mitad not in rutas:
                            return Decimal(mitad)
                    # Si no hay hueco entero, usar la siguiente centena completa
                    return Decimal(siguiente_centena(ps2))
                else:
                    # No hay siguiente: ir a la siguiente centena de inmediato
                    return Decimal(siguiente_centena(pa))

            # Solo siguiente: buscar anterior y aplicar estrategia simétrica
            if ps is not None:
                anteriores = [r for r in rutas if r < ps]
                if anteriores:
                    pa2 = anteriores[-1]
                    if ps - pa2 > 1:
                        mitad = (pa2 + ps) // 2
                        if mitad > pa2 and mitad < ps and mitad not in rutas:
                            return Decimal(mitad)
                    # Sin hueco entero, bajar a la centena anterior si existe
                    cent = ((ps - 1) // 100) * 100
                    if cent >= 100 and cent not in rutas:
                        return Decimal(cent)
                    return Decimal(max(100, ps - 1))
                else:
                    # No hay anterior: tomar la centena previa
                    cent = ((ps - 1) // 100) * 100
                    return Decimal(max(100, cent))

            # Sin referencia: si hay espacio para centena siguiente
            max_r = rutas[-1]
            cand = siguiente_centena(max_r)
            if cand not in rutas:
                return Decimal(cand)
            # Si ya estamos en 9900, intentar la siguiente unidad disponible hasta 9999
            for c in range(max_r + 1, 10000):
                if c not in rutas and c <= 9999:
                    return Decimal(c)
            # Fallback a 9900
            return Decimal('9900')

    except Exception as e:
        logger.error(f"Error al obtener siguiente número de ruta: {e}")
        return Decimal('1.000')

def crear_tarjeta(
    cliente_identificacion: str,
    empleado_identificacion: str,
    monto: Decimal,
    cuotas: int,
    interes: int,
    modalidad_pago: str = 'diario',
    numero_ruta: Optional[Decimal] = None,
    observaciones: Optional[str] = None,
    posicion_anterior: Optional[Decimal] = None,
    posicion_siguiente: Optional[Decimal] = None,
    fecha_creacion: Optional[datetime] = None
) -> Optional[str]:
    try:
        # Validar campos requeridos
        if not all([
            cliente_identificacion,
            empleado_identificacion,
            monto,
            cuotas,
            isinstance(interes, (int, float))
        ]):
            logger.error("Faltan campos requeridos para crear la tarjeta")
            return None

        # Obtener número de ruta si no se proporciona
        if numero_ruta is None:
            numero_ruta = obtener_siguiente_numero_ruta(
                empleado_identificacion,
                posicion_anterior,
                posicion_siguiente
            )

        with DatabasePool.get_cursor() as cursor:
            # Fecha efectiva para código y registro (FORZAR UTC NAIVE)
            from datetime import timezone as _tz
            target_dt_raw = fecha_creacion or datetime.now(_tz.utc)
            # Normalizar a UTC naive (DB TIMESTAMP sin TZ)
            target_dt = target_dt_raw.astimezone(_tz.utc).replace(tzinfo=None)
            # logs de diagnóstico removidos tras estabilizar la migración
            # Prefijo AAMMDD-XXXX-
            fecha_pref = target_dt.strftime('%y%m%d')
            ultimos = cliente_identificacion[-4:]
            prefix = f"{fecha_pref}-{ultimos}-"

            # Calcular punto de inicio consultando el máximo existente con ese prefijo
            try:
                cursor.execute("SELECT MAX(codigo) FROM tarjetas WHERE codigo LIKE %s", (prefix + '%',))
                row = cursor.fetchone()
                start_n = int(row[0][-3:]) + 1 if row and row[0] else 1
            except Exception:
                start_n = 1

            # Intentar insertar de forma atómica evitando colisiones de PK
            col_ok = _modalidad_column_exists()
            for n in range(start_n, 1000):
                codigo_try = f"{prefix}{n:03d}"
                if col_ok:
                    query = '''
                        INSERT INTO tarjetas (
                            codigo, cliente_identificacion, empleado_identificacion,
                            numero_ruta, monto, cuotas, interes,
                            estado, observaciones, fecha_creacion, modalidad_pago
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, 'activas', %s, %s, %s)
                        ON CONFLICT (codigo) DO NOTHING
                        RETURNING codigo
                    '''
                    cursor.execute(query, (
                        codigo_try,
                        cliente_identificacion,
                        empleado_identificacion,
                        numero_ruta,
                        monto,
                        cuotas,
                        interes,
                        observaciones,
                        target_dt,
                        (modalidad_pago or 'diario')
                    ))
                else:
                    query = '''
                        INSERT INTO tarjetas (
                            codigo, cliente_identificacion, empleado_identificacion,
                            numero_ruta, monto, cuotas, interes,
                            estado, observaciones, fecha_creacion
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, 'activas', %s, %s)
                        ON CONFLICT (codigo) DO NOTHING
                        RETURNING codigo
                    '''
                    cursor.execute(query, (
                        codigo_try,
                        cliente_identificacion,
                        empleado_identificacion,
                        numero_ruta,
                        monto,
                        cuotas,
                        interes,
                        observaciones,
                        target_dt
                    ))
                got = cursor.fetchone()
                if got and got[0]:
                    codigo_tarjeta = got[0]
                    # comprobación post-inserción removida (innecesaria en producción)
                    break
            else:
                # no se pudo encontrar un código libre
                logger.error("No hay secuencias disponibles para prefijo %s", prefix)
                return None
            
            # Limpiar el caché después de crear la tarjeta
            _cache.clear()
            
            return codigo_tarjeta
            
    except Exception as e:
        logger.error(f"Error al crear tarjeta: {str(e)}")
        return None

def actualizar_tarjeta(
    tarjeta_codigo: str,
    monto: Optional[Decimal] = None,
    cuotas: Optional[int] = None,
    fecha_creacion: Optional[datetime] = None,
    numero_ruta: Optional[Decimal] = None,
    interes: Optional[int] = None,
    observaciones: Optional[str] = None,
    modalidad_pago: Optional[str] = None
) -> bool:
    """Actualiza los campos editables de una tarjeta"""
    try:
        with DatabasePool.get_cursor() as cursor:
            updates = []
            params = []
            
            if monto is not None:
                updates.append("monto = %s")
                params.append(monto)
            if cuotas is not None:
                updates.append("cuotas = %s")
                params.append(cuotas)
            if fecha_creacion is not None:
                updates.append("fecha_creacion = %s")
                params.append(fecha_creacion)
            if numero_ruta is not None:
                updates.append("numero_ruta = %s")
                params.append(numero_ruta)
            if interes is not None:
                updates.append("interes = %s")
                params.append(interes)
            if observaciones is not None:
                updates.append("observaciones = %s")
                params.append(observaciones)
            if modalidad_pago is not None and _modalidad_column_exists():
                updates.append("modalidad_pago = %s")
                params.append(modalidad_pago)
                
            if not updates:
                return False
                
            query = f'''
                UPDATE tarjetas 
                SET {', '.join(updates)}
                WHERE codigo = %s
                RETURNING codigo
            '''
            params.append(tarjeta_codigo)
            cursor.execute(query, params)
            
            _cache.clear()
            return cursor.fetchone() is not None
    except Exception as e:
        logger.error(f"Error al actualizar tarjeta: {e}")
        return False

def buscar_tarjetas(
    termino: str,
    empleado_identificacion: Optional[str] = None,
    estado: str = 'activas'
) -> List[Tuple]:
    """Busca tarjetas por nombre o apellido del cliente"""
    try:
        with DatabasePool.get_cursor() as cursor:
            query = '''
                SELECT t.codigo, t.codigo, t.numero_ruta, 
                       c.nombre, c.apellido,
                       t.fecha_creacion, t.monto, t.cuotas
                FROM tarjetas t
                JOIN clientes c ON t.cliente_identificacion = c.identificacion
                WHERE t.estado = %s
                AND (LOWER(c.nombre) LIKE LOWER(%s) OR 
                     LOWER(c.apellido) LIKE LOWER(%s))
                AND (CASE WHEN %s IS NULL THEN TRUE 
                         ELSE t.empleado_identificacion = %s END)
                ORDER BY t.numero_ruta
            '''
            termino_busqueda = f'%{termino}%'
            cursor.execute(query, (
                estado, termino_busqueda, termino_busqueda,
                empleado_identificacion, empleado_identificacion
            ))
            return cursor.fetchall()
    except Exception as e:
        logger.error(f"Error al buscar tarjetas: {e}")
        return []

def mover_tarjeta(
    tarjeta_codigo: str,
    nuevo_empleado_identificacion: str,
    nuevo_numero_ruta: Optional[Decimal] = None
) -> bool:
    """Asigna una tarjeta a otro empleado"""
    try:
        with DatabasePool.get_cursor() as cursor:
            if nuevo_numero_ruta is None:
                # Obtener último número de ruta del nuevo empleado
                cursor.execute('''
                    SELECT COALESCE(MAX(numero_ruta), 0) + 1
                    FROM tarjetas
                    WHERE empleado_identificacion = %s
                ''', (nuevo_empleado_identificacion,))
                nuevo_numero_ruta = cursor.fetchone()[0]
            
            query = '''
                UPDATE tarjetas
                SET empleado_identificacion = %s,
                    numero_ruta = %s
                WHERE codigo = %s
                RETURNING codigo
            '''
            cursor.execute(query, (
                nuevo_empleado_identificacion, nuevo_numero_ruta, tarjeta_codigo
            ))
            
            _cache.clear()
            return cursor.fetchone() is not None
    except Exception as e:
        logger.error(f"Error al mover tarjeta: {e}")
        return False

def eliminar_tarjeta(tarjeta_codigo: str) -> bool:
    """Elimina una tarjeta y sus abonos asociados"""
    try:
        with DatabasePool.get_cursor() as cursor:
            # Primero eliminar abonos asociados
            cursor.execute('DELETE FROM abonos WHERE tarjeta_codigo = %s', (tarjeta_codigo,))
            
            # Luego eliminar la tarjeta
            cursor.execute('DELETE FROM tarjetas WHERE codigo = %s RETURNING codigo', (tarjeta_codigo,))
            
            _cache.clear()  # Limpiar caché
            return cursor.fetchone() is not None
            
    except Exception as e:
        logger.error(f"Error al eliminar tarjeta: {e}")
        return False

def obtener_historial_cliente(cliente_identificacion: str, cuenta_id: Optional[int] = None) -> List[Dict]:
    """
    Obtiene el historial de tarjetas de un cliente.
    Si cuenta_id se proporciona, filtra solo tarjetas de empleados de esa cuenta (aislamiento multi-tenant).
    Si cuenta_id es None, devuelve todas las tarjetas (para DataCrédito global).
    """
    try:
        with DatabasePool.get_cursor() as cursor:
            if cuenta_id is not None:
                # Filtrar por empleados de la cuenta específica
                query = """
                    SELECT 
                        t.fecha_creacion,
                        t.monto * (1 + t.interes::decimal/100) as monto_total,
                        t.estado,
                        t.cuotas,
                        t.fecha_cancelacion,
                        CASE 
                            WHEN t.fecha_cancelacion IS NOT NULL THEN 
                                (DATE(t.fecha_cancelacion) - DATE(t.fecha_creacion)) - t.cuotas
                            ELSE
                                (CURRENT_DATE - DATE(t.fecha_creacion)) - t.cuotas
                        END as dias_atrasados,
                        t.interes,
                        e.nombre as empleado
                    FROM tarjetas t
                    JOIN empleados e ON t.empleado_identificacion = e.identificacion
                    WHERE t.cliente_identificacion = %s
                      AND e.cuenta_id = %s
                    ORDER BY t.fecha_creacion DESC
                """
                cursor.execute(query, (cliente_identificacion, cuenta_id))
            else:
                # Sin filtro de cuenta (global)
                query = """
                    SELECT 
                        t.fecha_creacion,
                        t.monto * (1 + t.interes::decimal/100) as monto_total,
                        t.estado,
                        t.cuotas,
                        t.fecha_cancelacion,
                        CASE 
                            WHEN t.fecha_cancelacion IS NOT NULL THEN 
                                (DATE(t.fecha_cancelacion) - DATE(t.fecha_creacion)) - t.cuotas
                            ELSE
                                (CURRENT_DATE - DATE(t.fecha_creacion)) - t.cuotas
                        END as dias_atrasados,
                        t.interes,
                        e.nombre as empleado
                    FROM tarjetas t
                    JOIN empleados e ON t.empleado_identificacion = e.identificacion
                    WHERE t.cliente_identificacion = %s
                    ORDER BY t.fecha_creacion DESC
                """
                cursor.execute(query, (cliente_identificacion,))
            
            registros = cursor.fetchall()
            
            resultados = []
            for registro in registros:
                resultados.append({
                    'fecha_creacion': registro[0],
                    'monto_total': registro[1],
                    'estado': registro[2],
                    'cuotas': registro[3],
                    'fecha_cancelacion': registro[4],
                    'dias_atrasados': registro[5],
                    'interes': registro[6],
                    'empleado': registro[7]
                })
            return resultados
    except Exception as e:
        logger.error(f"Error al obtener historial del cliente: {e}")
        return []

def obtener_estadisticas_cliente(cliente_identificacion: str, cuenta_id: Optional[int] = None) -> Dict:
    """
    Obtiene estadísticas de tarjetas de un cliente.
    Si cuenta_id se proporciona, filtra solo tarjetas de empleados de esa cuenta (aislamiento multi-tenant).
    Si cuenta_id es None, devuelve estadísticas globales.
    """
    try:
        with DatabasePool.get_cursor() as cursor:
            if cuenta_id is not None:
                # Filtrar por empleados de la cuenta específica
                query = """
                    SELECT 
                        COUNT(*) as cantidad_tarjetas,
                        COALESCE(SUM(t.monto * (1 + t.interes::decimal/100)), 0) as total_prestado
                    FROM tarjetas t
                    JOIN empleados e ON t.empleado_identificacion = e.identificacion
                    WHERE t.cliente_identificacion = %s
                      AND e.cuenta_id = %s
                """
                cursor.execute(query, (cliente_identificacion, cuenta_id))
            else:
                # Sin filtro de cuenta (global)
                query = """
                    SELECT 
                        COUNT(*) as cantidad_tarjetas,
                        COALESCE(SUM(monto * (1 + interes::decimal/100)), 0) as total_prestado
                    FROM tarjetas
                    WHERE cliente_identificacion = %s
                """
                cursor.execute(query, (cliente_identificacion,))
            
            row = cursor.fetchone()
            return {
                'cantidad_tarjetas': row[0],
                'total_prestado': row[1] or Decimal('0')
            }
    except Exception as e:
        logger.error(f"Error al obtener estadísticas del cliente: {e}")
        return {'cantidad_tarjetas': 0, 'total_prestado': Decimal('0')}

def obtener_tarjetas_cliente(cliente_identificacion: str, cuenta_id: Optional[int] = None) -> List[Dict]:
    """
    Obtiene todas las tarjetas de un cliente (activas, canceladas, pendientes)
    con sus datos crudos para análisis.
    
    Si cuenta_id se proporciona, filtra solo tarjetas de empleados de esa cuenta.
    Si cuenta_id es None, devuelve todas las tarjetas (para DataCrédito global).
    """
    try:
        with DatabasePool.get_cursor() as cursor:
            if cuenta_id is not None:
                # Filtrar por empleados de la cuenta específica
                query = '''
                    SELECT 
                        t.codigo,
                        t.monto,
                        t.interes,
                        t.cuotas,
                        t.numero_ruta,
                        t.estado,
                        t.fecha_creacion,
                        t.fecha_cancelacion,
                        t.observaciones,
                        t.empleado_identificacion
                    FROM tarjetas t
                    JOIN empleados e ON t.empleado_identificacion = e.identificacion
                    WHERE t.cliente_identificacion = %s
                      AND e.cuenta_id = %s
                    ORDER BY t.fecha_creacion DESC
                '''
                cursor.execute(query, (cliente_identificacion, cuenta_id))
            else:
                # Sin filtro de cuenta (global para DataCrédito)
                # Necesitamos cuenta_id para anonimizar correctamente por empresa
                query = '''
                    SELECT 
                        t.codigo,
                        t.monto,
                        t.interes,
                        t.cuotas,
                        t.numero_ruta,
                        t.estado,
                        t.fecha_creacion,
                        t.fecha_cancelacion,
                        t.observaciones,
                        t.empleado_identificacion,
                        COALESCE(t.modalidad_pago, 'diario') as modalidad_pago,
                        e.cuenta_id
                    FROM tarjetas t
                    JOIN empleados e ON t.empleado_identificacion = e.identificacion
                    WHERE t.cliente_identificacion = %s
                    ORDER BY t.fecha_creacion DESC
                '''
                cursor.execute(query, (cliente_identificacion,))
            
            rows = cursor.fetchall()
            
            tarjetas = []
            for row in rows:
                # Manejar variabilidad en columnas retornadas según la rama del if
                if cuenta_id is not None:
                    # Rama filtrada (sin JOIN extra, estructura vieja)
                    tarjeta = {
                        'codigo': row[0],
                        'monto': row[1],
                        'interes': row[2],
                        'cuotas': row[3],
                        'numero_ruta': row[4],
                        'estado': row[5],
                        'fecha_creacion': row[6],
                        'fecha_cancelacion': row[7],
                        'observaciones': row[8],
                        'empleado_identificacion': row[9]
                    }
                else:
                    # Rama global (con modalidad y cuenta_id)
                    tarjeta = {
                        'codigo': row[0],
                        'monto': row[1],
                        'interes': row[2],
                        'cuotas': row[3],
                        'numero_ruta': row[4],
                        'estado': row[5],
                        'fecha_creacion': row[6],
                        'fecha_cancelacion': row[7],
                        'observaciones': row[8],
                        'empleado_identificacion': row[9],
                        'modalidad_pago': row[10],
                        'cuenta_id': row[11]
                    }
                tarjetas.append(tarjeta)
            return tarjetas
            
    except Exception as e:
        logger.error(f"Error al obtener tarjetas del cliente: {e}")
        return []

def obtener_tarjetas_canceladas_antiguas(meses_antiguedad: int = 12) -> List[Dict]:
    """
    Obtiene tarjetas canceladas hace más de 'meses_antiguedad'.
    Devuelve lista de dicts con toda la info necesaria para RiskEngine.
    """
    try:
        from datetime import timedelta
        with DatabasePool.get_cursor() as cursor:
            # Calcular fecha de corte
            fecha_corte = date.today() - timedelta(days=meses_antiguedad*30)
            
            modalidad_expr = "COALESCE(t.modalidad_pago, 'diario')" if _modalidad_column_exists() else "'diario'"
            
            # Necesitamos cliente_identificacion para agrupar y actualizar el historial
            # Necesitamos cuenta_id para el historial
            query = f'''
                SELECT 
                    t.codigo,
                    t.monto,
                    t.interes,
                    t.cuotas,
                    t.numero_ruta,
                    t.estado,
                    t.fecha_creacion,
                    t.fecha_cancelacion,
                    t.cliente_identificacion,
                    t.empleado_identificacion,
                    {modalidad_expr} as modalidad_pago,
                    e.cuenta_id
                FROM tarjetas t
                JOIN empleados e ON t.empleado_identificacion = e.identificacion
                WHERE t.estado IN ('cancelada', 'canceladas')
                  AND t.fecha_cancelacion IS NOT NULL
                  AND t.fecha_cancelacion <= %s
                ORDER BY t.cliente_identificacion
            '''
            cursor.execute(query, (fecha_corte,))
            rows = cursor.fetchall()
            
            tarjetas = []
            for row in rows:
                t = {
                    'codigo': row[0],
                    'monto': row[1],
                    'interes': row[2],
                    'cuotas': row[3],
                    'numero_ruta': row[4],
                    'estado': row[5],
                    'fecha_creacion': row[6],
                    'fecha_cancelacion': row[7],
                    'cliente_identificacion': row[8],
                    'empleado_identificacion': row[9],
                    'modalidad_pago': row[10],
                    'cuenta_id': row[11]
                }
                tarjetas.append(t)
            return tarjetas
    except Exception as e:
        logger.error(f"Error al obtener tarjetas antiguas: {e}")
        return []

def verificar_reactivacion_tarjeta(tarjeta_codigo: str) -> bool:
    """
    Verifica el saldo de una tarjeta y actualiza su estado automáticamente.
    - Si saldo > 0 y estaba cancelada -> Reactiva a 'activas' y quita fecha_cancelacion.
    - Si saldo <= 0 y estaba activa -> Cancela y pone fecha_cancelacion.
    Retorna True si hubo cambio de estado.
    """
    try:
        # Importación local para evitar circularidad
        from .abonos_db import obtener_saldo_tarjeta
        
        saldo = obtener_saldo_tarjeta(tarjeta_codigo)
        if saldo is None:
            return False
            
        tarjeta = obtener_tarjeta_por_codigo(tarjeta_codigo)
        if not tarjeta:
            return False
            
        estado_actual = tarjeta.get('estado')
        nuevo_estado = None
        nueva_fecha_cancelacion = None
        cambio_necesario = False
        
        # Lógica de transición
        if saldo > 0 and estado_actual in ('cancelada', 'canceladas'):
            nuevo_estado = 'activas'
            nueva_fecha_cancelacion = None
            cambio_necesario = True
            logger.info(f"Reactivando tarjeta {tarjeta_codigo} (Saldo: {saldo})")
            
        elif saldo <= 0 and estado_actual == 'activas':
            nuevo_estado = 'cancelada'
            nueva_fecha_cancelacion = date.today()
            cambio_necesario = True
            logger.info(f"Cancelando tarjeta {tarjeta_codigo} (Saldo: {saldo})")
            
        if cambio_necesario:
            with DatabasePool.get_cursor() as cursor:
                query = '''
                    UPDATE tarjetas 
                    SET estado = %s,
                        fecha_cancelacion = %s
                    WHERE codigo = %s
                '''
                cursor.execute(query, (nuevo_estado, nueva_fecha_cancelacion, tarjeta_codigo))
                
            _cache.clear()
            return True
            
        return False
        
    except Exception as e:
        logger.error(f"Error al verificar reactivación de tarjeta {tarjeta_codigo}: {e}")
        return False

def listar_tarjetas_sin_abono_dia(empleado_identificacion: str, fecha_filtro: date, timezone_name: Optional[str] = None) -> List[Dict]:
    """
    Lista las tarjetas ACTIVAS asignadas al empleado que NO tienen abonos
    registrados en la fecha específica (fecha local del usuario).
    """
    try:
        from datetime import datetime, timezone
        from zoneinfo import ZoneInfo
        
        tz_name = timezone_name or 'America/Bogota'
        
        # ... (código existente comentado o eliminado en el replace) ...

        with DatabasePool.get_cursor() as cursor:
            modalidad_expr = "COALESCE(t.modalidad_pago, 'diario')" if _modalidad_column_exists() else "'diario'"
            
            query = f'''
                SELECT 
                    t.codigo, t.monto, t.cuotas,
                    c.nombre, c.apellido, t.numero_ruta,
                    t.interes,
                    t.fecha_creacion,
                    {modalidad_expr},
                    COALESCE(SUM(ah.monto), 0) as total_pagado
                FROM tarjetas t
                JOIN clientes c ON t.cliente_identificacion = c.identificacion
                LEFT JOIN abonos ah ON t.codigo = ah.tarjeta_codigo
                WHERE t.empleado_identificacion = %s
                  AND t.estado = 'activas'
                  AND t.codigo NOT IN (
                      SELECT a.tarjeta_codigo 
                      FROM abonos a
                      JOIN tarjetas t2 ON a.tarjeta_codigo = t2.codigo
                      WHERE t2.empleado_identificacion = %s
                        AND (a.fecha AT TIME ZONE 'UTC' AT TIME ZONE %s)::date = %s
                  )
                GROUP BY t.codigo, c.identificacion
                ORDER BY t.numero_ruta ASC, t.codigo ASC
            '''
            cursor.execute(query, (empleado_identificacion, empleado_identificacion, tz_name, fecha_filtro))
            rows = cursor.fetchall()
            
            resultado = []
            for row in rows:
                codigo = row[0]
                monto = Decimal(str(row[1] or 0))
                cuotas = int(row[2] or 1)
                interes = Decimal(str(row[6] or 0))
                fecha_creacion = row[7]
                if hasattr(fecha_creacion, 'date'): fecha_creacion = fecha_creacion.date()
                modalidad = str(row[8] or 'diario').lower()
                pagado = Decimal(str(row[9] or 0))
                
                # Calcular atraso
                if 'semanal' in modalidad: factor = 7
                elif 'quincenal' in modalidad: factor = 15
                elif 'mensual' in modalidad: factor = 30
                else: factor = 1
                
                dias_transcurridos = (fecha_filtro - fecha_creacion).days
                cuotas_teoricas = dias_transcurridos // factor
                
                monto_total_deuda = monto * (1 + interes/100)
                valor_cuota = monto_total_deuda / cuotas if cuotas > 0 else Decimal(1)
                
                cuotas_pagadas = int(pagado / valor_cuota) if valor_cuota > 0 else 0
                atraso = max(0, cuotas_teoricas - cuotas_pagadas)

                resultado.append({
                    'codigo': codigo,
                    'monto': float(monto),
                    'cuotas': cuotas,
                    'cliente_nombre': row[3],
                    'cliente_apellido': row[4],
                    'numero_ruta': row[5],
                    'interes': float(interes),
                    'atraso': atraso
                })
            return resultado

    except Exception as e:
        logger.error(f"Error al listar tarjetas sin abono: {e}")
        return []

def calcular_total_clavos(empleado_identificacion: Optional[str], fecha_corte: date, cuenta_id: Optional[int] = None) -> Decimal:
    """
    Calcula el saldo total de tarjetas 'activas' que tienen más de 60 días de vencidas
    a la fecha de corte. Aislado por cuenta si se proporciona cuenta_id.
    
    Criterio Clavo: (Fecha Corte - Fecha Vencimiento) >= 60 días.
    Fecha Vencimiento = Fecha Creación + (Cuotas * Factor Modalidad)
    Factor Modalidad: diario=1, semanal=7, quincenal=15, mensual=30.
    """
    try:
        with DatabasePool.get_cursor() as cursor:
            # Filtros de aislamiento
            where_clauses = ["t.estado = 'activas'"]
            params = []
            
            if empleado_identificacion:
                where_clauses.append("t.empleado_identificacion = %s")
                params.append(empleado_identificacion)
            
            if cuenta_id is not None:
                where_clauses.append("e.cuenta_id = %s")
                params.append(cuenta_id)

            modalidad_expr = "COALESCE(t.modalidad_pago, 'diario')" if _modalidad_column_exists() else "'diario'"
            
            where_sql = " AND ".join(where_clauses)
            
            query = f'''
                SELECT 
                    t.codigo, 
                    t.fecha_creacion, 
                    t.cuotas, 
                    {modalidad_expr},
                    t.monto,
                    t.interes,
                    COALESCE(SUM(a.monto), 0) as abonado
                FROM tarjetas t
                JOIN empleados e ON t.empleado_identificacion = e.identificacion
                LEFT JOIN abonos a ON t.codigo = a.tarjeta_codigo
                WHERE {where_sql}
                GROUP BY t.codigo, t.fecha_creacion, t.cuotas, t.modalidad_pago, t.monto, t.interes
            '''
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            total_clavos = Decimal(0)
            
            from datetime import timedelta, datetime
            
            for row in rows:
                fecha_creacion = row[1]
                if not fecha_creacion: continue

                # Asegurar que es date
                if isinstance(fecha_creacion, datetime):
                    fecha_creacion = fecha_creacion.date()
                
                cuotas = int(row[2] or 0)
                modalidad = str(row[3] or 'diario').lower()
                monto = Decimal(row[4] or 0)
                interes = Decimal(row[5] or 0)
                abonado = Decimal(row[6] or 0)
                
                monto_total = monto * (1 + (interes / Decimal(100)))
                saldo = monto_total - abonado
                
                if saldo <= 0: continue # No debe pasar si está activa, pero por seguridad
                
                # Factor modalidad
                if 'semanal' in modalidad: factor = 7
                elif 'quincenal' in modalidad: factor = 15
                elif 'mensual' in modalidad: factor = 30
                else: factor = 1
                
                dias_duracion = cuotas * factor
                fecha_vencimiento = fecha_creacion + timedelta(days=dias_duracion)
                
                # Días pasados desde vencimiento hasta corte
                dias_pasados = (fecha_corte - fecha_vencimiento).days
                
                if dias_pasados >= 60:
                    total_clavos += saldo
            
            return total_clavos

    except Exception as e:
        logger.error(f"Error calculando total clavos: {e}")
        return Decimal(0)
