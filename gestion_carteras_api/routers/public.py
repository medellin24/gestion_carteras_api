from datetime import date, timedelta, datetime
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr

from ..database.connection_pool import DatabasePool
from ..security import get_password_hash

router = APIRouter()

try:
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
except ImportError:
    from backports.zoneinfo import ZoneInfo, ZoneInfoNotFoundError

def _hoy_local(tz_name: Optional[str]) -> date:
    tz_eff = (tz_name or 'America/Bogota').strip() if tz_name else 'America/Bogota'
    try:
        return datetime.now(ZoneInfo(tz_eff)).date()
    except (ZoneInfoNotFoundError, Exception):
        return datetime.now(ZoneInfo('UTC')).date()


class SignupRequest(BaseModel):
    nombre_negocio: str
    email: EmailStr
    contacto: Optional[str] = None
    plan_max_empleados: Optional[int] = None  # si None => trial 1 empleado
    password_admin: str
    timezone: Optional[str] = None  # IANA, ej: 'America/Bogota'


class SignupResponse(BaseModel):
    cuenta_id: int
    trial: bool
    max_empleados: int


@router.post("/signup", response_model=SignupResponse)
def signup(body: SignupRequest):
    max_emp = body.plan_max_empleados if body.plan_max_empleados and body.plan_max_empleados > 0 else 1
    trial = body.plan_max_empleados is None
    # Importante: usar el día LOCAL del usuario/cuenta para no “perder 1 día” por UTC/servidor.
    hoy = _hoy_local(body.timezone or 'America/Bogota')
    trial_until = hoy + timedelta(days=30) if trial else None

    with DatabasePool.get_cursor() as cur:
        # Validar que el email (username) no exista ya
        cur.execute("SELECT 1 FROM usuarios WHERE username=%s", (body.email,))
        if cur.fetchone():
            raise HTTPException(status_code=409, detail="Email ya registrado. Inicia sesión o usa otro email.")

        # crear cuenta (guardar timezone_default si se envía)
        cur.execute(
            """
            ALTER TABLE cuentas_admin ADD COLUMN IF NOT EXISTS timezone_default TEXT
            """
        )
        cur.execute(
            """
            INSERT INTO cuentas_admin (nombre, estado_suscripcion, plan, fecha_inicio, fecha_fin, max_empleados, trial_until, timezone_default)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                body.nombre_negocio,
                'activa' if trial else 'pendiente_pago',
                f"plan_{max_emp}",
                hoy,  # fecha_inicio siempre
                (hoy + timedelta(days=30)) if not trial else trial_until,  # fecha_fin para planes pagos (placeholder 30 días) o None en trial
                max_emp,
                trial_until,
                (body.timezone or 'America/Bogota'),
            ),
        )
        cuenta_id = cur.fetchone()[0]

        # crear admin (guardar timezone si se envía, default UTC)
        pwd_hash = get_password_hash(body.password_admin)
        cur.execute(
            """
            INSERT INTO usuarios (username, password_hash, role, cuenta_id, is_active, timezone)
            VALUES (%s, %s, 'admin', %s, TRUE, %s)
            RETURNING id
            """,
            (body.email, pwd_hash, cuenta_id, (body.timezone or 'America/Bogota')),
        )

    return SignupResponse(cuenta_id=cuenta_id, trial=trial, max_empleados=max_emp)


