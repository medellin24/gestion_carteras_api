# Solución para Error de Eliminación de Empleados

## Problema Original

El error que estabas experimentando era:

```
ERROR:gestion_carteras_api.database.connection_pool:Error en operación de BD: update or delete on table "empleados" violates foreign key constraint "tarjetas_empleado_identificacion_fkey" on table "tarjetas"
DETAIL:  Key (identificacion)=(1045112243) is still referenced from table "tarjetas".
```

Este error ocurre cuando intentas eliminar un empleado que aún tiene tarjetas asociadas en la tabla `tarjetas`. La base de datos impide esta operación para mantener la integridad referencial.

## Solución Implementada

### 1. Funciones de Verificación (empleados_db.py)

Se agregaron dos nuevas funciones:

- **`verificar_empleado_tiene_tarjetas(identificacion: str)`**: Verifica si un empleado tiene tarjetas asociadas y retorna la cantidad.
- **`obtener_tarjetas_empleado(identificacion: str)`**: Obtiene todas las tarjetas asociadas a un empleado con sus detalles.

### 2. Endpoint DELETE Mejorado

El endpoint `DELETE /empleados/{identificacion}` ahora:

1. **Verifica la existencia del empleado**
2. **Verifica si tiene tarjetas asociadas**
3. **Si tiene tarjetas**: Retorna un error 409 (Conflict) con información detallada
4. **Si no tiene tarjetas**: Procede con la eliminación normal

### 3. Nuevos Endpoints para Manejo de Casos Especiales

#### A. Transferir Tarjetas
**`POST /empleados/{identificacion}/transferir-tarjetas`**

Permite transferir todas las tarjetas de un empleado a otro empleado.

```json
{
  "empleado_destino": "1234567890",
  "confirmar_transferencia": true
}
```

#### B. Eliminación Forzada
**`DELETE /empleados/{identificacion}/forzar-eliminacion`**

Permite eliminar un empleado y opcionalmente todas sus tarjetas asociadas.

```json
{
  "confirmar_eliminacion": true,
  "eliminar_tarjetas": true
}
```

## Cómo Usar la Solución

### Escenario 1: Empleado sin tarjetas
```bash
DELETE /empleados/1234567890
```
**Resultado**: Eliminación exitosa (200 OK)

### Escenario 2: Empleado con tarjetas
```bash
DELETE /empleados/1045112243
```
**Resultado**: Error 409 con información detallada:
```json
{
  "error": "No se puede eliminar el empleado porque tiene tarjetas asociadas",
  "empleado": {...},
  "tarjetas_asociadas": {
    "total": 5,
    "activas": 3,
    "canceladas": 2,
    "detalle": [...]
  },
  "opciones": [
    "Transferir todas las tarjetas a otro empleado",
    "Cancelar todas las tarjetas activas primero",
    "Eliminar empleado y todas sus tarjetas (acción irreversible)"
  ]
}
```

### Escenario 3: Transferir tarjetas
```bash
POST /empleados/1045112243/transferir-tarjetas
{
  "empleado_destino": "9876543210",
  "confirmar_transferencia": true
}
```

### Escenario 4: Eliminación forzada
```bash
DELETE /empleados/1045112243/forzar-eliminacion
{
  "confirmar_eliminacion": true,
  "eliminar_tarjetas": true
}
```

## Beneficios de la Solución

1. **Previene errores de base de datos**: Ya no recibirás el error de restricción de clave foránea
2. **Proporciona información útil**: El error 409 incluye detalles sobre las tarjetas asociadas
3. **Ofrece opciones**: Presenta alternativas para manejar la situación
4. **Mantiene integridad**: Las operaciones son seguras y reversibles (excepto la eliminación forzada)
5. **Flexibilidad**: Permite diferentes estrategias según el caso de uso

## Pruebas

Se incluye un script de prueba (`test_empleado_delete_fix.py`) que verifica:

- El manejo correcto del error de restricción de clave foránea
- La verificación de tarjetas asociadas
- El funcionamiento de los nuevos endpoints

Para ejecutar las pruebas:
```bash
python test_empleado_delete_fix.py
```

## Consideraciones de Seguridad

- **Eliminación forzada**: Es una acción irreversible que elimina datos permanentemente
- **Transferencia de tarjetas**: Cambia la propiedad de las tarjetas, afectando reportes y liquidaciones
- **Permisos**: Todos los endpoints requieren permisos de administrador

## Recomendaciones

1. **Siempre verifica** las tarjetas asociadas antes de eliminar un empleado
2. **Usa transferencia** cuando sea posible en lugar de eliminación forzada
3. **Documenta** las transferencias y eliminaciones para auditoría
4. **Considera** implementar un sistema de soft delete para empleados importantes
