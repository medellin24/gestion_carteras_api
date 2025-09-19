from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ..security import require_admin
from ..database.usuarios_db import count_empleados_in_cuenta

router = APIRouter()


class BillingQuote(BaseModel):
    empleados: int
    precio_por_empleado: int
    total_mensual: int


def calcular_precio_mensual_por_empleado(num_empleados: int) -> int:
    # Regla: con 5 empleados ya aplica 25.000; con 1-4 es 30.000
    return 25000 if num_empleados >= 5 else 30000


@router.get("/quote", response_model=BillingQuote)
def get_billing_quote(principal: dict = Depends(require_admin)):
    cuenta_id = principal.get("cuenta_id")
    num_empleados = count_empleados_in_cuenta(cuenta_id) if cuenta_id is not None else 0
    precio = calcular_precio_mensual_por_empleado(num_empleados)
    total = precio * max(1, num_empleados)
    return BillingQuote(empleados=num_empleados, precio_por_empleado=precio, total_mensual=total)


