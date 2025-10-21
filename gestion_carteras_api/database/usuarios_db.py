from typing import Optional, Dict
import logging
from ..database.connection_pool import DatabasePool

logger = logging.getLogger(__name__)


def get_user_by_username(username: str) -> Optional[Dict]:
    try:
        with DatabasePool.get_cursor() as cursor:
            cursor.execute(
                """
                SELECT id, username, password_hash, role, cuenta_id, empleado_identificacion, is_active, timezone
                FROM usuarios
                WHERE username = %s
                """,
                (username,),
            )
            row = cursor.fetchone()
            if not row:
                return None
            return {
                "id": row[0],
                "username": row[1],
                "password_hash": row[2],
                "role": row[3],
                "cuenta_id": row[4],
                "empleado_identificacion": row[5],
                "is_active": row[6],
                "timezone": row[7] if len(row) > 7 else None,
            }
    except Exception as e:
        logger.error(f"Error al obtener usuario: {e}")
        return None


def create_user(
    *,
    username: str,
    password_hash: str,
    role: str,
    cuenta_id: Optional[int],
    empleado_identificacion: Optional[str],
) -> Optional[int]:
    try:
        with DatabasePool.get_cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO usuarios (username, password_hash, role, cuenta_id, empleado_identificacion, is_active)
                VALUES (%s, %s, %s, %s, %s, TRUE)
                RETURNING id
                """,
                (username, password_hash, role, cuenta_id, empleado_identificacion),
            )
            new_id = cursor.fetchone()[0]
            return int(new_id)
    except Exception as e:
        logger.error(f"Error al crear usuario: {e}")
        return None


def count_empleados_in_cuenta(cuenta_id: int) -> int:
    """Cuenta empleados asociados a una cuenta.
    Requiere que la tabla empleados tenga columna cuenta_id.
    """
    try:
        with DatabasePool.get_cursor() as cursor:
            cursor.execute(
                """
                SELECT COUNT(*)
                FROM empleados
                WHERE cuenta_id = %s
                """,
                (cuenta_id,),
            )
            row = cursor.fetchone()
            return int(row[0]) if row and row[0] is not None else 0
    except Exception as e:
        logger.error(f"Error al contar empleados de la cuenta {cuenta_id}: {e}")
        return 0


