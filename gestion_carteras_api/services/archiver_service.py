from __future__ import annotations

import json
import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Dict, List, Optional, Any, Tuple

from ..database.connection_pool import DatabasePool
from ..database.abonos_db import obtener_abonos_por_tarjeta
from ..database.tarjetas_db import obtener_tarjetas_canceladas_antiguas
from ..services.risk_engine import RiskEngine

logger = logging.getLogger(__name__)


@dataclass
class ArchiveResult:
    tarjetas_procesadas: int
    clientes_afectados: int
    errores: int
    detalle: Optional[List[Dict[str, Any]]] = None


def archivar_tarjetas_canceladas_antiguas(
    *,
    meses: int = 12,
    dry_run: bool = False,
    include_detalle: bool = False,
) -> ArchiveResult:
    """
    Archiva tarjetas canceladas con antigüedad >= meses:
    - Calcula indicadores finales
    - Appendea resumen a clientes.historial_crediticio (jsonb)
    - Elimina abonos y tarjetas (solo si el update del cliente fue exitoso)

    Nota:
    - Se hace transaccional POR CLIENTE (no global).
    - Este método está pensado para ser invocado por cron externo (sin HTTP ni tokens).
    """
    candidatas = obtener_tarjetas_canceladas_antiguas(meses)
    if not candidatas:
        return ArchiveResult(tarjetas_procesadas=0, clientes_afectados=0, errores=0, detalle=[] if include_detalle else None)

    # Agrupar por cliente
    por_cliente: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for t in candidatas:
        por_cliente[t["cliente_identificacion"]].append(t)

    tarjetas_procesadas = 0
    clientes_afectados = 0
    errores = 0
    detalle: List[Dict[str, Any]] = []

    for cliente_id, tarjetas in por_cliente.items():
        try:
            # Transacción por cliente: update JSON + deletes
            with DatabasePool.get_cursor() as cursor:
                cursor.execute(
                    """
                    SELECT COALESCE(historial_crediticio, '[]'::jsonb) as historial, COALESCE(score_global, 100) as score
                    FROM clientes
                    WHERE identificacion = %s
                    FOR UPDATE
                    """,
                    (cliente_id,),
                )
                row = cursor.fetchone()
                if not row:
                    continue

                historial_actual = row[0] or []
                # En psycopg2, jsonb puede venir como dict/list ya parseado; si viene string, intentar parsear.
                if isinstance(historial_actual, str):
                    try:
                        historial_actual = json.loads(historial_actual)
                    except Exception:
                        historial_actual = []

                nuevos_items: List[Dict[str, Any]] = []
                codigos_a_borrar: List[str] = []

                for t in tarjetas:
                    codigo = t["codigo"]
                    abonos = obtener_abonos_por_tarjeta(codigo)
                    indicadores = RiskEngine.calcular_indicadores_tarjeta_activa(t, abonos)

                    # Guardamos cuenta_id en el historial para re-etiquetar dinámicamente luego.
                    item = {
                        "id_referencia": codigo,
                        "fecha_inicio": str(t.get("fecha_creacion"))[:10],
                        "monto": float(t.get("monto", 0)),
                        "dias_retraso_final": int(indicadores["dias_retraso_final"]),
                        "frecuencia_pagos": float(indicadores["frecuencia_pagos"]),
                        "max_cuotas_atrasadas": float(indicadores["max_cuotas_atrasadas"]),
                        "puntaje_atraso_cierre": float(indicadores["puntaje_atraso_cierre"]),
                        "score_individual": float(indicadores["score_individual"]),
                        "estado_final": "archivada",
                        "cuenta_id": t.get("cuenta_id"),
                        # Empresa se recalcula en el reporte; dejamos algo no-nulo para no romper UI
                        "empresa_anonym": "Entidad Externa",
                    }
                    nuevos_items.append(item)
                    codigos_a_borrar.append(codigo)

                if include_detalle:
                    detalle.append({"cliente_identificacion": cliente_id, "tarjetas": codigos_a_borrar})

                if dry_run:
                    # No tocar BD (ni update ni deletes)
                    continue

                historial_final = list(historial_actual) + nuevos_items
                historial_json = json.dumps(historial_final)

                # 1) Update del cliente
                cursor.execute(
                    """
                    UPDATE clientes
                    SET historial_crediticio = %s::jsonb
                    WHERE identificacion = %s
                    """,
                    (historial_json, cliente_id),
                )

                # 2) Deletes (abonos, tarjetas)
                # Borramos primero abonos para evitar FK si existe.
                cursor.execute("DELETE FROM abonos WHERE tarjeta_codigo = ANY(%s)", (codigos_a_borrar,))
                cursor.execute("DELETE FROM tarjetas WHERE codigo = ANY(%s)", (codigos_a_borrar,))

                tarjetas_procesadas += len(codigos_a_borrar)
                clientes_afectados += 1

        except Exception as e:
            errores += 1
            logger.error(f"Error archivando cliente {cliente_id}: {e}", exc_info=True)

    return ArchiveResult(
        tarjetas_procesadas=tarjetas_procesadas,
        clientes_afectados=clientes_afectados,
        errores=errores,
        detalle=detalle if include_detalle else None,
    )


