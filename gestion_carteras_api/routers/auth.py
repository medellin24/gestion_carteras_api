from typing import Optional, Literal
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from datetime import datetime as _dt, date as _date, timedelta

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
    fin_plan: Optional[_date] = None
    if cuenta_id:
        from ..database.connection_pool import DatabasePool
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
                try:
                    today_local = _dt.now(ZoneInfo(tz)).date()
                except ZoneInfoNotFoundError:
                    today_local = _dt.now(ZoneInfo("UTC")).date()
                if fin and today_local > fin:
                    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Suscripción vencida. Contacte al administrador para reactivar.")
                fin_plan = fin

    # Timezone: preferir la del usuario; si no, usar la default de la cuenta
    tz = user.get("timezone") or "UTC"
    try:
        with DatabasePool.get_cursor() as cur:
            cur.execute("SELECT timezone_default FROM cuentas_admin WHERE id=%s", (cuenta_id,))
            row = cur.fetchone()
            if row and row[0] and not user.get("timezone"):
                tz = row[0]
    except Exception:
        pass
    # Expiración alineada a inicio de día (medianoche local) para evitar cortes a mitad de jornada.
    # - Access: siempre vence a la próxima medianoche local
    # - Refresh: vence a la medianoche siguiente al fin del plan (fin_plan + 1 día a las 00:00 local),
    #           y además no supera REFRESH_TOKEN_EXPIRE_DAYS si no hay fin_plan.
    now_local = None
    try:
        now_local = _dt.now(ZoneInfo(tz))
    except Exception:
        now_local = _dt.utcnow()
    next_midnight_local = (now_local + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    if fin_plan:
        refresh_exp_local = _dt(fin_plan.year, fin_plan.month, fin_plan.day) + timedelta(days=1)
        refresh_exp_local = refresh_exp_local.replace(tzinfo=ZoneInfo(tz)) if hasattr(ZoneInfo(tz), 'key') else refresh_exp_local
    else:
        # Fallback: 30 días completos, venciendo al inicio del día después
        end_date = now_local.date() + timedelta(days=30)
        refresh_exp_local = _dt(end_date.year, end_date.month, end_date.day) + timedelta(days=1)
        try:
            refresh_exp_local = refresh_exp_local.replace(tzinfo=ZoneInfo(tz))
        except Exception:
            pass
    # Access no debe durar más que refresh
    access_exp_local = next_midnight_local
    try:
        if refresh_exp_local and access_exp_local > refresh_exp_local:
            access_exp_local = refresh_exp_local
    except Exception:
        pass

    access_token = create_token(
        subject=str(user["id"]),
        token_type="access",
        role=role,
        cuenta_id=cuenta_id,
        empleado_identificacion=empleado_identificacion,
        timezone_name=tz,
        expires_at=access_exp_local,
    )
    refresh_token = create_token(
        subject=str(user["id"]),
        token_type="refresh",
        role=role,
        cuenta_id=cuenta_id,
        empleado_identificacion=empleado_identificacion,
        timezone_name=tz,
        expires_at=refresh_exp_local,
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
        if not enforce_account_state(cuenta_id, payload.get("timezone")):
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

    # Refrescar timezone desde usuario o default de cuenta si no viene en el token
    tz = payload.get("timezone") or "UTC"
    try:
        with DatabasePool.get_cursor() as cur:
            cur.execute("SELECT timezone FROM usuarios WHERE id=%s", (subject,))
            row_u = cur.fetchone()
            if row_u and row_u[0]:
                tz = row_u[0]
            else:
                cur.execute("SELECT timezone_default FROM cuentas_admin WHERE id=%s", (cuenta_id,))
                row_c = cur.fetchone()
                if row_c and row_c[0]:
                    tz = row_c[0]
    except Exception:
        pass
    # Recalcular expiración alineada a medianoche local y sincronizada con el fin del plan
    fin_plan: Optional[_date] = None
    try:
        from ..database.connection_pool import DatabasePool
        with DatabasePool.get_cursor() as cur:
            cur.execute("SELECT trial_until, fecha_fin, fecha_inicio FROM cuentas_admin WHERE id=%s", (cuenta_id,))
            row = cur.fetchone()
            if row:
                trial_until, fecha_fin, fecha_inicio = row
                fin = fecha_fin or trial_until
                if fin and hasattr(fin, 'date'):
                    fin = fin.date()
                if not fin and fecha_inicio:
                    fin = fecha_inicio + timedelta(days=30)
                fin_plan = fin
    except Exception:
        fin_plan = None

    try:
        now_local = _dt.now(ZoneInfo(tz))
    except Exception:
        now_local = _dt.utcnow()
    next_midnight_local = (now_local + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    if fin_plan:
        refresh_exp_local = _dt(fin_plan.year, fin_plan.month, fin_plan.day) + timedelta(days=1)
        try:
            refresh_exp_local = refresh_exp_local.replace(tzinfo=ZoneInfo(tz))
        except Exception:
            pass
    else:
        end_date = now_local.date() + timedelta(days=30)
        refresh_exp_local = _dt(end_date.year, end_date.month, end_date.day) + timedelta(days=1)
        try:
            refresh_exp_local = refresh_exp_local.replace(tzinfo=ZoneInfo(tz))
        except Exception:
            pass
    access_exp_local = next_midnight_local
    try:
        if refresh_exp_local and access_exp_local > refresh_exp_local:
            access_exp_local = refresh_exp_local
    except Exception:
        pass

    access_token = create_token(
        subject=str(subject), token_type="access", role=role, cuenta_id=cuenta_id, empleado_identificacion=empleado_identificacion, timezone_name=tz, expires_at=access_exp_local
    )
    # Mantener refresh rotativo pero con la misma fecha de corte (no extender más allá del plan)
    new_refresh_token = create_token(
        subject=str(subject), token_type="refresh", role=role, cuenta_id=cuenta_id, empleado_identificacion=empleado_identificacion, timezone_name=tz, expires_at=refresh_exp_local
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=new_refresh_token,
        role=role,
        timezone=tz,
    )


