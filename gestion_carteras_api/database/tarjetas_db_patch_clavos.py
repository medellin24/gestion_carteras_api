
def calcular_total_clavos(empleado_identificacion: Optional[str], fecha_corte: date) -> Decimal:
    """
    Calcula el saldo total de tarjetas 'activas' que tienen más de 60 días de vencidas
    a la fecha de corte.
    
    Criterio Clavo: (Fecha Corte - Fecha Vencimiento) >= 60 días.
    Fecha Vencimiento = Fecha Creación + (Cuotas * Factor Modalidad)
    Factor Modalidad: diario=1, semanal=7, quincenal=15, mensual=30.
    """
    try:
        with DatabasePool.get_cursor() as cursor:
            # Primero obtenemos las tarjetas activas y sus datos para calcular en Python
            # (Más fácil que manejar la lógica de modalidad compleja en SQL puro portable)
            
            # Filtro de empleado
            if empleado_identificacion:
                where_emp = "AND t.empleado_identificacion = %s"
                params = (empleado_identificacion,)
            else:
                where_emp = ""
                params = ()

            modalidad_expr = "COALESCE(t.modalidad_pago, 'diario')" if _modalidad_column_exists() else "'diario'"
            
            query = f'''
                SELECT 
                    t.id, 
                    t.fecha_creacion, 
                    t.cuotas, 
                    {modalidad_expr},
                    t.monto,
                    COALESCE(SUM(a.monto), 0) as abonado
                FROM tarjetas t
                LEFT JOIN abonos a ON t.id = a.tarjeta_id
                WHERE t.estado = 'activas'
                  {where_emp}
                GROUP BY t.id
            '''
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            total_clavos = Decimal(0)
            
            from datetime import timedelta
            
            for row in rows:
                fecha_creacion = row[1]
                if not fecha_creacion: continue
                
                cuotas = int(row[2] or 0)
                modalidad = str(row[3] or 'diario').lower()
                monto = Decimal(row[4] or 0)
                abonado = Decimal(row[5] or 0)
                saldo = monto - abonado
                
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

