import sys
import os
from decimal import Decimal
from datetime import date, datetime
try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo # type: ignore

# Agregar root al path
sys.path.append(os.getcwd())

from gestion_carteras_api.database.db_config import DB_CONFIG
from gestion_carteras_api.database.connection_pool import DatabasePool
from gestion_carteras_api.database.tarjetas_db import buscar_tarjetas, obtener_tarjeta_por_codigo
from gestion_carteras_api.database.abonos_db import obtener_abonos_tarjeta
from gestion_carteras_api.services.risk_engine import RiskEngine

def test_ferley():
    # Inicializar BD
    DatabasePool.initialize(**DB_CONFIG)
    
    try:
        # 1. Buscar tarjeta
        print("--- Buscando tarjeta de 'ferley' ---")
        encontradas = buscar_tarjetas('ferley')
        if not encontradas:
            print("No se encontraron tarjetas.")
            return

        target_codigo = None
        for t in encontradas:
            # t[5] es fecha_creacion. Verificamos si es dic 2025 o cercana
            fecha_crea = t[5]
            if str(fecha_crea).startswith('2025-12'):
                target_codigo = t[0]
                break
        
        if not target_codigo:
            target_codigo = encontradas[0][0]
            
        print(f"--- Analizando tarjeta: {target_codigo} ---")
        
        # 2. Obtener datos completos
        tarjeta = obtener_tarjeta_por_codigo(target_codigo)
        abonos_raw = obtener_abonos_tarjeta(target_codigo)
        
        # Convertir abonos a formato dict AJUSTANDO ZONA HORARIA
        abonos = []
        try:
            tz_co = ZoneInfo('America/Bogota')
            utc = ZoneInfo('UTC')
        except:
            tz_co = None
            utc = None
        
        print("\n--- ABONOS EN BD (Ajustados a Colombia) ---")
        for a in abonos_raw:
            # a[1] es fecha (datetime o date)
            fecha_bd = a[1]
            if isinstance(fecha_bd, datetime) and tz_co:
                # Si es naive, asumir UTC y convertir. Si tiene tz, convertir.
                if fecha_bd.tzinfo is None:
                    fecha_bd = fecha_bd.replace(tzinfo=utc)
                fecha_co = fecha_bd.astimezone(tz_co).date()
            else:
                fecha_co = fecha_bd if not isinstance(fecha_bd, datetime) else fecha_bd.date()
                
            monto = float(a[2])
            abonos.append({
                'id': a[0],
                'fecha': fecha_co,
                'monto': monto
            })
            print(f"Abono: {fecha_co} - ${monto:,.0f}")
            
        print(f"\nTarjeta Fecha: {tarjeta['fecha_creacion']}")
        print(f"Monto: {tarjeta['monto']}, Cuotas: {tarjeta['cuotas']}")
        print(f"Total Abonos: {len(abonos)}")
        
        # 3. Correr RiskEngine con datos ajustados
        indicadores = RiskEngine.calcular_indicadores_tarjeta_activa(tarjeta, abonos, fecha_calculo=date(2026, 1, 16))
        
        print("\n--- RESULTADOS RISK ENGINE ---")
        print(f"Puntualidad (Frecuencia): {indicadores['frecuencia_pagos']}%")
        print(f"Score: {indicadores['score_individual']}")
        
        # Simulacion detallada con los mismos datos ajustados
        print("\n--- DETALLE DÍA A DÍA (Con datos ajustados) ---")
        fecha_inicio = tarjeta['fecha_creacion']
        if isinstance(fecha_inicio, datetime) and tz_co:
             if fecha_inicio.tzinfo is None:
                 fecha_inicio = fecha_inicio.replace(tzinfo=utc)
             fecha_inicio = fecha_inicio.astimezone(tz_co).date()
        elif isinstance(fecha_inicio, datetime):
             fecha_inicio = fecha_inicio.date()
        
        monto_total = float(tarjeta['monto']) * (1 + float(tarjeta['interes'])/100.0)
        valor_cuota = monto_total / int(tarjeta['cuotas'])
        
        dias_transcurridos = (date(2026, 1, 16) - fecha_inicio).days
        total_abonado_acum = 0
        abonos_por_fecha = {}
        for a in abonos:
            f = a['fecha']
            abonos_por_fecha[f] = abonos_por_fecha.get(f, 0) + a['monto']
            
        dias_cubiertos = 0
        
        for i in range(1, dias_transcurridos + 1):
            dia_iter = fecha_inicio + query_timedelta(i)
            deuda_esperada = valor_cuota * i
            if deuda_esperada > monto_total: deuda_esperada = monto_total
            
            abono_hoy = abonos_por_fecha.get(dia_iter, 0)
            total_abonado_acum += abono_hoy
            
            cubierto = False
            estado = "FALLO"
            
            if abono_hoy > 0:
                cubierto = True
                estado = "PAGO"
            elif total_abonado_acum >= (deuda_esperada - (valor_cuota * 0.1)):
                cubierto = True
                estado = "SALDO"
            
            # Gabela
            if not cubierto and i < dias_transcurridos:
                deuda_manana = valor_cuota * (i + 1)
                dia_manana = fecha_inicio + query_timedelta(i+1)
                abono_manana = abonos_por_fecha.get(dia_manana, 0)
                acum_manana = total_abonado_acum + abono_manana
                if acum_manana >= (deuda_manana - (valor_cuota * 0.1)):
                    cubierto = True
                    estado = "GABELA"
            
            if cubierto:
                dias_cubiertos += 1
            
            print(f"Dia {i} ({dia_iter}): Esperado={deuda_esperada:.0f}, Acum={total_abonado_acum:.0f} (+{abono_hoy:.0f}) -> {estado}")

    finally:
        DatabasePool.close_all()

from datetime import timedelta
def query_timedelta(d):
    return timedelta(days=d)

if __name__ == "__main__":
    test_ferley()