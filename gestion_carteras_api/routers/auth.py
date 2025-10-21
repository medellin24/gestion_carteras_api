from typing import Optional, Literal
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from zoneinfo import ZoneInfo
from datetime import datetime as _dt

from ..security import (
    verify_password,
    get_password_hash,
    create_token,
)
from ..database.usuarios_db import get_user_by_username


router = APIRouter()


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: Literal["bearer"] = "bearer"
    role: Literal["admin", "cobrador"]
    timezone: Optional[str] = None


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest):
    user = get_user_by_username(body.username)
    if not user or not user.get("is_active"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciales inválidas")
    if not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciales inválidas")

    role = user["role"]
    cuenta_id = user.get("cuenta_id")
    empleado_identificacion = user.get("empleado_identificacion")

    # Enforzar suscripción vigente solo para admin y cobrador que dependan de la cuenta
    if cuenta_id:
        from ..database.connection_pool import DatabasePool
        from datetime import timedelta
        with DatabasePool.get_cursor() as cur:
            cur.execute("SELECT estado_suscripcion, trial_until, fecha_fin, fecha_inicio FROM cuentas_admin WHERE id=%s", (cuenta_id,))
            row = cur.fetchone()
            if row:
                estado, trial_until, fecha_fin, fecha_inicio = row
                fin = fecha_fin or trial_until
                # Normalizar 'fin' a date si viene como datetime
                if fin and hasattr(fin, 'date'):
                    fin = fin.date()
                if not fin and fecha_inicio:
                    fin = fecha_inicio + timedelta(days=30)
                tz = (user.get("timezone") or "UTC")
                today_local = _dt.now(ZoneInfo(tz)).date()
                if fin and today_local > fin:
                    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Suscripción vencida. Contacte al administrador para reactivar.")

    tz = user.get("timezone") or "UTC"
    access_token = create_token(
        subject=str(user["id"]),
        token_type="access",
        role=role,
        cuenta_id=cuenta_id,
        empleado_identificacion=empleado_identificacion,
        timezone_name=tz,
    )
    refresh_token = create_token(
        subject=str(user["id"]),
        token_type="refresh",
        role=role,
        cuenta_id=cuenta_id,
        empleado_identificacion=empleado_identificacion,
        timezone_name=tz,
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        role=role,
        timezone=tz,
    )


class RefreshRequest(BaseModel):
    refresh_token: str


@router.post("/refresh", response_model=TokenResponse)
def refresh_tokens(body: RefreshRequest):
    from ..security import decode_token

    try:
        payload = decode_token(body.refresh_token)
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token inválido")
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token inválido")

    role = payload.get("role")
    cuenta_id = payload.get("cuenta_id")
    empleado_identificacion = payload.get("empleado_identificacion")
    subject = payload.get("sub")

    # Validar estado de la suscripción en cada refresh
    if cuenta_id:
        from ..routers.admin_users import enforce_account_state
        if not enforce_account_state(cuenta_id):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Suscripción vencida. Renueve para continuar.")
        
        # Validación adicional para usuarios cobrador
        if role == "cobrador" and empleado_identificacion:
            from ..database.connection_pool import DatabasePool
            with DatabasePool.get_cursor() as cur:
                cur.execute("""
                    SELECT is_active FROM usuarios 
                    WHERE role='cobrador' AND cuenta_id=%s AND empleado_identificacion=%s
                """, (cuenta_id, empleado_identificacion))
                row = cur.fetchone()
                if not row or not row[0]:  # No existe o está inactivo
                    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario cobrador desactivado. Token expirado.")

    tz = payload.get("timezone") or "UTC"
    access_token = create_token(
        subject=str(subject), token_type="access", role=role, cuenta_id=cuenta_id, empleado_identificacion=empleado_identificacion, timezone_name=tz
    )
    new_refresh_token = create_token(
        subject=str(subject), token_type="refresh", role=role, cuenta_id=cuenta_id, empleado_identificacion=empleado_identificacion, timezone_name=tz
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=new_refresh_token,
        role=role,
        timezone=tz,
    )


