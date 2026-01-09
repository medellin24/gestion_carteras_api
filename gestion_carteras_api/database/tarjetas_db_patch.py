
def listar_tarjetas_sin_abono_dia(empleado_identificacion: str, fecha_filtro: date, timezone_name: Optional[str] = None) -> List[Dict]:
    """
    Lista las tarjetas ACTIVAS asignadas al empleado que NO tienen abonos
    registrados en la fecha específica (fecha local del usuario).
    """
    try:
        from datetime import datetime, timezone
        from zoneinfo import ZoneInfo
        
        # 1. Definir rango del día en UTC para filtrar abonos
        tz = ZoneInfo(timezone_name) if timezone_name else ZoneInfo("America/Bogota")
        
        start_local = datetime.combine(fecha_filtro, datetime.min.time()).replace(tzinfo=tz)
        end_local = datetime.combine(fecha_filtro, datetime.max.time()).replace(tzinfo=tz)
        
        start_utc = start_local.astimezone(timezone.utc)
        end_utc = end_local.astimezone(timezone.utc)

        with DatabasePool.get_cursor() as cursor:
            modalidad_expr = "COALESCE(t.modalidad_pago, 'diario')" if _modalidad_column_exists() else "'diario'"
            
            # Seleccionamos tarjetas activas de este empleado
            # que NO estén en la subconsulta de abonos de ese rango de tiempo
            query = f'''
                SELECT 
                    t.codigo, t.monto, t.cuotas,
                    c.nombre, c.apellido, t.numero_ruta
                FROM tarjetas t
                JOIN clientes c ON t.cliente_identificacion = c.identificacion
                WHERE t.empleado_identificacion = %s
                  AND t.estado = 'activas'
                  AND t.id NOT IN (
                      SELECT a.tarjeta_id 
                      FROM abonos a
                      WHERE a.empleado_identificacion = %s
                        AND a.created_at >= %s 
                        AND a.created_at <= %s
                  )
                ORDER BY t.numero_ruta ASC, t.codigo ASC
            '''
            cursor.execute(query, (empleado_identificacion, empleado_identificacion, start_utc, end_utc))
            rows = cursor.fetchall()
            
            resultado = []
            for row in rows:
                resultado.append({
                    'codigo': row[0],
                    'monto': row[1],
                    'cuotas': row[2],
                    'cliente_nombre': row[3],
                    'cliente_apellido': row[4],
                    'numero_ruta': row[5]
                })
            return resultado

    except Exception as e:
        logger.error(f"Error al listar tarjetas sin abono: {e}")
        return []

