from datetime import date, timedelta
from gestion_carteras_api.services.risk_engine import RiskEngine

def test_ferley_manual():
    print("--- Simulación Ferley con Datos Manuales Corregidos ---")
    
    # Configuración de tarjeta
    fecha_inicio = date(2025, 12, 12)
    monto = 1000000.0
    interes = 20.0
    cuotas = 40
    
    monto_total = monto * (1 + interes/100.0)
    valor_cuota = monto_total / cuotas  # 30.000
    
    # Abonos reportados por usuario
    # Diccionario {dia_relativo: abono}
    # Dia 1 = 13-dic
    abonos_map = {
        1: 30000, 2: 30000, 3: 30000, 4: 30000, 5: 30000, 6: 30000, 7: 30000, # 13-19 dic (ok)
        8: 30000, # 20 dic (ok según usuario)
        9: 0,     # 21 dic (Fallo)
        10: 60000, # 22 dic (Paga 2)
        11: 30000, 12: 30000, # 23-24 dic
        13: 0,    # 25 dic (Fallo)
        14: 60000, # 26 dic (Paga 2)
        15: 30000, # 27 dic
        16: 0,    # 28 dic (Fallo)
        17: 60000, # 29 dic (Paga 2)
        18: 30000, # 30 dic
        19: 0,    # 31 dic (Fallo)
        20: 0,    # 01 ene (Fallo)
        21: 90000, # 02 ene (Paga 3)
        22: 30000, # 03 ene
        23: 0,    # 04 ene (Fallo)
        24: 60000, # 05 ene (Paga 2)
        25: 30000, 26: 30000, 27: 30000, 28: 30000, 29: 30000, # 06-10 ene
        30: 0,    # 11 ene (Fallo)
        31: 60000, # 12 ene (Paga 2)
        32: 30000, 33: 30000, 34: 30000, 35: 30000 # 13-16 ene
    }
    
    # Construir lista de abonos para RiskEngine
    abonos_list = []
    for d, m in abonos_map.items():
        if m > 0:
            f = fecha_inicio + timedelta(days=d)
            abonos_list.append({'fecha': f, 'monto': m})
            
    tarjeta = {
        'fecha_creacion': fecha_inicio,
        'monto': monto,
        'interes': interes,
        'cuotas': cuotas,
        'estado': 'activa',
        'modalidad_pago': 'diario'
    }
    
    # Ejecutar RiskEngine REAL
    indicadores = RiskEngine.calcular_indicadores_tarjeta_activa(tarjeta, abonos_list, fecha_calculo=date(2026, 1, 16))
    
    print("\n--- RESULTADOS RISK ENGINE (Lógica Real) ---")
    print(f"Puntualidad: {indicadores['frecuencia_pagos']:.2f}%")
    print(f"Score: {indicadores['score_individual']}")
    
    # Validar contra expectativa (97.1%)
    # 35 días, 1 fallo = 34/35 = 97.14%
    esperado = (34/35) * 100
    print(f"Esperado: {esperado:.2f}%")
    
    if abs(indicadores['frecuencia_pagos'] - esperado) < 0.1:
        print("✅ LA LÓGICA COINCIDE PERFECTAMENTE CON TU ANÁLISIS")
    else:
        print("❌ AÚN HAY DISCREPANCIA")

if __name__ == "__main__":
    test_ferley_manual()