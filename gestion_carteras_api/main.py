from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
import os
from typing import List, Optional
import logging
from decimal import Decimal
from datetime import date
from time import perf_counter as _pc

"""Importaciones del paquete interno (usar rutas relativas del paquete)."""
from .database.db_config import DB_CONFIG
from .database.connection_pool import DatabasePool

from .database.clientes_db import crear_cliente, obtener_cliente_por_identificacion, actualizar_cliente, eliminar_cliente
from .database.empleados_db import insertar_empleado, buscar_empleado_por_identificacion, actualizar_empleado, eliminar_empleado, obtener_empleados, verificar_empleado_tiene_tarjetas, obtener_tarjetas_empleado
from .database.tarjetas_db import crear_tarjeta, obtener_tarjeta_por_codigo, actualizar_tarjeta, actualizar_estado_tarjeta, mover_tarjeta, eliminar_tarjeta, obtener_todas_las_tarjetas
from .database.abonos_db import registrar_abono, obtener_abono_por_id, actualizar_abono, eliminar_abono_por_id, eliminar_ultimo_abono
from .database.bases_db import insertar_base, obtener_base, actualizar_base, eliminar_base
# CORRECCIÓN: Se importa la función correcta 'obtener_tipos_gastos' (plural)
from .database.gastos_db import agregar_gasto, obtener_gasto_por_id, actualizar_gasto, eliminar_gasto, obtener_resumen_gastos_por_tipo, obtener_tipos_gastos, obtener_todos_los_gastos
from .database.liquidacion_db import obtener_datos_liquidacion, obtener_resumen_financiero_fecha

from .schemas import (
    Cliente, ClienteCreate, ClienteUpdate, Empleado, EmpleadoCreate, EmpleadoUpdate,
    Tarjeta, TarjetaCreate, TarjetaUpdate, Abono, AbonoCreate, AbonoUpdate, Base,
    BaseCreate, BaseUpdate, TipoGasto, Gasto, GastoCreate, GastoUpdate,
    ResumenGasto, LiquidacionDiaria, ResumenFinanciero,
    SyncRequest, SyncResponse
)

# Configuración del logging
logging.basicConfig(level=logging.INFO)
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
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "http://172.20.10.7:5174",
        "http://172.20.10.7:5173",
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
app.include_router(auth_router.router, prefix="/auth", tags=["auth"])
app.include_router(billing_router.router, prefix="/billing", tags=["billing"])
app.include_router(public_router.router, prefix="/public", tags=["public"])
app.include_router(admin_users_router.router, prefix="/admin", tags=["admin"])

# Seguridad
from .security import get_current_principal, require_admin

def _enforce_empleado_scope(principal: dict, empleado_id: str):
    role = principal.get("role")
    if role == "admin":
        return
    if role == "cobrador" and principal.get("empleado_identificacion") == str(empleado_id):
        return
    raise HTTPException(status_code=403, detail="Acceso denegado para este empleado")

# --- Evento de Arranque (Startup) ---
@app.on_event("startup")
def startup_event():
    logger.info("Iniciando la aplicación y el pool de conexiones a la base de datos...")
    try:
        DatabasePool.initialize(**DB_CONFIG)
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
            return {
                "descargar": bool(row[0]),
                "subir": bool(row[1]),
                "fecha_accion": row[2].isoformat() if row[2] else None,
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
            return {
                "descargar": bool(row[0]),
                "subir": bool(row[1]),
                "fecha_accion": row[2].isoformat() if row[2] else None,
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
                cursor.execute("SELECT COUNT(*) FROM cobrador_permisos_diarios WHERE empleado_identificacion=%s", (identificacion,))
                deps["permisos_cobrador"] = int(cursor.fetchone()[0] or 0)
            except Exception:
                pass
            try:
                cursor.execute("SELECT COUNT(*) FROM usuarios WHERE empleado_identificacion=%s", (identificacion,))
                deps["usuarios_cobrador"] = int(cursor.fetchone()[0] or 0)
            except Exception:
                pass

        if any([tiene_tarjetas, deps["gastos"] > 0, deps["bases"] > 0, deps["permisos_cobrador"] > 0, deps["usuarios_cobrador"] > 0]):
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

            # 4) Eliminar permisos diarios de cobrador (si existen)
            try:
                cursor.execute("""
                    DELETE FROM cobrador_permisos_diarios
                    WHERE empleado_identificacion = %s
                """, (identificacion,))
                permisos_cobrador_eliminados = cursor.rowcount or 0
            except Exception:
                # La tabla puede no existir en algunas instalaciones
                permisos_cobrador_eliminados = 0

            # 5) Eliminar usuarios con role=cobrador vinculados a este empleado
            try:
                cursor.execute("""
                    DELETE FROM usuarios
                    WHERE empleado_identificacion = %s
                """, (identificacion,))
                usuarios_cobrador_eliminados = cursor.rowcount or 0
            except Exception:
                usuarios_cobrador_eliminados = 0

        # 6) Finalmente, eliminar el empleado (usa cuenta_id)
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
        return db_gasto
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error al actualizar gasto: {e}")
        raise HTTPException(status_code=500, detail="Error interno al actualizar el gasto.")

@app.delete("/gastos/{gasto_id}")
def delete_gasto_endpoint(gasto_id: int, principal: dict = Depends(get_current_principal)):
    try:
        ok = eliminar_gasto(gasto_id)
        if not ok:
            raise HTTPException(status_code=404, detail="Gasto no encontrado.")
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
        from datetime import datetime
        fecha_obj = datetime.strptime(fecha, '%Y-%m-%d').date()
        
        from .database.gastos_db import obtener_gastos_por_fecha_empleado
        gastos_tuplas = obtener_gastos_por_fecha_empleado(fecha_obj, empleado_id)
        
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
                'fecha': fecha_obj
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
        from datetime import datetime as _dt
        fecha_obj = _dt.strptime(fecha, '%Y-%m-%d').date()
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
                  AND DATE(t.fecha_cancelacion) = %s
                ORDER BY t.numero_ruta
                ''', (empleado_id, fecha_obj)
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
        from datetime import datetime as _dt
        fecha_obj = _dt.strptime(fecha, '%Y-%m-%d').date()
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
                  AND DATE(t.fecha_creacion) = %s
                ORDER BY t.numero_ruta
                ''', (empleado_id, fecha_obj)
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
        from datetime import datetime as _dt
        fecha_obj = _dt.strptime(fecha, '%Y-%m-%d').date()
        abonos: List[dict] = []
        with DatabasePool.get_cursor() as cursor:
            cursor.execute(
                '''
                SELECT a.id, a.fecha, a.monto, a.indice_orden, a.tarjeta_codigo,
                       c.nombre, c.apellido
                FROM abonos a
                JOIN tarjetas t ON a.tarjeta_codigo = t.codigo
                JOIN clientes c ON t.cliente_identificacion = c.identificacion
                WHERE t.empleado_identificacion = %s
                  AND DATE(a.fecha) = %s
                ORDER BY a.fecha, a.id
                ''', (empleado_id, fecha_obj)
            )
            for row in cursor.fetchall() or []:
                abono = {
                    'id': row[0],
                    'fecha': row[1],
                    'monto': row[2],
                    'indice_orden': row[3],
                    'tarjeta_codigo': row[4],
                    'cliente_nombre': row[5],
                    'cliente_apellido': row[6]
                }
                abonos.append(abono)
        return abonos
    except ValueError:
        raise HTTPException(status_code=400, detail="Formato de fecha inválido. Use YYYY-MM-DD.")
    except Exception as e:
        logger.error(f"Error al obtener abonos del día: {e}")
        raise HTTPException(status_code=500, detail="Error interno al consultar abonos del día.")

@app.get("/empleados/{empleado_id}/gastos/{fecha}/resumen", response_model=List[ResumenGasto])
def read_resumen_gastos_by_empleado_fecha_endpoint(empleado_id: str, fecha: str):
    """
    Obtiene el resumen de gastos de un empleado en una fecha específica.
    """
    try:
        from datetime import datetime
        fecha_obj = datetime.strptime(fecha, '%Y-%m-%d').date()
        
        from .database.gastos_db import obtener_total_gastos_fecha_empleado, obtener_conteo_gastos_fecha_empleado
        total = obtener_total_gastos_fecha_empleado(fecha_obj, empleado_id)
        conteo = obtener_conteo_gastos_fecha_empleado(fecha_obj, empleado_id)
        
        # Crear resumen
        resumen = [{
            'empleado_identificacion': empleado_id,
            'fecha': fecha_obj,
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
                'fecha_cancelacion': row[12]
            }
            tarjetas.append(tarjeta)
        return tarjetas
    except Exception as e:
        logger.error(f"Error al obtener la lista de tarjetas: {e}")
        raise HTTPException(status_code=500, detail="Error interno al consultar las tarjetas.")

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

@app.get("/empleados/{empleado_id}/tarjetas/", response_model=List[Tarjeta])
def read_tarjetas_by_empleado_endpoint(empleado_id: str, estado: str = 'activas', skip: int = 0, limit: int = 100, principal: dict = Depends(get_current_principal)):
    _enforce_empleado_scope(principal, empleado_id)
    """
    Obtiene una lista de tarjetas de un empleado específico filtradas por estado.
    """
    try:
        # Usar la función existente obtener_tarjetas con empleado_identificacion y estado
        from .database.tarjetas_db import obtener_tarjetas
        tarjetas_tuplas = obtener_tarjetas(empleado_identificacion=empleado_id, estado=estado, offset=skip, limit=limit)
        
        # Convertir tuplas a diccionarios para FastAPI con estructura anidada
        tarjetas = []
        for row in tarjetas_tuplas:
            # Normalizar fecha_creacion
            try:
                from datetime import datetime as _dt
                fc = row[8]
                if fc is None:
                    fc_norm = _dt.utcnow()
                elif hasattr(fc, 'year') and not hasattr(fc, 'hour'):
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
                'fecha_cancelacion': row[12]
            }
            tarjetas.append(tarjeta)
        return tarjetas
    except Exception as e:
        logger.error(f"Error al obtener las tarjetas del empleado: {e}")
        raise HTTPException(status_code=500, detail="Error interno al consultar las tarjetas del empleado.")

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
def read_cliente_historial_endpoint(identificacion: str):
    try:
        from .database.tarjetas_db import obtener_historial_cliente
        return obtener_historial_cliente(identificacion)
    except Exception as e:
        logger.error(f"Error al obtener historial de cliente: {e}")
        raise HTTPException(status_code=500, detail="Error interno al consultar historial")

@app.get("/clientes/{identificacion}/estadisticas")
def read_cliente_estadisticas_endpoint(identificacion: str):
    try:
        from .database.tarjetas_db import obtener_estadisticas_cliente
        return obtener_estadisticas_cliente(identificacion)
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
        codigo = crear_tarjeta(
            cliente_identificacion=tarjeta.cliente_identificacion,
            empleado_identificacion=tarjeta.empleado_identificacion,
            monto=Decimal(tarjeta.monto),
            cuotas=tarjeta.cuotas,
            interes=tarjeta.interes,
            numero_ruta=Decimal(str(tarjeta.numero_ruta)) if tarjeta.numero_ruta is not None else None,
            observaciones=tarjeta.observaciones,
            posicion_anterior=Decimal(str(tarjeta.posicion_anterior)) if tarjeta.posicion_anterior is not None else None,
            posicion_siguiente=Decimal(str(tarjeta.posicion_siguiente)) if tarjeta.posicion_siguiente is not None else None
        )
        if not codigo:
            raise HTTPException(status_code=400, detail="No se pudo crear la tarjeta.")
        db_tarjeta = obtener_tarjeta_por_codigo(codigo)
        if db_tarjeta is None:
            raise HTTPException(status_code=500, detail="Tarjeta creada pero no encontrada.")
        # Si se solicitó una fecha_creacion específica, actualizar inmediatamente
        try:
            if tarjeta.fecha_creacion is not None:
                _ = actualizar_tarjeta(
                    tarjeta_codigo=codigo,
                    fecha_creacion=tarjeta.fecha_creacion,
                )
                db_tarjeta = obtener_tarjeta_por_codigo(codigo) or db_tarjeta
        except Exception:
            pass
        # Adaptar a esquema Tarjeta (añadir cliente anidado si aplica)
        db_tarjeta["cliente"] = {
            "identificacion": db_tarjeta.get("cliente_identificacion", tarjeta.cliente_identificacion),
            "nombre": db_tarjeta.get("cliente_nombre", ""),
            "apellido": db_tarjeta.get("cliente_apellido", "")
        }
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
            observaciones=tarjeta.observaciones
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
        ok = eliminar_tarjeta(tarjeta_codigo)
        if not ok:
            raise HTTPException(status_code=404, detail="Tarjeta no encontrada o no se pudo eliminar.")
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
            metodo_pago=metodo
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
        success = eliminar_abono_por_id(abono_id)
        if not success:
            raise HTTPException(status_code=404, detail="Abono no encontrado.")
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
        success = eliminar_ultimo_abono(tarjeta_codigo)
        if not success:
            raise HTTPException(status_code=404, detail="No se encontró ningún abono para eliminar.")
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

@app.get("/liquidacion/{empleado_id}/{fecha}", response_model=LiquidacionDiaria)
def read_liquidacion_diaria_endpoint(empleado_id: str, fecha: str, principal: dict = Depends(get_current_principal)):
    _enforce_empleado_scope(principal, empleado_id)
    try:
        from datetime import datetime as _dt
        fecha_obj = _dt.strptime(fecha, '%Y-%m-%d').date()
        datos = obtener_datos_liquidacion(empleado_id, fecha_obj)
        # Adaptar tipos a float/int donde aplique
        adaptado = {
            'empleado': datos.get('empleado', empleado_id),
            'fecha': fecha_obj,
            'tarjetas_activas': int(datos.get('tarjetas_activas', 0)),
            'tarjetas_canceladas': int(datos.get('tarjetas_canceladas', 0)),
            'tarjetas_nuevas': int(datos.get('tarjetas_nuevas', 0)),
            'total_registros': int(datos.get('total_registros', 0)),
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

# --- Endpoint de Resumen de Tarjeta ---

@app.get("/tarjetas/{tarjeta_codigo}/resumen")
def read_tarjeta_resumen_endpoint(tarjeta_codigo: str):
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

        monto_total = monto * (1 + interes / 100.0)
        valor_cuota = monto_total / cuotas if cuotas > 0 else monto_total
        saldo_pendiente = max(0.0, monto_total - float(total_abonado))

        # Cálculos según tu regla
        from math import floor, ceil
        from datetime import datetime as dt
        fecha_creacion = tarjeta.get("fecha_creacion")
        hoy = dt.now().date()
        if fecha_creacion:
            fecha_crea = fecha_creacion.date() if hasattr(fecha_creacion, 'date') else fecha_creacion
        else:
            fecha_crea = hoy
        dias_transcurridos = (hoy - fecha_crea).days
        cuotas_pagadas = floor(float(total_abonado) / valor_cuota) if valor_cuota > 0 else 0
        # Puede ser negativo (atraso) o positivo (adelanto). 0 si va al día
        cuotas_pendientes_a_la_fecha = cuotas_pagadas - dias_transcurridos
        # Días pasados desde el vencimiento del plazo (si se superó el número total de cuotas/días)
        dias_pasados_cancelacion = max(0, dias_transcurridos - cuotas)
        cuotas_restantes = ceil(saldo_pendiente / valor_cuota) if valor_cuota > 0 else 0
        # Regla: no mostrar más cuotas pendientes (en atraso) que las restantes por pagar
        if cuotas_pendientes_a_la_fecha < 0 and cuotas_restantes > 0:
            cuotas_pendientes_a_la_fecha = max(cuotas_pendientes_a_la_fecha, -cuotas_restantes)

        resumen = {
            "tarjeta_id": tarjeta_codigo,
            "codigo_tarjeta": tarjeta_codigo,
            "estado_tarjeta": tarjeta.get("estado", "activas"),
            "total_abonado": float(total_abonado),
            "valor_cuota": float(valor_cuota),
            "saldo_pendiente": float(saldo_pendiente),
            "cuotas_restantes": int(cuotas_restantes),
            "cuotas_pendientes_a_la_fecha": int(cuotas_pendientes_a_la_fecha),
            "dias_pasados_cancelacion": int(dias_pasados_cancelacion),
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
                    today = date.today()
                    
                    # Verificar permiso de subida
                    if not subir:
                        raise HTTPException(
                            status_code=403, 
                            detail=f"Empleado {emp_id} no tiene permiso de subida habilitado"
                        )
                    
                    # Verificar fecha de última acción
                    if fecha_accion and fecha_accion >= today:
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
                            SET estado='cancelada'
                            WHERE codigo IN ({placeholders2})
                              AND (estado='activas' OR estado='activa')
                            """,
                            to_cancel,
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
                hoy_local = date.today()
                with DatabasePool.get_cursor() as cur2:
                    cur2.execute(
                        "UPDATE empleados SET fecha_accion=%s, subir=FALSE, descargar=TRUE WHERE identificacion=%s RETURNING identificacion",
                        (hoy_local, emp_id),
                    )
                    if cur2.fetchone() is not None:
                        logger.info(f"Permisos sincronización actualizados para empleado {emp_id}: subir=FALSE, descargar=TRUE, fecha_accion={hoy_local}")
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