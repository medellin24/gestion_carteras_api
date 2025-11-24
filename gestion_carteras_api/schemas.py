from pydantic import BaseModel
from typing import Optional, List
from datetime import date, datetime

class ClienteBase(BaseModel):
    identificacion: str
    nombre: str
    apellido: str
    telefono: Optional[str] = None
    direccion: Optional[str] = None
    email: Optional[str] = None
    profesion: Optional[str] = None
    empresa: Optional[str] = None
    referencia_nombre: Optional[str] = None
    referencia_telefono: Optional[str] = None
    observaciones: Optional[str] = None

class ClienteCreate(ClienteBase):
    pass

class ClienteUpdate(BaseModel):
    nombre: Optional[str] = None
    apellido: Optional[str] = None
    telefono: Optional[str] = None
    direccion: Optional[str] = None
    email: Optional[str] = None
    profesion: Optional[str] = None
    empresa: Optional[str] = None
    referencia_nombre: Optional[str] = None
    referencia_telefono: Optional[str] = None
    observaciones: Optional[str] = None

class Cliente(ClienteBase):
    fecha_creacion: Optional[date] = None

    class Config:
        from_attributes = True

class EmpleadoBase(BaseModel):
    identificacion: str
    nombre_completo: str
    telefono: Optional[str] = None
    direccion: Optional[str] = None

class EmpleadoCreate(EmpleadoBase):
    pass

class EmpleadoUpdate(BaseModel):
    nombre_completo: Optional[str] = None
    telefono: Optional[str] = None
    direccion: Optional[str] = None

class Empleado(EmpleadoBase):
    class Config:
        orm_mode = True

class TarjetaBase(BaseModel):
    cliente_identificacion: str
    empleado_identificacion: str
    monto: float
    cuotas: int
    interes: int
    observaciones: Optional[str] = None

class TarjetaCreate(TarjetaBase):
    numero_ruta: Optional[float] = None
    posicion_anterior: Optional[float] = None
    posicion_siguiente: Optional[float] = None
    fecha_creacion: Optional[datetime] = None

class TarjetaUpdate(BaseModel):
    monto: Optional[float] = None
    cuotas: Optional[int] = None
    interes: Optional[int] = None
    numero_ruta: Optional[float] = None
    observaciones: Optional[str] = None
    estado: Optional[str] = None

class ClienteLite(BaseModel):
    identificacion: str
    nombre: str
    apellido: str


class Tarjeta(TarjetaBase):
    codigo: str
    numero_ruta: float
    estado: str
    fecha_creacion: datetime
    fecha_cancelacion: Optional[date] = None
    cliente: ClienteLite

    class Config:
        orm_mode = True

class AbonoBase(BaseModel):
    monto: float
    metodo_pago: Optional[str] = 'efectivo'

class AbonoCreate(AbonoBase):
    tarjeta_codigo: str
    id_temporal: Optional[str] = None

class AbonoUpdate(BaseModel):
    monto: Optional[float] = None
    fecha: Optional[datetime] = None

class Abono(AbonoBase):
    id: int
    tarjeta_codigo: str
    fecha: datetime
    indice_orden: int

    class Config:
        orm_mode = True

class AbonoConCliente(BaseModel):
    id: int
    fecha: datetime
    monto: float
    tarjeta_codigo: str
    cliente_nombre: str
    cliente_apellido: str

class Base(BaseModel):
    id: int
    empleado_id: str
    fecha: date
    monto: float
    empleado_nombre: Optional[str] = None

    class Config:
        orm_mode = True

class BaseCreate(BaseModel):
    empleado_id: str
    fecha: date
    monto: float

class BaseUpdate(BaseModel):
    monto: float

class TipoGasto(BaseModel):
    id: int
    nombre: str
    descripcion: str

class GastoBase(BaseModel):
    tipo: str
    valor: float
    observacion: Optional[str] = None
    fecha: Optional[date] = None

class GastoCreate(GastoBase):
    empleado_identificacion: str

class GastoUpdate(BaseModel):
    tipo: Optional[str] = None
    valor: Optional[float] = None
    observacion: Optional[str] = None

class Gasto(GastoBase):
    id: int
    empleado_identificacion: str
    fecha_creacion: datetime

    class Config:
        orm_mode = True

class ResumenGasto(BaseModel):
    tipo: str
    cantidad: int
    total: float

class LiquidacionDiaria(BaseModel):
    empleado: str
    fecha: date
    tarjetas_activas: int
    tarjetas_canceladas: int
    tarjetas_nuevas: int
    total_registros: int
    total_recaudado: float
    base_dia: float
    prestamos_otorgados: float
    total_gastos: float
    subtotal: float
    total_final: float

class ResumenFinanciero(BaseModel):
    fecha: date
    total_recaudado_todos: float
    total_bases_asignadas: float
    total_prestamos_otorgados: float
    total_gastos_todos: float
    empleados_activos: int 

# --- Modelos para sincronización ---

class SyncTarjetaNew(BaseModel):
    temp_id: str
    cliente: ClienteBase
    empleado_identificacion: str
    monto: float
    cuotas: int
    interes: int
    numero_ruta: Optional[float] = None
    observaciones: Optional[str] = None
    posicion_anterior: Optional[float] = None
    posicion_siguiente: Optional[float] = None

class SyncAbonoItem(BaseModel):
    id_temporal: Optional[str] = None
    tarjeta_codigo: str  # puede ser codigo real o temp_id de tarjeta
    monto: float
    metodo_pago: str

class SyncGastoItem(BaseModel):
    empleado_identificacion: str
    tipo: str
    valor: float
    observacion: Optional[str] = None
    fecha: Optional[date] = None

class SyncBaseItem(BaseModel):
    empleado_id: str
    fecha: date
    monto: float

class SyncRequest(BaseModel):
    idempotency_key: str
    tarjetas_nuevas: List[SyncTarjetaNew] = []
    abonos: List[SyncAbonoItem] = []
    gastos: List[SyncGastoItem] = []
    bases: List[SyncBaseItem] = []

class SyncResponse(BaseModel):
    already_processed: bool = False
    created_tarjetas: List[dict] = []  # {temp_id, codigo}
    created_abonos: List[dict] = []    # {id_temporal, id}
    created_gastos: int = 0
    created_bases: int = 0

# --- Control de descargas diarias por plan ---

class AttemptDownloadRequest(BaseModel):
    empleado_identificacion: str

class AttemptDownloadResponse(BaseModel):
    allowed: bool
    used: int
    limit: int
    already_registered: bool = False
    message: str = ""

# --- Modelos de Contabilidad / Caja ---

class ContabilidadQuery(BaseModel):
    empleado_id: Optional[str] = None  # None -> consolidado
    desde: date
    hasta: date

class ContabilidadMetricas(BaseModel):
    desde: date
    hasta: date
    empleado_id: Optional[str] = None
    total_cobrado: float
    total_prestamos: float
    total_gastos: float
    total_bases: float
    total_salidas: float
    total_entradas: float = 0.0
    caja: float  # saldo_caja desde control_caja en la fecha 'hasta'
    total_intereses: float = 0.0
    ganancia: float = 0.0
    cartera_en_calle: float = 0.0
    cartera_en_calle_desde: float = 0.0
    abonos_count: int = 0
    dias_en_rango: int = 0

class CajaValor(BaseModel):
    fecha: date
    valor: float

class CajaSalidaBase(BaseModel):
    fecha: date
    valor: float
    concepto: Optional[str] = None
    empleado_identificacion: Optional[str] = None

class CajaSalidaCreate(CajaSalidaBase):
    pass

class CajaSalida(CajaSalidaBase):
    id: int

    class Config:
        orm_mode = True

class CajaEntradaCreate(CajaSalidaBase):
    pass

class CajaEntrada(CajaSalidaBase):
    id: int

    class Config:
        orm_mode = True

class VerificacionEsquemaCaja(BaseModel):
    ok: bool
    tabla_caja: bool
    tabla_salidas: bool
    columnas_caja: List[str] = []
    columnas_salidas: List[str] = []