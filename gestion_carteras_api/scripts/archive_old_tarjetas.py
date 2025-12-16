import argparse
import sys
import logging

from gestion_carteras_api.database.connection_pool import DatabasePool
from gestion_carteras_api.database.db_config import DB_CONFIG
from gestion_carteras_api.services.archiver_service import archivar_tarjetas_canceladas_antiguas


def main() -> int:
    parser = argparse.ArgumentParser(description="Archiva tarjetas canceladas antiguas y elimina tarjetas+abonos.")
    parser.add_argument("--meses", type=int, default=12, help="Antigüedad mínima en meses (default: 12).")
    parser.add_argument("--dry-run", action="store_true", help="Solo reporta cuántas se archivarían, no modifica BD.")
    parser.add_argument("--detalle", action="store_true", help="Incluye detalle por cliente.")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    # Inicializar pool
    DatabasePool.initialize(**DB_CONFIG)

    res = archivar_tarjetas_canceladas_antiguas(
        meses=args.meses,
        dry_run=args.dry_run,
        include_detalle=args.detalle,
    )

    print(f"tarjetas_procesadas={res.tarjetas_procesadas} clientes_afectados={res.clientes_afectados} errores={res.errores}")
    if args.detalle and res.detalle is not None:
        for d in res.detalle:
            print(f"cliente={d['cliente_identificacion']} tarjetas={len(d['tarjetas'])}")

    # exit code no-cero si hubo errores
    return 0 if res.errores == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())


