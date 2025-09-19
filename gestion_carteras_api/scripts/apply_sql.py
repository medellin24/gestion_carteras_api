import sys
import pathlib
import psycopg2

from gestion_carteras_api.database.db_config import DB_CONFIG


def main():
    if len(sys.argv) < 2:
        print("Usage: apply_sql.py <path_to_sql_file>")
        sys.exit(1)
    sql_path = pathlib.Path(sys.argv[1])
    if not sql_path.exists():
        print(f"SQL file not found: {sql_path}")
        sys.exit(2)
    sql = sql_path.read_text(encoding="utf-8")

    conn = psycopg2.connect(**DB_CONFIG)
    conn.autocommit = True
    cur = conn.cursor()
    try:
        # Ejecutar múltiples sentencias separadas por ';'
        statements = [s.strip() for s in sql.split(';') if s.strip()]
        for idx, stmt in enumerate(statements, start=1):
            try:
                cur.execute(stmt)
                if cur.description:  # Es un SELECT
                    rows = cur.fetchall()
                    print(f"-- RESULT {idx}: {len(rows)} rows")
                    for row in rows:
                        print(row)
                else:
                    print(f"-- OK {idx}: command executed")
            except Exception as e:
                print(f"-- ERROR {idx}: {e}")
                raise
        print(f"APPLIED: {sql_path}")
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()


