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
    """Recalcula la caja del día como: caja_prev + cobrado + base - prestamos - gastos - salidas.
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
        cobrado = Decimal('0'); prestamos = Decimal('0'); gastos = Decimal('0'); base = Decimal('0'); salidas = Decimal('0')
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
            # base del día (fecha DATE exacta)
            cur.execute(
                """
                SELECT COALESCE(SUM(b.monto),0)
                FROM bases b
                WHERE b.empleado_id = %s AND b.fecha = %s
                """,
                (empleado_identificacion, fecha),
            )
            r = cur.fetchone(); base = Decimal(str((r[0] if (r and len(r)>0) else 0) or 0))
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
                    SELECT COALESCE(dividendos,0)
                    FROM control_caja
                    WHERE empleado_identificacion = %s AND fecha = %s
                    """,
                    (empleado_identificacion, fecha),
                )
                r = cur.fetchone(); salidas = Decimal(str((r[0] if (r and len(r)>0) else 0) or 0))

        valor = prev + cobrado + base - prestamos - gastos - salidas
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
            INSERT INTO control_caja (empleado_identificacion, fecha, saldo_caja, dividendos, observaciones)
            VALUES (%s, %s, %s, 0, NULL)
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
                INSERT INTO control_caja (empleado_identificacion, fecha, saldo_caja, dividendos, observaciones)
                VALUES (%s, %s, NULL, %s, %s)
                RETURNING 1
                """,
                (empleado_identificacion, fecha, valor, concepto),
            )
            return 0 if cur.fetchone() else None
    except Exception as e:
        logger.error(f"Error al registrar salida de caja: {e}")
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


def obtener_metricas_contabilidad(desde: date, hasta: date, empleado_id: Optional[str] = None, timezone_name: Optional[str] = None) -> Dict:
    """Calcula métricas de contabilidad para el rango.
    - total_cobrado: suma de abonos (UTC) filtrado por tarjetas de empleado si aplica.
    - total_prestamos: suma de monto de tarjetas creadas en el rango (UTC).
    - total_gastos: suma de gastos en el rango (usar fecha_creacion UTC) y/o por empleado.
    - total_bases: suma de bases del rango (DATE local exacta, comparando por fecha).
    - total_salidas: suma de caja_salidas en el rango (DATE).
    """
    from datetime import datetime as _dt, timezone as _tz
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
        "total_intereses": Decimal('0'),
        "cartera_en_calle": Decimal('0'),
        "abonos_count": 0,
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
            # COBRADO (abonos)
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
                    WHERE a.fecha >= %s AND a.fecha <= %s
                    """,
                    (start_naive, end_naive),
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
                    WHERE t.fecha_creacion >= %s AND t.fecha_creacion <= %s
                    """,
                    (start_naive, end_naive),
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
                    WHERE g.fecha_creacion >= %s AND g.fecha_creacion <= %s
                    """,
                    (start_naive, end_naive),
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
                    WHERE b.fecha >= %s AND b.fecha <= %s
                    """,
                    (desde, hasta),
                )
            r = cur.fetchone()
            totals["total_bases"] = Decimal(str((r[0] if (r and len(r)>0) else 0) or 0))

            # SALIDAS (DATE exacta) — tolerar ausencia de tabla devolviendo 0
            # SALIDAS: sumar control_caja.dividendos
            if empleado_id:
                cur.execute(
                    """
                    SELECT COALESCE(SUM(COALESCE(dividendos,0)),0)
                    FROM control_caja
                    WHERE fecha >= %s AND fecha <= %s AND empleado_identificacion = %s
                    """,
                    (desde, hasta, empleado_id),
                )
            else:
                cur.execute(
                    """
                    SELECT COALESCE(SUM(COALESCE(dividendos,0)),0)
                    FROM control_caja
                    WHERE fecha >= %s AND fecha <= %s
                    """,
                    (desde, hasta),
                )
            r = cur.fetchone()
            totals["total_salidas"] = Decimal(str((r[0] if (r and len(r)>0) else 0) or 0))

            # CARTERA EN CALLE (saldo pendiente) con filtros y saneo:
            # saldo = GREATEST(monto*(1+COALESCE(interes,0)/100) - SUM(abonos hasta end_utc), 0)
            # Filtrado por tarjetas activas; por empleado si aplica
            if hasta:
                try:
                    if empleado_id:
                        _sql = (
                            """
                            WITH tarjetas_emp AS (
                              SELECT codigo, monto, COALESCE(interes,0)::numeric AS interes
                              FROM tarjetas
                              WHERE empleado_identificacion = %s
                                AND (COALESCE(estado,'activa') NOT ILIKE 'cancelad%%')
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
                        _params = (empleado_id, end_naive)
                        cur.execute(_sql, _params)
                    else:
                        _sql = (
                            """
                            WITH tarjetas_all AS (
                              SELECT codigo, monto, COALESCE(interes,0)::numeric AS interes
                              FROM tarjetas
                              WHERE (COALESCE(estado,'activa') NOT ILIKE 'cancelad%%')
                            ),
                            tot_abonos AS (
                              SELECT a.tarjeta_codigo, COALESCE(SUM(a.monto),0) AS abonado
                              FROM abonos a
                              WHERE a.fecha <= %s
                              GROUP BY a.tarjeta_codigo
                            )
                            SELECT COALESCE(SUM(
                              GREATEST( (t.monto * (1 + t.interes/100.0)) - COALESCE(ta.abonado,0), 0)
                            ),0)
                            FROM tarjetas_all t
                            LEFT JOIN tot_abonos ta ON ta.tarjeta_codigo = t.codigo
                            """
                        )
                        _params = (end_naive,)
                        cur.execute(_sql, _params)
                    _r = cur.fetchone()
                    totals["cartera_en_calle"] = Decimal(str((_r[0] if (_r and len(_r) > 0) else 0) or 0))
                except Exception as e:
                    logger.error(f"Error calculando cartera_en_calle (emp={empleado_id}, hasta={hasta}): {e}")
                    totals["cartera_en_calle"] = Decimal('0')

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
                        SELECT DISTINCT ON (empleado_identificacion)
                               empleado_identificacion, saldo_caja, fecha
                        FROM control_caja
                        WHERE fecha <= %s
                        ORDER BY empleado_identificacion, fecha DESC
                    ) x
                    """,
                    (hasta,),
                )
                rr = cur2.fetchone()
                caja_val = Decimal(str((rr[0] if (rr and len(rr)>0) else 0) or 0))
        result = {k: v for k, v in totals.items()}
        result["caja"] = caja_val
        return result
    except Exception as e:
        logger.error(f"Error al calcular métricas de contabilidad: {e}")
        return totals


