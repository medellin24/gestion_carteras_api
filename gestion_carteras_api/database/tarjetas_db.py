from .connection_pool import DatabasePool
from .connection_pool import DatabasePool
import logging
from datetime import datetime, date
from typing import List, Dict, Optional, Tuple
from decimal import Decimal

logger = logging.getLogger(__name__)

# Cache para almacenar resultados frecuentes
_cache = {}
_cache_timeout = 300  # 5 minutos

def obtener_todas_las_tarjetas(skip: int = 0, limit: int = 100) -> List[Dict]:
    """Obtiene todas las tarjetas con paginación (para endpoint API)"""
    try:
        with DatabasePool.get_cursor() as cursor:
            cursor.execute('''
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
                    'empleado_nombre': row[13]
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
                    use_cache: bool = True) -> List[Tuple]:
                    
    """
    Obtiene las tarjetas según filtros especificados.
    
    Args:
        empleado_identificacion: Identificación del empleado (opcional)
        estado: Estado de las tarjetas ('activas', 'cancelada', 'pendiente')
        offset: Número de registros a saltar
        limit: Número máximo de registros a retornar
        use_cache: Si se debe usar el caché
    """
    cache_key = f"tarjetas_{empleado_identificacion}_{estado}_{offset}_{limit}"
    
    if use_cache and cache_key in _cache:
        return _cache[cache_key]
        
    try:
        with DatabasePool.get_cursor() as cursor:
            query = '''
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
                    t.fecha_cancelacion
                FROM tarjetas t
                JOIN clientes c ON t.cliente_identificacion = c.identificacion
                WHERE t.estado = %s
                AND (CASE WHEN %s IS NULL THEN TRUE 
                         ELSE t.empleado_identificacion = %s END)
                ORDER BY t.numero_ruta, t.codigo
                OFFSET %s LIMIT %s
            '''
            cursor.execute(query, (estado, empleado_identificacion, empleado_identificacion, offset, limit))
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
            query = '''
                SELECT t.*, c.nombre, c.apellido, c.telefono
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
                    'cliente_nombre': result[11],
                    'cliente_apellido': result[12],
                    'cliente_telefono': result[13]
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
            # Fecha efectiva para código y registro
            target_dt = fecha_creacion or datetime.now()
            target_date = target_dt.date()
            # Generar código único: AAMMDD-XXXX-NNN (formato más corto)
            fecha = target_dt.strftime('%y%m%d')  # Formato de año con 2 dígitos
            ultimos_digitos = cliente_identificacion[-4:]  # Últimos 4 dígitos de la identificación
            
            # Obtener último número secuencial del día para este cliente
            cursor.execute("""
                SELECT COUNT(*) + 1
                FROM tarjetas
                WHERE cliente_identificacion = %s
                AND DATE(fecha_creacion) = %s
            """, (cliente_identificacion, target_date))
            secuencial = cursor.fetchone()[0]
            
            # Crear código único con formato simplificado
            codigo = f"{fecha}-{ultimos_digitos}-{secuencial:03d}"
            
            # Preparar los valores para la inserción usando fecha local
            query = '''
                INSERT INTO tarjetas (
                    codigo, cliente_identificacion, empleado_identificacion,
                    numero_ruta, monto, cuotas, interes,
                    estado, observaciones, fecha_creacion
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, 'activas', %s, %s)
                RETURNING codigo
            '''
            
            cursor.execute(query, (
                codigo,
                cliente_identificacion,
                empleado_identificacion,
                numero_ruta,  # Guardamos como float en la base de datos
                monto,
                cuotas,
                interes,
                observaciones,
                target_dt  # Usar fecha/hora efectiva
            ))
            
            codigo_tarjeta = cursor.fetchone()[0]
            
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
    observaciones: Optional[str] = None
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

def obtener_historial_cliente(cliente_identificacion: str) -> List[Dict]:
    try:
        with DatabasePool.get_cursor() as cursor:
            query = """
                SELECT 
                    t.fecha_creacion,
                    t.monto * (1 + t.interes::decimal/100) as monto_total,
                    t.estado,
                    t.cuotas,
                    t.fecha_cancelacion,
                    CASE 
                        WHEN t.fecha_cancelacion IS NOT NULL THEN 
                            (t.fecha_cancelacion - t.fecha_creacion) - t.cuotas
                        ELSE
                            (CURRENT_DATE - t.fecha_creacion) - t.cuotas
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

def obtener_estadisticas_cliente(cliente_identificacion: str) -> Dict:
    try:
        with DatabasePool.get_cursor() as cursor:
            # Verificar si el cliente existe
            cursor.execute("SELECT * FROM clientes WHERE identificacion = %s", (cliente_identificacion,))
            cliente = cursor.fetchone()

            # Ver todas las tarjetas en la base de datos
            cursor.execute("SELECT codigo, cliente_identificacion, monto, estado FROM tarjetas")
            todas_tarjetas = cursor.fetchall()

            # Ver todos los clientes
            cursor.execute("SELECT identificacion, nombre, apellido FROM clientes")
            todos_clientes = cursor.fetchall()

            # Consulta original
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