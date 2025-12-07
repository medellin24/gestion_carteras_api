
from datetime import date, datetime, timedelta
import math
from typing import List, Dict, Any, Optional

class RiskEngine:
    @staticmethod
    def normalizar_dias_retraso(dias: int) -> float:
        """
        Normaliza los días de retraso final a una escala 0-100.
        <= 0 días (puntual/adelantado) -> 100
        >= 30 días -> 0
        """
        if dias <= 0:
            return 100.0
        elif dias >= 30:
            return 0.0
        else:
            # Descenso lineal
            return 100.0 - (dias * 100.0 / 30.0)

    @staticmethod
    def normalizar_frecuencia(freq_porcentaje: float) -> float:
        """
        Normaliza la frecuencia de pagos (que ya viene en %).
        Simplemente clippea entre 0 y 100.
        """
        return min(100.0, max(0.0, freq_porcentaje))

    @staticmethod
    def normalizar_promedio_atraso(cuotas_promedio: float) -> float:
        """
        Normaliza el promedio de cuotas de atraso durante la vida del crédito.
        0 cuotas de atraso -> 100 (Excelente)
        >= 3 cuotas de atraso -> 0 (Pésimo)
        """
        if cuotas_promedio <= 0:
            return 100.0
        elif cuotas_promedio >= 3:
            return 0.0
        else:
            return 100.0 - (cuotas_promedio * 100.0 / 3.0)

    @staticmethod
    def normalizar_puntaje_cierre(puntaje_total: float) -> float:
        """
        Normaliza el indicador de 'Estrés Total al Cierre' (Cuotas Pendientes + Días Pasados).
        0 puntos -> 100
        >= 10 puntos -> 0
        """
        if puntaje_total <= 0:
            return 100.0
        elif puntaje_total >= 10:
            return 0.0
        else:
            return 100.0 - (puntaje_total * 100.0 / 10.0)

    @staticmethod
    def calcular_score_tarjeta(dias_retraso_final: int, 
                               frecuencia_pagos: float, 
                               promedio_atraso: float, 
                               puntaje_atraso_cierre: float) -> float:
        """
        Calcula el Score Individual de una tarjeta (0-100) usando ponderación.
        Pesos:
        - 30% Cumplimiento Fecha Final
        - 25% Frecuencia Pagos
        - 25% Promedio Atraso (Estrés diario)
        - 20% Puntaje Cierre (Foto final)
        """
        p_dias = RiskEngine.normalizar_dias_retraso(dias_retraso_final)
        p_freq = RiskEngine.normalizar_frecuencia(frecuencia_pagos)
        p_cuotas = RiskEngine.normalizar_promedio_atraso(promedio_atraso)
        p_cierre = RiskEngine.normalizar_puntaje_cierre(puntaje_atraso_cierre)

        score = (0.30 * p_dias) + (0.25 * p_freq) + (0.25 * p_cuotas) + (0.20 * p_cierre)
        return round(score, 1)

    @staticmethod
    def calcular_score_global_cliente(actuales: List[float], 
                                      historicos_recientes: List[float], 
                                      historicos_restantes: List[float]) -> int:
        """
        Calcula el Score Global del Cliente (0-100).
        Estrategia de Recencia:
        - 50% Promedio Tarjetas Activas (Presente)
        - 30% Promedio Últimos 3 Históricos (Reciente)
        - 20% Promedio Resto Históricos (Pasado)
        
        Si no tiene activas, el peso se redistribuye: 60% Reciente / 40% Pasado.
        Si no tiene nada, retorna 100 (Base inicial).
        """
        # Calcular promedios parciales
        s_actuales = sum(actuales) / len(actuales) if actuales else None
        s_hist3 = sum(historicos_recientes) / len(historicos_recientes) if historicos_recientes else None
        s_histR = sum(historicos_restantes) / len(historicos_restantes) if historicos_restantes else None

        # Caso 1: Cliente Nuevo (Nada de nada)
        if s_actuales is None and s_hist3 is None and s_histR is None:
            return 100

        # Caso 2: Solo Activas
        if s_actuales is not None and s_hist3 is None and s_histR is None:
            return int(s_actuales)

        # Caso 3: Sin Activas (Solo historia)
        if s_actuales is None:
            # Redistribución de pesos si no hay deuda actual
            # Si tiene ambos históricos
            if s_hist3 is not None and s_histR is not None:
                return int((0.6 * s_hist3) + (0.4 * s_histR))
            # Solo recientes
            elif s_hist3 is not None:
                return int(s_hist3)
            # Solo antiguos (raro pero posible)
            else:
                return int(s_histR)

        # Caso 4: Mix Completo (Estándar)
        # Si falta alguno de los históricos, ajustamos pesos dinámicamente
        peso_actual = 0.5
        peso_hist3 = 0.3
        peso_histR = 0.2
        
        acumulado = (peso_actual * s_actuales)
        divisor = peso_actual

        if s_hist3 is not None:
            acumulado += (peso_hist3 * s_hist3)
            divisor += peso_hist3
        
        if s_histR is not None:
            acumulado += (peso_histR * s_histR)
            divisor += peso_histR
            
        return int(acumulado / divisor)

    @staticmethod
    def calcular_indicadores_tarjeta_activa(tarjeta: Dict[str, Any], abonos: List[Dict[str, Any]], fecha_calculo: date = None) -> Dict[str, Any]:
        """
        Calcula los 4 indicadores en tiempo real para una tarjeta activa.
        """
        if not fecha_calculo:
            fecha_calculo = date.today()

        # Datos básicos
        fecha_inicio = tarjeta.get('fecha_creacion') or tarjeta.get('fecha')
        if isinstance(fecha_inicio, datetime):
            fecha_inicio = fecha_inicio.date()
        elif isinstance(fecha_inicio, str):
             fecha_inicio = date.fromisoformat(str(fecha_inicio)[:10])

        cuotas_pactadas = int(tarjeta.get('cuotas', 1))
        monto_total = float(tarjeta.get('monto', 0))
        valor_cuota = monto_total / cuotas_pactadas if cuotas_pactadas > 0 else 0
        
        # 1. Días Retraso Final (Proyectado)
        # Si hoy > fecha_fin_pactada, ya hay retraso
        fecha_fin_pactada = fecha_inicio + timedelta(days=cuotas_pactadas)
        dias_retraso_final = (fecha_calculo - fecha_fin_pactada).days
        # Si es negativo (aún no vence), lo dejamos en negativo (adelanto/tiempo a favor)
        
        # 2. Frecuencia Pagos (Hábito)
        # Días con cobertura (pago o adelanto) / Días transcurridos
        dias_transcurridos = (fecha_calculo - fecha_inicio).days
        if dias_transcurridos <= 0: dias_transcurridos = 1
        
        # Lógica simplificada de cobertura:
        # Un día está cubierto si el total abonado hasta ese día >= deuda esperada hasta ese día
        # O si hizo un abono ese día específico.
        # Para eficiencia, iteraremos los días
        
        dias_cubiertos = 0
        abonos_por_fecha = {}
        for a in abonos:
            f = a.get('fecha')
            if isinstance(f, datetime): f = f.date()
            elif isinstance(f, str): f = date.fromisoformat(str(f)[:10])
            abonos_por_fecha[f] = abonos_por_fecha.get(f, 0) + float(a.get('monto', 0))

        total_abonado_acum = 0
        atrasos_diarios_acum = 0

        for i in range(1, dias_transcurridos + 1):
            dia_iter = fecha_inicio + timedelta(days=i)
            deuda_esperada = valor_cuota * i
            if deuda_esperada > monto_total: deuda_esperada = monto_total
            
            # Sumar abono del día si existe
            abono_hoy = abonos_por_fecha.get(dia_iter, 0)
            total_abonado_acum += abono_hoy
            
            # Verificar cobertura (Frecuencia)
            cubierto = False
            if abono_hoy > 0:
                cubierto = True
            elif total_abonado_acum >= (deuda_esperada - (valor_cuota * 0.1)): # Margen tolerancia
                cubierto = True
            
            if cubierto:
                dias_cubiertos += 1
            
            # Calcular Atraso Diario (Estrés)
            deficit = deuda_esperada - total_abonado_acum
            cuotas_atraso_hoy = deficit / valor_cuota if valor_cuota > 0 else 0
            if cuotas_atraso_hoy < 0: cuotas_atraso_hoy = 0
            atrasos_diarios_acum += cuotas_atraso_hoy

        frecuencia_pagos = (dias_cubiertos / dias_transcurridos) * 100.0
        promedio_atraso = atrasos_diarios_acum / dias_transcurridos

        # 4. Puntaje Atraso Cierre (Foto Hoy)
        # Cuotas pendientes hoy + Días pasados vencimiento
        total_pagado_hoy = sum(float(a.get('monto', 0)) for a in abonos)
        saldo_pendiente = max(0.0, monto_total - total_pagado_hoy)
        cuotas_pendientes_hoy = saldo_pendiente / valor_cuota if valor_cuota > 0 else 0
        
        dias_pasados = max(0, dias_retraso_final)
        
        puntaje_atraso_cierre = cuotas_pendientes_hoy + dias_pasados

        return {
            "dias_retraso_final": int(dias_retraso_final),
            "frecuencia_pagos": round(frecuencia_pagos, 1),
            "promedio_atraso": round(promedio_atraso, 2),
            "puntaje_atraso_cierre": round(puntaje_atraso_cierre, 1),
            # Extra calculada
            "score_individual": RiskEngine.calcular_score_tarjeta(
                int(dias_retraso_final), frecuencia_pagos, promedio_atraso, puntaje_atraso_cierre
            )
        }

