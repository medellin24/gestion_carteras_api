from datetime import date, timedelta
import sys
import psycopg2

from gestion_carteras_api.database.db_config import DB_CONFIG
from gestion_carteras_api.security import get_password_hash


def upsert_trial_account_and_users(
    negocio_nombre: str,
    admin_email: str,
    admin_password: str,
    empleado_identificacion: str,
    cobrador_username: str,
    cobrador_password: str,
):
    conn = psycopg2.connect(**DB_CONFIG)
    conn.autocommit = True
    cur = conn.cursor()
    try:
        # Detectar columnas opcionales (por si la migración 003 no está aplicada)
        cur.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name='cuentas_admin'"
        )
        cols = {r[0] for r in cur.fetchall()}
        trial_until = date.today() + timedelta(days=30)
        if {'max_empleados', 'trial_until'}.issubset(cols):
            cur.execute(
                """
                INSERT INTO cuentas_admin (nombre, estado_suscripcion, plan, fecha_inicio, fecha_fin, max_empleados, trial_until)
                VALUES (%s, 'activa', 'trial_1', %s, %s, 1, %s)
                ON CONFLICT (id) DO NOTHING
                RETURNING id
                """,
                (negocio_nombre, date.today(), trial_until, trial_until),
            )
        else:
            cur.execute(
                """
                INSERT INTO cuentas_admin (nombre, estado_suscripcion, plan, fecha_inicio, fecha_fin)
                VALUES (%s, 'activa', 'trial_1', %s, %s)
                ON CONFLICT (id) DO NOTHING
                RETURNING id
                """,
                (negocio_nombre, date.today(), trial_until),
            )
        row = cur.fetchone()
        if row is None:
            # Buscar cuenta por nombre (simple)
            cur.execute("SELECT id FROM cuentas_admin WHERE nombre=%s ORDER BY id DESC LIMIT 1", (negocio_nombre,))
            cuenta_id = cur.fetchone()[0]
        else:
            cuenta_id = row[0]

        # Asegurar empleado existe y pertenece a la cuenta
        cur.execute("SELECT 1 FROM empleados WHERE identificacion=%s", (empleado_identificacion,))
        if cur.fetchone() is None:
            cur.execute(
                """
                INSERT INTO empleados (identificacion, nombre, telefono, direccion, cuenta_id)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (empleado_identificacion, empleado_identificacion, '', '', cuenta_id),
            )
        else:
            # Asegurar cuenta_id
            cur.execute(
                "UPDATE empleados SET cuenta_id=%s WHERE identificacion=%s AND (cuenta_id IS NULL OR cuenta_id<>%s)",
                (cuenta_id, empleado_identificacion, cuenta_id),
            )

        # Upsert admin
        admin_hash = get_password_hash(admin_password)
        cur.execute("SELECT id, cuenta_id FROM usuarios WHERE username=%s AND role='admin'", (admin_email,))
        u = cur.fetchone()
        if u is None:
            cur.execute(
                """
                INSERT INTO usuarios (username, password_hash, role, cuenta_id, is_active)
                VALUES (%s, %s, 'admin', %s, TRUE)
                RETURNING id
                """,
                (admin_email, admin_hash, cuenta_id),
            )
        else:
            cur.execute("UPDATE usuarios SET password_hash=%s, cuenta_id=%s, is_active=TRUE WHERE username=%s AND role='admin'",
                        (admin_hash, cuenta_id, admin_email))

        # Crear cobrador si no existe (para ese empleado)
        cobrador_hash = get_password_hash(cobrador_password)
        cur.execute(
            "SELECT id FROM usuarios WHERE role='cobrador' AND empleado_identificacion=%s AND cuenta_id=%s",
            (empleado_identificacion, cuenta_id),
        )
        if cur.fetchone() is None:
            cur.execute(
                """
                INSERT INTO usuarios (username, password_hash, role, cuenta_id, empleado_identificacion, is_active)
                VALUES (%s, %s, 'cobrador', %s, %s, TRUE)
                RETURNING id
                """,
                (cobrador_username, cobrador_hash, cuenta_id, empleado_identificacion),
            )
        else:
            cur.execute(
                """
                UPDATE usuarios SET username=%s, password_hash=%s, is_active=TRUE
                WHERE role='cobrador' AND empleado_identificacion=%s AND cuenta_id=%s
                """,
                (cobrador_username, cobrador_hash, empleado_identificacion, cuenta_id),
            )

        print(f"OK cuenta_id={cuenta_id}")
    finally:
        cur.close()
        conn.close()


def main():
    # Args: admin_email, empleado_identificacion
    if len(sys.argv) < 3:
        print("Usage: provision_accounts.py <admin_email> <empleado_identificacion>")
        sys.exit(1)
    admin_email = sys.argv[1]
    empleado_identificacion = sys.argv[2].strip()
    negocio_nombre = f"Cuenta {admin_email.split('@')[0]}"
    admin_password = "AdminTemp123!"
    cobrador_username = empleado_identificacion.lower()
    cobrador_password = "CobradorTemp123!"

    upsert_trial_account_and_users(
        negocio_nombre=negocio_nombre,
        admin_email=admin_email,
        admin_password=admin_password,
        empleado_identificacion=empleado_identificacion,
        cobrador_username=cobrador_username,
        cobrador_password=cobrador_password,
    )
    print("ADMIN_USER:", admin_email, admin_password)
    print("COBRADOR_USER:", cobrador_username, cobrador_password)


if __name__ == "__main__":
    main()


