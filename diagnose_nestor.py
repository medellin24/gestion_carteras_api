import sys
import os
import logging
from datetime import date, datetime, timedelta
from decimal import Decimal

sys.path.append(os.getcwd())
logging.basicConfig(level=logging.INFO)

from gestion_carteras_api.database.connection_pool import DatabasePool
from gestion_carteras_api.database.db_config import DB_CONFIG

def diagnose():
    DatabasePool.initialize(**DB_CONFIG)
    
    nombre_buscado = 'NESTOR CONDE'
    fecha_analisis = date(2025, 12, 4)
    
    with DatabasePool.get_cursor() as cur:
        # 1. Buscar ID del empleado
        try:
            cur.execute("SELECT identificacion, nombre, timezone FROM empleados WHERE nombre ILIKE %s", (f"%{nombre_buscado}%",))
            emp = cur.fetchone()
        except:
            cur.connection.rollback()
            cur.execute("SELECT identificacion, nombre FROM empleados WHERE nombre ILIKE %s", (f"%{nombre_buscado}%",))
            emp = cur.fetchone()
            if emp: emp = emp + ('America/Bogota',) # Default TZ
            
        if not emp:
            print(f"Empleado '{nombre_buscado}' no encontrado.")
            return
        
        emp_id, emp_nombre, emp_tz = emp
        print(f"Empleado encontrado: {emp_nombre} ({emp_id}) - TZ: {emp_tz}")
        
        # 2. Caja previa
        cur.execute("""
            SELECT saldo_caja, fecha FROM control_caja 
            WHERE empleado_identificacion = %s AND fecha < %s 
            ORDER BY fecha DESC LIMIT 1
        """, (emp_id, fecha_analisis))
        prev = cur.fetchone()
        prev_val = Decimal(str(prev[0])) if prev else Decimal('0')
        print(f"Caja PREVIA (< {fecha_analisis}): {prev_val} (Fecha: {prev[1] if prev else 'N/A'})")
        
        # 3. Rangos de tiempo (simulando lógica de caja_db)
        from datetime import timezone as _tz
        try:
            from zoneinfo import ZoneInfo
            _tz_local = ZoneInfo(emp_tz) if emp_tz else _tz.utc
        except:
            _tz_local = _tz.utc
            
        start_local = datetime(fecha_analisis.year, fecha_analisis.month, fecha_analisis.day, 0, 0, 0, tzinfo=_tz_local)
        end_local = datetime(fecha_analisis.year, fecha_analisis.month, fecha_analisis.day, 23, 59, 59, 999000, tzinfo=_tz_local)
        
        start_utc = start_local.astimezone(_tz.utc)
        end_utc = end_local.astimezone(_tz.utc)
        
        print(f"Rango UTC análisis: {start_utc} a {end_utc}")
        
        # 4. Abonos (cobrado)
        cur.execute("""
            SELECT SUM(a.monto), COUNT(*)
            FROM abonos a JOIN tarjetas t ON a.tarjeta_codigo = t.codigo
            WHERE t.empleado_identificacion = %s AND a.fecha >= %s AND a.fecha <= %s
        """, (emp_id, start_utc, end_utc))
        abonos_res = cur.fetchone()
        abonos_val = Decimal(str(abonos_res[0] or 0))
        print(f"Abonos (cobrado): {abonos_val} ({abonos_res[1]} operaciones)")
        
        # 5. Prestamos (tarjetas)
        cur.execute("""
            SELECT SUM(t.monto), COUNT(*)
            FROM tarjetas t
            WHERE t.empleado_identificacion = %s AND t.fecha_creacion >= %s AND t.fecha_creacion <= %s
        """, (emp_id, start_utc, end_utc))
        prestamos_res = cur.fetchone()
        prestamos_val = Decimal(str(prestamos_res[0] or 0))
        print(f"Prestamos: {prestamos_val} ({prestamos_res[1]} operaciones)")
        
        # 6. Gastos
        cur.execute("""
            SELECT SUM(g.valor), COUNT(*)
            FROM gastos g
            WHERE g.empleado_identificacion = %s AND g.fecha_creacion >= %s AND g.fecha_creacion <= %s
        """, (emp_id, start_utc, end_utc))
        gastos_res = cur.fetchone()
        gastos_val = Decimal(str(gastos_res[0] or 0))
        print(f"Gastos: {gastos_val} ({gastos_res[1]} operaciones)")
        
        # 7. Salidas/Entradas (control_caja)
        cur.execute("""
            SELECT dividendos, entradas
            FROM control_caja
            WHERE empleado_identificacion = %s AND fecha = %s
        """, (emp_id, fecha_analisis))
        ctrl = cur.fetchone()
        salidas_val = Decimal(str(ctrl[0] or 0)) if ctrl else Decimal('0')
        entradas_val = Decimal(str(ctrl[1] or 0)) if ctrl else Decimal('0')
        print(f"Salidas (dividendos): {salidas_val}")
        print(f"Entradas (control_caja): {entradas_val}")
        
        # 8. Cálculo Final
        calculado = prev_val + abonos_val - prestamos_val - gastos_val - salidas_val + entradas_val
        print(f"\n--- RESUMEN ---")
        print(f"Previo:    {prev_val:>10}")
        print(f"+ Cobrado: {abonos_val:>10}")
        print(f"- Prestado:{prestamos_val:>10}")
        print(f"- Gastos:  {gastos_val:>10}")
        print(f"- Salidas: {salidas_val:>10}")
        print(f"+ Entradas:{entradas_val:>10}")
        print(f"----------------------")
        print(f"Calculado: {calculado:>10}")
        
        # 9. Valor actual en BD
        cur.execute("SELECT saldo_caja FROM control_caja WHERE empleado_identificacion = %s AND fecha = %s", (emp_id, fecha_analisis))
        actual = cur.fetchone()
        print(f"Valor en BD: {actual[0] if actual else 'NO REGISTRO'}")
        
        # 10. Listar detalle de préstamos para ver duplicados o valores extraños
        if prestamos_val > 0:
            print("\nDetalle Préstamos:")
            cur.execute("""
                SELECT codigo, monto, fecha_creacion AT TIME ZONE 'UTC' AT TIME ZONE 'America/Bogota' 
                FROM tarjetas 
                WHERE empleado_identificacion = %s AND fecha_creacion >= %s AND fecha_creacion <= %s
            """, (emp_id, start_utc, end_utc))
            for r in cur.fetchall():
                print(f" - Tarjeta {r[0]}: {r[1]} ({r[2]})")

if __name__ == "__main__":
    diagnose()

