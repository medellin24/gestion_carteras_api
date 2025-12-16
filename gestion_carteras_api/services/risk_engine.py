from datetime import date, datetime, timedelta
import math
from typing import List, Dict, Any, Optional

class RiskEngine:
    @staticmethod
    def normalizar_dias_retraso(dias: int) -> float:
        """
        [OBSOLETO PARA SCORE DIRECTO] Se mantiene por si se quiere visualizar.
        Normaliza los días de retraso final a una escala 0-100.
        """
        if dias <= 0:
            return 100.0
        elif dias >= 30:
            return 0.0
        else:
            return 100.0 - (dias * 100.0 / 30.0)

    @staticmethod
    def normalizar_frecuencia(freq_porcentaje: float) -> float:
        """
        Normaliza la frecuencia de pagos (Puntualidad).
        Ya viene en % (0-100).
        """
        return min(100.0, max(0.0, freq_porcentaje))

    @staticmethod
    def normalizar_puntaje_cierre(puntaje_total: float) -> float:
        """
        Normaliza el indicador de 'Estrés Total al Cierre' (Cuotas Pendientes + Días Pasados).
        Escala definida por usuario:
        - <= 0 puntos  -> 100 (Excelente)
        - 1 a 6        -> 90  (Bueno)
        - 7 a 15       -> 60  (Regular)
        - 16 a 60      -> 20  (Malo)
        - > 60         -> 0   (Clavo)
        """
        if puntaje_total <= 0:
            return 100.0
        elif puntaje_total <= 6:
            return 90.0
        elif puntaje_total <= 15:
            return 60.0
        elif puntaje_total <= 60:
            return 20.0
        else:
            return 0.0

    @staticmethod
    def calcular_score_tarjeta(frecuencia_pagos: float, 
                               puntaje_atraso_cierre: float) -> float:
        """
        Calcula el Score Individual de una tarjeta (0-100) usando nueva ponderación.
        Pesos:
        - 40% Puntualidad (Frecuencia Pagos)
        - 60% Estrés Cierre (Cuotas Atrasadas + Días Retraso)
        
        Notas:
        - 'Cuotas Atrasadas (Max)' es informativo, no pondera.
        - 'Días Retraso Final' ya está incluido en 'Estrés Cierre'.
        """
        p_freq = RiskEngine.normalizar_frecuencia(frecuencia_pagos)
        p_cierre = RiskEngine.normalizar_puntaje_cierre(puntaje_atraso_cierre)

        score = (0.40 * p_freq) + (0.60 * p_cierre)
        return round(score, 1)

    @staticmethod
    def calcular_score_global_cliente(actuales: List[float], 
                                      historicos_recientes: List[float], 
                                      historicos_restantes: List[float]) -> int:
        """
        Calcula el Score Global del Cliente (0-100).

        Estrategia de Ponderación (si no aplica regla crítica):
        - 50% Promedio Tarjetas Activas
        - 30% Promedio Últimos 3 Históricos
        - 20% Promedio Resto Históricos
        """

        # NOTA DE POLÍTICA:
        # La regla de negocio tipo "manzana podrida" (si hay score < 30, colapsar el global)
        # se controla a nivel de Router porque requiere distinguir estados (ACTIVA vs HISTÓRICA).
        # El motor (RiskEngine) solo hace el promedio ponderado.

        # Cálculo Ponderado Estándar
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
            if s_hist3 is not None and s_histR is not None:
                return int((0.6 * s_hist3) + (0.4 * s_histR))
            elif s_hist3 is not None:
                return int(s_hist3)
            else:
                return int(s_histR)

        # Caso 4: Mix Completo
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
        Calcula los 3 indicadores clave + Score para una tarjeta activa.
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
        monto_capital = float(tarjeta.get('monto', 0))
        tasa_interes = float(tarjeta.get('interes', 0)) # % de interés (ej. 20.0)
        
        # Corrección 1: Valor cuota DEBE incluir interés
        # Total a pagar = Capital * (1 + Interes/100)
        monto_total_con_interes = monto_capital * (1 + (tasa_interes / 100.0))
        valor_cuota = monto_total_con_interes / cuotas_pactadas if cuotas_pactadas > 0 else 0
        
        # 1. Días Retraso Final (Proyectado/Real)
        # Si la tarjeta está cancelada, usamos fecha de cancelación real
        estado = str(tarjeta.get('estado', '')).lower()
        es_cancelada = estado == 'cancelada'
        fecha_cancelacion = tarjeta.get('fecha_cancelacion')

        # Helper: normalizar fecha (date/datetime/str) a date
        def _to_date(x) -> Optional[date]:
            if x is None:
                return None
            if isinstance(x, datetime):
                return x.date()
            if isinstance(x, date):
                return x
            if isinstance(x, str):
                try:
                    return date.fromisoformat(str(x)[:10])
                except Exception:
                    return None
            return None

        # Si está cancelada pero NO tiene fecha_cancelacion (datos viejos),
        # usamos la fecha del último abono como proxy de cierre.
        fecha_fin_real: Optional[date] = None
        if es_cancelada:
            fecha_fin_real = _to_date(fecha_cancelacion)
            if fecha_fin_real is None and abonos:
                try:
                    fechas_ab = [_to_date(a.get('fecha')) for a in abonos]
                    fechas_ab = [f for f in fechas_ab if f is not None]
                    if fechas_ab:
                        fecha_fin_real = max(fechas_ab)
                except Exception:
                    fecha_fin_real = None
            if fecha_fin_real is None:
                # Último recurso: evitar None (pero puede inflar; mejor que castigar por años).
                fecha_fin_real = fecha_calculo
        
        # Detección de Frecuencia de Cobro (Modalidad)
        modalidad = str(tarjeta.get('modalidad_pago', 'diario')).lower()
        
        step_dias = 1
        if 'semanal' in modalidad:
            step_dias = 7
        elif 'quincenal' in modalidad:
            step_dias = 15
        elif 'mensual' in modalidad:
            step_dias = 30
            
        # Ajuste: fecha_fin_pactada depende de la modalidad
        # Cuotas = N pagos. Duración = cuotas * step_dias
        duracion_estimada_dias = cuotas_pactadas * step_dias
        fecha_fin_pactada = fecha_inicio + timedelta(days=duracion_estimada_dias)
        
        if es_cancelada:
            dias_retraso_final = (fecha_fin_real - fecha_fin_pactada).days
        else:
            # Si está activa, es la fecha actual vs pactada
            dias_retraso_final = (fecha_calculo - fecha_fin_pactada).days
        
        # 2. Puntualidad (Frecuencia Pagos)
        # Lógica: Días cubiertos / Días transcurridos (o duración total si cancelada)
        if es_cancelada:
             dias_transcurridos = (fecha_fin_real - fecha_inicio).days
        else:
             dias_transcurridos = (fecha_calculo - fecha_inicio).days
             
        # CASO ESPECIAL: Día 0 (Crédito creado hoy)
        # Si aún no ha pasado ni un día desde la creación, el cliente está al día por definición.
        if dias_transcurridos <= 0:
            return {
                "dias_retraso_final": max(0, int(dias_retraso_final)),
                "frecuencia_pagos": 100.0, # Perfecto por defecto
                "max_cuotas_atrasadas": 0,
                "puntaje_atraso_cierre": 0,
                "score_individual": 100.0 # Score máximo
            }
        
        # Cálculo de cobertura diaria y máx cuotas atrasadas
        dias_cubiertos = 0
        max_cuotas_atrasadas = 0
        
        abonos_por_fecha = {}
        for a in abonos:
            f = a.get('fecha')
            if isinstance(f, datetime): f = f.date()
            elif isinstance(f, str): f = date.fromisoformat(str(f)[:10])
            abonos_por_fecha[f] = abonos_por_fecha.get(f, 0) + float(a.get('monto', 0))

        total_abonado_acum = 0
        
        # Iteramos por día para ser precisos, pero la "deuda_esperada" crece por escalones
        for i in range(1, dias_transcurridos + 1):
            dia_iter = fecha_inicio + timedelta(days=i)
            
            # Calcular cuantas cuotas "enteras" deberían llevarse pagadas al día i
            # Ejemplo: Semanal. Día 1-6 -> 0 cuotas. Día 7 -> 1 cuota. Día 14 -> 2 cuotas.
            cuotas_devengadas = i // step_dias
            
            # Si el residuo es 0 (día de pago exacto), ya se cuenta la cuota.
            # Pero para ser justos en 'puntualidad', damos todo el ciclo de gracia hasta el día de corte.
            # Sin embargo, si estamos en el día 4 de 7, la deuda exigible es la del periodo ANTERIOR completo.
            
            # Si cuotas_devengadas > cuotas_pactadas, capeamos (no exigir más del total)
            if cuotas_devengadas > cuotas_pactadas:
                cuotas_devengadas = cuotas_pactadas
                
            deuda_esperada = valor_cuota * cuotas_devengadas
            if deuda_esperada > monto_total_con_interes: deuda_esperada = monto_total_con_interes
            
            # Sumar abono del día
            abono_hoy = abonos_por_fecha.get(dia_iter, 0)
            total_abonado_acum += abono_hoy
            
            # Verificar cobertura (Puntualidad)
            # Un día se considera "cubierto" si:
            # A) Se hizo un abono ese mismo día (intención de pago).
            # B) El acumulado pagado >= deuda esperada hasta ese momento.
            
            cubierto = False
            if abono_hoy > 0:
                cubierto = True
            elif total_abonado_acum >= (deuda_esperada - (valor_cuota * 0.1)): # Tolerancia 10% cuota
                cubierto = True
            
            if cubierto:
                dias_cubiertos += 1
            
            # Calcular Atraso Diario
            deficit = deuda_esperada - total_abonado_acum
            if deficit <= 0:
                cuotas_atraso_hoy = 0
            else:
                # Tolerancia: si falta <= 10% de una cuota, consideramos 0 (evita decimales por redondeos).
                if deficit <= (valor_cuota * 0.1):
                    cuotas_atraso_hoy = 0
                else:
                    cuotas_atraso_hoy = int(math.ceil(deficit / valor_cuota)) if valor_cuota > 0 else 0

            if cuotas_atraso_hoy > max_cuotas_atrasadas:
                max_cuotas_atrasadas = cuotas_atraso_hoy

        frecuencia_observada = (dias_cubiertos / dias_transcurridos) * 100.0
        
        # Corrección 3: Puntualidad Ponderada por Avance
        # Evita castigar créditos nuevos.
        # Progreso = días_transcurridos / duración_estimada
        # Score = (Observed * Progreso) + (100 * (1 - Progreso))
        
        if es_cancelada:
            progreso = 1.0
        else:
            total_dias_credito = duracion_estimada_dias
            if total_dias_credito <= 0: total_dias_credito = 1
            progreso = dias_transcurridos / total_dias_credito
            if progreso > 1.0: progreso = 1.0
            if progreso < 0.0: progreso = 0.0
            
        frecuencia_pagos = (frecuencia_observada * progreso) + (100.0 * (1.0 - progreso))

        # 3. Estrés Cierre (Sintético)
        # Cuotas pendientes HOY + Días pasados vencimiento
        # Si es cancelada, las cuotas pendientes son 0, solo queda el retraso final.
        if es_cancelada:
            cuotas_pendientes_hoy = 0.0
        else:
            # Corrección 2: Estrés de cierre debe ser sobre DEUDA VENCIDA, no saldo total
            # Calculamos deuda esperada a la fecha de hoy
            cuotas_devengadas_hoy = dias_transcurridos // step_dias
            if cuotas_devengadas_hoy > cuotas_pactadas: cuotas_devengadas_hoy = cuotas_pactadas
            
            deuda_exigible_hoy = valor_cuota * cuotas_devengadas_hoy
            
            total_pagado_hoy = sum(float(a.get('monto', 0)) for a in abonos)
            
            deficit_real = max(0.0, deuda_exigible_hoy - total_pagado_hoy)
            if deficit_real <= 0:
                cuotas_pendientes_hoy = 0
            else:
                if deficit_real <= (valor_cuota * 0.1):
                    cuotas_pendientes_hoy = 0
                else:
                    cuotas_pendientes_hoy = int(math.ceil(deficit_real / valor_cuota)) if valor_cuota > 0 else 0
        
        # Días pasados solo cuentan si son positivos (retraso real)
        dias_pasados_reales = max(0, dias_retraso_final)
        
        puntaje_atraso_cierre = int(cuotas_pendientes_hoy) + int(dias_pasados_reales)

        return {
            "dias_retraso_final": max(0, int(dias_retraso_final)),
            "frecuencia_pagos": round(frecuencia_pagos, 1),
            "max_cuotas_atrasadas": int(max_cuotas_atrasadas),
            "puntaje_atraso_cierre": int(puntaje_atraso_cierre),
            "score_individual": RiskEngine.calcular_score_tarjeta(
                frecuencia_pagos, puntaje_atraso_cierre
            )
        }
