import pathlib
import sys
import psycopg2

from gestion_carteras_api.database.db_config import DB_CONFIG
from gestion_carteras_api.security import get_password_hash


def run_sql_file(cursor, path: pathlib.Path) -> None:
    sql = path.read_text(encoding="utf-8")
    cursor.execute(sql)


def main() -> None:
    base = pathlib.Path(__file__).resolve().parents[1] / "database" / "migrations"
    file_001 = base / "001_auth_and_billing.sql"
    file_002 = base / "002_seed_admin.sql"

    conn = psycopg2.connect(**DB_CONFIG)
    conn.autocommit = True
    cur = conn.cursor()
    try:
        print(f"Ejecutando: {file_001}")
        run_sql_file(cur, file_001)
        print(f"Ejecutando: {file_002}")
        run_sql_file(cur, file_002)

        # Asegurar hash de admin
        admin_password = "admin123"
        admin_hash = get_password_hash(admin_password)
        cur.execute(
            """
            UPDATE usuarios
            SET password_hash = %s
            WHERE username = 'admin'
            """,
            (admin_hash,),
        )
        print("Usuario admin actualizado con nueva contraseña por defecto: admin123")

        # Asignar cuenta a empleados sin cuenta
        cur.execute(
            """
            UPDATE empleados
            SET cuenta_id = (
                SELECT id FROM cuentas_admin ORDER BY id ASC LIMIT 1
            )
            WHERE cuenta_id IS NULL
            """
        )
        print("Empleados sin cuenta asignados a la cuenta administrativa por defecto")

        print("Migraciones y configuración inicial completadas correctamente.")
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()


