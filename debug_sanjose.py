import sys
import os
import logging
from datetime import date, datetime
from decimal import Decimal

sys.path.append(os.getcwd())
logging.basicConfig(level=logging.INFO)

from gestion_carteras_api.database.connection_pool import DatabasePool
from gestion_carteras_api.database.db_config import DB_CONFIG
from gestion_carteras_api.database.caja_db import get_ultima_caja_antes

def inspect():
    try:
        DatabasePool.initialize(**DB_CONFIG)
        emp_id = '4' # San Jose
        fecha_str = '2026-01-03'
        fecha = datetime.strptime(fecha_str, "%Y-%m-%d").date()
        
        print(f"Inspeccionando ID {emp_id} para {fecha}...")
        
        with DatabasePool.get_cursor() as cur:
            # 1. Previo REAL que ve el sistema
            prev = get_ultima_caja_antes(emp_id, fecha)
            print(f"Caja Previa (antes de {fecha}): {prev:,.2f}")
            
            # 2. Ver saldo del 31 de Dic para comparar
            cur.execute("SELECT saldo_caja FROM control_caja WHERE empleado_identificacion=%s AND fecha='2025-12-31'", (emp_id,))
            r = cur.fetchone()
            print(f"Saldo 31 Dic en BD: {r[0] if r else 'NO EXISTE'}")
            
            # 3. Ver si existe saldo el 1 Ene
            cur.execute("SELECT saldo_caja FROM control_caja WHERE empleado_identificacion=%s AND fecha='2026-01-01'", (emp_id,))
            r = cur.fetchone()
            print(f"Saldo 1 Ene en BD: {r[0] if r else 'NO EXISTE'}")

            # 4. Componentes del día 2 (aprox UTC para ver magnitud)
            # Nota: el script de reparación usó America/Bogota. Aquí usaré consultas simples de fecha
            # Si las columnas son timestamp, esto puede variar, pero nos dará una idea.
            
            # Cobrado
            cur.execute("""
                SELECT SUM(a.monto) 
                FROM abonos a JOIN tarjetas t ON a.tarjeta_codigo = t.codigo
                WHERE t.empleado_identificacion = %s AND a.fecha::date = %s
            """, (emp_id, fecha))
            cobrado = cur.fetchone()[0] or 0
            print(f"Cobrado (filtro fecha::date): {cobrado:,.2f}")
            
            # Prestado
            cur.execute("SELECT SUM(monto) FROM tarjetas WHERE empleado_identificacion=%s AND fecha_creacion::date = %s", (emp_id, fecha))
            prestado = cur.fetchone()[0] or 0
            print(f"Prestado: {prestado:,.2f}")
            
            # Gastos
            cur.execute("SELECT SUM(valor) FROM gastos WHERE empleado_identificacion=%s AND fecha_creacion::date = %s", (emp_id, fecha))
            gastos = cur.fetchone()[0] or 0
            print(f"Gastos: {gastos:,.2f}")
            
            # Entradas/Salidas en control_caja
            cur.execute("SELECT entradas, dividendos, saldo_caja FROM control_caja WHERE empleado_identificacion=%s AND fecha=%s", (emp_id, fecha))
            row = cur.fetchone()
            if row:
                print(f"Control Caja: Entradas={row[0]:,.2f}, Salidas={row[1]:,.2f}")
                print(f"SALDO GUARDADO EN BD: {row[2]:,.2f}")
            else:
                print("No hay registro en control_caja")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    inspect()

