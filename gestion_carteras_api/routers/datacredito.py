from fastapi import APIRouter, HTTPException, Depends, status
from typing import List, Optional, Set
import logging
from datetime import date, datetime

from ..schemas import DataCreditoReport, IndicadoresTarjeta
from ..security import get_current_principal, require_admin
from ..services.risk_engine import RiskEngine
from ..database.connection_pool import DatabasePool
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
        # Normalizar cuenta_id del token (puede venir como int o str según versiones)
        cuenta_id_raw = principal.get("cuenta_id")
        try:
            cuenta_id = int(cuenta_id_raw) if cuenta_id_raw is not None else None
        except Exception:
            cuenta_id = None

        # Fallback robusto: algunos tokens viejos de cobrador pueden venir sin cuenta_id.
        # Si tenemos empleado_identificacion, inferimos cuenta_id desde empleados.
        if cuenta_id is None:
            emp_id = principal.get("empleado_identificacion")
            if emp_id:
                try:
                    with DatabasePool.get_cursor() as cur:
                        cur.execute("SELECT cuenta_id FROM empleados WHERE identificacion=%s", (str(emp_id),))
                        row = cur.fetchone()
                        if row and row[0] is not None:
                            cuenta_id = int(row[0])
                except Exception:
                    pass

        empleados_cuenta_actual = _get_empleados_cuenta(cuenta_id)
        
        # 1. Obtener Cliente y su historial compactado
        cliente = obtener_cliente_por_identificacion(identificacion)
        if not cliente:
            raise HTTPException(status_code=404, detail="Cliente no encontrado")
        
        historial_compactado_raw = cliente.get('historial_crediticio') or []
        
        # 2. Obtener TODAS las Tarjetas del cliente (global, sin filtrar por cuenta)
        # Esto es intencional: DataCrédito ve todo el historial inter-cuenta
        tarjetas_vivas = obtener_tarjetas_cliente(identificacion, cuenta_id=None)
        
        # Mapas temporales para anonimizar empresas externas (compartido entre historial y vivas)
        externas_map = {}
        next_externa_char = 'A'

        # Helper para obtener etiqueta anonimizada
        def get_empresa_label(t_cuenta_id, empleado_identificacion: Optional[str] = None):
            nonlocal next_externa_char

            # Si el empleado pertenece a la cuenta actual, es "Esta Empresa"
            # (Esto cubre casos de cuenta_id nulo o inconsistente en datos viejos)
            if empleado_identificacion and empleado_identificacion in empleados_cuenta_actual:
                return "Esta Empresa"

            if not t_cuenta_id:
                return "Entidad Desconocida"

            # Normalizar cuenta_id de la tarjeta/historial (puede venir como int o str en JSON)
            try:
                t_cuenta_norm = int(t_cuenta_id)
            except Exception:
                t_cuenta_norm = None

            if t_cuenta_norm is None:
                return "Entidad Desconocida"

            if cuenta_id is not None and t_cuenta_norm == cuenta_id:
                return "Esta Empresa"
            
            if t_cuenta_norm not in externas_map:
                externas_map[t_cuenta_norm] = f"Empresa Externa {next_externa_char}"
                next_externa_char = chr(ord(next_externa_char) + 1)
            
            return externas_map[t_cuenta_norm]

        # Re-procesar historial para asignar etiquetas consistentes si tienen cuenta_id
        historial_objs = []
        for h in historial_compactado_raw:
            try:
                # Si el historial tiene cuenta_id guardado, usamos la lógica unificada
                h_cuenta_id = h.get('cuenta_id')
                if h_cuenta_id:
                    h['empresa_anonym'] = get_empresa_label(h_cuenta_id, None)
                elif 'empresa_anonym' not in h:
                    h['empresa_anonym'] = "Entidad Externa" # Fallback para datos viejos
                
                # Asegurar que no sea None
                if not h.get('empresa_anonym'):
                    h['empresa_anonym'] = "Entidad Externa"

                historial_objs.append(IndicadoresTarjeta(**h))
            except Exception as e:
                logger.warning(f"Error al parsear historial item: {e}")
                continue

        # Ordenar historial por fecha (más reciente primero). Esto hace que "últimos 3" sea real,
        # incluso si el JSON fue construido por appends a lo largo del tiempo.
        def _hist_sort_key(it: IndicadoresTarjeta):
            # None al final
            return (it.fecha_inicio is not None, it.fecha_inicio or date.min)

        historial_objs.sort(key=_hist_sort_key, reverse=True)

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
        # (El mapa externas_map ya se inicializó arriba)

        for t in tarjetas_vivas:
            codigo = t.get('codigo')
            estado = str(t.get('estado', '')).lower()
            # Ahora tenemos cuenta_id en t gracias al cambio en tarjetas_db
            tarjeta_cuenta_id = t.get('cuenta_id')
            
            # Determinar etiqueta usando la misma lógica
            empresa_label = get_empresa_label(tarjeta_cuenta_id, t.get("empleado_identificacion"))
            
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
                max_cuotas_atrasadas=indicadores['max_cuotas_atrasadas'],
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
        # Regla: Si hay alguna tarjeta ACTIVA (viva) con score < 30, el global se cae.
        # Si es histórica, se promedia normalmente (evita castigo por errores de datos viejos).
        
        min_score_activo_critico = 100.0
        hay_critico_activo = False
        
        # Buscar en activas
        for a in activas_analizadas:
            if a.score_individual < 30:
                # Verificar si realmente está activa/pendiente (no cancelada reciente)
                st = str(a.estado_final).lower()
                if st in ('activa', 'activas', 'pendiente', 'pendientes'):
                    hay_critico_activo = True
                    if a.score_individual < min_score_activo_critico:
                        min_score_activo_critico = a.score_individual

        if hay_critico_activo:
            score_final = int(min_score_activo_critico)
        else:
            # Cálculo estándar ponderado
            score_final = RiskEngine.calcular_score_global_cliente(
                actuales=scores_actuales,
                historicos_recientes=scores_historicos_recientes,
                historicos_restantes=scores_historicos_restantes
            )

        # 5. Calcular Resúmenes

        # 5. Calcular Resúmenes
        total_cerrados = len(historial_objs) + len([t for t in tarjetas_vivas if str(t.get('estado', '')).lower() == 'cancelada'])
        total_activos = len(scores_actuales) # Ya contiene activas y pendientes (deuda viva)
        
        # Para el promedio de retraso (Estrés Global), solo consideramos valores positivos (retraso real)
        # Si un crédito va adelantado (dias_retraso < 0), contribuye con 0 al estrés.
        suma_retraso = sum(max(0, h.dias_retraso_final) for h in historial_objs) + \
                       sum(max(0, a.dias_retraso_final) for a in activas_analizadas)
                       
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

@router.post("/mantenimiento/archivar-antiguas")
def archivar_tarjetas_antiguas(meses: int = 12, principal: dict = Depends(require_admin)):
    """
    Mueve tarjetas canceladas hace más de 'meses' al historial JSON del cliente
    y las elimina de la tabla tarjetas para liberar espacio.
    Transaccional por cliente.
    """
    # Reusar el mismo servicio que se usa en el script de cron (sin duplicar lógica)
    from ..services.archiver_service import archivar_tarjetas_canceladas_antiguas

    res = archivar_tarjetas_canceladas_antiguas(meses=meses, dry_run=False, include_detalle=False)
    return {
        "message": f"Proceso completado. {res.tarjetas_procesadas} tarjetas archivadas.",
        "tarjetas_procesadas": res.tarjetas_procesadas,
        "clientes_afectados": res.clientes_afectados,
        "errores": res.errores,
    }

