import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Optional, Dict, List, Tuple

from .connection_pool import DatabasePool

logger = logging.getLogger(__name__)


def verificar_esquema_caja() -> Dict:
    """Verifica existencia de la tabla real 'control_caja' y sus columnas.
    Mapea:
      - tabla_caja => existencia de columna 'saldo_caja'
      - tabla_salidas => existencia de columna 'dividendos'
    """
    info = {
        "ok": False,
        "tabla_caja": False,
        "tabla_salidas": False,
        "columnas_caja": [],
        "columnas_salidas": [],
    }
    try:
        with DatabasePool.get_cursor() as cur:
            cur.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'control_caja'
                ORDER BY ordinal_position
                """
            )
            cols = [r[0] for r in cur.fetchall() or []]
            # Exponer columnas en los campos esperados
            info["columnas_caja"] = cols
            info["columnas_salidas"] = cols
            info["tabla_caja"] = 'saldo_caja' in cols
            info["tabla_salidas"] = 'dividendos' in cols
            info["ok"] = info["tabla_caja"] and info["tabla_salidas"]
    except Exception as e:
        logger.error(f"Error verificando esquema de caja: {e}")
    return info
# --- Utilidades de histórico de caja ---


def _tabla_existe(cur, fqname: str) -> bool:
    try:
        cur.execute("SELECT to_regclass(%s)", (fqname,))
        row = cur.fetchone()
        return bool(row and len(row) > 0 and row[0])
    except Exception:
        return False

def get_ultima_caja_antes(empleado_identificacion: str, fecha: date) -> Decimal:
    """Obtiene la última caja registrada antes de 'fecha'. Si no hay, 0."""
    try:
        with DatabasePool.get_cursor() as cur:
            if _tabla_existe(cur, 'public.caja'):
                cur.execute(
                    """
                    SELECT valor FROM caja
                    WHERE empleado_identificacion = %s AND fecha < %s
                    ORDER BY fecha DESC LIMIT 1
                    """,
                    (empleado_identificacion, fecha),
                )
                r = cur.fetchone()
                if r and r[0] is not None:
                    return Decimal(str(r[0]))
            if _tabla_existe(cur, 'public.control_caja'):
                cur.execute(
                    """
                    SELECT saldo_caja FROM control_caja
                    WHERE empleado_identificacion = %s AND fecha < %s
                    ORDER BY fecha DESC LIMIT 1
                    """,
                    (empleado_identificacion, fecha),
                )
                r = cur.fetchone()
                if r and r[0] is not None:
                    return Decimal(str(r[0]))
    except Exception as e:
        logger.error(f"Error en get_ultima_caja_antes: {e}")
    return Decimal('0')

def recalcular_caja_dia(empleado_identificacion: str, fecha: date, timezone_name: Optional[str] = None) -> Decimal:
    """Recalcula la caja del día como: caja_prev + cobrado - prestamos - gastos - salidas + entradas.
    La 'base' se ha eliminado de la ecuación.
    Usa la zona horaria de la cuenta/usuario para calcular los límites diarios.
    """
    try:
        prev = get_ultima_caja_antes(empleado_identificacion, fecha)
        # Obtener deltas del día (fecha exacta) según timezone local
        from datetime import datetime as _dt, timezone as _tz
        try:
            from zoneinfo import ZoneInfo
            _tz_local = ZoneInfo(timezone_name) if timezone_name else _tz.utc
        except Exception:
            _tz_local = _tz.utc
        start_local = _dt(fecha.year, fecha.month, fecha.day, 0, 0, 0, tzinfo=_tz_local)
        end_local = _dt(fecha.year, fecha.month, fecha.day, 23, 59, 59, 999000, tzinfo=_tz_local)
        start_utc = start_local.astimezone(_tz.utc)
        end_utc = end_local.astimezone(_tz.utc)
        # Usar límites UTC sin tz para columnas timestamp sin zona
        start_naive = start_utc.replace(tzinfo=None)
        end_naive = end_utc.replace(tzinfo=None)
        # Para tablas con timestamp sin zona, usar límites UTC sin tz (naive)
        start_naive = start_utc.replace(tzinfo=None)
        end_naive = end_utc.replace(tzinfo=None)
        cobrado = Decimal('0'); prestamos = Decimal('0'); gastos = Decimal('0'); salidas = Decimal('0'); entradas = Decimal('0')
        with DatabasePool.get_cursor() as cur:
            # cobrado del día por empleado
            cur.execute(
                """
                SELECT COALESCE(SUM(a.monto),0)
                FROM abonos a JOIN tarjetas t ON a.tarjeta_codigo = t.codigo
                WHERE t.empleado_identificacion = %s AND a.fecha >= %s AND a.fecha <= %s
                """,
                (empleado_identificacion, start_utc, end_utc),
            )
            r = cur.fetchone(); cobrado = Decimal(str((r[0] if (r and len(r)>0) else 0) or 0))
            # prestamos del día
            cur.execute(
                """
                SELECT COALESCE(SUM(t.monto),0)
                FROM tarjetas t
                WHERE t.empleado_identificacion = %s AND t.fecha_creacion >= %s AND t.fecha_creacion <= %s
                """,
                (empleado_identificacion, start_utc, end_utc),
            )
            r = cur.fetchone(); prestamos = Decimal(str((r[0] if (r and len(r)>0) else 0) or 0))
            # gastos del día
            cur.execute(
                """
                SELECT COALESCE(SUM(g.valor),0)
                FROM gastos g
                WHERE g.empleado_identificacion = %s AND g.fecha_creacion >= %s AND g.fecha_creacion <= %s
                """,
                (empleado_identificacion, start_utc, end_utc),
            )
            r = cur.fetchone(); gastos = Decimal(str((r[0] if (r and len(r)>0) else 0) or 0))
            
            # salidas del día (leer de caja_salidas o control_caja)
            if _tabla_existe(cur, 'public.caja_salidas'):
                cur.execute(
                    """
                    SELECT COALESCE(SUM(s.valor),0)
                    FROM caja_salidas s
                    WHERE s.empleado_identificacion = %s AND s.fecha = %s
                    """,
                    (empleado_identificacion, fecha),
                )
                r = cur.fetchone(); salidas = Decimal(str((r[0] if (r and len(r)>0) else 0) or 0))
            elif _tabla_existe(cur, 'public.control_caja'):
                cur.execute(
                    """
                    SELECT COALESCE(dividendos,0), COALESCE(entradas,0)
                    FROM control_caja
                    WHERE empleado_identificacion = %s AND fecha = %s
                    """,
                    (empleado_identificacion, fecha),
                )
                r = cur.fetchone()
                if r:
                    salidas = Decimal(str(r[0] or 0))
                    entradas = Decimal(str(r[1] or 0))

        valor = prev + cobrado - prestamos - gastos - salidas + entradas
        # Guardar en 'caja' o fallback en 'control_caja.saldo_caja'
        ok = upsert_caja(empleado_identificacion, fecha, valor)
        if not ok:
            logger.warning("No se pudo upsert caja; se devolverá valor calculado sin persistir")
        return valor
    except Exception as e:
        logger.error(f"Error en recalcular_caja_dia: {e}")
        return Decimal('0')


def upsert_caja(empleado_identificacion: str, fecha: date, valor: Decimal) -> bool:
    """Inserta/actualiza el valor de caja en control_caja.saldo_caja."""
    try:
        with DatabasePool.get_cursor() as cur:
            # Intentar actualizar
            cur.execute(
                """
                UPDATE control_caja
                SET saldo_caja = %s
                WHERE empleado_identificacion = %s AND fecha = %s
                RETURNING 1
                """,
                (valor, empleado_identificacion, fecha),
            )
            row = cur.fetchone()
            if row:
                return True
            # Insertar si no existe
            cur.execute(
            """
            INSERT INTO control_caja (empleado_identificacion, fecha, saldo_caja, dividendos, entradas, observaciones)
            VALUES (%s, %s, %s, 0, 0, NULL)
            ON CONFLICT (empleado_identificacion, fecha)
            DO UPDATE SET saldo_caja = EXCLUDED.saldo_caja
            RETURNING 1
            """,
            (empleado_identificacion, fecha, valor),
            )
            return cur.fetchone() is not None
    except Exception as e:
        logger.error(f"Error al upsert caja: {e}")
        return False


def get_caja_en_fecha(empleado_identificacion: str, fecha: date) -> Decimal:
    """Obtiene el último saldo de caja (control_caja.saldo_caja) con fecha <= dada.
    Si no hay registros previos, devuelve 0.
    """
    try:
        with DatabasePool.get_cursor() as cur:
            cur.execute(
                """
                SELECT COALESCE(saldo_caja,0)
                FROM control_caja
                WHERE empleado_identificacion = %s AND fecha <= %s
                ORDER BY fecha DESC
                LIMIT 1
                """,
                (empleado_identificacion, fecha),
            )
            val = cur.fetchone()
            return Decimal(str(val[0])) if val and len(val)>0 and val[0] is not None else Decimal('0')
    except Exception as e:
        logger.error(f"Error al leer caja: {e}")
        return Decimal('0')


def registrar_salida(fecha: date, valor: Decimal, concepto: Optional[str] = None, empleado_identificacion: Optional[str] = None) -> Optional[int]:
    """Acumula una salida de caja en control_caja.dividendos (insert/update)."""
    try:
        with DatabasePool.get_cursor() as cur:
            # Intentar actualizar fila del día
            cur.execute(
                """
                UPDATE control_caja
                SET dividendos = COALESCE(dividendos, 0) + %s,
                    observaciones = COALESCE(observaciones, '') || CASE WHEN %s IS NOT NULL THEN CONCAT(' ', %s) ELSE '' END
                WHERE empleado_identificacion = %s AND fecha = %s
                RETURNING 1
                """,
                (valor, concepto, concepto, empleado_identificacion, fecha),
            )
            row = cur.fetchone()
            if row:
                return 0
            # Insertar si no existe
            cur.execute(
                """
                INSERT INTO control_caja (empleado_identificacion, fecha, saldo_caja, dividendos, entradas, observaciones)
                VALUES (%s, %s, NULL, %s, 0, %s)
                RETURNING 1
                """,
                (empleado_identificacion, fecha, valor, concepto),
            )
            return 0 if cur.fetchone() else None
    except Exception as e:
        logger.error(f"Error al registrar salida de caja: {e}")
        return None


def registrar_entrada(fecha: date, valor: Decimal, concepto: Optional[str] = None, empleado_identificacion: Optional[str] = None) -> Optional[int]:
    """Acumula una entrada de caja en control_caja.entradas (insert/update)."""
    try:
        with DatabasePool.get_cursor() as cur:
            # Intentar actualizar fila del día
            cur.execute(
                """
                UPDATE control_caja
                SET entradas = COALESCE(entradas, 0) + %s,
                    observaciones = COALESCE(observaciones, '') || CASE WHEN %s IS NOT NULL THEN CONCAT(' [Entrada: ', %s, ']') ELSE '' END
                WHERE empleado_identificacion = %s AND fecha = %s
                RETURNING 1
                """,
                (valor, concepto, concepto, empleado_identificacion, fecha),
            )
            row = cur.fetchone()
            if row:
                return 0
            # Insertar si no existe
            cur.execute(
                """
                INSERT INTO control_caja (empleado_identificacion, fecha, saldo_caja, dividendos, entradas, observaciones)
                VALUES (%s, %s, NULL, 0, %s, %s)
                RETURNING 1
                """,
                (empleado_identificacion, fecha, valor, f"[Entrada: {concepto}]" if concepto else None),
            )
            return 0 if cur.fetchone() else None
    except Exception as e:
        logger.error(f"Error al registrar entrada de caja: {e}")
        return None


def obtener_salidas(fecha_desde: date, fecha_hasta: date, empleado_id: Optional[str] = None) -> List[Tuple]:
    """Obtiene salidas desde control_caja.dividendos (sin id/fecha_creacion reales)."""
    try:
        with DatabasePool.get_cursor() as cur:
            if empleado_id:
                cur.execute(
                    """
                    SELECT NULL::int AS id, fecha, COALESCE(dividendos,0) AS valor,
                           observaciones AS concepto, empleado_identificacion, NULL::timestamp AS fecha_creacion
                    FROM control_caja
                    WHERE fecha >= %s AND fecha <= %s AND empleado_identificacion = %s
                    ORDER BY fecha
                    """,
                    (fecha_desde, fecha_hasta, empleado_id),
                )
            else:
                cur.execute(
                    """
                    SELECT NULL::int AS id, fecha, COALESCE(dividendos,0) AS valor,
                           observaciones AS concepto, empleado_identificacion, NULL::timestamp AS fecha_creacion
                    FROM control_caja
                    WHERE fecha >= %s AND fecha <= %s
                    ORDER BY fecha
                    """,
                    (fecha_desde, fecha_hasta),
                )
            return cur.fetchall() or []
    except Exception as e:
        logger.error(f"Error al obtener salidas de caja: {e}")
        return []


def _calcular_cartera_al_corte(cur, fecha_corte_utc, fecha_corte_local_date, empleado_id=None, cuenta_id=None) -> Decimal:
    """Calcula el saldo pendiente de la cartera activa a una fecha de corte.
    
    Snapshot histórico preciso:
    - Incluye tarjetas creadas antes del corte.
    - Incluye tarjetas que estaban activas en esa fecha (no canceladas O canceladas después de esa fecha).
    - Resta solo los abonos realizados hasta ese momento.
    """
    try:
        # Condición de estado:
        # Si la tarjeta NO es cancelada HOY, estaba activa antes.
        # Si es cancelada HOY, verificamos si se canceló DESPUÉS de la fecha de corte local.
        # fecha_cancelacion es DATE.
        
        filtros_estado = """
            AND (
                (COALESCE(estado,'activa') NOT ILIKE 'cancelad%%' AND COALESCE(estado,'activa') NOT ILIKE 'pendiente%%')
                OR (t.fecha_cancelacion IS NOT NULL AND t.fecha_cancelacion > %s)
            )
        """
        
        if empleado_id:
            sql = (
                f"""
                WITH tarjetas_emp AS (
                  SELECT codigo, monto, COALESCE(interes,0)::numeric AS interes
                  FROM tarjetas t
                  WHERE empleado_identificacion = %s
                    AND t.fecha_creacion <= %s
                    {filtros_estado}
                ),
                tot_abonos AS (
                  SELECT a.tarjeta_codigo, COALESCE(SUM(a.monto),0) AS abonado
                  FROM abonos a
                  WHERE a.fecha <= %s
                    AND a.tarjeta_codigo IN (SELECT codigo FROM tarjetas_emp)
                  GROUP BY a.tarjeta_codigo
                )
                SELECT COALESCE(SUM(
                  GREATEST( (t.monto * (1 + t.interes/100.0)) - COALESCE(ta.abonado,0), 0)
                ),0)
                FROM tarjetas_emp t
                LEFT JOIN tot_abonos ta ON ta.tarjeta_codigo = t.codigo
                """
            )
            # Parámetros: empleado, fecha_limite_creacion(UTC), fecha_corte_cancelacion(DATE), fecha_limite_abonos(UTC)
            cur.execute(sql, (empleado_id, fecha_corte_utc, fecha_corte_local_date, fecha_corte_utc))
        else:
            # Consolidado por cuenta
            sql = (
                f"""
                WITH tarjetas_all AS (
                  SELECT t.codigo, t.monto, COALESCE(t.interes,0)::numeric AS interes
                  FROM tarjetas t
                  JOIN empleados e ON t.empleado_identificacion = e.identificacion
                  WHERE e.cuenta_id = %s
                    AND t.fecha_creacion <= %s
                    {filtros_estado}
                ),
                tot_abonos AS (
                  SELECT a.tarjeta_codigo, COALESCE(SUM(a.monto),0) AS abonado
                  FROM abonos a
                  WHERE a.fecha <= %s
                    AND a.tarjeta_codigo IN (SELECT codigo FROM tarjetas_all)
                  GROUP BY a.tarjeta_codigo
                )
                SELECT COALESCE(SUM(
                  GREATEST( (t.monto * (1 + t.interes/100.0)) - COALESCE(ta.abonado,0), 0)
                ),0)
                FROM tarjetas_all t
                LEFT JOIN tot_abonos ta ON ta.tarjeta_codigo = t.codigo
                """
            )
            # Parámetros: cuenta_id, fecha_limite_creacion(UTC), fecha_corte_cancelacion(DATE), fecha_limite_abonos(UTC)
            cur.execute(sql, (cuenta_id, fecha_corte_utc, fecha_corte_local_date, fecha_corte_utc))
            
        r = cur.fetchone()
        return Decimal(str((r[0] if (r and len(r) > 0) else 0) or 0))
    except Exception as e:
        logger.error(f"Error calculando cartera al corte: {e}")
        return Decimal('0')


def obtener_metricas_contabilidad(desde: date, hasta: date, empleado_id: Optional[str] = None, timezone_name: Optional[str] = None, cuenta_id: Optional[int] = None) -> Dict:
    """Calcula métricas de contabilidad para el rango, aisladas por cuenta."""
    from datetime import datetime as _dt, timezone as _tz, timedelta
    # Preparar zona horaria local (desde token/cuenta) para convertir a UTC
    try:
        from zoneinfo import ZoneInfo  # Python >=3.9
        _tz_local = ZoneInfo(timezone_name) if timezone_name else _tz.utc
    except Exception:
        _tz_local = _tz.utc
    totals = {
        "total_cobrado": Decimal('0'),
        "total_prestamos": Decimal('0'),
        "total_gastos": Decimal('0'),
        "total_bases": Decimal('0'),
        "total_salidas": Decimal('0'),
        "total_entradas": Decimal('0'),
        "total_intereses": Decimal('0'),
        "cartera_en_calle": Decimal('0'),
        "cartera_en_calle_desde": Decimal('0'),
        "abonos_count": 0,
        "total_efectivo": Decimal('0'),  # Nuevo: Cobrado + Base - Prestamos - Gastos
        "total_clavos": Decimal('0'),    # Nuevo: Saldo de tarjetas vencidas > 60 días
    }
    try:
        # Determinar límites de día local y convertir a UTC para columnas con timestamp
        start_local = _dt(desde.year, desde.month, desde.day, 0, 0, 0, tzinfo=_tz_local)
        end_local = _dt(hasta.year, hasta.month, hasta.day, 23, 59, 59, 999000, tzinfo=_tz_local)
        start_utc = start_local.astimezone(_tz.utc)
        end_utc = end_local.astimezone(_tz.utc)
        # Usar límites UTC sin tz para tablas con timestamp sin zona
        start_naive = start_utc.replace(tzinfo=None)
        end_naive = end_utc.replace(tzinfo=None)
        with DatabasePool.get_cursor() as cur:
            # COBRADO
            if empleado_id:
                cur.execute(
                    """
                    SELECT COALESCE(SUM(a.monto),0), COUNT(*)
                    FROM abonos a
                    JOIN tarjetas t ON a.tarjeta_codigo = t.codigo
                    WHERE t.empleado_identificacion = %s
                      AND a.fecha >= %s AND a.fecha <= %s
                    """,
                    (empleado_id, start_naive, end_naive),
                )
            else:
                cur.execute(
                    """
                    SELECT COALESCE(SUM(a.monto),0), COUNT(*)
                    FROM abonos a
                    JOIN tarjetas t ON a.tarjeta_codigo = t.codigo
                    JOIN empleados e ON t.empleado_identificacion = e.identificacion
                    WHERE e.cuenta_id = %s
                      AND a.fecha >= %s AND a.fecha <= %s
                    """,
                    (cuenta_id, start_naive, end_naive),
                )
            row = cur.fetchone()
            if not row:
                totals["total_cobrado"] = Decimal('0')
                totals["abonos_count"] = 0
            else:
                # Proteger tamaños inesperados
                try:
                    totals["total_cobrado"] = Decimal(str(row[0] or 0))
                except Exception:
                    totals["total_cobrado"] = Decimal('0')
                try:
                    totals["abonos_count"] = int(row[1] or 0)
                except Exception:
                    totals["abonos_count"] = 0

            # PRESTAMOS (tarjetas nuevas)
            if empleado_id:
                cur.execute(
                    """
                    SELECT COALESCE(SUM(t.monto),0), COALESCE(SUM(t.monto * t.interes/100.0),0)
                    FROM tarjetas t
                    WHERE t.empleado_identificacion = %s
                      AND t.fecha_creacion >= %s AND t.fecha_creacion <= %s
                    """,
                    (empleado_id, start_naive, end_naive),
                )
            else:
                cur.execute(
                    """
                    SELECT COALESCE(SUM(t.monto),0), COALESCE(SUM(t.monto * t.interes/100.0),0)
                    FROM tarjetas t
                    JOIN empleados e ON t.empleado_identificacion = e.identificacion
                    WHERE e.cuenta_id = %s
                      AND t.fecha_creacion >= %s AND t.fecha_creacion <= %s
                    """,
                    (cuenta_id, start_naive, end_naive),
                )
            row = cur.fetchone()
            if not row:
                totals["total_prestamos"] = Decimal('0')
                totals["total_intereses"] = Decimal('0')
            else:
                try:
                    totals["total_prestamos"] = Decimal(str(row[0] or 0))
                except Exception:
                    totals["total_prestamos"] = Decimal('0')
                try:
                    totals["total_intereses"] = Decimal(str(row[1] or 0))
                except Exception:
                    totals["total_intereses"] = Decimal('0')

            # GASTOS (fecha_creacion UTC)
            if empleado_id:
                cur.execute(
                    """
                    SELECT COALESCE(SUM(g.valor),0)
                    FROM gastos g
                    WHERE g.empleado_identificacion = %s
                      AND g.fecha_creacion >= %s AND g.fecha_creacion <= %s
                    """,
                    (empleado_id, start_naive, end_naive),
                )
            else:
                cur.execute(
                    """
                    SELECT COALESCE(SUM(g.valor),0)
                    FROM gastos g
                    JOIN empleados e ON g.empleado_identificacion = e.identificacion
                    WHERE e.cuenta_id = %s
                      AND g.fecha_creacion >= %s AND g.fecha_creacion <= %s
                    """,
                    (cuenta_id, start_naive, end_naive),
                )
            r = cur.fetchone()
            totals["total_gastos"] = Decimal(str((r[0] if (r and len(r)>0) else 0) or 0))

            # BASES (DATE exacta)
            if empleado_id:
                cur.execute(
                    """
                    SELECT COALESCE(SUM(b.monto),0)
                    FROM bases b
                    WHERE b.empleado_id = %s AND b.fecha >= %s AND b.fecha <= %s
                    """,
                    (empleado_id, desde, hasta),
                )
            else:
                cur.execute(
                    """
                    SELECT COALESCE(SUM(b.monto),0)
                    FROM bases b
                    JOIN empleados e ON b.empleado_id = e.identificacion
                    WHERE e.cuenta_id = %s AND b.fecha >= %s AND b.fecha <= %s
                    """,
                    (cuenta_id, desde, hasta),
                )
            r = cur.fetchone()
            totals["total_bases"] = Decimal(str((r[0] if (r and len(r)>0) else 0) or 0))

            # SALIDAS (DATE exacta) — tolerar ausencia de tabla devolviendo 0
            # SALIDAS: sumar control_caja.dividendos
            if empleado_id:
                cur.execute(
                    """
                    SELECT COALESCE(SUM(COALESCE(dividendos,0)),0), COALESCE(SUM(COALESCE(entradas,0)),0)
                    FROM control_caja
                    WHERE fecha >= %s AND fecha <= %s AND empleado_identificacion = %s
                    """,
                    (desde, hasta, empleado_id),
                )
            else:
                cur.execute(
                    """
                    SELECT COALESCE(SUM(COALESCE(dividendos,0)),0), COALESCE(SUM(COALESCE(entradas,0)),0)
                    FROM control_caja c
                    JOIN empleados e ON c.empleado_identificacion = e.identificacion
                    WHERE e.cuenta_id = %s AND c.fecha >= %s AND c.fecha <= %s
                    """,
                    (cuenta_id, desde, hasta),
                )
            r = cur.fetchone()
            totals["total_salidas"] = Decimal(str((r[0] if (r and len(r)>0) else 0) or 0))
            totals["total_entradas"] = Decimal(str((r[1] if (r and len(r)>1) else 0) or 0))

            # CARTERA EN CALLE (saldo pendiente)
            # 1. Cartera al final del periodo (hasta)
            if hasta:
                # end_naive es el fin del día 'hasta' en UTC.
                # 'hasta' es la fecha local. Si se cancela mañana, hoy sigue activa.
                totals["cartera_en_calle"] = _calcular_cartera_al_corte(cur, end_naive, hasta, empleado_id, cuenta_id)
            
            # 2. Cartera al inicio del periodo (desde)
            # start_naive es el inicio del día 'desde' en UTC (00:00 local).
            if desde:
                # Para el saldo INICIAL del día 'desde', una tarjeta cancelada DURANTE el día 'desde'
                # debe contar como activa (existía a las 00:00).
                # Por eso usamos (desde - 1 día) como referencia de corte para cancelación.
                # fecha_cancelacion (hoy) > (ayer) -> True -> Activa.
                ayer = desde - timedelta(days=1)
                totals["cartera_en_calle_desde"] = _calcular_cartera_al_corte(cur, start_naive, ayer, empleado_id, cuenta_id)
            
            # Calcular TOTAL EFECTIVO (Cobrado + Base - Prestamos - Gastos)
            # Nota: Esto es puramente efectivo operativo, no incluye entradas/salidas de caja
            totals["total_efectivo"] = (
                totals["total_cobrado"] + 
                totals["total_bases"] - 
                totals["total_prestamos"] - 
                totals["total_gastos"]
            )

            # Tarjetas Activas Históricas (al corte 'hasta')
            # Para mostrar "X de Y posibles" en reportes históricos
            if hasta:
                try:
                    if empleado_id:
                        # Contar tarjetas que existían (creadas antes del fin del día)
                        # Y que no estaban canceladas en ese momento (fecha_cancelacion > hasta)
                        # O siguen activas hoy.
                        q_activas = """
                            SELECT COUNT(*)
                            FROM tarjetas
                            WHERE empleado_identificacion = %s
                              AND fecha_creacion <= %s
                              AND (
                                  estado = 'activas' OR 
                                  (estado IN ('cancelada', 'canceladas') AND fecha_cancelacion > %s)
                              )
                        """
                        cur.execute(q_activas, (empleado_id, end_naive, hasta))
                    else:
                        q_activas = """
                            SELECT COUNT(*)
                            FROM tarjetas t
                            JOIN empleados e ON t.empleado_identificacion = e.identificacion
                            WHERE e.cuenta_id = %s
                              AND t.fecha_creacion <= %s
                              AND (
                                  t.estado = 'activas' OR 
                                  (t.estado IN ('cancelada', 'canceladas') AND t.fecha_cancelacion > %s)
                              )
                        """
                        cur.execute(q_activas, (cuenta_id, end_naive, hasta))
                    totals["tarjetas_activas_historicas"] = cur.fetchone()[0]
                except Exception as e:
                    logger.error(f"Error contando activas históricas: {e}")
                    totals["tarjetas_activas_historicas"] = 0

            # Calcular TOTAL CLAVOS
            # Usar la función de tarjetas_db
            try:
                from .tarjetas_db import calcular_total_clavos
                totals["total_clavos"] = calcular_total_clavos(empleado_id, hasta, cuenta_id)
            except Exception as e:
                logger.error(f"Error calculando clavos en métricas: {e}")

        # Agregar caja (saldo_caja) usando el último registro <= 'hasta'
        with DatabasePool.get_cursor() as cur2:
            if empleado_id:
                # Última caja del empleado hasta esa fecha
                cur2.execute(
                    """
                    SELECT COALESCE(saldo_caja,0)
                    FROM control_caja
                    WHERE empleado_identificacion = %s AND fecha <= %s
                    ORDER BY fecha DESC
                    LIMIT 1
                    """,
                    (empleado_id, hasta),
                )
                rr = cur2.fetchone()
                try:
                    # Métricas de apoyo para diagnóstico
                    cur2.execute(
                        """
                        SELECT COUNT(*), MIN(fecha), MAX(fecha), SUM(CASE WHEN saldo_caja IS NULL THEN 1 ELSE 0 END)
                        FROM control_caja WHERE empleado_identificacion = %s
                        """,
                        (empleado_id,)
                    )
                    diag = cur2.fetchone()
                    logger.info(f"[caja][diag] emp={empleado_id} hasta={hasta} row={rr} resumen={diag}")
                except Exception:
                    pass
                caja_val = Decimal(str((rr[0] if (rr and len(rr)>0) else 0) or 0))
            else:
                # Consolidados: sumar última caja de cada empleado hasta esa fecha
                cur2.execute(
                    """
                    SELECT COALESCE(SUM(saldo_caja),0) FROM (
                        SELECT DISTINCT ON (c.empleado_identificacion)
                               c.empleado_identificacion, c.saldo_caja, c.fecha
                        FROM control_caja c
                        JOIN empleados e ON c.empleado_identificacion = e.identificacion
                        WHERE e.cuenta_id = %s AND c.fecha <= %s
                        ORDER BY c.empleado_identificacion, c.fecha DESC
                    ) x
                    """,
                    (cuenta_id, hasta),
                )
                rr = cur2.fetchone()
                caja_val = Decimal(str((rr[0] if (rr and len(rr)>0) else 0) or 0))
        result = {k: v for k, v in totals.items()}
        result["caja"] = caja_val
        return result
    except Exception as e:
        logger.error(f"Error al calcular métricas de contabilidad: {e}")
        return totals


