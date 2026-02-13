from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
import os
from typing import List, Optional
import logging
from decimal import Decimal
from datetime import date
from zoneinfo import ZoneInfo
from time import perf_counter as _pc

"""Importaciones del paquete interno (usar rutas relativas del paquete)."""
from .database.db_config import DB_CONFIG
from .database.connection_pool import DatabasePool

from .database.clientes_db import crear_cliente, obtener_cliente_por_identificacion, actualizar_cliente, eliminar_cliente, listar_clientes_por_empleado, buscar_datos_clavo
from .database.empleados_db import insertar_empleado, buscar_empleado_por_identificacion, actualizar_empleado, eliminar_empleado, obtener_empleados, verificar_empleado_tiene_tarjetas, obtener_tarjetas_empleado
from .database.tarjetas_db import crear_tarjeta, obtener_tarjeta_por_codigo, actualizar_tarjeta, actualizar_estado_tarjeta, mover_tarjeta, eliminar_tarjeta, obtener_todas_las_tarjetas, actualizar_rutas_masivo, buscar_tarjetas, verificar_reactivacion_tarjeta, listar_tarjetas_sin_abono_dia
from .database.abonos_db import registrar_abono, obtener_abono_por_id, actualizar_abono, eliminar_abono_por_id, eliminar_ultimo_abono
from .database.bases_db import insertar_base, obtener_base, actualizar_base, eliminar_base
# CORRECCIÓN: Se importa la función correcta 'obtener_tipos_gastos' (plural)
from .database.gastos_db import agregar_gasto, obtener_gasto_por_id, actualizar_gasto, eliminar_gasto, obtener_resumen_gastos_por_tipo, obtener_tipos_gastos, obtener_todos_los_gastos
from .database.liquidacion_db import obtener_datos_liquidacion, obtener_resumen_financiero_fecha, mover_liquidacion
from .database.caja_db import (
    verificar_esquema_caja,
    upsert_caja,
    get_caja_en_fecha,
    registrar_salida,
    registrar_entrada,
    obtener_salidas,
    obtener_metricas_contabilidad,
    recalcular_caja_dia,
)

from .schemas import (
    Cliente, ClienteCreate, ClienteUpdate, ClienteBase, Empleado, EmpleadoCreate, EmpleadoUpdate,
    Tarjeta, TarjetaCreate, TarjetaUpdate, Abono, AbonoCreate, AbonoUpdate, Base,
    BaseCreate, BaseUpdate, TipoGasto, Gasto, GastoCreate, GastoUpdate,
    ResumenGasto, LiquidacionDiaria, ResumenFinanciero,
    SyncRequest, SyncResponse,
    ContabilidadQuery, ContabilidadMetricas, CajaValor, CajaSalida, CajaSalidaCreate, CajaEntrada, CajaEntradaCreate, VerificacionEsquemaCaja,
    RutaUpdateItem, ClienteClavo
)

# Configuración del logging (producción-friendly).
# En prod debe ser INFO/WARNING; en dev puedes usar DEBUG.
_log_level = os.getenv("LOG_LEVEL", "INFO").upper().strip()
if _log_level not in ("CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"):
    _log_level = "INFO"

logging.basicConfig(level=getattr(logging, _log_level, logging.INFO))
logging.getLogger().setLevel(getattr(logging, _log_level, logging.INFO))

for _name in (
    "gestion_carteras_api",
    "gestion_carteras_api.database",
    "gestion_carteras_api.database.caja_db",
):
    _lg = logging.getLogger(_name)
    _lg.setLevel(getattr(logging, _log_level, logging.INFO))
    _lg.propagate = True

logger = logging.getLogger(__name__)

# --- Creación de la app FastAPI ---
app = FastAPI(
    title="Gestión de Carteras API",
    description="API para la gestión de carteras de cobro.",
    version="1.0.0",
)

# CORS: permitir orígenes configurables por entorno (CORS_ORIGINS="https://app.pages.dev,https://tu-dominio.com")
_env_cors = os.getenv("CORS_ORIGINS", "")
if _env_cors:
    _allowed_origins = [o.strip() for o in _env_cors.split(',') if o.strip()]
else:
    # Fallback a orígenes locales de desarrollo
    _allowed_origins = [
        "http://192.168.100.158:5174",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "http://172.20.10.7:5174",
        "http://172.20.10.7:5173",
        "http://172.20.10.3:5174",
        "http://192.168.1.135:5174"
    ]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True, 
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers: auth y billing
from .routers import auth as auth_router
from .routers import billing as billing_router
from .routers import public as public_router
from .routers import admin_users as admin_users_router
from .routers import datacredito as datacredito_router
from .routers import telegram_bot as telegram_router

app.include_router(auth_router.router, prefix="/auth", tags=["auth"])
app.include_router(billing_router.router, prefix="/billing", tags=["billing"])
app.include_router(public_router.router, prefix="/public", tags=["public"])
app.include_router(admin_users_router.router, prefix="/admin", tags=["admin"])
app.include_router(datacredito_router.router, prefix="/datacredito", tags=["datacredito"])
app.include_router(telegram_router.router, prefix="/telegram", tags=["telegram"])

# Seguridad
from .security import get_current_principal, require_admin

def _enforce_empleado_scope(principal: dict, empleado_id: str):
    role = principal.get("role")
    if role == "admin":
        return
    if role == "cobrador" and principal.get("empleado_identificacion") == str(empleado_id):
        return
    raise HTTPException(status_code=403, detail="Acceso denegado para este empleado")

def _day_bounds_utc_str(fecha_str: str, tz_name: str):
    """Devuelve (inicio_utc, fin_utc) como strings ISO para filtrar un día local en UTC."""
    try:
        from datetime import datetime as _dt, timezone as _tz
        tz = ZoneInfo(tz_name or 'UTC')
        d = _dt.strptime(fecha_str, '%Y-%m-%d').date()
        start_local = _dt(d.year, d.month, d.day, 0, 0, 0, tzinfo=tz)
        end_local = _dt(d.year, d.month, d.day, 23, 59, 59, 999000, tzinfo=tz)
        start_utc = start_local.astimezone(_tz.utc)
        end_utc = end_local.astimezone(_tz.utc)
        # debug removido
        return (start_utc, end_utc)
    except Exception:
        # Fallback seguro a día UTC si falla el parseo
        from datetime import datetime as _dt, timezone as _tz
        d = _dt.strptime(fecha_str, '%Y-%m-%d').date()
        start_utc = _dt(d.year, d.month, d.day, 0, 0, 0, tzinfo=_tz.utc)
        end_utc = _dt(d.year, d.month, d.day, 23, 59, 59, 999000, tzinfo=_tz.utc)
        return (start_utc, end_utc)

# --- Evento de Arranque (Startup) ---
@app.on_event("startup")
def startup_event():
    logger.info("Iniciando la aplicación y el pool de conexiones a la base de datos...")
    try:
        # Permitir configurar tamaño del pool por entorno
        _minconn = int(os.getenv("POOL_MINCONN", "1"))
        _maxconn = int(os.getenv("POOL_MAXCONN", "50"))
        DatabasePool.initialize(minconn=_minconn, maxconn=_maxconn, **DB_CONFIG)
        # Asegurar columna modalidad_pago para soportar modalidades (diario/semanal/quincenal/mensual)
        try:
            from .database.tarjetas_db import ensure_modalidad_pago_column
            ensure_modalidad_pago_column()
        except Exception:
            pass

        logger.info("Pool de conexiones a la base de datos inicializado con éxito.")
    except Exception as e:
        logger.critical(f"Error crítico al inicializar el pool de conexiones: {e}", exc_info=True)
        raise RuntimeError(f"No se pudo conectar a la base de datos: {e}")

# --- Evento de Cierre (Shutdown) ---
@app.on_event("shutdown")
def shutdown_event():
    logger.info("Cerrando el pool de conexiones de la base de datos...")
    DatabasePool.close_all()
    logger.info("Pool de conexiones cerrado.")


# --- Endpoints ---

@app.get("/")
def read_root():
    return {"message": "¡Bienvenido a la API de Gestión de Carteras!"}

# --- Versión de la aplicación de escritorio ---
# Actualizar aquí con cada release del instalador .exe
DESKTOP_APP_VERSION = {
    "version": "2.2",
    "download_url": "https://drive.google.com/drive/folders/1bblA_PA60sMO3El06SJwvwGX93qwMtAU?usp=sharing",
    "notas": "Scroll restore en busqueda, indicador amarillo no-diario, auto-actualizacion, limpieza de proyecto",
}

@app.get("/app/version")
def get_app_version():
    """Devuelve la versión actual de la app de escritorio y el link de descarga (público, sin auth)."""
    return DESKTOP_APP_VERSION

# --- Endpoints de Contabilidad / Caja ---

@app.get("/contabilidad/esquema", response_model=VerificacionEsquemaCaja)
def contabilidad_verificar_esquema_endpoint(principal: dict = Depends(require_admin)):
    try:
        info = verificar_esquema_caja()
        return info
    except Exception as e:
        logger.error(f"Error al verificar esquema de caja: {e}")
        raise HTTPException(status_code=500, detail="Error interno al verificar esquema de caja")


@app.post("/contabilidad/metricas", response_model=ContabilidadMetricas)
def contabilidad_metricas_endpoint(query: ContabilidadQuery, principal: dict = Depends(get_current_principal)):
    try:
        tz_name = principal.get("timezone")
        datos = obtener_metricas_contabilidad(
            desde=query.desde,
            hasta=query.hasta,
            empleado_id=query.empleado_id,
            timezone_name=tz_name,
            cuenta_id=principal.get("cuenta_id")
        )
        # días en rango
        try:
            dias = (query.hasta - query.desde).days + 1
            if dias < 0:
                dias = 0
        except Exception:
            dias = 0
        return {
            'desde': query.desde,
            'hasta': query.hasta,
            'empleado_id': query.empleado_id,
            'total_cobrado': float(datos.get('total_cobrado', 0)),
            'total_prestamos': float(datos.get('total_prestamos', 0)),
            'total_gastos': float(datos.get('total_gastos', 0)),
            'total_bases': float(datos.get('total_bases', 0)),
            'total_salidas': float(datos.get('total_salidas', 0)),
            'total_entradas': float(datos.get('total_entradas', 0)),
            'caja': float(datos.get('caja', 0)),
            'total_intereses': float(datos.get('total_intereses', 0)),
            'ganancia': float(datos.get('total_intereses', 0)) - float(datos.get('total_gastos', 0)),
            'cartera_en_calle': float(datos.get('cartera_en_calle', 0)),
            'cartera_en_calle_desde': float(datos.get('cartera_en_calle_desde', 0)),
            'abonos_count': int(datos.get('abonos_count', 0)),
            'dias_en_rango': int(dias),
            'total_efectivo': float(datos.get('total_efectivo', 0)),
            'total_clavos': float(datos.get('total_clavos', 0)),
            'tarjetas_activas_historicas': int(datos.get('tarjetas_activas_historicas', 0)),
        }
    except Exception as e:
        logger.error(f"Error al calcular métricas de contabilidad: {e}")
        raise HTTPException(status_code=500, detail="Error interno al calcular métricas")


@app.get("/caja/{empleado_id}/{fecha}", response_model=CajaValor)
def caja_valor_endpoint(empleado_id: str, fecha: str, principal: dict = Depends(get_current_principal)):
    try:
        from datetime import datetime as _dt
        fecha_obj = _dt.strptime(fecha, '%Y-%m-%d').date()
        val = get_caja_en_fecha(empleado_id, fecha_obj)
        return { 'fecha': fecha_obj, 'valor': float(val) }
    except ValueError:
        raise HTTPException(status_code=400, detail="Formato de fecha inválido. Use YYYY-MM-DD.")
    except Exception as e:
        logger.error(f"Error al obtener valor de caja: {e}")
        raise HTTPException(status_code=500, detail="Error interno al obtener caja")


@app.post("/caja/salidas", response_model=CajaSalida, status_code=201)
def caja_registrar_salida_endpoint(payload: CajaSalidaCreate, principal: dict = Depends(get_current_principal)):
    try:
        from decimal import Decimal as _Dec
        sid = registrar_salida(
            fecha=payload.fecha,
            valor=_Dec(str(payload.valor)),
            concepto=payload.concepto,
            empleado_identificacion=payload.empleado_identificacion,
        )
        if sid is None:
            raise HTTPException(status_code=400, detail="No se pudo registrar la salida de caja")
        # Recalcular caja del día si hay empleado
        try:
            if payload.empleado_identificacion:
                # Usar fecha enviada por el cliente (ya debería ser local), pero pasar timezone para que la función sepa
                # calcular límites de día en base a esa fecha.
                _ = recalcular_caja_dia(payload.empleado_identificacion, payload.fecha, principal.get("timezone"))
        except Exception:
            pass
        return { 'id': sid, **payload.dict() }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error al registrar salida de caja: {e}")
        raise HTTPException(status_code=500, detail="Error interno al registrar salida de caja")


@app.post("/caja/entradas", response_model=CajaEntrada, status_code=201)
def caja_registrar_entrada_endpoint(payload: CajaEntradaCreate, principal: dict = Depends(get_current_principal)):
    try:
        from decimal import Decimal as _Dec
        sid = registrar_entrada(
            fecha=payload.fecha,
            valor=_Dec(str(payload.valor)),
            concepto=payload.concepto,
            empleado_identificacion=payload.empleado_identificacion,
        )
        if sid is None:
            raise HTTPException(status_code=400, detail="No se pudo registrar la entrada de caja")
        # Recalcular caja del día si hay empleado
        try:
            if payload.empleado_identificacion:
                _ = recalcular_caja_dia(payload.empleado_identificacion, payload.fecha, principal.get("timezone"))
        except Exception:
            pass
        return { 'id': sid, **payload.dict() }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error al registrar entrada de caja: {e}")
        raise HTTPException(status_code=500, detail="Error interno al registrar entrada de caja")


@app.post("/caja/recalcular-dia", response_model=CajaValor)
def caja_recalcular_dia_endpoint(body: dict, principal: dict = Depends(get_current_principal)):
    try:
        emp = str(body.get('empleado_identificacion'))
        from datetime import datetime as _dt, date
        fecha = body.get('fecha')
        
        # Si viene string, parsear
        if isinstance(fecha, str):
            fecha = _dt.strptime(fecha, '%Y-%m-%d').date()
        
        # Si no viene fecha, usar hoy en timezone local
        if not fecha:
            try:
                from zoneinfo import ZoneInfo
                from datetime import timezone as _tz
                tz = ZoneInfo(principal.get("timezone")) if principal.get("timezone") else _tz.utc
                fecha = _dt.now(tz).date()
            except Exception:
                fecha = date.today()

        if not emp:
            raise HTTPException(status_code=400, detail='empleado_identificacion es requerido')
            
        val = recalcular_caja_dia(emp, fecha, principal.get("timezone"))
        return { 'fecha': fecha, 'valor': float(val) }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error al recalcular caja del día: {e}")
        raise HTTPException(status_code=500, detail='Error interno al recalcular caja')


@app.get("/caja/salidas")
def caja_listar_salidas_endpoint(desde: str, hasta: str, empleado_id: Optional[str] = None, principal: dict = Depends(get_current_principal)):
    try:
        from datetime import datetime as _dt
        d1 = _dt.strptime(desde, '%Y-%m-%d').date()
        d2 = _dt.strptime(hasta, '%Y-%m-%d').date()
        rows = obtener_salidas(d1, d2, empleado_id)
        salidas = []
        for r in rows:
            salidas.append({
                'id': r[0],
                'fecha': r[1],
                'valor': float(r[2] or 0),
                'concepto': r[3],
                'empleado_identificacion': r[4],
                'fecha_creacion': r[5],
            })
        return salidas
    except ValueError:
        raise HTTPException(status_code=400, detail="Parámetros de fecha inválidos. Use YYYY-MM-DD")
    except Exception as e:
        logger.error(f"Error al listar salidas de caja: {e}")
        raise HTTPException(status_code=500, detail="Error interno al listar salidas de caja")

# --- Endpoint para Tipos de Gastos ---

# CORRECCIÓN: Endpoint reactivado y funcionando con la función correcta.
@app.get("/gastos/tipos", response_model=List[TipoGasto])
def read_tipos_gastos_endpoint():
    """
    Obtiene la lista de todos los tipos de gastos disponibles.
    """
    try:
        # Usa la función correcta 'obtener_tipos_gastos'
        tipos_tuplas = obtener_tipos_gastos()
        # Convierte las tuplas a una lista de diccionarios que Pydantic puede usar
        return [{"id": t[0], "nombre": t[1], "descripcion": t[2]} for t in tipos_tuplas]
    except Exception as e:
        logger.error(f"Error al obtener los tipos de gasto: {e}")
        raise HTTPException(status_code=500, detail="Error interno al consultar los tipos de gasto.")

# --- Endpoints para Empleados ---

@app.get("/empleados/", response_model=List[Empleado])
def read_empleados_endpoint(principal: dict = Depends(require_admin)):
    """
    Obtiene una lista de todos los empleados.
    """
    try:
        cuenta_id = principal.get("cuenta_id")
        empleados = obtener_empleados(cuenta_id)
        return empleados
    except Exception as e:
        logger.error(f"Error al obtener la lista de empleados: {e}")
        raise HTTPException(status_code=500, detail="Error interno al consultar los empleados.")

@app.post("/empleados/", response_model=Empleado, status_code=201)
def create_empleado_endpoint(empleado: EmpleadoCreate, principal: dict = Depends(require_admin)):
    try:
        cuenta_id = principal.get("cuenta_id")
        nuevo_id = insertar_empleado(
            identificacion=empleado.identificacion,
            nombre=empleado.nombre_completo,
            telefono=empleado.telefono or "",
            direccion=empleado.direccion or "",
            cuenta_id=cuenta_id
        )
        if not nuevo_id:
            raise HTTPException(status_code=400, detail="No se pudo crear el empleado. Puede que ya exista.")
        db_emp = buscar_empleado_por_identificacion(empleado.identificacion, cuenta_id)
        if db_emp is None:
            raise HTTPException(status_code=500, detail="Empleado creado pero no encontrado.")
        return db_emp
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error al crear empleado: {e}")
        raise HTTPException(status_code=500, detail="Error interno al crear el empleado.")

@app.put("/empleados/{identificacion}", response_model=Empleado)
def update_empleado_endpoint(identificacion: str, empleado: EmpleadoUpdate, principal: dict = Depends(require_admin)):
    try:
        cuenta_id = principal.get("cuenta_id")
        ok = actualizar_empleado(
            identificacion=identificacion,
            nombre=empleado.nombre_completo or "",
            telefono=empleado.telefono or "",
            direccion=empleado.direccion or "",
            cuenta_id=cuenta_id
        )
        if not ok:
            raise HTTPException(status_code=404, detail="Empleado no encontrado o no se pudo actualizar.")
        db_emp = buscar_empleado_por_identificacion(identificacion, cuenta_id)
        if db_emp is None:
            raise HTTPException(status_code=404, detail="Empleado no encontrado después de actualizar.")
        return db_emp
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error al actualizar empleado: {e}")
        raise HTTPException(status_code=500, detail="Error interno al actualizar el empleado.")

# --- Permisos diarios en columnas de empleados (descargar, subir, fecha_accion) ---

from pydantic import BaseModel
from datetime import datetime as _dt


class EmpleadoPermsUpdate(BaseModel):
    descargar: Optional[bool] = None
    subir: Optional[bool] = None
    fecha_accion: Optional[str] = None  # YYYY-MM-DD


@app.get("/empleados/{identificacion}/permissions")
def get_empleado_permissions_endpoint(identificacion: str, principal: dict = Depends(get_current_principal)):
    _enforce_empleado_scope(principal, identificacion)
    try:
        logger.info(f"GET permisos empleado: {identificacion}")
        tz_name = principal.get("timezone") or "UTC"
        from datetime import datetime as _dt
        today_local = _dt.now(ZoneInfo(tz_name)).date()
        with DatabasePool.get_cursor() as cur:
            cur.execute(
                """
                SELECT descargar, subir, fecha_accion
                FROM empleados
                WHERE identificacion = %s
                """,
                (identificacion,),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Empleado no encontrado")
            descargar = bool(row[0])
            subir = bool(row[1])
            fecha_accion = row[2]
            # Derivados por zona: se puede subir si tiene flag subir y no ha subido hoy local
            puede_subir = bool(subir and (not fecha_accion or fecha_accion < today_local))
            puede_descargar = bool(descargar)
            return {
                "descargar": descargar,
                "subir": subir,
                "fecha_accion": fecha_accion.isoformat() if fecha_accion else None,
                "puede_subir": puede_subir,
                "puede_descargar": puede_descargar,
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error al leer permisos de empleado: {e}")
        raise HTTPException(status_code=500, detail="Error interno al consultar permisos")


@app.post("/empleados/{identificacion}/permissions")
def set_empleado_permissions_endpoint(identificacion: str, body: EmpleadoPermsUpdate, principal: dict = Depends(get_current_principal)):
    _enforce_empleado_scope(principal, identificacion)
    try:
        logger.info(f"POST permisos empleado: {identificacion} body={body.dict()}")
        tz_name = principal.get("timezone") or "UTC"
        from datetime import datetime as _dt
        today_local = _dt.now(ZoneInfo(tz_name)).date()
        sets = []
        params = []
        if body.descargar is not None:
            sets.append("descargar = %s")
            params.append(bool(body.descargar))
        if body.subir is not None:
            sets.append("subir = %s")
            params.append(bool(body.subir))
        if body.fecha_accion is not None:
            try:
                fa = _dt.strptime(body.fecha_accion, "%Y-%m-%d").date()
            except Exception:
                raise HTTPException(status_code=400, detail="fecha_accion debe tener formato YYYY-MM-DD")
            sets.append("fecha_accion = %s")
            params.append(fa)
        if not sets:
            raise HTTPException(status_code=400, detail="No hay campos para actualizar")
        params.append(identificacion)
        with DatabasePool.get_cursor() as cur:
            cur.execute(f"UPDATE empleados SET {', '.join(sets)} WHERE identificacion = %s RETURNING identificacion", params)
            if cur.fetchone() is None:
                raise HTTPException(status_code=404, detail="Empleado no encontrado")
            # devolver valores actuales
            cur.execute(
                "SELECT descargar, subir, fecha_accion FROM empleados WHERE identificacion = %s",
                (identificacion,),
            )
            row = cur.fetchone()
            logger.info(f"Permisos actualizados {identificacion}: descargar={row[0]}, subir={row[1]}, fecha_accion={row[2]}")
            descargar = bool(row[0]); subir = bool(row[1]); fecha_accion = row[2]
            return {
                "descargar": descargar,
                "subir": subir,
                "fecha_accion": fecha_accion.isoformat() if fecha_accion else None,
                "puede_subir": bool(subir and (not fecha_accion or fecha_accion < today_local)),
                "puede_descargar": bool(descargar),
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error al actualizar permisos de empleado: {e}")
        raise HTTPException(status_code=500, detail="Error interno al actualizar permisos")

@app.delete("/empleados/{identificacion}")
def delete_empleado_endpoint(identificacion: str, principal: dict = Depends(require_admin)):
    try:
        cuenta_id = principal.get("cuenta_id")
        
        # Verificar si el empleado existe
        empleado = buscar_empleado_por_identificacion(identificacion, cuenta_id)
        if not empleado:
            raise HTTPException(status_code=404, detail="Empleado no encontrado.")
        
        # Verificar dependencias: tarjetas, gastos, bases, permisos de cobrador y usuarios
        tiene_tarjetas, cantidad_tarjetas = verificar_empleado_tiene_tarjetas(identificacion)

        deps = {
            "tarjetas_total": int(cantidad_tarjetas or 0),
            "gastos": 0,
            "bases": 0,
            "permisos_cobrador": 0,
            "usuarios_cobrador": 0,
            "control_caja": 0,
        }

        # Consultar otras tablas que referencian a empleados
        with DatabasePool.get_cursor() as cursor:
            try:
                cursor.execute("SELECT COUNT(*) FROM gastos WHERE empleado_identificacion=%s", (identificacion,))
                deps["gastos"] = int(cursor.fetchone()[0] or 0)
            except Exception:
                pass
            try:
                cursor.execute("SELECT COUNT(*) FROM bases WHERE empleado_id=%s", (identificacion,))
                deps["bases"] = int(cursor.fetchone()[0] or 0)
            except Exception:
                pass
            try:
                cursor.execute("SELECT COUNT(*) FROM control_caja WHERE empleado_identificacion=%s", (identificacion,))
                deps["control_caja"] = int(cursor.fetchone()[0] or 0)
            except Exception:
                pass
            try:
                cursor.execute("SELECT COUNT(*) FROM cobrador_permisos_diarios WHERE empleado_identificacion=%s", (identificacion,))
                deps["permisos_cobrador"] = int(cursor.fetchone()[0] or 0)
            except Exception:
                pass
            try:
                cursor.execute("SELECT COUNT(*) FROM usuarios WHERE empleado_identificacion=%s", (identificacion,))
                deps["usuarios_cobrador"] = int(cursor.fetchone()[0] or 0)
            except Exception:
                pass

        if any([tiene_tarjetas, deps["gastos"] > 0, deps["bases"] > 0, deps["permisos_cobrador"] > 0, deps["usuarios_cobrador"] > 0, deps["control_caja"] > 0]):
            tarjetas_serializables = []
            tarjetas_activas = []
            tarjetas_canceladas = []
            if tiene_tarjetas:
                tarjetas = obtener_tarjetas_empleado(identificacion)
                tarjetas_activas = [t for t in tarjetas if t['estado'] == 'activas']
                tarjetas_canceladas = [t for t in tarjetas if t['estado'] == 'canceladas']
                for tarjeta in tarjetas:
                    tarjeta_serializable = {
                        'codigo': tarjeta['codigo'],
                        'estado': tarjeta['estado'],
                        'monto': float(tarjeta['monto']) if isinstance(tarjeta['monto'], Decimal) else tarjeta['monto'],
                        'cliente_identificacion': tarjeta['cliente_identificacion']
                    }
                    tarjetas_serializables.append(tarjeta_serializable)

            raise HTTPException(
                status_code=409,
                detail={
                    "error": "No se puede eliminar el empleado porque tiene datos relacionados",
                    "empleado": empleado,
                    "dependencias": deps,
                    "tarjetas_asociadas": {
                        "total": cantidad_tarjetas,
                        "activas": len(tarjetas_activas),
                        "canceladas": len(tarjetas_canceladas),
                        "detalle": tarjetas_serializables
                    } if tiene_tarjetas else None,
                    "opciones": [
                        "Transferir todas las tarjetas a otro empleado",
                        "Eliminar empleado y todos sus datos relacionados (acción irreversible)",
                    ]
                }
            )
        
        # Si no tiene tarjetas, proceder con la eliminación
        ok = eliminar_empleado(identificacion, cuenta_id)
        if not ok:
            raise HTTPException(status_code=500, detail="Error al eliminar el empleado.")
        
        return {"ok": True, "message": "Empleado eliminado exitosamente"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error al eliminar empleado: {e}")
        raise HTTPException(status_code=500, detail="Error interno al eliminar el empleado.")

# --- Endpoints adicionales para manejo de empleados con tarjetas ---

class TransferirTarjetasRequest(BaseModel):
    empleado_destino: str
    confirmar_transferencia: bool = False

@app.post("/empleados/{identificacion}/transferir-tarjetas")
def transferir_tarjetas_empleado_endpoint(identificacion: str, request: TransferirTarjetasRequest, principal: dict = Depends(require_admin)):
    """
    Transfiere todas las tarjetas de un empleado a otro empleado.
    """
    try:
        cuenta_id = principal.get("cuenta_id")
        
        # Verificar que el empleado origen existe
        empleado_origen = buscar_empleado_por_identificacion(identificacion, cuenta_id)
        if not empleado_origen:
            raise HTTPException(status_code=404, detail="Empleado origen no encontrado.")
        
        # Verificar que el empleado destino existe
        empleado_destino = buscar_empleado_por_identificacion(request.empleado_destino, cuenta_id)
        if not empleado_destino:
            raise HTTPException(status_code=404, detail="Empleado destino no encontrado.")
        
        if identificacion == request.empleado_destino:
            raise HTTPException(status_code=400, detail="No se puede transferir tarjetas al mismo empleado.")
        
        # Verificar si tiene tarjetas para transferir
        tiene_tarjetas, cantidad_tarjetas = verificar_empleado_tiene_tarjetas(identificacion)
        if not tiene_tarjetas:
            raise HTTPException(status_code=400, detail="El empleado no tiene tarjetas para transferir.")
        
        if not request.confirmar_transferencia:
            # Solo devolver información sin hacer la transferencia
            tarjetas = obtener_tarjetas_empleado(identificacion)
            
            # Convertir Decimal a float para serialización JSON
            tarjetas_serializables = []
            for tarjeta in tarjetas:
                tarjeta_serializable = {
                    'codigo': tarjeta['codigo'],
                    'estado': tarjeta['estado'],
                    'monto': float(tarjeta['monto']) if isinstance(tarjeta['monto'], Decimal) else tarjeta['monto'],
                    'cliente_identificacion': tarjeta['cliente_identificacion']
                }
                tarjetas_serializables.append(tarjeta_serializable)
            
            return {
                "confirmacion_requerida": True,
                "empleado_origen": empleado_origen,
                "empleado_destino": empleado_destino,
                "tarjetas_a_transferir": {
                    "total": cantidad_tarjetas,
                    "detalle": tarjetas_serializables
                },
                "mensaje": "Confirme la transferencia enviando confirmar_transferencia: true"
            }
        
        # Realizar la transferencia
        tarjetas_transferidas = 0
        with DatabasePool.get_cursor() as cursor:
            cursor.execute('''
                UPDATE tarjetas 
                SET empleado_identificacion = %s 
                WHERE empleado_identificacion = %s
                RETURNING codigo
            ''', (request.empleado_destino, identificacion))
            
            tarjetas_actualizadas = cursor.fetchall()
            tarjetas_transferidas = len(tarjetas_actualizadas)
        
        return {
            "ok": True,
            "mensaje": f"Transferencia completada exitosamente",
            "tarjetas_transferidas": tarjetas_transferidas,
            "empleado_origen": empleado_origen,
            "empleado_destino": empleado_destino
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error al transferir tarjetas: {e}")
        raise HTTPException(status_code=500, detail="Error interno al transferir las tarjetas.")

class EliminarEmpleadoConTarjetasRequest(BaseModel):
    confirmar_eliminacion: bool = False
    eliminar_tarjetas: bool = False

@app.delete("/empleados/{identificacion}/forzar-eliminacion")
def eliminar_empleado_con_tarjetas_endpoint(identificacion: str, request: EliminarEmpleadoConTarjetasRequest, principal: dict = Depends(require_admin)):
    """
    Elimina un empleado y opcionalmente todas sus tarjetas asociadas.
    ADVERTENCIA: Esta es una acción irreversible.
    """
    try:
        cuenta_id = principal.get("cuenta_id")
        
        # Verificar que el empleado existe
        empleado = buscar_empleado_por_identificacion(identificacion, cuenta_id)
        if not empleado:
            raise HTTPException(status_code=404, detail="Empleado no encontrado.")
        
        # Verificar si tiene tarjetas
        tiene_tarjetas, cantidad_tarjetas = verificar_empleado_tiene_tarjetas(identificacion)
        
        if not request.confirmar_eliminacion:
            # Solo devolver información sin hacer la eliminación
            tarjetas = obtener_tarjetas_empleado(identificacion) if tiene_tarjetas else []
            
            # Convertir Decimal a float para serialización JSON
            tarjetas_serializables = []
            if tiene_tarjetas:
                for tarjeta in tarjetas:
                    tarjeta_serializable = {
                        'codigo': tarjeta['codigo'],
                        'estado': tarjeta['estado'],
                        'monto': float(tarjeta['monto']) if isinstance(tarjeta['monto'], Decimal) else tarjeta['monto'],
                        'cliente_identificacion': tarjeta['cliente_identificacion']
                    }
                    tarjetas_serializables.append(tarjeta_serializable)
            
            return {
                "confirmacion_requerida": True,
                "empleado": empleado,
                "tiene_tarjetas": tiene_tarjetas,
                "tarjetas_asociadas": {
                    "total": cantidad_tarjetas,
                    "detalle": tarjetas_serializables
                } if tiene_tarjetas else None,
                "advertencia": "Esta acción es IRREVERSIBLE. Confirme enviando confirmar_eliminacion: true",
                "opciones": {
                    "eliminar_tarjetas": "Si eliminar_tarjetas es true, se eliminarán también todas las tarjetas del empleado",
                    "solo_empleado": "Si eliminar_tarjetas es false, solo se eliminará el empleado (fallará si tiene tarjetas)"
                }
            }
        
        if tiene_tarjetas and not request.eliminar_tarjetas:
            raise HTTPException(
                status_code=409, 
                detail="El empleado tiene tarjetas asociadas. Use eliminar_tarjetas: true para eliminarlas también."
            )
        
        # Eliminar dependencias adicionales y luego el empleado
        tarjetas_eliminadas = 0
        gastos_eliminados = 0
        bases_eliminadas = 0
        control_caja_eliminados = 0
        permisos_cobrador_eliminados = 0
        usuarios_cobrador_eliminados = 0

        with DatabasePool.get_cursor() as cursor:
            # 1) Si aplica, eliminar abonos y tarjetas del empleado
            if tiene_tarjetas and request.eliminar_tarjetas:
                cursor.execute('''
                    DELETE FROM abonos 
                    WHERE tarjeta_codigo IN (
                        SELECT codigo FROM tarjetas WHERE empleado_identificacion = %s
                    )
                ''', (identificacion,))
                cursor.execute('''
                    DELETE FROM tarjetas 
                    WHERE empleado_identificacion = %s
                    RETURNING codigo
                ''', (identificacion,))
                tarjetas_eliminadas = len(cursor.fetchall())

            # 2) Eliminar gastos asociados al empleado
            cursor.execute("""
                DELETE FROM gastos
                WHERE empleado_identificacion = %s
            """, (identificacion,))
            gastos_eliminados = cursor.rowcount or 0

            # 3) Eliminar bases del empleado
            cursor.execute("""
                DELETE FROM bases
                WHERE empleado_id = %s
            """, (identificacion,))
            bases_eliminadas = cursor.rowcount or 0

            # 4) Eliminar control_caja asociado al empleado
            try:
                cursor.execute("""
                    DELETE FROM control_caja
                    WHERE empleado_identificacion = %s
                """, (identificacion,))
                control_caja_eliminados = cursor.rowcount or 0
            except Exception:
                control_caja_eliminados = 0

            # 5) Eliminar permisos diarios de cobrador (si existen)
            try:
                cursor.execute("""
                    DELETE FROM cobrador_permisos_diarios
                    WHERE empleado_identificacion = %s
                """, (identificacion,))
                permisos_cobrador_eliminados = cursor.rowcount or 0
            except Exception:
                # La tabla puede no existir en algunas instalaciones
                permisos_cobrador_eliminados = 0

            # 5) Eliminar permisos diarios de cobrador (si existen)
            try:
                cursor.execute("""
                    DELETE FROM cobrador_permisos_diarios
                    WHERE empleado_identificacion = %s
                """, (identificacion,))
                permisos_cobrador_eliminados = cursor.rowcount or 0
            except Exception:
                # La tabla puede no existir en algunas instalaciones
                permisos_cobrador_eliminados = 0

            # 6) Eliminar usuarios con role=cobrador vinculados a este empleado
            try:
                cursor.execute("""
                    DELETE FROM usuarios
                    WHERE empleado_identificacion = %s
                """, (identificacion,))
                usuarios_cobrador_eliminados = cursor.rowcount or 0
            except Exception:
                usuarios_cobrador_eliminados = 0

        # 7) Finalmente, eliminar el empleado (usa cuenta_id)
        ok = eliminar_empleado(identificacion, cuenta_id)
        if not ok:
            raise HTTPException(status_code=500, detail="Error al eliminar el empleado.")

        return {
            "ok": True,
            "mensaje": "Empleado eliminado exitosamente",
            "empleado_eliminado": empleado,
            "resumen": {
                "tarjetas_eliminadas": tarjetas_eliminadas if request.eliminar_tarjetas else 0,
                "gastos_eliminados": gastos_eliminados,
                "bases_eliminadas": bases_eliminadas,
                "control_caja_eliminados": control_caja_eliminados,
                "permisos_cobrador_eliminados": permisos_cobrador_eliminados,
                "usuarios_cobrador_eliminados": usuarios_cobrador_eliminados,
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error al eliminar empleado con tarjetas: {e}")
        raise HTTPException(status_code=500, detail="Error interno al eliminar el empleado.")

# --- Endpoints para Bases ---

@app.get("/bases/{empleado_id}/{fecha}", response_model=Optional[Base])
def read_base_by_empleado_fecha_endpoint(empleado_id: str, fecha: str, principal: dict = Depends(get_current_principal)):
    _enforce_empleado_scope(principal, empleado_id)
    """
    Obtiene la base de un empleado en una fecha específica.
    """
    try:
        tz_name = principal.get('timezone') or 'UTC'
        start_utc, end_utc = _day_bounds_utc_str(fecha, tz_name)
        start_naive = start_utc.replace(tzinfo=None)
        end_naive = end_utc.replace(tzinfo=None)
        start_naive = start_utc.replace(tzinfo=None)
        end_naive = end_utc.replace(tzinfo=None)
        start_naive = start_utc.replace(tzinfo=None)
        end_naive = end_utc.replace(tzinfo=None)
        # Usar límites UTC sin tz (naive) para columnas timestamp sin zona
        start_naive = start_utc.replace(tzinfo=None)
        end_naive = end_utc.replace(tzinfo=None)
        # La tabla bases guarda fecha (date) y/o fecha_creacion (timestamp). Usar la función actual por date exacta.
        from datetime import datetime as _dt
        fecha_obj = _dt.strptime(fecha, '%Y-%m-%d').date()
        base = obtener_base(empleado_id, fecha_obj)
        if base is None:
            raise HTTPException(status_code=404, detail="Base no encontrada para el empleado y fecha especificados.")
        return base
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error al obtener base: {e}")
        raise HTTPException(status_code=500, detail="Error interno al consultar la base.")

@app.post("/bases/", response_model=Base, status_code=201)
def create_base_endpoint(base: BaseCreate, principal: dict = Depends(get_current_principal)):
    _enforce_empleado_scope(principal, base.empleado_id)
    """
    Crea una nueva base para un empleado.
    """
    try:
        from decimal import Decimal as _Dec
        base_id = insertar_base(
            empleado_id=base.empleado_id,
            fecha=base.fecha,
            monto=_Dec(str(base.monto))
        )
        if base_id is None:
            raise HTTPException(status_code=400, detail="No se pudo crear la base.")

        # Obtener la base recién creada por id
        from .database.bases_db import obtener_base_por_id
        db_base = obtener_base_por_id(base_id)
        if db_base is None:
            raise HTTPException(status_code=500, detail="Base creada pero no encontrada.")
        return db_base
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error al crear base: {e}")
        raise HTTPException(status_code=500, detail="Error interno al crear la base.")

@app.put("/bases/{base_id}", response_model=Base)
def update_base_endpoint(base_id: int, base: BaseUpdate, principal: dict = Depends(get_current_principal)):
    """
    Actualiza una base existente.
    """
    try:
        from decimal import Decimal as _Dec
        from .database.bases_db import actualizar_base_por_id, obtener_base_por_id
        success = actualizar_base_por_id(base_id=base_id, nuevo_monto=_Dec(str(base.monto)))
        if not success:
            raise HTTPException(status_code=404, detail="Base no encontrada o no se pudo actualizar.")

        db_base = obtener_base_por_id(base_id)
        if db_base is None:
            raise HTTPException(status_code=404, detail="Base no encontrada después de actualizar.")
        return db_base
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error al actualizar base: {e}")
        raise HTTPException(status_code=500, detail="Error interno al actualizar la base.")

@app.delete("/bases/{base_id}")
def delete_base_endpoint(base_id: int, principal: dict = Depends(get_current_principal)):
    """
    Elimina una base.
    """
    try:
        from .database.bases_db import eliminar_base_por_id
        success = eliminar_base_por_id(base_id)
        if not success:
            raise HTTPException(status_code=404, detail="Base no encontrada.")
        return {"ok": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error al eliminar base: {e}")
        raise HTTPException(status_code=500, detail="Error interno al eliminar la base.")

@app.get("/empleados/{empleado_id}/bases/", response_model=List[Base])
def read_bases_by_empleado_endpoint(empleado_id: str, skip: int = 0, limit: int = 100):
    """
    Obtiene todas las bases de un empleado específico.
    """
    try:
        # Esta función necesita ser implementada en bases_db.py
        bases = []  # Temporalmente vacío hasta implementar la función
        return bases
    except Exception as e:
        logger.error(f"Error al obtener bases del empleado: {e}")
        raise HTTPException(status_code=500, detail="Error interno al consultar las bases del empleado.")

# --- Endpoints para Gastos ---

@app.get("/gastos/", response_model=List[Gasto])
def read_gastos_endpoint(skip: int = 0, limit: int = 100, principal: dict = Depends(get_current_principal)):
    """
    Obtiene una lista de todos los gastos.
    """
    try:
        gastos = obtener_todos_los_gastos(skip=skip, limit=limit)
        return gastos
    except Exception as e:
        logger.error(f"Error al obtener la lista de gastos: {e}")
        raise HTTPException(status_code=500, detail="Error interno al consultar los gastos.")

@app.post("/gastos/", response_model=Gasto, status_code=201)
def create_gasto_endpoint(gasto: GastoCreate, principal: dict = Depends(get_current_principal)):
    _enforce_empleado_scope(principal, gasto.empleado_identificacion)
    """
    Crea un nuevo gasto.
    """
    try:
        from decimal import Decimal as _Dec
        from datetime import datetime as _dt
        # Si no viene fecha, la función de DB la asume; aquí la normalizamos si viene string
        fecha_val = gasto.fecha
        gasto_id = agregar_gasto(
            empleado_identificacion=gasto.empleado_identificacion,
            tipo=gasto.tipo,
            valor=_Dec(str(gasto.valor)),
            fecha=fecha_val,
            observacion=gasto.observacion
        )
        if gasto_id is None:
            raise HTTPException(status_code=400, detail="No se pudo crear el gasto.")
        db_gasto = obtener_gasto_por_id(gasto_id)
        if db_gasto is None:
            raise HTTPException(status_code=500, detail="Gasto creado pero no encontrado.")
            
        # Recalcular caja
        try:
            from datetime import datetime, date, timezone as _tz
            f_calc = gasto.fecha
            # Si no hay fecha explícita, usar ahora en la zona horaria del usuario
            if not f_calc:
                try:
                    from zoneinfo import ZoneInfo
                    tz = ZoneInfo(principal.get("timezone")) if principal.get("timezone") else _tz.utc
                    f_calc = datetime.now(tz).date()
                except Exception:
                    f_calc = date.today()
            _ = recalcular_caja_dia(gasto.empleado_identificacion, f_calc, principal.get("timezone"))
        except Exception:
            pass

        return db_gasto
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error al crear gasto: {e}")
        raise HTTPException(status_code=500, detail="Error interno al crear el gasto.")

@app.get("/gastos/{gasto_id}", response_model=Gasto)
def read_gasto_endpoint(gasto_id: int, principal: dict = Depends(get_current_principal)):
    try:
        db_gasto = obtener_gasto_por_id(gasto_id)
        if db_gasto is None:
            raise HTTPException(status_code=404, detail="Gasto no encontrado.")
        return db_gasto
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error al obtener gasto: {e}")
        raise HTTPException(status_code=500, detail="Error interno al consultar el gasto.")

@app.put("/gastos/{gasto_id}", response_model=Gasto)
def update_gasto_endpoint(gasto_id: int, gasto: GastoUpdate, principal: dict = Depends(get_current_principal)):
    try:
        from decimal import Decimal as _Dec
        ok = actualizar_gasto(
            gasto_id,
            tipo=gasto.tipo,
            valor=_Dec(str(gasto.valor)) if gasto.valor is not None else None,
            observacion=gasto.observacion
        )
        if not ok:
            raise HTTPException(status_code=404, detail="Gasto no encontrado o no se pudo actualizar.")
        db_gasto = obtener_gasto_por_id(gasto_id)
        if db_gasto is None:
            raise HTTPException(status_code=404, detail="Gasto no encontrado después de actualizar.")
            
        # Recalcular caja
        try:
            from datetime import datetime, date, timezone as _tz
            f_creacion = db_gasto.get("fecha_creacion")
            if f_creacion:
                tz_name = principal.get("timezone")
                try:
                    from zoneinfo import ZoneInfo
                    tz = ZoneInfo(tz_name) if tz_name else _tz.utc
                    if isinstance(f_creacion, datetime):
                        if f_creacion.tzinfo is None:
                            f_creacion = f_creacion.replace(tzinfo=_tz.utc)
                        f_calc = f_creacion.astimezone(tz).date()
                    else:
                        f_calc = f_creacion
                except Exception:
                    f_calc = f_creacion if isinstance(f_creacion, date) else date.today()
                
                _ = recalcular_caja_dia(db_gasto.get("empleado_identificacion"), f_calc, tz_name)
        except Exception:
            pass

        return db_gasto
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error al actualizar gasto: {e}")
        raise HTTPException(status_code=500, detail="Error interno al actualizar el gasto.")

@app.delete("/gastos/{gasto_id}")
def delete_gasto_endpoint(gasto_id: int, principal: dict = Depends(get_current_principal)):
    try:
        # Obtener gasto previo para recalcular
        prev_gasto = obtener_gasto_por_id(gasto_id)

        ok = eliminar_gasto(gasto_id)
        if not ok:
            raise HTTPException(status_code=404, detail="Gasto no encontrado.")
            
        # Recalcular caja
        if prev_gasto:
            try:
                from datetime import datetime, date, timezone as _tz
                f_creacion = prev_gasto.get("fecha_creacion")
                if f_creacion:
                    tz_name = principal.get("timezone")
                    try:
                        from zoneinfo import ZoneInfo
                        tz = ZoneInfo(tz_name) if tz_name else _tz.utc
                        if isinstance(f_creacion, datetime):
                            if f_creacion.tzinfo is None:
                                f_creacion = f_creacion.replace(tzinfo=_tz.utc)
                            f_calc = f_creacion.astimezone(tz).date()
                        else:
                            f_calc = f_creacion
                    except Exception:
                        f_calc = f_creacion if isinstance(f_creacion, date) else date.today()
                    _ = recalcular_caja_dia(prev_gasto.get("empleado_identificacion"), f_calc, tz_name)
            except Exception:
                pass

        return {"ok": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error al eliminar gasto: {e}")
        raise HTTPException(status_code=500, detail="Error interno al eliminar el gasto.")

@app.get("/empleados/{empleado_id}/gastos/{fecha}", response_model=List[Gasto])
def read_gastos_by_empleado_fecha_endpoint(empleado_id: str, fecha: str, principal: dict = Depends(get_current_principal)):
    _enforce_empleado_scope(principal, empleado_id)
    """
    Obtiene todos los gastos de un empleado en una fecha específica.
    """
    try:
        tz_name = principal.get('timezone') or 'UTC'
        start_utc, end_utc = _day_bounds_utc_str(fecha, tz_name)
        start_naive = start_utc.replace(tzinfo=None)
        end_naive = end_utc.replace(tzinfo=None)
        from .database.connection_pool import DatabasePool as _DB
        gastos_tuplas = []
        with _DB.get_cursor() as cur:
            cur.execute(
                '''
                SELECT id, tipo, valor, observacion, fecha_creacion
                FROM gastos
                WHERE empleado_identificacion = %s
                  AND fecha_creacion >= %s AND fecha_creacion <= %s
                ORDER BY fecha_creacion DESC
                ''', (empleado_id, start_naive, end_naive)
            )
            gastos_tuplas = cur.fetchall() or []
        
        # Convertir tuplas a diccionarios para FastAPI
        gastos = []
        for row in gastos_tuplas:
            gasto = {
                'id': row[0],
                'tipo': row[1],
                'tipo_gasto_nombre': row[1],
                'valor': row[2],
                'observacion': row[3],
                'fecha_creacion': row[4],
                'empleado_identificacion': empleado_id,
                'fecha': fecha
            }
            gastos.append(gasto)
        return gastos
    except ValueError:
        raise HTTPException(status_code=400, detail="Formato de fecha inválido. Use YYYY-MM-DD.")
    except Exception as e:
        logger.error(f"Error al obtener gastos del empleado: {e}")
        raise HTTPException(status_code=500, detail="Error interno al consultar los gastos del empleado.")

# --- Endpoints de detalle para Liquidación (Tarjetas y Abonos por día) ---

@app.get("/empleados/{empleado_id}/tarjetas/canceladas/{fecha}", response_model=List[Tarjeta])
def read_tarjetas_canceladas_del_dia_endpoint(empleado_id: str, fecha: str, principal: dict = Depends(get_current_principal)):
    _enforce_empleado_scope(principal, empleado_id)
    """
    Lista las tarjetas canceladas en la fecha indicada para un empleado.
    """
    try:
        tz_name = principal.get('timezone') or 'UTC'
        # Para columnas DATE como fecha_cancelacion, comparar por fecha local directamente
        from datetime import datetime as _dt
        from zoneinfo import ZoneInfo as _ZI
        d_local = _dt.strptime(fecha, '%Y-%m-%d').date()
        # debug removido
        tarjetas: List[dict] = []
        with DatabasePool.get_cursor() as cursor:
            cursor.execute(
                '''
                SELECT 
                    t.codigo,
                    t.monto,
                    t.interes,
                    c.nombre AS cliente_nombre,
                    c.apellido AS cliente_apellido,
                    t.cuotas,
                    t.numero_ruta,
                    t.estado,
                    t.fecha_creacion,
                    t.cliente_identificacion,
                    t.empleado_identificacion,
                    t.observaciones,
                    t.fecha_cancelacion
                FROM tarjetas t
                JOIN clientes c ON c.identificacion = t.cliente_identificacion
                WHERE t.empleado_identificacion = %s
                  AND t.estado = 'cancelada'
                  AND t.fecha_cancelacion = %s
                ORDER BY t.numero_ruta
                ''', (empleado_id, d_local)
            )
            for row in cursor.fetchall() or []:
                tarjeta = {
                    'codigo': row[0],
                    'monto': row[1],
                    'interes': row[2],
                    'cliente': {
                        'nombre': row[3],
                        'apellido': row[4],
                        'identificacion': row[9]
                    },
                    'cuotas': row[5],
                    'numero_ruta': row[6],
                    'estado': row[7],
                    'fecha_creacion': row[8],
                    'cliente_identificacion': row[9],
                    'empleado_identificacion': row[10],
                    'observaciones': row[11],
                    'fecha_cancelacion': row[12]
                }
                # debug removido
                tarjetas.append(tarjeta)
        return tarjetas
    except ValueError:
        raise HTTPException(status_code=400, detail="Formato de fecha inválido. Use YYYY-MM-DD.")
    except Exception as e:
        logger.error(f"Error al obtener tarjetas canceladas del día: {e}")
        raise HTTPException(status_code=500, detail="Error interno al consultar tarjetas canceladas del día.")

@app.get("/empleados/{empleado_id}/tarjetas/nuevas/{fecha}", response_model=List[Tarjeta])
def read_tarjetas_nuevas_del_dia_endpoint(empleado_id: str, fecha: str, principal: dict = Depends(get_current_principal)):
    _enforce_empleado_scope(principal, empleado_id)
    """
    Lista las tarjetas creadas en la fecha indicada para un empleado.
    """
    try:
        tz_name = principal.get('timezone') or 'UTC'
        # Para tarjetas nuevas usamos fecha_creacion (timestamp) → BETWEEN por día local convertido a UTC
        start_utc, end_utc = _day_bounds_utc_str(fecha, tz_name)
        start_naive = start_utc.replace(tzinfo=None)
        end_naive = end_utc.replace(tzinfo=None)
        tarjetas: List[dict] = []
        with DatabasePool.get_cursor() as cursor:
            # Con la migración, fecha_creacion es TIMESTAMP (UTC) → usar siempre límites UTC naive
            cursor.execute(
                '''
                SELECT 
                    t.codigo,
                    t.monto,
                    t.interes,
                    c.nombre AS cliente_nombre,
                    c.apellido AS cliente_apellido,
                    c.telefono AS cliente_telefono,
                    c.direccion AS cliente_direccion,
                    t.cuotas,
                    t.numero_ruta,
                    t.estado,
                    t.fecha_creacion,
                    t.cliente_identificacion,
                    t.empleado_identificacion,
                    t.observaciones,
                    t.fecha_cancelacion
                FROM tarjetas t
                JOIN clientes c ON c.identificacion = t.cliente_identificacion
                WHERE t.empleado_identificacion = %s
                  AND t.fecha_creacion >= %s AND t.fecha_creacion <= %s
                ORDER BY t.numero_ruta
                ''', (empleado_id, start_naive, end_naive)
            )
            rows = cursor.fetchall() or []
            for row in rows:
                tarjeta = {
                    'codigo': row[0],
                    'monto': row[1],
                    'interes': row[2],
                    'cliente': {
                        'nombre': row[3],
                        'apellido': row[4],
                        'telefono': row[5],
                        'direccion': row[6],
                        'identificacion': row[11]
                    },
                    'cuotas': row[7],
                    'numero_ruta': row[8],
                    'estado': row[9],
                    'fecha_creacion': row[10],
                    'cliente_identificacion': row[11],
                    'empleado_identificacion': row[12],
                    'observaciones': row[13],
                    'fecha_cancelacion': row[14]
                }
                # Añadir fecha local (día) para UI consistente
                try:
                    from datetime import timezone as _tz
                    from zoneinfo import ZoneInfo as _ZI
                    import datetime as _dtmod
                    dt = row[10]
                    if dt is not None:
                        if getattr(dt, 'tzinfo', None) is None:
                            dt = dt.replace(tzinfo=_tz.utc)
                        local_dt = dt.astimezone(_ZI(tz_name))
                        tarjeta['fecha'] = local_dt.date().isoformat()
                except Exception:
                    pass
                tarjetas.append(tarjeta)
        return tarjetas
    except ValueError:
        raise HTTPException(status_code=400, detail="Formato de fecha inválido. Use YYYY-MM-DD.")
    except Exception as e:
        logger.error(f"Error al obtener tarjetas nuevas del día: {e}")
        raise HTTPException(status_code=500, detail="Error interno al consultar tarjetas nuevas del día.")

@app.get("/empleados/{empleado_id}/abonos/{fecha}")
def read_abonos_del_dia_endpoint(empleado_id: str, fecha: str, principal: dict = Depends(get_current_principal)):
    _enforce_empleado_scope(principal, empleado_id)
    """
    Lista los abonos del día para un empleado (join abonos + tarjetas).
    """
    try:
        tz_name = principal.get('timezone') or 'UTC'
        start_utc, end_utc = _day_bounds_utc_str(fecha, tz_name)
        start_naive = start_utc.replace(tzinfo=None)
        end_naive = end_utc.replace(tzinfo=None)
        abonos: List[dict] = []
        with DatabasePool.get_cursor() as cursor:
            cursor.execute(
                '''
                SELECT a.id, a.fecha, a.monto, a.indice_orden, a.tarjeta_codigo, a.metodo_pago,
                       t.monto AS tarjeta_monto,
                       c.nombre, c.apellido
                FROM abonos a
                JOIN tarjetas t ON a.tarjeta_codigo = t.codigo
                JOIN clientes c ON t.cliente_identificacion = c.identificacion
                WHERE t.empleado_identificacion = %s
                  AND a.fecha >= %s AND a.fecha <= %s
                ORDER BY a.fecha, a.id
                ''', (empleado_id, start_naive, end_naive)
            )
            for row in cursor.fetchall() or []:
                abono = {
                    'id': row[0],
                    'fecha': row[1],
                    'monto': row[2],
                    'indice_orden': row[3],
                    'tarjeta_codigo': row[4],
                    'metodo_pago': row[5],
                    'tarjeta_monto': row[6],
                    'cliente_nombre': row[7],
                    'cliente_apellido': row[8]
                }
                abonos.append(abono)
        return abonos
    except ValueError:
        raise HTTPException(status_code=400, detail="Formato de fecha inválido. Use YYYY-MM-DD.")
    except Exception as e:
        logger.error(f"Error al obtener abonos del día: {e}")
        raise HTTPException(status_code=500, detail="Error interno al consultar abonos del día.")

@app.get("/empleados/{empleado_id}/gastos/{fecha}/resumen", response_model=List[ResumenGasto])
def read_resumen_gastos_by_empleado_fecha_endpoint(empleado_id: str, fecha: str, principal: dict = Depends(get_current_principal)):
    """
    Obtiene el resumen de gastos de un empleado en una fecha específica.
    """
    try:
        tz_name = principal.get('timezone') or 'UTC'
        start_utc, end_utc = _day_bounds_utc_str(fecha, tz_name)
        start_naive = start_utc.replace(tzinfo=None)
        end_naive = end_utc.replace(tzinfo=None)
        from .database.connection_pool import DatabasePool as _DB
        with _DB.get_cursor() as cur:
            cur.execute(
                '''SELECT COALESCE(SUM(valor),0) FROM gastos WHERE empleado_identificacion=%s AND fecha_creacion >= %s AND fecha_creacion <= %s''',
                (empleado_id, start_naive, end_naive)
            )
            total = cur.fetchone()[0] or 0
            cur.execute(
                '''SELECT COUNT(*) FROM gastos WHERE empleado_identificacion=%s AND fecha_creacion >= %s AND fecha_creacion <= %s''',
                (empleado_id, start_naive, end_naive)
            )
            conteo = cur.fetchone()[0] or 0
        
        # Crear resumen
        resumen = [{
            'empleado_identificacion': empleado_id,
            'fecha': fecha,
            'total_gastos': total,
            'cantidad_gastos': conteo
        }]
        return resumen
    except ValueError:
        raise HTTPException(status_code=400, detail="Formato de fecha inválido. Use YYYY-MM-DD.")
    except Exception as e:
        logger.error(f"Error al obtener resumen de gastos: {e}")
        raise HTTPException(status_code=500, detail="Error interno al consultar el resumen de gastos.")

@app.get("/gastos/fecha/{fecha}", response_model=List[Gasto])
def read_gastos_by_fecha_endpoint(fecha: str, tipo: Optional[str] = None):
    """
    Obtiene todos los gastos de una fecha específica, opcionalmente filtrados por tipo.
    """
    try:
        from datetime import datetime
        fecha_obj = datetime.strptime(fecha, '%Y-%m-%d').date()
        
        from .database.gastos_db import obtener_gastos_por_tipo_y_fecha
        gastos_tuplas = obtener_gastos_por_tipo_y_fecha(fecha_obj, tipo)
        
        # Convertir tuplas a diccionarios para FastAPI
        gastos = []
        for row in gastos_tuplas:
            gasto = {
                'empleado_identificacion': row[0],
                'tipo': row[1],
                'tipo_gasto_nombre': row[1],
                'valor': row[2],
                'observacion': row[3],
                'fecha_creacion': row[4],
                'fecha': fecha_obj
            }
            gastos.append(gasto)
        return gastos
    except ValueError:
        raise HTTPException(status_code=400, detail="Formato de fecha inválido. Use YYYY-MM-DD.")
    except Exception as e:
        logger.error(f"Error al obtener gastos por fecha: {e}")
        raise HTTPException(status_code=500, detail="Error interno al consultar los gastos por fecha.")

# --- Endpoints para Tarjetas ---

@app.get("/tarjetas/", response_model=List[Tarjeta])
def read_tarjetas_endpoint(estado: str = 'activas', skip: int = 0, limit: int = 100, principal: dict = Depends(get_current_principal)):
    """
    Obtiene una lista de todas las tarjetas filtradas por estado.
    """
    try:
        # Usar la función original que acepta filtros
        from .database.tarjetas_db import obtener_tarjetas
        tarjetas_tuplas = obtener_tarjetas(empleado_identificacion=None, estado=estado, offset=skip, limit=limit)
        
        # Convertir tuplas a diccionarios para FastAPI con estructura anidada
        tarjetas = []
        for row in tarjetas_tuplas:
            # Normalizar fecha_creacion (puede venir NULL en datos antiguos)
            try:
                from datetime import datetime as _dt
                fc = row[8]
                if fc is None:
                    fc_norm = _dt.utcnow()
                elif hasattr(fc, 'year') and not hasattr(fc, 'hour'):
                    # es date, convertir a datetime
                    fc_norm = _dt(fc.year, fc.month, fc.day, 0, 0, 0)
                else:
                    fc_norm = fc
            except Exception:
                from datetime import datetime as _dt
                fc_norm = _dt.utcnow()

            tarjeta = {
                'codigo': row[0],
                'monto': float(row[1]) if row[1] is not None else 0.0, 
                'interes': row[2],
                'cliente': {
                    'nombre': row[3],
                    'apellido': row[4],
                    'identificacion': row[9]
                },
                'cuotas': row[5],
                'numero_ruta': row[6],
                'estado': row[7],
                'fecha_creacion': fc_norm,
                'cliente_identificacion': row[9],
                'empleado_identificacion': row[10],
                'observaciones': row[11],
                'fecha_cancelacion': row[12],
                'modalidad_pago': (row[13] if len(row) > 13 else 'diario') or 'diario'
            }
            tarjetas.append(tarjeta)
        return tarjetas
    except Exception as e:
        logger.error(f"Error al obtener la lista de tarjetas: {e}")
        raise HTTPException(status_code=500, detail="Error interno al consultar las tarjetas.")

@app.get("/tarjetas/buscar", response_model=List[Tarjeta])
def buscar_tarjetas_endpoint(
    termino: str, 
    empleado_id: Optional[str] = None, 
    estado: str = 'activas',
    principal: dict = Depends(get_current_principal)
):
    """
    Busca tarjetas por nombre o apellido del cliente.
    """
    if empleado_id:
        _enforce_empleado_scope(principal, empleado_id)
        
    try:
        hits = buscar_tarjetas(termino, empleado_id, estado)
        resultados = []
        for hit in hits:
            # hit[0] es codigo
            t_full = obtener_tarjeta_por_codigo(hit[0])
            if t_full:
                 # Convert dict to Tarjeta schema structure
                 # La estructura de t_full (dict) coincide con el esquema Pydantic Tarjeta
                 # excepto que 'cliente' debe ser un objeto/dict
                 
                 tarjeta = {
                    'codigo': t_full['codigo'],
                    'monto': float(t_full['monto']),
                    'interes': t_full['interes'],
                    'cliente': {
                        'identificacion': t_full['cliente_identificacion'],
                        'nombre': t_full['cliente_nombre'],
                        'apellido': t_full['cliente_apellido']
                    },
                    'cuotas': t_full['cuotas'],
                    'numero_ruta': float(t_full['numero_ruta']) if t_full['numero_ruta'] else 0.0,
                    'estado': t_full['estado'],
                    'fecha_creacion': t_full['fecha_creacion'],
                    'cliente_identificacion': t_full['cliente_identificacion'],
                    'empleado_identificacion': t_full['empleado_identificacion'],
                    'observaciones': t_full['observaciones'],
                    'fecha_cancelacion': t_full['fecha_cancelacion'],
                    'modalidad_pago': t_full.get('modalidad_pago', 'diario')
                }
                 resultados.append(tarjeta)
        return resultados

    except Exception as e:
        logger.error(f"Error buscando tarjetas: {e}")
        raise HTTPException(status_code=500, detail="Error buscando tarjetas")

@app.get("/tarjetas/{tarjeta_codigo}", response_model=Tarjeta)
def read_tarjeta_endpoint(tarjeta_codigo: str, principal: dict = Depends(get_current_principal)):
    """
    Obtiene una tarjeta específica por su código.
    """
    try:
        db_tarjeta = obtener_tarjeta_por_codigo(tarjeta_codigo)
        if db_tarjeta is None:
            raise HTTPException(status_code=404, detail="Tarjeta no encontrada")
        # Adaptar a esquema Tarjeta (añadir cliente anidado)
        db_tarjeta["cliente"] = {
            "identificacion": db_tarjeta.get("cliente_identificacion", ""),
            "nombre": db_tarjeta.get("cliente_nombre", ""),
            "apellido": db_tarjeta.get("cliente_apellido", "")
        }
        return db_tarjeta
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error al obtener tarjeta: {e}")
        raise HTTPException(status_code=500, detail="Error interno al consultar la tarjeta.")

@app.put("/tarjetas/rutas/masivo")
def update_rutas_masivo_endpoint(items: List[RutaUpdateItem], principal: dict = Depends(get_current_principal)):
    """
    Actualiza masivamente las rutas de las tarjetas.
    """
    # Convert to list of tuples for DB function
    updates = [(item.codigo, item.numero_ruta) for item in items]
    
    if actualizar_rutas_masivo(updates):
        return {"ok": True, "message": "Rutas actualizadas correctamente"}
    else:
        raise HTTPException(status_code=500, detail="Error al actualizar rutas")

@app.get("/empleados/{empleado_id}/tarjetas/", response_model=List[Tarjeta])
def read_tarjetas_by_empleado_endpoint(
    empleado_id: str,
    estado: str = 'activas',
    skip: int = 0,
    limit: int = 100,
    desde: Optional[date] = None,
    principal: dict = Depends(get_current_principal),
):
    _enforce_empleado_scope(principal, empleado_id)
    """
    Obtiene una lista de tarjetas de un empleado específico filtradas por estado.
    """
    try:
        tz_name = principal.get('timezone') or 'UTC'
        # Usar la función existente obtener_tarjetas con empleado_identificacion y estado
        # use_cache=False: En producción (AWS App Runner) hay múltiples instancias,
        # cada una con su propio caché en memoria. El _cache.clear() de una instancia
        # no afecta a las otras, causando datos obsoletos.
        from .database.tarjetas_db import obtener_tarjetas
        tarjetas_tuplas = obtener_tarjetas(
            empleado_identificacion=empleado_id,
            estado=estado,
            offset=skip,
            limit=limit,
            use_cache=False,
            fecha_cancelacion_desde=desde,
        )
        
        # Convertir tuplas a diccionarios para FastAPI con estructura anidada
        tarjetas = []
        for row in tarjetas_tuplas:
            # Normalizar fecha_creacion
            try:
                from datetime import datetime as _dt
                from datetime import timezone as _tz
                from zoneinfo import ZoneInfo as _ZI
                fc = row[8]
                if fc is None:
                    fc_norm = _dt.utcnow()
                elif hasattr(fc, 'year') and not hasattr(fc, 'hour'):
                    fc_norm = _dt(fc.year, fc.month, fc.day, 0, 0, 0)
                else:
                    fc_norm = fc
                # Derivar fecha_local consistente: si el valor original era DATE (sin hora), tomarlo tal cual;
                # si era TIMESTAMP, convertir a tz local y extraer el día
                try:
                    if hasattr(fc, 'year') and not hasattr(fc, 'hour'):
                        fecha_local_str = fc.isoformat()
                    else:
                        _base = fc_norm
                        if getattr(_base, 'tzinfo', None) is None:
                            _base = _base.replace(tzinfo=_tz.utc)
                        _loc = _base.astimezone(_ZI(tz_name))
                        fecha_local_str = _loc.date().isoformat()
                except Exception:
                    fecha_local_str = None
            except Exception:
                from datetime import datetime as _dt
                fc_norm = _dt.utcnow()
                fecha_local_str = None

            tarjeta = {
                'codigo': row[0],
                'monto': float(row[1]) if row[1] is not None else 0.0, 
                'interes': row[2],
                'cliente': {
                    'nombre': row[3],
                    'apellido': row[4],
                    'identificacion': row[9]
                },
                'cuotas': row[5],
                'numero_ruta': row[6],
                'estado': row[7],
                'fecha_creacion': fc_norm,
                'fecha': fecha_local_str,
                'cliente_identificacion': row[9],
                'empleado_identificacion': row[10],
                'observaciones': row[11],
                'fecha_cancelacion': row[12],
                'modalidad_pago': (row[13] if len(row) > 13 else 'diario') or 'diario'
            }
            tarjetas.append(tarjeta)
        return tarjetas
    except Exception as e:
        logger.error(f"Error al obtener las tarjetas del empleado: {e}")
        raise HTTPException(status_code=500, detail="Error interno al consultar las tarjetas del empleado.")

@app.get("/empleados/{empleado_id}/clientes", response_model=List[ClienteBase])
def list_clientes_por_empleado_endpoint(
    empleado_id: str,
    scope: str = 'todos',
    principal: dict = Depends(get_current_principal)
):
    """
    Lista los clientes asociados a un empleado.
    scope: 'todos' o 'activos'
    """
    _enforce_empleado_scope(principal, empleado_id)
    
    solo_activos = (scope == 'activos')
    clientes = listar_clientes_por_empleado(empleado_id, solo_activos)
    
    # Mapear a ClienteBase
    resultados = []
    for c in clientes:
        resultados.append({
            "identificacion": c["identificacion"],
            "nombre": c["nombre"],
            "apellido": c["apellido"],
            "telefono": c.get("telefono"),
            "direccion": c.get("direccion"),
            "email": None,
            "profesion": None,
            "empresa": None,
            "referencia_nombre": None,
            "referencia_telefono": None,
            "observaciones": None
        })
    return resultados

# --- Endpoints para Clientes (Ejemplos) ---

@app.post("/clientes/", response_model=Cliente, status_code=201)
def create_cliente_endpoint(cliente: ClienteCreate):
    nuevo = crear_cliente(
        identificacion=cliente.identificacion,
        nombre=cliente.nombre,
        apellido=cliente.apellido,
        telefono=cliente.telefono,
        direccion=cliente.direccion,
        observaciones=cliente.observaciones
    )
    if not nuevo:
        raise HTTPException(status_code=400, detail="No se pudo crear el cliente, la identificación podría ya existir.")
    return nuevo

@app.get("/clientes/{identificacion}/rastreo", response_model=ClienteClavo)
def rastrear_cliente_clavo(identificacion: str, principal: dict = Depends(get_current_principal)):
    """
    Busca un cliente por identificación para rastreo ('Encontrar clavo').
    Devuelve datos personales y fecha de la última tarjeta.
    """
    # No filtramos por empleado, permitimos buscar en la base global (del admin)
    # asumiendo que el 'clavo' puede estar en otra ruta.
    
    data = buscar_datos_clavo(identificacion)
    if not data:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
        
    return data

@app.get("/clientes/{identificacion}", response_model=Optional[Cliente])
def read_cliente_endpoint(identificacion: str):
    db_cliente = obtener_cliente_por_identificacion(identificacion)
    # Si no existe, devolver 200 con null para permitir flujos donde el cliente aún no está registrado
    if db_cliente is None:
        return None
    return db_cliente

@app.put("/clientes/{identificacion}", response_model=Cliente)
def update_cliente_endpoint(identificacion: str, cliente: ClienteUpdate):
    try:
        ok = actualizar_cliente(
            identificacion=identificacion,
            nombre=cliente.nombre or "",
            apellido=cliente.apellido or "",
            telefono=cliente.telefono,
            direccion=cliente.direccion,
            observaciones=cliente.observaciones
        )
        if not ok:
            raise HTTPException(status_code=404, detail="Cliente no encontrado o no se pudo actualizar")
        db_cliente = obtener_cliente_por_identificacion(identificacion)
        return db_cliente
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error al actualizar cliente: {e}")
        raise HTTPException(status_code=500, detail="Error interno al actualizar cliente")

@app.get("/clientes/{identificacion}/historial")
def read_cliente_historial_endpoint(identificacion: str, principal: dict = Depends(get_current_principal)):
    """
    Obtiene el historial de tarjetas de un cliente.
    Solo muestra tarjetas de empleados de la cuenta del usuario logueado (aislamiento multi-tenant).
    """
    try:
        from .database.tarjetas_db import obtener_historial_cliente
        cuenta_id = principal.get("cuenta_id")
        return obtener_historial_cliente(identificacion, cuenta_id=cuenta_id)
    except Exception as e:
        logger.error(f"Error al obtener historial de cliente: {e}")
        raise HTTPException(status_code=500, detail="Error interno al consultar historial")

@app.get("/clientes/{identificacion}/estadisticas")
def read_cliente_estadisticas_endpoint(identificacion: str, principal: dict = Depends(get_current_principal)):
    """
    Obtiene estadísticas de tarjetas de un cliente.
    Solo cuenta tarjetas de empleados de la cuenta del usuario logueado (aislamiento multi-tenant).
    """
    try:
        from .database.tarjetas_db import obtener_estadisticas_cliente
        cuenta_id = principal.get("cuenta_id")
        return obtener_estadisticas_cliente(identificacion, cuenta_id=cuenta_id)
    except Exception as e:
        logger.error(f"Error al obtener estadísticas de cliente: {e}")
        raise HTTPException(status_code=500, detail="Error interno al consultar estadísticas")

# --- Endpoints para Tarjetas (crear/actualizar/eliminar) ---

@app.post("/tarjetas/", response_model=Tarjeta, status_code=201)
def create_tarjeta_endpoint(tarjeta: TarjetaCreate, principal: dict = Depends(get_current_principal)):
    _enforce_empleado_scope(principal, tarjeta.empleado_identificacion)
    try:
        # 0) Si el cliente ya existe y el frontend envió cambios en nombre/apellido/telefono/direccion,
        # actualizarlos primero para que no se pierdan al sincronizar
        try:
            cli = obtener_cliente_por_identificacion(tarjeta.cliente_identificacion)
            # El modelo TarjetaCreate no incluye los datos del cliente; en flujos online puro no hay cambios aquí.
            # Esta lógica se maneja mejor en /sync; aquí no hay payload de cliente.
            # Se deja el bloque por claridad y posible extensión futura.
            _ = cli  # no-op
        except Exception:
            pass
        tz_name = principal.get("timezone") or "UTC"
        codigo = crear_tarjeta(
            cliente_identificacion=tarjeta.cliente_identificacion,
            empleado_identificacion=tarjeta.empleado_identificacion,
            monto=Decimal(tarjeta.monto),
            cuotas=tarjeta.cuotas,
            interes=tarjeta.interes,
            modalidad_pago=getattr(tarjeta, 'modalidad_pago', None) or 'diario',
            numero_ruta=Decimal(str(tarjeta.numero_ruta)) if tarjeta.numero_ruta is not None else None,
            observaciones=tarjeta.observaciones,
            posicion_anterior=Decimal(str(tarjeta.posicion_anterior)) if tarjeta.posicion_anterior is not None else None,
            posicion_siguiente=Decimal(str(tarjeta.posicion_siguiente)) if tarjeta.posicion_siguiente is not None else None,
            fecha_creacion=tarjeta.fecha_creacion
        )
        if not codigo:
            raise HTTPException(status_code=400, detail="No se pudo crear la tarjeta.")
        db_tarjeta = obtener_tarjeta_por_codigo(codigo)
        if db_tarjeta is None:
            raise HTTPException(status_code=500, detail="Tarjeta creada pero no encontrada.")
        # Nota: fecha_creacion ya fue aplicada en crear_tarjeta si vino en el payload
        # Adaptar a esquema Tarjeta (añadir cliente anidado si aplica)
        db_tarjeta["cliente"] = {
            "identificacion": db_tarjeta.get("cliente_identificacion", tarjeta.cliente_identificacion),
            "nombre": db_tarjeta.get("cliente_nombre", ""),
            "apellido": db_tarjeta.get("cliente_apellido", "")
        }
        # Recalcular caja del día de la tarjeta nueva
        try:
            from datetime import datetime as _dt, date, timezone as _tz
            fecha_dt = tarjeta.fecha_creacion
            if fecha_dt and isinstance(fecha_dt, str):
                try:
                    fecha_dt = _dt.fromisoformat(fecha_dt.replace('Z', '+00:00'))
                except Exception:
                    fecha_dt = None
            
            # Ajustar a zona horaria local para saber el día de caja
            try:
                from zoneinfo import ZoneInfo
                tz = ZoneInfo(tz_name) if tz_name else _tz.utc
                if fecha_dt:
                    if fecha_dt.tzinfo is None:
                        fecha_dt = fecha_dt.replace(tzinfo=_tz.utc)
                    fecha_dia = fecha_dt.astimezone(tz).date()
                else:
                    fecha_dia = _dt.now(tz).date()
            except Exception:
                fecha_dia = date.today()

            _ = recalcular_caja_dia(tarjeta.empleado_identificacion, fecha_dia, tz_name)
        except Exception:
            pass
        return db_tarjeta
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error al crear tarjeta: {e}")
        raise HTTPException(status_code=500, detail="Error interno al crear la tarjeta.")

@app.put("/tarjetas/{tarjeta_codigo}", response_model=Tarjeta)
def update_tarjeta_endpoint(tarjeta_codigo: str, tarjeta: TarjetaUpdate, principal: dict = Depends(get_current_principal)):
    try:
        # Si hay cambio de estado explícito, usar función dedicada
        if tarjeta.estado is not None:
            ok = actualizar_estado_tarjeta(tarjeta_codigo, tarjeta.estado)
            if not ok:
                raise HTTPException(status_code=404, detail="Tarjeta no encontrada o no se pudo actualizar el estado.")
        # Actualizar otros campos
        ok2 = actualizar_tarjeta(
            tarjeta_codigo=tarjeta_codigo,
            monto=Decimal(tarjeta.monto) if tarjeta.monto is not None else None,
            cuotas=tarjeta.cuotas,
            numero_ruta=Decimal(str(tarjeta.numero_ruta)) if tarjeta.numero_ruta is not None else None,
            interes=tarjeta.interes,
            observaciones=tarjeta.observaciones,
            modalidad_pago=getattr(tarjeta, 'modalidad_pago', None)
        )
        if not ok2 and tarjeta.estado is None:
            raise HTTPException(status_code=404, detail="Tarjeta no encontrada o no se pudo actualizar.")
        db_tarjeta = obtener_tarjeta_por_codigo(tarjeta_codigo)
        if db_tarjeta is None:
            raise HTTPException(status_code=404, detail="Tarjeta no encontrada después de actualizar.")
        db_tarjeta["cliente"] = {
            "identificacion": db_tarjeta.get("cliente_identificacion", ""),
            "nombre": db_tarjeta.get("cliente_nombre", ""),
            "apellido": db_tarjeta.get("cliente_apellido", "")
        }
        return db_tarjeta
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error al actualizar tarjeta: {e}")
        raise HTTPException(status_code=500, detail="Error interno al actualizar la tarjeta.")

@app.delete("/tarjetas/{tarjeta_codigo}")
def delete_tarjeta_endpoint(tarjeta_codigo: str, principal: dict = Depends(get_current_principal)):
    try:
        # Obtener info antes de eliminar para recalcular caja
        tarjeta = obtener_tarjeta_por_codigo(tarjeta_codigo)
        
        ok = eliminar_tarjeta(tarjeta_codigo)
        if not ok:
            raise HTTPException(status_code=404, detail="Tarjeta no encontrada o no se pudo eliminar.")
            
        # Recalcular caja (resta el préstamo eliminado)
        if tarjeta:
            try:
                from datetime import datetime, date, timezone as _tz
                f_creacion = tarjeta.get("fecha_creacion")
                if f_creacion:
                    try:
                        from zoneinfo import ZoneInfo
                        tz = ZoneInfo(principal.get("timezone")) if principal.get("timezone") else _tz.utc
                        if isinstance(f_creacion, datetime):
                            if f_creacion.tzinfo is None:
                                f_creacion = f_creacion.replace(tzinfo=_tz.utc)
                            f_calc = f_creacion.astimezone(tz).date()
                        elif isinstance(f_creacion, date):
                            f_calc = f_creacion
                        else:
                            f_calc = date.today()
                    except Exception:
                        f_calc = date.today()
                    
                    _ = recalcular_caja_dia(tarjeta["empleado_identificacion"], f_calc, principal.get("timezone"))
            except Exception:
                pass
                
        return {"ok": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error al eliminar tarjeta: {e}")
        raise HTTPException(status_code=500, detail="Error interno al eliminar la tarjeta.")

# --- Endpoints para Abonos ---

@app.get("/tarjetas/{tarjeta_codigo}/abonos/", response_model=List[Abono])
def read_abonos_by_tarjeta_endpoint(tarjeta_codigo: str, principal: dict = Depends(get_current_principal)):
    """
    Obtiene todos los abonos de una tarjeta específica.
    """
    try:
        from .database.abonos_db import obtener_abonos_tarjeta
        abonos_tuplas = obtener_abonos_tarjeta(tarjeta_codigo)
        
        # Convertir tuplas a diccionarios para FastAPI
        abonos = []
        for row in abonos_tuplas:
            abono = {
                'id': row[0],
                'fecha': row[1],
                'monto': row[2],
                'indice_orden': int(row[3]) if row[3] is not None else 0,
                'metodo_pago': row[4] or 'efectivo',
                'tarjeta_codigo': tarjeta_codigo
            }
            abonos.append(abono)
        return abonos
    except Exception as e:
        logger.error(f"Error al obtener abonos de la tarjeta: {e}")
        raise HTTPException(status_code=500, detail="Error interno al consultar los abonos.")

@app.get("/abonos/{abono_id}", response_model=Abono)
def read_abono_endpoint(abono_id: int, principal: dict = Depends(get_current_principal)):
    """
    Obtiene un abono específico por su ID.
    """
    try:
        abono = obtener_abono_por_id(abono_id)
        if abono is None:
            raise HTTPException(status_code=404, detail="Abono no encontrado.")
        # Normalizar campos opcionales
        try:
            if abono.get('indice_orden') is None:
                abono['indice_orden'] = 0
            else:
                abono['indice_orden'] = int(abono.get('indice_orden') or 0)
        except Exception:
            abono['indice_orden'] = 0
        abono['metodo_pago'] = (abono.get('metodo_pago') or 'efectivo')
        return abono
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error al obtener abono: {e}")
        raise HTTPException(status_code=500, detail="Error interno al consultar el abono.")

@app.post("/abonos/", response_model=Abono, status_code=201)
def create_abono_endpoint(abono: AbonoCreate, principal: dict = Depends(get_current_principal)):
    """
    Registra un nuevo abono.
    """
    try:
        metodo = (abono.metodo_pago or 'efectivo').lower()
        if metodo not in ('efectivo','consignacion'):
            raise HTTPException(status_code=400, detail="metodo_pago inválido")
        abono_id = registrar_abono(
            tarjeta_codigo=abono.tarjeta_codigo,
            monto=Decimal(str(abono.monto)),
            metodo_pago=metodo,
            fecha=abono.fecha
        )
        if abono_id is None:
            raise HTTPException(status_code=400, detail="No se pudo registrar el abono.")
        
        # Obtener el abono recién creado
        db_abono = obtener_abono_por_id(abono_id)
        if db_abono is None:
            raise HTTPException(status_code=500, detail="Abono creado pero no encontrado.")
        # Normalizar campos opcionales
        try:
            if db_abono.get('indice_orden') is None:
                db_abono['indice_orden'] = 0
            else:
                db_abono['indice_orden'] = int(db_abono.get('indice_orden') or 0)
        except Exception:
            db_abono['indice_orden'] = 0
        db_abono['metodo_pago'] = (db_abono.get('metodo_pago') or 'efectivo')

        # Recalcular caja del día automáticamente
        try:
            tarjeta_info = obtener_tarjeta_por_codigo(abono.tarjeta_codigo)
            if tarjeta_info:
                from datetime import datetime, date, timezone as _tz
                try:
                    from zoneinfo import ZoneInfo
                    tz = ZoneInfo(principal.get("timezone")) if principal.get("timezone") else _tz.utc
                    f_calc = datetime.now(tz).date()
                    if abono.fecha:
                        dt_ref = abono.fecha
                        if dt_ref.tzinfo is None:
                            dt_ref = dt_ref.replace(tzinfo=_tz.utc)
                        f_calc = dt_ref.astimezone(tz).date()
                except Exception:
                    f_calc = date.today()
                
                _ = recalcular_caja_dia(tarjeta_info["empleado_identificacion"], f_calc, principal.get("timezone"))
        except Exception:
            pass

        return db_abono
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error al crear abono: {e}")
        raise HTTPException(status_code=500, detail="Error interno al crear el abono.")

@app.put("/abonos/{abono_id}", response_model=Abono)
def update_abono_endpoint(abono_id: int, abono: AbonoUpdate, principal: dict = Depends(get_current_principal)):
    """
    Actualiza un abono existente.
    """
    try:
        success = actualizar_abono(abono_id, Decimal(str(abono.monto)) if abono.monto is not None else None, abono.fecha)
        if not success:
            raise HTTPException(status_code=404, detail="Abono no encontrado o no se pudo actualizar.")
        
        # Obtener el abono actualizado
        db_abono = obtener_abono_por_id(abono_id)
        if db_abono is None:
            raise HTTPException(status_code=500, detail="Abono actualizado pero no encontrado.")
        # Normalizar campos opcionales
        try:
            if db_abono.get('indice_orden') is None:
                db_abono['indice_orden'] = 0
            else:
                db_abono['indice_orden'] = int(db_abono.get('indice_orden') or 0)
        except Exception:
            db_abono['indice_orden'] = 0
        db_abono['metodo_pago'] = (db_abono.get('metodo_pago') or 'efectivo')

        # Recalcular caja y estado tarjeta
        try:
            tarjeta_info = obtener_tarjeta_por_codigo(db_abono.get("tarjeta_codigo"))
            if tarjeta_info:
                from datetime import datetime, date, timezone as _tz
                try:
                    from zoneinfo import ZoneInfo
                    tz = ZoneInfo(principal.get("timezone")) if principal.get("timezone") else _tz.utc
                    f_calc = datetime.now(tz).date()
                    if db_abono.get('fecha'):
                        dt_ref = db_abono['fecha']
                        if isinstance(dt_ref, datetime):
                            if dt_ref.tzinfo is None:
                                dt_ref = dt_ref.replace(tzinfo=_tz.utc)
                            f_calc = dt_ref.astimezone(tz).date()
                        elif isinstance(dt_ref, date):
                            f_calc = dt_ref
                except Exception:
                    f_calc = date.today()
                _ = recalcular_caja_dia(tarjeta_info["empleado_identificacion"], f_calc, principal.get("timezone"))
                # Verificar si debe reactivarse o cancelarse
                verificar_reactivacion_tarjeta(db_abono.get("tarjeta_codigo"))
        except Exception:
            pass

        return db_abono
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error al actualizar abono: {e}")
        raise HTTPException(status_code=500, detail="Error interno al actualizar el abono.")

@app.delete("/abonos/{abono_id}")
def delete_abono_endpoint(abono_id: int, principal: dict = Depends(get_current_principal)):
    """
    Elimina un abono.
    """
    try:
        # Obtener datos para recalcular antes de eliminar
        prev_abono = obtener_abono_por_id(abono_id)

        success = eliminar_abono_por_id(abono_id)
        if not success:
            raise HTTPException(status_code=404, detail="Abono no encontrado.")
            
        # Recalcular caja y estado tarjeta
        if prev_abono:
            try:
                tarjeta_info = obtener_tarjeta_por_codigo(prev_abono.get("tarjeta_codigo"))
                if tarjeta_info:
                    from datetime import datetime, date, timezone as _tz
                    try:
                        from zoneinfo import ZoneInfo
                        tz = ZoneInfo(principal.get("timezone")) if principal.get("timezone") else _tz.utc
                        f_calc = datetime.now(tz).date()
                        if prev_abono.get('fecha'):
                            dt_ref = prev_abono['fecha']
                            if isinstance(dt_ref, datetime):
                                if dt_ref.tzinfo is None:
                                    dt_ref = dt_ref.replace(tzinfo=_tz.utc)
                                f_calc = dt_ref.astimezone(tz).date()
                            elif isinstance(dt_ref, date):
                                f_calc = dt_ref
                    except Exception:
                        f_calc = date.today()
                    _ = recalcular_caja_dia(tarjeta_info["empleado_identificacion"], f_calc, principal.get("timezone"))
                    # Verificar si debe reactivarse
                    verificar_reactivacion_tarjeta(prev_abono.get("tarjeta_codigo"))
            except Exception:
                pass

        return {"ok": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error al eliminar abono: {e}")
        raise HTTPException(status_code=500, detail="Error interno al eliminar el abono.")

@app.delete("/tarjetas/{tarjeta_codigo}/abonos/ultimo")
def delete_ultimo_abono_endpoint(tarjeta_codigo: str, principal: dict = Depends(get_current_principal)):
    """
    Elimina el último abono de una tarjeta.
    """
    try:
        from .database.abonos_db import eliminar_ultimo_abono
        
        # Obtener info tarjeta antes para recalcular
        tarjeta_info = obtener_tarjeta_por_codigo(tarjeta_codigo)
        
        success = eliminar_ultimo_abono(tarjeta_codigo)
        if not success:
            raise HTTPException(status_code=404, detail="No se encontró ningún abono para eliminar.")
            
        # Recalcular caja
        if tarjeta_info:
            try:
                from datetime import datetime, date
                try:
                    from zoneinfo import ZoneInfo
                    from datetime import timezone as _tz
                    tz = ZoneInfo(principal.get("timezone")) if principal.get("timezone") else _tz.utc
                    f_calc = datetime.now(tz).date()
                except Exception:
                    f_calc = date.today()
                _ = recalcular_caja_dia(tarjeta_info["empleado_identificacion"], f_calc, principal.get("timezone"))
                verificar_reactivacion_tarjeta(tarjeta_codigo)
            except Exception:
                pass
                
        return {"ok": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error al eliminar último abono: {e}")
        raise HTTPException(status_code=500, detail="Error interno al eliminar el último abono.")

# --- Endpoints para Bases Adicionales ---

@app.get("/bases/", response_model=List[Base])
def read_bases_endpoint(fecha: Optional[str] = None, skip: int = 0, limit: int = 100):
    """
    Obtiene todas las bases, opcionalmente filtradas por fecha.
    """
    try:
        # Esta función necesita ser implementada en bases_db.py
        # Por ahora devolver lista vacía
        bases = []
        return bases
    except Exception as e:
        logger.error(f"Error al obtener bases: {e}")
        raise HTTPException(status_code=500, detail="Error interno al consultar las bases.")

# (Aquí puedes añadir el resto de tus endpoints: POST de empleados, de tarjetas, etc.) 

# --- Endpoints de Liquidación ---

class TarjetaSinAbono(BaseModel):
    codigo: str
    monto: float
    cuotas: int
    cliente_nombre: str
    cliente_apellido: str
    numero_ruta: Optional[Decimal] = None
    interes: float = 0.0
    atraso: float = 0.0

@app.get("/empleados/{empleado_id}/tarjetas-sin-abono/{fecha}", response_model=List[TarjetaSinAbono])
def list_tarjetas_sin_abono_dia_endpoint(
    empleado_id: str,
    fecha: date,
    timezone: Optional[str] = None,
    principal: dict = Depends(get_current_principal)
):
    """
    Lista las tarjetas activas de un empleado que no recibieron abono en la fecha indicada.
    """
    _enforce_empleado_scope(principal, empleado_id)
    tz_name = timezone or principal.get('timezone') or 'UTC'
    return listar_tarjetas_sin_abono_dia(empleado_id, fecha, tz_name)

@app.get("/liquidacion/{empleado_id}/{fecha}", response_model=LiquidacionDiaria)
def read_liquidacion_diaria_endpoint(empleado_id: str, fecha: str, principal: dict = Depends(get_current_principal)):
    _enforce_empleado_scope(principal, empleado_id)
    try:
        from datetime import datetime as _dt
        fecha_obj = _dt.strptime(fecha, '%Y-%m-%d').date()
        tz_name = principal.get('timezone') or 'UTC'
        datos = obtener_datos_liquidacion(empleado_id, fecha_obj, tz_name)
        # Adaptar tipos a float/int donde aplique
        adaptado = {
            'empleado': datos.get('empleado', empleado_id),
            'fecha': fecha_obj,
            'tarjetas_activas': int(datos.get('tarjetas_activas', 0)),
            'tarjetas_canceladas': int(datos.get('tarjetas_canceladas', 0)),
            'tarjetas_nuevas': int(datos.get('tarjetas_nuevas', 0)),
            'total_registros': int(datos.get('total_registros', 0)),
            'tarjetas_sin_abono': int(datos.get('tarjetas_sin_abono', 0)),
            'total_recaudado': float(datos.get('total_recaudado', 0)),
            'base_dia': float(datos.get('base_dia', 0)),
            'prestamos_otorgados': float(datos.get('prestamos_otorgados', 0)),
            'total_gastos': float(datos.get('total_gastos', 0)),
            'subtotal': float(datos.get('subtotal', 0)),
            'total_final': float(datos.get('total_final', 0))
        }
        return adaptado
    except ValueError:
        raise HTTPException(status_code=400, detail="Formato de fecha inválido. Use YYYY-MM-DD.")
    except Exception as e:
        logger.error(f"Error al obtener liquidación diaria: {e}")
        raise HTTPException(status_code=500, detail="Error interno al consultar la liquidación diaria.")

@app.get("/liquidacion/resumen/{fecha}", response_model=ResumenFinanciero)
def read_resumen_financiero_endpoint(fecha: str, principal: dict = Depends(require_admin)):
    try:
        from datetime import datetime as _dt
        fecha_obj = _dt.strptime(fecha, '%Y-%m-%d').date()
        res = obtener_resumen_financiero_fecha(fecha_obj)
        adaptado = {
            'fecha': fecha_obj,
            'total_recaudado_todos': float(res.get('total_recaudado_todos', 0)),
            'total_bases_asignadas': float(res.get('total_bases_asignadas', 0)),
            'total_prestamos_otorgados': float(res.get('total_prestamos_otorgados', 0)),
            'total_gastos_todos': float(res.get('total_gastos_todos', 0)),
            'empleados_activos': int(res.get('empleados_activos', 0))
        }
        return adaptado
    except ValueError:
        raise HTTPException(status_code=400, detail="Formato de fecha inválido. Use YYYY-MM-DD.")
    except Exception as e:
        logger.error(f"Error al obtener resumen financiero: {e}")
        raise HTTPException(status_code=500, detail="Error interno al consultar el resumen financiero.")

class MoverLiquidacionRequest(BaseModel):
    empleado_id: str
    fecha_origen: date
    fecha_destino: date

@app.post("/liquidacion/mover")
def mover_liquidacion_endpoint(req: MoverLiquidacionRequest, principal: dict = Depends(get_current_principal)):
    """Mueve la liquidación de una fecha a otra."""
    _enforce_empleado_scope(principal, req.empleado_id)
    
    # Obtener timezone del usuario autenticado
    tz = principal.get('timezone') or 'UTC'
    
    try:
        if mover_liquidacion(req.empleado_id, req.fecha_origen, req.fecha_destino, tz):
            return {"ok": True, "message": "Liquidación movida correctamente"}
        else:
            raise HTTPException(status_code=500, detail="Error al mover liquidación")
    except ValueError as e:
        # Errores de validación (ej. base duplicada) -> 400 Bad Request
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error moviendo liquidación: {e}")
        raise HTTPException(status_code=500, detail="Error interno al mover liquidación")

# --- Endpoint de Resumen de Tarjeta ---

@app.get("/tarjetas/{tarjeta_codigo}/resumen")
def read_tarjeta_resumen_endpoint(tarjeta_codigo: str, principal: dict = Depends(get_current_principal)):
    """
    Devuelve un resumen de la tarjeta: saldo, total abonado, valor de cuota, etc.
    """
    try:
        tarjeta = obtener_tarjeta_por_codigo(tarjeta_codigo)
        if tarjeta is None:
            raise HTTPException(status_code=404, detail="Tarjeta no encontrada")

        # Obtener total abonado
        with DatabasePool.get_cursor() as cursor:
            cursor.execute("SELECT COALESCE(SUM(monto), 0) FROM abonos WHERE tarjeta_codigo = %s", (tarjeta_codigo,))
            total_abonado = cursor.fetchone()[0] or 0

        monto = float(tarjeta["monto"]) if isinstance(tarjeta.get("monto"), (int, float)) else float(tarjeta.get("monto", 0))
        interes = int(tarjeta.get("interes", 0))
        cuotas = int(tarjeta.get("cuotas", 1)) or 1
        modalidad = str(tarjeta.get("modalidad_pago") or "diario").strip().lower()
        if modalidad not in ("diario", "semanal", "quincenal", "mensual"):
            modalidad = "diario"

        monto_total = monto * (1 + interes / 100.0)
        valor_cuota = monto_total / cuotas if cuotas > 0 else monto_total
        saldo_pendiente = max(0.0, monto_total - float(total_abonado))

        # Cálculos (al día / atraso) según modalidad de pago (diario/semanal/quincenal/mensual)
        from math import floor, ceil
        from datetime import datetime as dt, timezone as _tz
        
        # Timezone del usuario para calcular 'hoy' correctamente
        tz_name = principal.get("timezone") or "UTC"
        try:
            tz = ZoneInfo(tz_name)
        except Exception:
            tz = _tz.utc
            
        hoy = dt.now(tz).date()
        
        fecha_creacion = tarjeta.get("fecha_creacion")
        if fecha_creacion:
            if isinstance(fecha_creacion, dt):
                if fecha_creacion.tzinfo is None:
                    fecha_creacion = fecha_creacion.replace(tzinfo=_tz.utc)
                fecha_crea = fecha_creacion.astimezone(tz).date()
            elif hasattr(fecha_creacion, 'date'):
                fecha_crea = fecha_creacion
            else:
                fecha_crea = hoy
        else:
            fecha_crea = hoy
            
        dias_transcurridos = (hoy - fecha_crea).days
        if dias_transcurridos < 0:
            dias_transcurridos = 0

        if modalidad == "diario":
            periodos_transcurridos = dias_transcurridos
            fecha_venc = fecha_crea.replace()  # no-op (solo para inicializar)
            from datetime import timedelta
            fecha_venc = fecha_crea + timedelta(days=cuotas)
        elif modalidad == "semanal":
            periodos_transcurridos = dias_transcurridos // 7
            from datetime import timedelta
            fecha_venc = fecha_crea + timedelta(days=cuotas * 7)
        elif modalidad == "quincenal":
            periodos_transcurridos = dias_transcurridos // 15
            from datetime import timedelta
            fecha_venc = fecha_crea + timedelta(days=cuotas * 15)
        else:  # mensual
            # Regla solicitada: mensual = cada 30 días (no mes calendario)
            periodos_transcurridos = dias_transcurridos // 30
            from datetime import timedelta
            fecha_venc = fecha_crea + timedelta(days=cuotas * 30)
        cuotas_pagadas = floor(float(total_abonado) / valor_cuota) if valor_cuota > 0 else 0
        # Puede ser negativo (atraso) o positivo (adelanto). 0 si va al día
        cuotas_pendientes_a_la_fecha = cuotas_pagadas - int(periodos_transcurridos)
        # Días pasados desde el vencimiento del plazo (según la modalidad)
        dias_pasados_cancelacion = max(0, (hoy - fecha_venc).days)
        cuotas_restantes = ceil(saldo_pendiente / valor_cuota) if valor_cuota > 0 else 0
        # Regla: no mostrar más cuotas pendientes (en atraso) que las restantes por pagar
        if cuotas_pendientes_a_la_fecha < 0 and cuotas_restantes > 0:
            cuotas_pendientes_a_la_fecha = max(cuotas_pendientes_a_la_fecha, -cuotas_restantes)

        resumen = {
            "tarjeta_id": tarjeta_codigo,
            "codigo_tarjeta": tarjeta_codigo,
            "estado_tarjeta": tarjeta.get("estado", "activas"),
            "modalidad_pago": modalidad,
            "total_abonado": float(total_abonado),
            "valor_cuota": float(valor_cuota),
            "saldo_pendiente": float(saldo_pendiente),
            "cuotas_restantes": int(cuotas_restantes),
            "cuotas": int(cuotas),  # Agregado para frontend
            "cuotas_pendientes_a_la_fecha": int(cuotas_pendientes_a_la_fecha),
            "dias_pasados_cancelacion": int(dias_pasados_cancelacion),
            "fecha_vencimiento": fecha_venc.isoformat() if fecha_venc else None,
        }

        return resumen
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error al obtener resumen de la tarjeta: {e}")
        raise HTTPException(status_code=500, detail="Error interno al obtener el resumen de la tarjeta.")

@app.post("/sync", response_model=SyncResponse)
def sync_endpoint(payload: SyncRequest, principal: dict = Depends(get_current_principal)):
    """
    Sincroniza cambios del frontend (offline) con idempotencia.
    - Usa payload.idempotency_key para evitar procesar duplicado
    - Crea clientes/tarjetas nuevas, abonos con metodo_pago, gastos y bases en lote
    - Devuelve mapeos de IDs temporales a definitivos
    """
    try:
        t0 = _pc()
        from datetime import datetime as _dt
        from zoneinfo import ZoneInfo as _ZI, ZoneInfoNotFoundError as _ZINF
        tz_name = principal.get('timezone') or 'UTC'
        try:
            today_local = _dt.now(_ZI(tz_name)).date()
        except _ZINF:
            tz_name = 'UTC'
            today_local = _dt.now(_ZI('UTC')).date()
        
        # Verificar permisos ANTES de procesar cualquier dato
        # La sincronización debe ser por UN SOLO empleado seleccionado
        empleado_ids = set()
        
        # Recopilar todos los empleados del payload
        for t in payload.tarjetas_nuevas or []:
            if t.empleado_identificacion:
                empleado_ids.add(str(t.empleado_identificacion)[:20])
        for b in payload.bases or []:
            if b.empleado_id:
                empleado_ids.add(str(b.empleado_id)[:20])
        for g in payload.gastos or []:
            if g.empleado_identificacion:
                empleado_ids.add(str(g.empleado_identificacion)[:20])
        
        # Considerar abonos que referencian tarjetas temporales incluidas en este mismo payload
        # Mapa temp_id_tarjeta -> empleado_identificacion desde tarjetas_nuevas
        temp_tarjeta_to_empleado = {}
        for t in payload.tarjetas_nuevas or []:
            try:
                if t.temp_id and t.empleado_identificacion:
                    temp_tarjeta_to_empleado[str(t.temp_id)] = str(t.empleado_identificacion)[:20]
            except Exception:
                pass

        # Para abonos, necesitamos obtener el empleado de la tarjeta
        if payload.abonos:
            tarjeta_codigos = set()
            for a in payload.abonos:
                try:
                    # Si el abono referencia un temp_id presente en tarjetas_nuevas, agregar ese empleado
                    if a.tarjeta_codigo in temp_tarjeta_to_empleado:
                        empleado_ids.add(temp_tarjeta_to_empleado[a.tarjeta_codigo])
                    # Acumular códigos para consultar en BD (solo los que no son temporales)
                    if not str(a.tarjeta_codigo).startswith('tmp-'):
                        tarjeta_codigos.add(a.tarjeta_codigo)
                except Exception:
                    pass
            
            # Obtener empleados de las tarjetas
            if tarjeta_codigos:
                with DatabasePool.get_cursor() as cursor:
                    placeholders = ','.join(['%s'] * len(tarjeta_codigos))
                    cursor.execute(
                        f"""
                        SELECT DISTINCT empleado_identificacion
                        FROM tarjetas
                        WHERE codigo IN ({placeholders})
                        """,
                        list(tarjeta_codigos)
                    )
                    for row in cursor.fetchall():
                        if row[0]:
                            empleado_ids.add(str(row[0])[:20])
        
        # Si no se pudo inferir el empleado desde el payload, derivar del principal (para cobradores)
        if not empleado_ids:
            try:
                role = principal.get("role") if principal else None
                if role == "cobrador" and principal.get("empleado_identificacion"):
                    empleado_ids.add(str(principal.get("empleado_identificacion"))[:20])
                else:
                    raise HTTPException(
                        status_code=400,
                        detail="No se pudo determinar el empleado para sincronización. Incluya empleado_identificacion/empleado_id en el payload."
                    )
            except HTTPException:
                raise
            except Exception:
                raise HTTPException(
                    status_code=400,
                    detail="No se pudo determinar el empleado para sincronización."
                )

        # VALIDACIÓN CRÍTICA: Solo permitir sincronización de UN empleado
        if len(empleado_ids) > 1:
            raise HTTPException(
                status_code=400, 
                detail=f"No se puede sincronizar datos de múltiples empleados en una sola operación. Empleados detectados: {', '.join(empleado_ids)}"
            )
        
        # Si hay empleados en el payload, verificar permisos
        if empleado_ids:
            emp_id = next(iter(empleado_ids))  # Obtener el único empleado
            try:
                with DatabasePool.get_cursor() as cursor:
                    cursor.execute(
                        """
                        SELECT descargar, subir, fecha_accion
                        FROM empleados
                        WHERE identificacion = %s
                        """,
                        (emp_id,),
                    )
                    row = cursor.fetchone()
                    if not row:
                        raise HTTPException(status_code=404, detail=f"Empleado {emp_id} no encontrado")
                    
                    descargar, subir, fecha_accion = row
                    # Comparar contra el día LOCAL del usuario para evitar desfaces por huso
                    # Verificar permiso de subida
                    if not subir:
                        raise HTTPException(
                            status_code=403, 
                            detail=f"Empleado {emp_id} no tiene permiso de subida habilitado"
                        )
                    
                    # Verificar fecha de última acción
                    if fecha_accion and fecha_accion >= today_local:
                        raise HTTPException(
                            status_code=403, 
                            detail=f"Empleado {emp_id} ya realizó una subida hoy. Próxima subida disponible mañana"
                        )
                    
                    logger.info(f"Permisos verificados para empleado {emp_id}: subir={subir}, fecha_accion={fecha_accion}")
                    
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Error verificando permisos para empleado {emp_id}: {e}")
                raise HTTPException(status_code=500, detail="Error interno verificando permisos")
        
        # Idempotencia
        with DatabasePool.get_cursor() as cursor:
            cursor.execute("SELECT 1 FROM idempotency_keys WHERE key=%s", (payload.idempotency_key,))
            if cursor.fetchone():
                # DEBUGGING TEMPORAL: Log de respuesta de idempotencia
                response_data = SyncResponse(
                    already_processed=True,
                    created_tarjetas=[],
                    created_abonos=[],
                    created_gastos=0,
                    created_bases=0
                )
                
                logger.info("🔍 [DEBUG SYNC] Respuesta de idempotencia que se va a devolver:")
                logger.info(f"  - already_processed: {response_data.already_processed}")
                logger.info(f"  - created_tarjetas: {response_data.created_tarjetas}")
                logger.info(f"  - created_abonos: {response_data.created_abonos}")
                logger.info(f"  - created_gastos: {response_data.created_gastos}")
                logger.info(f"  - created_bases: {response_data.created_bases}")
                logger.info(f"  - Tipo de respuesta: {type(response_data)}")
                
                return response_data
        t_idem_chk = _pc()

        created_tarjetas = []
        created_abonos = []
        created_gastos = 0
        created_bases = 0

        # 1) Tarjetas nuevas (y clientes si no existen)
        for idx, t in enumerate(payload.tarjetas_nuevas or []):
            cli = obtener_cliente_por_identificacion(t.cliente.identificacion)
            if cli is None:
                _ = crear_cliente(
                    identificacion=t.cliente.identificacion,
                    nombre=t.cliente.nombre,
                    apellido=t.cliente.apellido,
                    telefono=t.cliente.telefono,
                    direccion=t.cliente.direccion,
                    observaciones=t.cliente.observaciones,
                )
            else:
                # Si ya existe, actualizar datos personales priorizando los valores NUEVOS del payload
                try:
                    _ = actualizar_cliente(
                        identificacion=cli.get('identificacion', t.cliente.identificacion),
                        nombre=(t.cliente.nombre if (t.cliente.nombre is not None and str(t.cliente.nombre).strip() != '') else cli.get('nombre', '')),
                        apellido=(t.cliente.apellido if (t.cliente.apellido is not None and str(t.cliente.apellido).strip() != '') else cli.get('apellido', '')),
                        telefono=(t.cliente.telefono if (t.cliente.telefono is not None and str(t.cliente.telefono).strip() != '') else cli.get('telefono')),
                        direccion=(t.cliente.direccion if (t.cliente.direccion is not None and str(t.cliente.direccion).strip() != '') else cli.get('direccion')),
                        observaciones=(t.cliente.observaciones if (t.cliente.observaciones is not None and str(t.cliente.observaciones).strip() != '') else cli.get('observaciones')),
                    )
                except Exception:
                    pass
            codigo = crear_tarjeta(
                cliente_identificacion=t.cliente.identificacion,
                empleado_identificacion=t.empleado_identificacion,
                monto=Decimal(str(t.monto)),
                cuotas=int(t.cuotas),
                interes=int(t.interes),
                modalidad_pago=(getattr(t, 'modalidad_pago', None) or 'diario'),
                numero_ruta=Decimal(str(t.numero_ruta)) if t.numero_ruta is not None else None,
                observaciones=t.observaciones,
                posicion_anterior=Decimal(str(t.posicion_anterior)) if t.posicion_anterior is not None else None,
                posicion_siguiente=Decimal(str(t.posicion_siguiente)) if t.posicion_siguiente is not None else None,
            )
            if not codigo:
                raise HTTPException(status_code=400, detail="No se pudo crear una tarjeta durante la sincronización")
            created_tarjetas.append({"temp_id": t.temp_id, "codigo": codigo})
            if (idx + 1) % 50 == 0:
                logger.info(f"Tarjetas procesadas: {idx + 1}")
        t_tar = _pc()

        # Mapa rápido temp_id -> codigo real
        temp_to_real = {it["temp_id"]: it["codigo"] for it in created_tarjetas}

        # 2) Abonos (inserción optimizada por lotes)
        abonos_payload = []
        tarjetas_con_abonos = set()
        for a in (payload.abonos or []):
            metodo = (a.metodo_pago or 'efectivo').lower()
            if metodo not in ('efectivo','consignacion'):
                raise HTTPException(status_code=400, detail="metodo_pago inválido en abono")
            tc = temp_to_real.get(a.tarjeta_codigo, a.tarjeta_codigo)
            try:
                abonos_payload.append((tc, Decimal(str(a.monto)), metodo))
                tarjetas_con_abonos.add(tc)
            except Exception:
                raise HTTPException(status_code=400, detail="Abono inválido en sincronización")

        if abonos_payload:
            # Preparar payload con tarjeta repetida para calcular indice_orden por tarjeta
            batch_rows = []
            for (tc, monto_dec, metodo) in abonos_payload:
                batch_rows.append((tc, monto_dec, tc, metodo))
            with DatabasePool.get_cursor() as cur:
                # Insertar con fecha NOW() y calcular indice_orden: max(indice_orden)+1 por tarjeta
                cur.executemany(
                    """
                    INSERT INTO abonos (tarjeta_codigo, fecha, monto, indice_orden, metodo_pago)
                    SELECT %s, NOW(), %s,
                           COALESCE((SELECT MAX(indice_orden) FROM abonos WHERE tarjeta_codigo=%s), 0) + 1,
                           %s
                    """,
                    batch_rows,
                )
            # Para la respuesta, solo reportar la cantidad creada
            created_abonos = [{"id_temporal": a.id_temporal or ""} for a in (payload.abonos or [])]
        t_abn = _pc()

        # 2.1) Actualización optimizada de estado de tarjetas: cancelar aquellas con saldo 0
        t_cancel = _pc()
        try:
            if tarjetas_con_abonos:
                tarjetas_list = list(tarjetas_con_abonos)
                with DatabasePool.get_cursor() as cur:
                    # Sumas de abonos por tarjeta afectada
                    placeholders = ','.join(['%s'] * len(tarjetas_list))
                    cur.execute(
                        f"""
                        SELECT tarjeta_codigo, COALESCE(SUM(monto),0)
                        FROM abonos
                        WHERE tarjeta_codigo IN ({placeholders})
                        GROUP BY tarjeta_codigo
                        """,
                        tarjetas_list,
                    )
                    sum_abonos = {row[0]: row[1] for row in cur.fetchall() or []}

                    # Datos base de tarjetas para calcular total
                    cur.execute(
                        f"""
                        SELECT codigo, monto, interes, cuotas, estado
                        FROM tarjetas
                        WHERE codigo IN ({placeholders})
                        """,
                        tarjetas_list,
                    )
                    to_cancel = []
                    for row in cur.fetchall() or []:
                        codigo, monto, interes, cuotas, estado = row
                        try:
                            monto_base = float(monto or 0)
                            interes_pct = int(interes or 0)
                            total = monto_base * (1 + interes_pct / 100.0)
                            abonado = float(sum_abonos.get(codigo, 0) or 0)
                            saldo = total - abonado
                            if saldo <= 0 and (estado == 'activas' or estado == 'activa'):
                                to_cancel.append(codigo)
                        except Exception:
                            continue
                    if to_cancel:
                        placeholders2 = ','.join(['%s'] * len(to_cancel))
                        cur.execute(
                            f"""
                            UPDATE tarjetas
                            SET estado='cancelada',
                                fecha_cancelacion=%s
                            WHERE codigo IN ({placeholders2})
                              AND (estado='activas' OR estado='activa')
                            """,
                            [today_local, *to_cancel],
                        )
        except Exception:
            # No bloquear la sincronización si algo falla aquí
            pass
        t_cancel = _pc()

        # 3) Gastos
        for idx, g in enumerate(payload.gastos or []):
            # Debug: Log del gasto
            logger.info(f"Procesando gasto: empleado={g.empleado_identificacion}, tipo={g.tipo}, valor={g.valor}, fecha={g.fecha}")
            
            # Truncar empleado_identificacion a 20 caracteres para evitar error de BD
            empleado_id_truncado = str(g.empleado_identificacion)[:20] if g.empleado_identificacion else None
            
            # Pydantic ya convierte la fecha a objeto date, usar directamente
            fecha_obj = g.fecha if g.fecha else date.today()
            
            gid = agregar_gasto(
                empleado_identificacion=empleado_id_truncado,
                tipo=g.tipo,
                valor=Decimal(str(g.valor)),
                fecha=fecha_obj,
                observacion=g.observacion,
            )
            if gid is None:
                logger.error(f"Error al crear gasto: empleado={empleado_id_truncado}, tipo={g.tipo}, fecha={g.fecha}")
                raise HTTPException(status_code=400, detail="No se pudo registrar un gasto durante la sincronización")
            created_gastos += 1
            if (idx + 1) % 100 == 0:
                logger.info(f"Gastos procesados: {idx + 1}")
        t_gas = _pc()

        # 4) Bases (una por día/empleado). Si ya existe, actualizar en vez de fallar
        for idx, b in enumerate(payload.bases or []):
            logger.info(f"Procesando base: empleado={b.empleado_id}, fecha={b.fecha}, monto={b.monto}")
            empleado_id_truncado = str(b.empleado_id)[:20] if b.empleado_id else None
            fecha_obj = b.fecha
            try:
                # ¿Existe ya una base para ese día/empleado?
                existente = obtener_base(empleado_id_truncado, fecha_obj)
                if existente:
                    ok = actualizar_base(empleado_id_truncado, fecha_obj, Decimal(str(b.monto)))
                    if not ok:
                        logger.error(f"Error al actualizar base existente: empleado={empleado_id_truncado}, fecha={b.fecha}")
                        raise HTTPException(status_code=400, detail="No se pudo actualizar la base existente durante la sincronización")
                    created_bases += 1
                else:
                    bid = insertar_base(empleado_id_truncado, fecha_obj, Decimal(str(b.monto)))
                    if bid is None:
                        logger.error(f"Error al crear base: empleado={empleado_id_truncado}, fecha={b.fecha}, monto={b.monto}")
                        raise HTTPException(status_code=400, detail="No se pudo registrar una base durante la sincronización")
                    created_bases += 1
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Excepción al procesar base: {e}")
                raise HTTPException(status_code=500, detail="Error interno al procesar base durante la sincronización")
            if (idx + 1) % 100 == 0:
                logger.info(f"Bases procesadas: {idx + 1}")
        t_bas = _pc()

        # Registrar la key de idempotencia al final (commit implícito con context manager)
        with DatabasePool.get_cursor() as cursor:
            cursor.execute("INSERT INTO idempotency_keys(key) VALUES (%s) ON CONFLICT (key) DO NOTHING", (payload.idempotency_key,))
        t_idem_ins = _pc()

        # Actualizar permisos DESPUÉS de sincronización exitosa
        # Solo actualizar el empleado único que se sincronizó
        try:
            if empleado_ids:
                emp_id = next(iter(empleado_ids))  # El único empleado
                with DatabasePool.get_cursor() as cur2:
                    cur2.execute(
                        "UPDATE empleados SET fecha_accion=%s, subir=FALSE, descargar=TRUE WHERE identificacion=%s RETURNING identificacion",
                        (today_local, emp_id),
                    )
                    if cur2.fetchone() is not None:
                        logger.info(f"Permisos sincronización actualizados para empleado {emp_id}: subir=FALSE, descargar=TRUE, fecha_accion={today_local}")
                    else:
                        logger.warning(f"No se pudo actualizar permisos para empleado {emp_id} - no encontrado")
                        
        except Exception as e:
            logger.error(f"No se pudo actualizar permisos post-sync: {e}")
            # No lanzar excepción aquí para no afectar la respuesta exitosa

        # Log resumido de performance (producción):
        logger.info(
            "SYNC perf(ms): idem=%d tarjetas=%d abonos=%d cancelar=%d gastos=%d bases=%d total=%d",
            int((t_idem_chk - t0)*1000),
            int((t_tar - t_idem_chk)*1000),
            int((t_abn - t_tar)*1000),
            int((t_cancel - t_abn)*1000),
            int((t_gas - t_cancel)*1000),
            int((t_bas - t_gas)*1000),
            int((_pc() - t0)*1000),
        )

        # Recalcular caja del día para el empleado sincronizado
        if empleado_ids:
            emp_id_sync = next(iter(empleado_ids))
            try:
                # Usar timezone del principal o 'UTC' si falló antes
                tz_sync = principal.get('timezone') or 'UTC'
                _ = recalcular_caja_dia(emp_id_sync, today_local, tz_sync)
                logger.info(f"Caja recalculada para {emp_id_sync} en fecha {today_local} tras sincronización")
            except Exception as e:
                logger.error(f"Error recalculando caja post-sync: {e}")

        response_data = SyncResponse(
            already_processed=False,
            created_tarjetas=created_tarjetas,
            created_abonos=created_abonos,
            created_gastos=created_gastos,
            created_bases=created_bases,
        )
        
        return response_data
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error en sincronización: {e}")
        raise HTTPException(status_code=500, detail="Error interno durante la sincronización")