import sys
from typing import List, Tuple, Dict, Any

_DRIVER = None  # set to 'psycopg2' or 'pg8000'
try:
    import psycopg2  # type: ignore
    from psycopg2.extras import RealDictCursor  # type: ignore
    _DRIVER = 'psycopg2'
except Exception:
    try:
        import pg8000  # type: ignore
        _DRIVER = 'pg8000'
    except Exception as e:
        print(
            "No PostgreSQL driver available. Install one of: 'psycopg2-binary' or 'pg8000'",
            file=sys.stderr,
        )
        raise

DB_CONFIG: Dict[str, Any] = {
    "host": "sirc-db-1.ct0oyaic6akp.us-east-2.rds.amazonaws.com",
    "port": 5432,
    "dbname": "sirc",
    "user": "base_de_datos_s",
    "password": "FWh9yox70ujMyC7g4THS",
    "sslmode": "require",
    "connect_timeout": 10,
}

TABLES_TO_CHECK: List[str] = [
    "empleados",
]

def _connect():
    if _DRIVER == 'psycopg2':
        return psycopg2.connect(**DB_CONFIG)
    else:
        raise RuntimeError("No DB driver available")

def fetchall(conn, query: str, params: Tuple = ()) -> List[Dict[str, Any]]:
    if _DRIVER == 'psycopg2':
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, params)
            return list(cur.fetchall())
    return []

def main() -> int:
    try:
        conn = _connect()
        
        columns_query = (
            "SELECT column_name, data_type\n"
            "FROM information_schema.columns\n"
            "WHERE table_name = 'empleados'\n"
            "  AND column_name IN ('fecha_accion', 'descargar', 'subir')\n"
            "ORDER BY column_name;"
        )
        columns = fetchall(conn, columns_query)

        print("\n=== Estructura de columnas ===")
        for row in columns:
            print(f"{row['column_name']} | {row['data_type']}")
            
        return 0
    except Exception as e:
        print(e)
        return 1
    finally:
        try:
            conn.close()
        except Exception:
            pass

if __name__ == "__main__":
    raise SystemExit(main())
