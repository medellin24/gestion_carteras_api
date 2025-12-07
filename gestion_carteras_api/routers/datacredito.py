from fastapi import APIRouter, HTTPException, Depends, status
from typing import List, Optional, Set
import logging
from datetime import date, datetime

from ..schemas import DataCreditoReport, IndicadoresTarjeta
from ..security import get_current_principal, require_admin
from ..services.risk_engine import RiskEngine
from ..database.clientes_db import obtener_cliente_por_identificacion, actualizar_score_historial
from ..database.tarjetas_db import obtener_tarjetas_cliente
from ..database.abonos_db import obtener_abonos_por_tarjeta
from ..database.empleados_db import obtener_empleados

router = APIRouter()
logger = logging.getLogger(__name__)

def _get_empleados_cuenta(cuenta_id: Optional[int]) -> Set[str]:
    """Obtiene el set de identificaciones de empleados de una cuenta."""
    if not cuenta_id:
        return set()
    try:
        empleados = obtener_empleados(cuenta_id)
        return {e['identificacion'] for e in empleados}
    except Exception:
        return set()

@router.get("/clientes/{identificacion}/reporte", response_model=DataCreditoReport)
def get_datacredito_report(identificacion: str, principal: dict = Depends(get_current_principal)):
    """
    Genera el reporte de DataCrédito Interno en tiempo real.
    Combina historial compactado con análisis en vivo de tarjetas activas.
    DataCrédito es GLOBAL (ve todas las tarjetas de todas las cuentas),
    pero marca las tarjetas de la cuenta actual como "Esta Empresa" y las demás como "Entidad Externa".
    """
    try:
        # Obtener cuenta_id del usuario logueado para identificar tarjetas propias
        cuenta_id = principal.get("cuenta_id")
        empleados_cuenta_actual = _get_empleados_cuenta(cuenta_id)
        
        # 1. Obtener Cliente y su historial compactado
        cliente = obtener_cliente_por_identificacion(identificacion)
        if not cliente:
            raise HTTPException(status_code=404, detail="Cliente no encontrado")
        
        historial_compactado_raw = cliente.get('historial_crediticio') or []
        
        # Convertir raw dicts a objetos IndicadoresTarjeta
        historial_objs = []
        for h in historial_compactado_raw:
            try:
                # El historial compactado ya tiene empresa_anonym guardado
                # Si no lo tiene, marcar como Entidad Externa por defecto
                if 'empresa_anonym' not in h:
                    h['empresa_anonym'] = "Entidad Externa" 
                historial_objs.append(IndicadoresTarjeta(**h))
            except Exception as e:
                logger.warning(f"Error al parsear historial item: {e}")
                continue

        # 2. Obtener TODAS las Tarjetas del cliente (global, sin filtrar por cuenta)
        # Esto es intencional: DataCrédito ve todo el historial inter-cuenta
        tarjetas_vivas = obtener_tarjetas_cliente(identificacion, cuenta_id=None)
        
        activas_analizadas = []
        
        scores_actuales = []
        scores_historicos_recientes = []
        scores_historicos_restantes = []

        # Separar historial en reciente (últimos 3) y resto
        for idx, h in enumerate(historial_objs):
            if idx < 3:
                scores_historicos_recientes.append(h.score_individual)
            else:
                scores_historicos_restantes.append(h.score_individual)

        # 3. Analizar Tarjetas Vivas con RiskEngine
        for t in tarjetas_vivas:
            codigo = t.get('codigo')
            estado = str(t.get('estado', '')).lower()
            empleado_id = t.get('empleado_identificacion')
            
            # Determinar si la tarjeta es de "Esta Empresa" o "Entidad Externa"
            es_empresa_actual = empleado_id in empleados_cuenta_actual
            empresa_label = "Esta Empresa" if es_empresa_actual else "Entidad Externa"
            
            abonos = obtener_abonos_por_tarjeta(codigo)
            indicadores = RiskEngine.calcular_indicadores_tarjeta_activa(t, abonos)
            
            # Crear objeto IndicadoresTarjeta
            fecha_inicio_val = t.get('fecha_creacion') or t.get('fecha')
            if isinstance(fecha_inicio_val, datetime):
                fecha_inicio_val = fecha_inicio_val.date()
            elif isinstance(fecha_inicio_val, str):
                try:
                    fecha_inicio_val = date.fromisoformat(fecha_inicio_val[:10])
                except:
                    pass

            indicador_obj = IndicadoresTarjeta(
                id_referencia=codigo,
                fecha_inicio=fecha_inicio_val,
                monto=float(t.get('monto', 0)),
                dias_retraso_final=indicadores['dias_retraso_final'],
                frecuencia_pagos=indicadores['frecuencia_pagos'],
                promedio_atraso=indicadores['promedio_atraso'],
                puntaje_atraso_cierre=indicadores['puntaje_atraso_cierre'],
                score_individual=indicadores['score_individual'],
                estado_final=estado,
                empresa_anonym=empresa_label
            )
            activas_analizadas.append(indicador_obj)
            
            # Si está activa o pendiente (deuda viva), su score impacta el componente 'Actual'
            if estado in ('activa', 'activas', 'pendiente', 'pendientes'):
                scores_actuales.append(indicadores['score_individual'])
            else:
                # Si es cancelada reciente (no archivada), cuenta como historial reciente
                scores_historicos_recientes.insert(0, indicadores['score_individual'])

        # 4. Calcular Score Global
        score_final = RiskEngine.calcular_score_global_cliente(
            actuales=scores_actuales,
            historicos_recientes=scores_historicos_recientes,
            historicos_restantes=scores_historicos_restantes
        )

        # 5. Calcular Resúmenes
        total_cerrados = len(historial_objs) + len([t for t in tarjetas_vivas if str(t.get('estado', '')).lower() == 'cancelada'])
        total_activos = len(scores_actuales) # Ya contiene activas y pendientes (deuda viva)
        
        suma_retraso = sum(h.dias_retraso_final for h in historial_objs) + sum(a.dias_retraso_final for a in activas_analizadas)
        promedio_retraso = suma_retraso / (len(historial_objs) + len(activas_analizadas)) if (historial_objs or activas_analizadas) else 0
        
        suma_freq = sum(h.frecuencia_pagos for h in historial_objs) + sum(a.frecuencia_pagos for a in activas_analizadas)
        promedio_freq = suma_freq / (len(historial_objs) + len(activas_analizadas)) if (historial_objs or activas_analizadas) else 0

        # 6. Actualizar Score en BD (Cache)
        if score_final != cliente.get('score_global'):
            try:
                actualizar_score_historial(identificacion, score_final, historial_compactado_raw)
            except Exception:
                pass

        return DataCreditoReport(
            cliente_identificacion=identificacion,
            cliente_nombre=cliente.get('nombre'),
            cliente_apellido=cliente.get('apellido'),
            score_global=score_final,
            total_creditos_cerrados=total_cerrados,
            total_creditos_activos=total_activos,
            promedio_retraso_historico=round(promedio_retraso, 1),
            frecuencia_pago_promedio=round(promedio_freq, 1),
            tarjetas_activas=activas_analizadas,
            historial_compactado=historial_objs
        )

    except Exception as e:
        logger.error(f"Error generando reporte DataCredito: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error generando reporte: {e}")

@router.post("/tarjetas/{codigo}/archivar")
def archivar_tarjeta(codigo: str, principal: dict = Depends(require_admin)):
    """
    Compacta una tarjeta cancelada:
    1. Calcula sus indicadores finales.
    2. La agrega al historial JSON del cliente.
    3. (Opcional) Elimina los abonos físicos para ahorrar espacio.
    """
    # TODO: Implementar lógica de archivado real
    # Requiere acceso a DB de tarjetas para cambiar estado a 'archivada' 
    # y update del cliente.
    return {"message": "Endpoint de archivado pendiente de implementación final"}

