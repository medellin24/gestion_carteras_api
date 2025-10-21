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
    # ssl params will vary by driver; psycopg2 uses sslmode, pg8000 uses ssl_context
    "sslmode": "require",
    "connect_timeout": 10,
}


TABLES_TO_CHECK: List[str] = [
    "usuarios",
    "cuentas_admin",
]


def _connect():
    if _DRIVER == 'psycopg2':
        return psycopg2.connect(**DB_CONFIG)
    elif _DRIVER == 'pg8000':
        # Map keys for pg8000
        return pg8000.connect(
            host=DB_CONFIG["host"],
            port=DB_CONFIG["port"],
            database=DB_CONFIG["dbname"],
            user=DB_CONFIG["user"],
            password=DB_CONFIG["password"],
            ssl_context=True,
            timeout=DB_CONFIG.get("connect_timeout", 10),
        )
    else:
        raise RuntimeError("No DB driver available")


def fetchall(conn, query: str, params: Tuple = ()) -> List[Dict[str, Any]]:
    if _DRIVER == 'psycopg2':
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, params)
            return list(cur.fetchall())
    else:
        # pg8000 returns tuples; convert to dicts
        with conn.cursor() as cur:
            cur.execute(query, params)
            colnames = [c[0] for c in cur.description]
            results: List[Dict[str, Any]] = []
            for row in cur.fetchall():
                results.append({colnames[i]: row[i] for i in range(len(colnames))})
            return results


def main() -> int:
    print(f"Connecting to PostgreSQL RDS using {_DRIVER}...", file=sys.stderr)
    try:
        conn = _connect()
    except Exception as conn_err:
        print(f"Connection failed: {conn_err}", file=sys.stderr)
        return 2

    try:
        # 1) Find schemas and tables
        tables_query = (
            "SELECT table_schema, table_name\n"
            "FROM information_schema.tables\n"
            "WHERE table_type = 'BASE TABLE'\n"
            "  AND table_name = ANY(%s)\n"
            "ORDER BY table_schema, table_name;"
        )
        tables = fetchall(conn, tables_query, (TABLES_TO_CHECK,))

        if not tables:
            print("No se encontraron tablas con esos nombres.")
            return 0

        print("\n=== Tablas encontradas (esquema.tabla) ===")
        for row in tables:
            print(f"- {row['table_schema']}.{row['table_name']}")

        # 2) Columns / structure
        columns_query = (
            "SELECT table_schema, table_name, ordinal_position, column_name, data_type, is_nullable, column_default\n"
            "FROM information_schema.columns\n"
            "WHERE table_name = ANY(%s)\n"
            "ORDER BY table_schema, table_name, ordinal_position;"
        )
        columns = fetchall(conn, columns_query, (TABLES_TO_CHECK,))

        print("\n=== Estructura de columnas ===")
        current = (None, None)
        for row in columns:
            key = (row["table_schema"], row["table_name"]) 
            if key != current:
                current = key
                print(f"\n{row['table_schema']}.{row['table_name']}")
                print("ordinal | column_name | data_type | is_nullable | default")
            print(
                f"{row['ordinal_position']:>6} | {row['column_name']} | {row['data_type']} | {row['is_nullable']} | {row['column_default']}"
            )

        # 3) Primary keys
        pk_query = (
            "SELECT tc.table_schema, tc.table_name, kcu.column_name, kcu.ordinal_position\n"
            "FROM information_schema.table_constraints tc\n"
            "JOIN information_schema.key_column_usage kcu\n"
            "  ON tc.constraint_name = kcu.constraint_name\n"
            " AND tc.table_schema   = kcu.table_schema\n"
            "WHERE tc.table_name = ANY(%s)\n"
            "  AND tc.constraint_type = 'PRIMARY KEY'\n"
            "ORDER BY tc.table_schema, tc.table_name, kcu.ordinal_position;"
        )
        pks = fetchall(conn, pk_query, (TABLES_TO_CHECK,))

        print("\n=== Claves primarias ===")
        if not pks:
            print("(No se encontraron PKs)")
        else:
            current = (None, None)
            cols: List[str] = []
            for row in pks:
                key = (row["table_schema"], row["table_name"]) 
                if key != current:
                    if current != (None, None):
                        print(f"- {current[0]}.{current[1]}: {', '.join(cols)}")
                    current = key
                    cols = [row["column_name"]]
                else:
                    cols.append(row["column_name"])
            if current != (None, None):
                print(f"- {current[0]}.{current[1]}: {', '.join(cols)}")

        # 4) Owner
        owner_query = (
            "SELECT n.nspname AS schema_name, c.relname AS table_name, pg_get_userbyid(c.relowner) AS owner\n"
            "FROM pg_class c\n"
            "JOIN pg_namespace n ON n.oid = c.relnamespace\n"
            "WHERE c.relname = ANY(%s)\n"
            "  AND c.relkind IN ('r','p')\n"
            "ORDER BY n.nspname, c.relname;"
        )
        owners = fetchall(conn, owner_query, (TABLES_TO_CHECK,))
        print("\n=== Dueños de tablas ===")
        for row in owners:
            print(f"- {row['schema_name']}.{row['table_name']}: {row['owner']}")

        # 5) Sample rows
        print("\n=== Primeras 50 filas de cada tabla ===")
        with conn.cursor() as cur:
            for row in tables:
                schema = row["table_schema"]
                name = row["table_name"]
                print(f"\n--- {schema}.{name} ---")
                sql = f"SELECT * FROM \"{schema}\".\"{name}\" LIMIT 50;"
                try:
                    cur.execute(sql)
                except Exception as qerr:
                    print(f"Error al leer {schema}.{name}: {qerr}")
                    continue
                rows = cur.fetchall()
                if not rows:
                    print("(sin filas)")
                    continue
                # Print header
                colnames = [desc[0] for desc in cur.description]
                print(" | ".join(colnames))
                for r in rows:
                    print(" | ".join(str(v) for v in r))

        return 0

    finally:
        try:
            conn.close()
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main())


