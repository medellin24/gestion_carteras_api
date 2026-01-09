import sys
import os
import logging
from datetime import date, timedelta, datetime

# Configurar path para importar módulos del proyecto
sys.path.append(os.getcwd())

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

from gestion_carteras_api.database.connection_pool import DatabasePool
from gestion_carteras_api.database.db_config import DB_CONFIG
from gestion_carteras_api.database.caja_db import recalcular_caja_dia

def fix_caja_historica():
    print("=== INICIANDO REPARACIÓN MASIVA DE CAJA ===")
    
    # 1. Inicializar BD
    try:
        DatabasePool.initialize(**DB_CONFIG)
        logger.info("Conexión a BD establecida.")
    except Exception as e:
        logger.error(f"Error conectando a BD: {e}")
        return

    # 2. Configurar rango de fechas
    FECHA_INICIO = date(2025, 12, 28) 
    HOY = date.today()
    
    logger.info(f"Rango de reparación: {FECHA_INICIO} hasta {HOY}")

    # 3. Obtener UNICAMENTE a San Jose
    empleados = []
    with DatabasePool.get_cursor() as cur:
        # Filtrar por nombre
        cur.execute("SELECT identificacion, nombre FROM empleados WHERE nombre ILIKE '%SAN JOSE%'") 
        empleados = cur.fetchall()
    
    logger.info(f"Se encontraron {len(empleados)} empleados en total.")

    # 4. Iterar y reparar
    total_recalculos = 0
    
    for emp in empleados:
        emp_id, emp_nombre = emp
        # Usar timezone de las cuentas (Bogotá)
        tz_name = 'America/Bogota'
        
        print(f"\nProcesando: {emp_nombre} ({emp_id})")
        
        fecha_actual = FECHA_INICIO
        while fecha_actual <= HOY:
            try:
                # La magia ocurre aquí: al ir en orden cronológico, 
                # cada día arregla la base para el siguiente.
                saldo = recalcular_caja_dia(emp_id, fecha_actual, timezone_name=tz_name)
                # logger.info(f"  - {fecha_actual}: Saldo recalculado -> {saldo}")
                total_recalculos += 1
            except Exception as e:
                logger.error(f"  Error en {fecha_actual}: {e}")
            
            fecha_actual += timedelta(days=1)
            
    print(f"\n=== FIN DEL PROCESO ===")
    print(f"Total de días recalculados: {total_recalculos}")

if __name__ == "__main__":
    fix_caja_historica()

