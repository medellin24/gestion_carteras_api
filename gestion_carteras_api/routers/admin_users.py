from typing import Optional
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from ..security import require_admin, get_password_hash, get_current_principal
from ..schemas import AttemptDownloadRequest, AttemptDownloadResponse
from ..database.connection_pool import DatabasePool

router = APIRouter()


def enforce_account_state(cuenta_id: str) -> bool:
    """
    Valida el estado de la cuenta y desactiva todos los cobradores si está vencida.
    Retorna True si la cuenta está activa, False si está vencida.
    """
    with DatabasePool.get_cursor() as cur:
        # Obtener información de la cuenta
        cur.execute("""
            SELECT max_empleados, fecha_fin, trial_until 
            FROM cuentas_admin WHERE id=%s
        """, (cuenta_id,))
        row = cur.fetchone()
        
        if not row:
            return False
            
        max_emp, fecha_fin, trial_until = row
        hoy = date.today()
        
        # Normalizar fechas a date si vienen como datetime
        if fecha_fin and hasattr(fecha_fin, 'date'):
            fecha_fin = fecha_fin.date()
        if trial_until and hasattr(trial_until, 'date'):
            trial_until = trial_until.date()
        
        # Verificar si está vencida
        vencida = False
        if fecha_fin and hoy > fecha_fin:
            vencida = True
        elif trial_until and hoy > trial_until and not fecha_fin:
            vencida = True
        
        # Si está vencida, desactivar todos los cobradores
        if vencida:
            cur.execute("""
                UPDATE usuarios 
                SET is_active = FALSE 
                WHERE role='cobrador' AND cuenta_id=%s AND is_active=TRUE
            """, (cuenta_id,))
        
        return not vencida


class CreateCobradorRequest(BaseModel):
    username: str
    password: str
    empleado_identificacion: str


class LimitsResponse(BaseModel):
    max_empleados: int
    usados: int
    disponibles: int
    days_remaining: int
    cobradores_activos: int
    cobradores_inactivos: int
    trial: bool


class RenewRequest(BaseModel):
    max_empleados: int
    dias: int
    es_renovacion: bool = True  # True para renovación, False para cambio de plan
    max_daily_routes: Optional[int] = None  # Si no viene, se iguala a max_empleados


@router.get("/limits", response_model=LimitsResponse)
def get_limits(principal: dict = Depends(require_admin)):
    cuenta_id = principal.get("cuenta_id")
    
    # Validar estado de la cuenta (desactiva cobradores si está vencida)
    enforce_account_state(cuenta_id)
    
    with DatabasePool.get_cursor() as cur:
        cur.execute("SELECT COALESCE(max_empleados,1), trial_until, fecha_fin, fecha_inicio FROM cuentas_admin WHERE id=%s", (cuenta_id,))
        row = cur.fetchone()
        max_emp = (row[0] or 1) if row else 1
        trial_until = row[1] if row else None
        fecha_fin = row[2] if row else None
        fecha_inicio = row[3] if row else None
        cur.execute("SELECT COUNT(*) FROM usuarios WHERE role='cobrador' AND cuenta_id=%s AND is_active=TRUE", (cuenta_id,))
        usados = cur.fetchone()[0] or 0
        cur.execute("SELECT COUNT(*) FROM usuarios WHERE role='cobrador' AND cuenta_id=%s AND is_active=FALSE", (cuenta_id,))
        inactivos = cur.fetchone()[0] or 0
    disp = max(0, max_emp - usados)
    # Calcular days_remaining de forma robusta
    from datetime import date as _date, datetime as _datetime, timedelta

    def _to_date(val):
        if val is None:
            return None
        if isinstance(val, _date) and not isinstance(val, _datetime):
            return val
        if isinstance(val, _datetime):
            return val.date()
        # Intentar parseo simple si viene como string ISO (opcional)
        try:
            return _datetime.fromisoformat(str(val)).date()
        except Exception:
            return None

    hoy = _date.today()
    trial_until_d = _to_date(trial_until)
    fecha_fin_d = _to_date(fecha_fin)
    fecha_inicio_d = _to_date(fecha_inicio)

    # Determinar si está en periodo de prueba
    es_trial = bool(trial_until_d) and hoy <= trial_until_d

    # Fecha de finalización efectiva: prioriza fecha_fin; si no, trial_until; si no, fallback de 30 días desde inicio
    fin = fecha_fin_d or trial_until_d
    if not fin and fecha_inicio_d:
        fin = fecha_inicio_d + timedelta(days=30)

    days_remaining = max((fin - hoy).days, 0) if fin else 0

    return LimitsResponse(
        max_empleados=max_emp,
        usados=usados,
        disponibles=disp,
        days_remaining=days_remaining,
        cobradores_activos=usados,
        cobradores_inactivos=inactivos,
        trial=es_trial,
    )


@router.post("/users/cobradores")
def create_cobrador(body: CreateCobradorRequest, principal: dict = Depends(require_admin)):
    cuenta_id = principal.get("cuenta_id")
    
    # Validar estado de la cuenta
    if not enforce_account_state(cuenta_id):
        raise HTTPException(status_code=403, detail="Suscripción vencida. Renueve para continuar.")
    
    with DatabasePool.get_cursor() as cur:
        # validar límite
        cur.execute("SELECT COALESCE(max_empleados,1) FROM cuentas_admin WHERE id=%s", (cuenta_id,))
        max_emp = cur.fetchone()[0] or 1
        cur.execute("SELECT COUNT(*) FROM usuarios WHERE role='cobrador' AND cuenta_id=%s AND is_active=TRUE", (cuenta_id,))
        usados = cur.fetchone()[0] or 0
        if usados >= max_emp:
            raise HTTPException(status_code=403, detail="Límite de cobradores alcanzado para tu plan")

        # validar que el empleado pertenezca a la cuenta; si no tiene cuenta_id, asignarla
        cur.execute("SELECT cuenta_id FROM empleados WHERE identificacion=%s", (body.empleado_identificacion,))
        row = cur.fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Empleado no encontrado")
        emp_cuenta = row[0]
        if emp_cuenta is None:
            cur.execute("UPDATE empleados SET cuenta_id=%s WHERE identificacion=%s", (cuenta_id, body.empleado_identificacion))
        elif emp_cuenta != cuenta_id:
            raise HTTPException(status_code=403, detail="El empleado pertenece a otra cuenta")

        # validar que no exista cobrador activo para ese empleado
        cur.execute(
            """
            SELECT 1 FROM usuarios
             WHERE role='cobrador' AND cuenta_id=%s AND empleado_identificacion=%s AND is_active=TRUE
            """,
            (cuenta_id, body.empleado_identificacion),
        )
        if cur.fetchone():
            raise HTTPException(status_code=409, detail="Ya existe un cobrador activo para este empleado")

        # crear usuario
        pwd_hash = get_password_hash(body.password)
        cur.execute(
            """
            INSERT INTO usuarios (username, password_hash, role, cuenta_id, empleado_identificacion, is_active)
            VALUES (%s, %s, 'cobrador', %s, %s, TRUE)
            RETURNING id
            """,
            (body.username, pwd_hash, cuenta_id, body.empleado_identificacion),
        )
        new_id = cur.fetchone()[0]
        
        # Guardar contraseña en texto plano para memorización
        _ensure_tabla_passwords(cur)
        cur.execute(
            """
            INSERT INTO cobrador_passwords (usuario_id, password_plain)
            VALUES (%s, %s)
            ON CONFLICT (usuario_id) DO UPDATE SET password_plain = EXCLUDED.password_plain
            """,
            (new_id, body.password),
        )
    return {"id": new_id, "username": body.username}


# --- Gestión de credenciales y permisos de cobradores ---

class UpsertCobradorRequest(BaseModel):
    username: str
    password: str


class CobradorCredsResponse(BaseModel):
    exists: bool
    username: Optional[str]
    password: Optional[str] = None
    is_active: Optional[bool] = None


# NUEVA LÓGICA SIMPLE - Sistema de permisos basado en empleados.descargar/subir/fecha_accion

class PermisosEmpleado(BaseModel):
    """Modelo para respuesta de permisos del empleado"""
    descargar: bool
    subir: bool
    fecha_accion: Optional[str] = None
    puede_descargar: bool  # Calculado: descargar=True AND fecha_accion < hoy
    puede_subir: bool      # Calculado: subir=True AND fecha_accion < hoy

class RehabilitarPermisosRequest(BaseModel):
    """Modelo para re-habilitar permisos desde escritorio"""
    descargar: bool = False
    subir: bool = False

class UsarPermisosRequest(BaseModel):
    """Modelo para usar permisos desde app móvil"""
    descargar: bool = False
    subir: bool = False

def _ensure_tabla_passwords(cur):
    # Crear tabla para guardar contraseñas en texto plano de cobradores
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS cobrador_passwords (
            usuario_id INTEGER PRIMARY KEY,
            password_plain TEXT NOT NULL,
            FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE
        )
        """
    )


@router.get("/users/cobradores/{empleado_id}/credentials", response_model=CobradorCredsResponse)
def get_cobrador_credentials(empleado_id: str, principal: dict = Depends(require_admin)):
    cuenta_id = principal.get("cuenta_id")
    with DatabasePool.get_cursor() as cur:
        # Asegurar que la tabla existe
        _ensure_tabla_passwords(cur)
        
        try:
            # Buscar si hay una contraseña guardada en texto plano
            cur.execute("""
                SELECT u.username, u.is_active, c.password_plain 
                FROM usuarios u
                LEFT JOIN cobrador_passwords c ON u.id = c.usuario_id
                WHERE u.role='cobrador' AND u.cuenta_id=%s AND u.empleado_identificacion=%s
            """, (cuenta_id, empleado_id))
            row = cur.fetchone()
            if not row:
                return CobradorCredsResponse(exists=False, username=None, password=None, is_active=None)
            
            username, is_active, password_plain = row
            
            # Si no hay contraseña guardada, indicar que necesita actualizar
            if password_plain is None:
                password_plain = "[Actualizar credenciales]"
            
            return CobradorCredsResponse(exists=True, username=username, password=password_plain, is_active=is_active)
        except Exception as e:
            # Si hay error con la tabla de passwords, usar consulta simple
            print(f"Error con tabla passwords: {e}")
            cur.execute("""
                SELECT username, is_active FROM usuarios 
                WHERE role='cobrador' AND cuenta_id=%s AND empleado_identificacion=%s
            """, (cuenta_id, empleado_id))
            row = cur.fetchone()
            if not row:
                return CobradorCredsResponse(exists=False, username=None, password=None, is_active=None)
            
            username, is_active = row
            return CobradorCredsResponse(exists=True, username=username, password=None, is_active=is_active)


@router.post("/users/cobradores/{empleado_id}/upsert")
def upsert_cobrador(empleado_id: str, body: UpsertCobradorRequest, principal: dict = Depends(require_admin)):
    if not body.username or not body.password or len(body.password) < 4:
        raise HTTPException(status_code=400, detail="Usuario y contraseña (>=4) son requeridos")
    cuenta_id = principal.get("cuenta_id")
    with DatabasePool.get_cursor() as cur:
        # ¿Existe activo?
        cur.execute(
            """
            SELECT id FROM usuarios
             WHERE role='cobrador' AND cuenta_id=%s AND empleado_identificacion=%s AND is_active=TRUE
            """,
            (cuenta_id, empleado_id),
        )
        row = cur.fetchone()
        pwd_hash = get_password_hash(body.password)
        if row:
            # Actualizar username y password
            cur.execute(
                "UPDATE usuarios SET username=%s, password_hash=%s WHERE id=%s",
                (body.username, pwd_hash, row[0]),
            )
            # Actualizar contraseña en texto plano
            _ensure_tabla_passwords(cur)
            cur.execute(
                """
                INSERT INTO cobrador_passwords (usuario_id, password_plain)
                VALUES (%s, %s)
                ON CONFLICT (usuario_id) DO UPDATE SET password_plain = EXCLUDED.password_plain
                """,
                (row[0], body.password),
            )
            return {"ok": True, "updated": True}
        else:
            # Crear nuevo cobrador activo
            cur.execute(
                """
                INSERT INTO usuarios (username, password_hash, role, cuenta_id, empleado_identificacion, is_active)
                VALUES (%s, %s, 'cobrador', %s, %s, TRUE)
                RETURNING id
                """,
                (body.username, pwd_hash, cuenta_id, empleado_id),
            )
            new_id = cur.fetchone()[0]
            # Guardar contraseña en texto plano
            _ensure_tabla_passwords(cur)
            cur.execute(
                """
                INSERT INTO cobrador_passwords (usuario_id, password_plain)
                VALUES (%s, %s)
                ON CONFLICT (usuario_id) DO UPDATE SET password_plain = EXCLUDED.password_plain
                """,
                (new_id, body.password),
            )
            return {"ok": True, "created": True}


# NUEVOS ENDPOINTS CON LÓGICA SIMPLE

@router.get("/users/cobradores/{empleado_id}/permissions", response_model=PermisosEmpleado)
def get_permisos_empleado(empleado_id: str, principal: dict = Depends(require_admin)):
    """
    Obtiene los permisos del empleado basado en empleados.descargar/subir/fecha_accion
    Lógica simple: puede descargar si descargar=TRUE Y fecha_accion < hoy
    """
    cuenta_id = principal.get("cuenta_id")
    hoy = date.today()
    
    with DatabasePool.get_cursor() as cur:
        # Obtener permisos del empleado
        cur.execute("""
            SELECT descargar, subir, fecha_accion 
            FROM empleados 
            WHERE identificacion=%s AND cuenta_id=%s
        """, (empleado_id, cuenta_id))
        
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Empleado no encontrado")
        
        descargar, subir, fecha_accion = row
        
        # Si es la primera vez (fecha_accion es NULL), inicializar con valores por defecto
        if fecha_accion is None:
            ayer = date.today() - timedelta(days=1)
            cur.execute("""
                UPDATE empleados 
                SET descargar=TRUE, subir=TRUE, fecha_accion=%s 
                WHERE identificacion=%s AND cuenta_id=%s
            """, (ayer, empleado_id, cuenta_id))
            descargar, subir, fecha_accion = True, True, ayer
        
        # Calcular si puede usar los permisos (fecha_accion < hoy)
        puede_descargar = bool(descargar) and fecha_accion < hoy
        puede_subir = bool(subir) and fecha_accion < hoy
        
        return PermisosEmpleado(
            descargar=bool(descargar),
            subir=bool(subir),
            fecha_accion=fecha_accion.isoformat() if fecha_accion else None,
            puede_descargar=puede_descargar,
            puede_subir=puede_subir
        )


@router.post("/users/cobradores/{empleado_id}/permissions/rehabilitar", response_model=PermisosEmpleado)
def rehabilitar_permisos(empleado_id: str, body: RehabilitarPermisosRequest, principal: dict = Depends(require_admin)):
    """
    Re-habilita permisos desde escritorio para casos de error.
    Lógica: pone descargar/subir en TRUE y fecha_accion en ayer para permitir hoy.
    """
    cuenta_id = principal.get("cuenta_id")
    ayer = date.today() - timedelta(days=1)
    
    with DatabasePool.get_cursor() as cur:
        # Verificar que el empleado existe
        cur.execute("""
            SELECT 1 FROM empleados 
            WHERE identificacion=%s AND cuenta_id=%s
        """, (empleado_id, cuenta_id))
        
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Empleado no encontrado")
        
        # Re-habilitar permisos según lo solicitado
        updates = []
        params = []
        
        if body.descargar:
            updates.append("descargar=TRUE")
        if body.subir:
            updates.append("subir=TRUE")
        
        if updates:
            updates.append("fecha_accion=%s")
            params.extend([ayer, empleado_id, cuenta_id])
            
            cur.execute(f"""
                UPDATE empleados 
                SET {', '.join(updates)}
                WHERE identificacion=%s AND cuenta_id=%s
            """, params)
        
        # Devolver estado actualizado
        cur.execute("""
            SELECT descargar, subir, fecha_accion 
            FROM empleados 
            WHERE identificacion=%s AND cuenta_id=%s
        """, (empleado_id, cuenta_id))
        
        row = cur.fetchone()
        descargar, subir, fecha_accion = row
        
        hoy = date.today()
        puede_descargar = bool(descargar) and fecha_accion < hoy
        puede_subir = bool(subir) and fecha_accion < hoy
        
        return PermisosEmpleado(
            descargar=bool(descargar),
            subir=bool(subir),
            fecha_accion=fecha_accion.isoformat() if fecha_accion else None,
            puede_descargar=puede_descargar,
            puede_subir=puede_subir
        )


@router.post("/users/cobradores/{empleado_id}/permissions/usar", response_model=PermisosEmpleado)
def usar_permisos(empleado_id: str, body: UsarPermisosRequest, principal: dict = Depends(require_admin)):
    """
    Usa permisos desde app móvil.
    Lógica: 
    - Al descargar: descargar=FALSE, subir=TRUE, fecha_accion=igual
    - Al subir: descargar=TRUE, subir=FALSE, fecha_accion=hoy
    """
    cuenta_id = principal.get("cuenta_id")
    hoy = date.today()
    
    with DatabasePool.get_cursor() as cur:
        # Verificar que el empleado existe
        cur.execute("""
            SELECT descargar, subir, fecha_accion 
            FROM empleados 
            WHERE identificacion=%s AND cuenta_id=%s
        """, (empleado_id, cuenta_id))
        
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Empleado no encontrado")
        
        descargar_actual, subir_actual, fecha_accion_actual = row
        
        # Aplicar lógica según la acción
        if body.descargar:
            # Al descargar: descargar=FALSE, subir=TRUE, fecha_accion=igual
            cur.execute("""
                UPDATE empleados 
                SET descargar=FALSE, subir=TRUE 
                WHERE identificacion=%s AND cuenta_id=%s
            """, (empleado_id, cuenta_id))
            descargar, subir, fecha_accion = False, True, fecha_accion_actual
            
        elif body.subir:
            # Al subir: descargar=TRUE, subir=FALSE, fecha_accion=hoy
            cur.execute("""
                UPDATE empleados 
                SET descargar=TRUE, subir=FALSE, fecha_accion=%s 
                WHERE identificacion=%s AND cuenta_id=%s
            """, (hoy, empleado_id, cuenta_id))
            descargar, subir, fecha_accion = True, False, hoy
        
        else:
            # No se especificó acción
            descargar, subir, fecha_accion = descargar_actual, subir_actual, fecha_accion_actual
        
        # Calcular permisos efectivos
        puede_descargar = bool(descargar) and fecha_accion < hoy
        puede_subir = bool(subir) and fecha_accion < hoy
        
        return PermisosEmpleado(
            descargar=bool(descargar),
            subir=bool(subir),
            fecha_accion=fecha_accion.isoformat() if fecha_accion else None,
            puede_descargar=puede_descargar,
            puede_subir=puede_subir
        )

@router.post("/users/cobradores/{empleado_id}/deactivate")
def deactivate_cobrador(empleado_id: str, principal: dict = Depends(require_admin)):
    cuenta_id = principal.get("cuenta_id")
    with DatabasePool.get_cursor() as cur:
        cur.execute(
            """
            UPDATE usuarios
               SET is_active = FALSE
             WHERE role='cobrador' AND cuenta_id=%s AND empleado_identificacion=%s AND is_active=TRUE
             RETURNING id
            """,
            (cuenta_id, empleado_id),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="No hay cobrador activo para este empleado")
    return {"ok": True}


@router.post("/users/cobradores/{empleado_id}/activate")
def activate_cobrador(empleado_id: str, principal: dict = Depends(require_admin)):
    cuenta_id = principal.get("cuenta_id")
    
    # Validar estado de la cuenta
    if not enforce_account_state(cuenta_id):
        raise HTTPException(status_code=403, detail="Suscripción vencida. Renueve para continuar.")
    
    with DatabasePool.get_cursor() as cur:
        # validar límite
        cur.execute("SELECT COALESCE(max_empleados,1) FROM cuentas_admin WHERE id=%s", (cuenta_id,))
        max_emp = cur.fetchone()[0] or 1
        cur.execute("SELECT COUNT(*) FROM usuarios WHERE role='cobrador' AND cuenta_id=%s AND is_active=TRUE", (cuenta_id,))
        usados = cur.fetchone()[0] or 0
        if usados >= max_emp:
            raise HTTPException(status_code=403, detail="Límite de cobradores activos alcanzado")

        # activar si existe un desactivado para el empleado
        cur.execute(
            """
            UPDATE usuarios
               SET is_active = TRUE
             WHERE role='cobrador' AND cuenta_id=%s AND empleado_identificacion=%s AND is_active=FALSE
             RETURNING id
            """,
            (cuenta_id, empleado_id),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="No hay cobrador desactivado para este empleado")
    return {"ok": True}


@router.post("/billing/renew")
def renew_subscription(body: RenewRequest, principal: dict = Depends(require_admin)):
    """
    Renueva o cambia el plan de suscripción.
    Si es renovación (es_renovacion=True), reactiva automáticamente los usuarios que estaban activos.
    Si es cambio de plan (es_renovacion=False), no reactiva automáticamente.
    """
    cuenta_id = principal.get("cuenta_id")
    
    with DatabasePool.get_cursor() as cur:
        # Asegurar columna max_daily_routes
        cur.execute("""
            ALTER TABLE cuentas_admin
            ADD COLUMN IF NOT EXISTS max_daily_routes INTEGER
        """)
        # 1. Guardar qué usuarios estaban activos ANTES de la renovación
        usuarios_para_reactivar = []
        if body.es_renovacion:
            cur.execute("""
                SELECT empleado_identificacion 
                FROM usuarios 
                WHERE role='cobrador' AND cuenta_id=%s AND is_active=FALSE
            """, (cuenta_id,))
            usuarios_para_reactivar = [row[0] for row in cur.fetchall()]
        
        # 2. Actualizar plan
        cur.execute(
            """
            UPDATE cuentas_admin 
               SET max_empleados=%s,
                   max_daily_routes=COALESCE(%s, %s),
                   fecha_fin=CURRENT_DATE + INTERVAL '%s days'
             WHERE id=%s
            """,
            (body.max_empleados, body.max_daily_routes, body.max_empleados, body.dias, cuenta_id),
        )
        
        # 3. Si es RENOVACIÓN: reactivar automáticamente hasta el límite
        reactivados = 0
        if body.es_renovacion and usuarios_para_reactivar:
            limite = min(len(usuarios_para_reactivar), body.max_empleados)
            for i in range(limite):
                cur.execute("""
                    UPDATE usuarios 
                    SET is_active=TRUE 
                    WHERE role='cobrador' AND cuenta_id=%s AND empleado_identificacion=%s
                """, (cuenta_id, usuarios_para_reactivar[i]))
            reactivados = limite
    
    return {
        "ok": True, 
        "reactivados": reactivados,
        "mensaje": f"Plan actualizado. Se reactivaron {reactivados} usuarios cobrador." if body.es_renovacion else "Plan actualizado. Active manualmente los usuarios que necesite."
    }


@router.post("/users/cobradores/activate-available")
def activate_available_cobradores(principal: dict = Depends(require_admin)):
    """
    Activa todos los usuarios cobrador disponibles hasta llenar el cupo del plan.
    """
    cuenta_id = principal.get("cuenta_id")
    
    # Validar estado de la cuenta
    if not enforce_account_state(cuenta_id):
        raise HTTPException(status_code=403, detail="Suscripción vencida. Renueve para continuar.")
    
    with DatabasePool.get_cursor() as cur:
        # Obtener límites actuales
        cur.execute("SELECT COALESCE(max_empleados,1) FROM cuentas_admin WHERE id=%s", (cuenta_id,))
        max_emp = cur.fetchone()[0] or 1
        
        cur.execute("SELECT COUNT(*) FROM usuarios WHERE role='cobrador' AND cuenta_id=%s AND is_active=TRUE", (cuenta_id,))
        activos = cur.fetchone()[0] or 0
        
        disponibles = max_emp - activos
        
        if disponibles <= 0:
            return {"activados": 0, "mensaje": "No hay cupos disponibles"}
        
        # Activar hasta llenar el cupo
        cur.execute("""
            UPDATE usuarios 
            SET is_active = TRUE 
            WHERE role='cobrador' AND cuenta_id=%s AND is_active=FALSE
            LIMIT %s
            RETURNING empleado_identificacion
        """, (cuenta_id, disponibles))
        
        activados = cur.fetchall()
        
        return {
            "activados": len(activados),
            "empleados": [row[0] for row in activados],
            "mensaje": f"Se activaron {len(activados)} usuarios cobrador"
        }


@router.post("/downloads/attempt", response_model=AttemptDownloadResponse)
def attempt_download(body: AttemptDownloadRequest, principal: dict = Depends(get_current_principal)):
    """
    Registra un intento de descarga para un empleado y valida límite por plan (sin histórico):
    - Usa campos volátiles en cuentas_admin: daily_routes_date (DATE local) y daily_routes_empleados (JSONB-set)
    - Acepta admin y cobrador; siempre suma a la cuenta (cuenta_id del token)
    - Permite múltiples descargas del MISMO empleado en el día
    - Bloquea si el empleado es nuevo en el día y ya se alcanzó el límite (max_daily_routes || max_empleados)
    """
    from datetime import datetime as _dt
    from zoneinfo import ZoneInfo as _ZI, ZoneInfoNotFoundError as _ZINF
    role = principal.get("role")
    if role not in ("admin", "cobrador"):
        raise HTTPException(status_code=403, detail="Rol no autorizado")
    cuenta_id = principal.get("cuenta_id")
    empleado_id = str(body.empleado_identificacion)
    # Si es cobrador, solo puede registrar su propio empleado
    if role == "cobrador":
        if str(principal.get("empleado_identificacion")) != empleado_id:
            raise HTTPException(status_code=403, detail="Cobrador no puede registrar otro empleado")
    # Calcular día LOCAL según timezone del token
    tz_name = principal.get('timezone') or 'UTC'
    try:
        hoy_local = _dt.now(_ZI(tz_name)).date()
    except _ZINF:
        hoy_local = _dt.now(_ZI('UTC')).date()
    with DatabasePool.get_cursor() as cur:
        # Asegurar columnas volátiles
        cur.execute("""
            ALTER TABLE cuentas_admin
            ADD COLUMN IF NOT EXISTS daily_routes_date DATE,
            ADD COLUMN IF NOT EXISTS daily_routes_empleados JSONB DEFAULT '{}'::jsonb,
            ADD COLUMN IF NOT EXISTS max_daily_routes INTEGER
        """)
        # Validar pertenencia del empleado a la cuenta cuando el rol es admin (opcional pero recomendable)
        if role == 'admin':
            cur.execute("SELECT 1 FROM empleados WHERE identificacion=%s AND cuenta_id=%s", (empleado_id, cuenta_id))
            if cur.fetchone() is None:
                raise HTTPException(status_code=403, detail="Empleado no pertenece a la cuenta")
        # Lock de la fila de cuenta para consistencia
        cur.execute(
            """
            SELECT daily_routes_date, daily_routes_empleados, COALESCE(max_daily_routes, max_empleados, 1) AS lim
            FROM cuentas_admin
            WHERE id=%s
            FOR UPDATE
            """,
            (cuenta_id,),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Cuenta no encontrada")
        d_date, d_json, limit_emp = row
        if not isinstance(d_json, dict):
            # psycopg2 convierte jsonb a dict; si no, normalizar
            try:
                import json as _json
                d_json = _json.loads(d_json) if d_json else {}
            except Exception:
                d_json = {}
        # Reset diario si cambió de día local
        if d_date != hoy_local:
            cur.execute(
                "UPDATE cuentas_admin SET daily_routes_date=%s, daily_routes_empleados='{}'::jsonb WHERE id=%s",
                (hoy_local, cuenta_id),
            )
            d_json = {}
        # Si el empleado ya está registrado hoy, permitir redescarga
        if empleado_id in d_json.keys():
            used = len(d_json)
            return AttemptDownloadResponse(allowed=True, used=used, limit=limit_emp, already_registered=True, message="Redescarga permitida")
        # Límite
        used = len(d_json)
        if used >= int(limit_emp or 1):
            return AttemptDownloadResponse(allowed=False, used=used, limit=int(limit_emp or 1), already_registered=False, message="Límite diario alcanzado para el plan")
        # Registrar empleado en set JSONB
        cur.execute(
            """
            UPDATE cuentas_admin
               SET daily_routes_empleados = COALESCE(daily_routes_empleados, '{}'::jsonb) || jsonb_build_object(%s, true),
                   daily_routes_date = %s
             WHERE id=%s
            """,
            (empleado_id, hoy_local, cuenta_id),
        )
        return AttemptDownloadResponse(allowed=True, used=used+1, limit=int(limit_emp or 1), already_registered=False, message="Descarga registrada")

@router.get("/users/cobradores/activos")
def get_cobradores_activos(principal: dict = Depends(require_admin)):
    """
    Obtiene la lista de empleados que tienen usuario cobrador activo.
    """
    cuenta_id = principal.get("cuenta_id")
    
    with DatabasePool.get_cursor() as cur:
        cur.execute("""
            SELECT u.empleado_identificacion, e.nombre_completo, u.username
            FROM usuarios u
            JOIN empleados e ON u.empleado_identificacion = e.identificacion
            WHERE u.role='cobrador' AND u.cuenta_id=%s AND u.is_active=TRUE
            ORDER BY e.nombre_completo
        """, (cuenta_id,))
        
        cobradores_activos = []
        for row in cur.fetchall():
            cobradores_activos.append({
                "identificacion": row[0],
                "nombre_completo": row[1],
                "username": row[2]
            })
    
    return {"cobradores_activos": cobradores_activos}


