from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr

from ..database.connection_pool import DatabasePool
from ..security import get_password_hash

router = APIRouter()


class SignupRequest(BaseModel):
    nombre_negocio: str
    email: EmailStr
    contacto: Optional[str] = None
    plan_max_empleados: Optional[int] = None  # si None => trial 1 empleado
    password_admin: str


class SignupResponse(BaseModel):
    cuenta_id: int
    trial: bool
    max_empleados: int


@router.post("/signup", response_model=SignupResponse)
def signup(body: SignupRequest):
    max_emp = body.plan_max_empleados if body.plan_max_empleados and body.plan_max_empleados > 0 else 1
    trial = body.plan_max_empleados is None
    hoy = date.today()
    trial_until = hoy + timedelta(days=30) if trial else None

    with DatabasePool.get_cursor() as cur:
        # Validar que el email (username) no exista ya
        cur.execute("SELECT 1 FROM usuarios WHERE username=%s", (body.email,))
        if cur.fetchone():
            raise HTTPException(status_code=409, detail="Email ya registrado. Inicia sesión o usa otro email.")

        # crear cuenta
        cur.execute(
            """
            INSERT INTO cuentas_admin (nombre, estado_suscripcion, plan, fecha_inicio, fecha_fin, max_empleados, trial_until)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
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
            ),
        )
        cuenta_id = cur.fetchone()[0]

        # crear admin
        pwd_hash = get_password_hash(body.password_admin)
        cur.execute(
            """
            INSERT INTO usuarios (username, password_hash, role, cuenta_id, is_active)
            VALUES (%s, %s, 'admin', %s, TRUE)
            RETURNING id
            """,
            (body.email, pwd_hash, cuenta_id),
        )

    return SignupResponse(cuenta_id=cuenta_id, trial=trial, max_empleados=max_emp)


