
def buscar_datos_clavo(identificacion: str) -> Optional[Dict]:
    """
    Busca cliente por identificación y obtiene sus datos personales
    más la fecha de su última tarjeta (activa o no).
    """
    try:
        with DatabasePool.get_cursor() as cursor:
            # Datos del cliente
            query_cliente = '''
                SELECT identificacion, nombre, apellido, telefono, direccion
                FROM clientes
                WHERE identificacion = %s
            '''
            cursor.execute(query_cliente, (identificacion,))
            cliente = cursor.fetchone()
            
            if not cliente:
                return None
            
            # Última tarjeta (fecha de creación más reciente)
            # Buscamos en todas las tarjetas de este cliente
            query_tarjeta = '''
                SELECT fecha_creacion
                FROM tarjetas
                WHERE cliente_identificacion = %s
                ORDER BY fecha_creacion DESC
                LIMIT 1
            '''
            cursor.execute(query_tarjeta, (identificacion,))
            tarjeta = cursor.fetchone()
            fecha_ultima = tarjeta[0] if tarjeta else None
            
            return {
                'identificacion': cliente[0],
                'nombre': cliente[1],
                'apellido': cliente[2],
                'telefono': cliente[3],
                'direccion': cliente[4],
                'fecha_ultima_tarjeta': fecha_ultima
            }
    except Exception as e:
        logger.error(f"Error al buscar clavo: {e}")
        return None

