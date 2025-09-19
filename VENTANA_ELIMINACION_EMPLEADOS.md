# Ventana de Eliminación de Empleados - Documentación

## Descripción

Se ha implementado una nueva ventana emergente que maneja inteligentemente la eliminación de empleados, proporcionando diferentes opciones según si el empleado tiene tarjetas asociadas o no.

## Funcionalidades Implementadas

### 1. VentanaEliminarEmpleado

**Ubicación**: `frames/frame_empleado.py`

**Características**:
- Ventana modal que se abre al hacer clic en "🗑️ Eliminar"
- Verifica automáticamente si el empleado tiene tarjetas asociadas
- Muestra diferentes opciones según la situación

### 2. Flujo de Eliminación

#### Caso 1: Empleado sin tarjetas
- **Comportamiento**: Muestra confirmación simple
- **Opciones**: 
  - ✅ Eliminar Empleado
  - ✖ Cancelar

#### Caso 2: Empleado con tarjetas asociadas
- **Comportamiento**: Muestra advertencia y opciones avanzadas
- **Opciones disponibles**:

##### Opción 1: Transferir Tarjetas
- **Descripción**: Transfiere todas las tarjetas a otro empleado
- **Interfaz**: 
  - Combobox con lista de empleados disponibles
  - Botón "🔄 Transferir"
- **Proceso**:
  1. Seleccionar empleado destino
  2. Confirmar transferencia
  3. Realizar transferencia
  4. Eliminar empleado original

##### Opción 2: Eliminación Forzada
- **Descripción**: Elimina empleado y todas sus tarjetas
- **Advertencias**: 
  - ⚠️ Acción IRREVERSIBLE
  - Elimina todas las tarjetas del empleado
  - Elimina todos los abonos asociados
  - Elimina el empleado
- **Proceso**:
  1. Marcar checkbox de confirmación
  2. Confirmación final
  3. Eliminación completa

### 3. Métodos del API Client

**Ubicación**: `api_client/client.py`

#### transferir_tarjetas_empleado()
```python
def transferir_tarjetas_empleado(self, empleado_origen: str, empleado_destino: str) -> Dict:
    """Transfiere todas las tarjetas de un empleado a otro empleado."""
```

#### eliminar_empleado_forzado()
```python
def eliminar_empleado_forzado(self, identificacion: str) -> Dict:
    """Elimina un empleado y opcionalmente todas sus tarjetas asociadas."""
```

### 4. Endpoints de la API Utilizados

#### POST /empleados/{id}/transferir-tarjetas
- **Payload**: `{"empleado_destino": "1234567890", "confirmar_transferencia": true}`
- **Función**: Transfiere todas las tarjetas del empleado origen al empleado destino

#### DELETE /empleados/{id}/forzar-eliminacion
- **Payload**: `{"confirmar_eliminacion": true, "eliminar_tarjetas": true}`
- **Función**: Elimina el empleado y todas sus tarjetas asociadas

## Interfaz de Usuario

### Diseño Visual
- **Tamaño**: 600x500 píxeles
- **Estilo**: Ventana modal con fondo blanco
- **Colores**:
  - 🔴 Rojo: Advertencias y acciones peligrosas
  - 🔵 Azul: Información y acciones normales
  - ⚫ Negro: Texto normal

### Elementos de la Interfaz

#### Información del Empleado
```
┌─ Información del Empleado ─┐
│ 👤 Nombre: Juan Pérez      │
│ 🆔 Identificación: 123456  │
│ 📞 Teléfono: 555-1234      │
│ 🏠 Dirección: Calle 123    │
└────────────────────────────┘
```

#### Opciones de Transferencia
```
┌─ Opciones Disponibles ─┐
│ 1️⃣ Transferir tarjetas │
│ Empleado destino: [▼]  │
│ [🔄 Transferir]        │
│                        │
│ 2️⃣ Eliminación forzada │
│ ⚠️ ADVERTENCIA: ...    │
│ ☑ Confirmo consecuencias│
│ [💥 Eliminar Todo]     │
└────────────────────────┘
```

## Flujo de Trabajo

### 1. Acceso a la Ventana
1. Usuario selecciona empleado en la lista
2. Hace clic en "🗑️ Eliminar"
3. Se abre `VentanaEliminarEmpleado`

### 2. Verificación Automática
1. La ventana intenta eliminar el empleado
2. Si falla por restricción de clave foránea:
   - Muestra opciones avanzadas
3. Si no falla:
   - Muestra confirmación simple

### 3. Procesamiento de Opciones

#### Transferencia de Tarjetas
1. Cargar lista de empleados disponibles
2. Usuario selecciona empleado destino
3. Confirmar transferencia
4. Realizar transferencia via API
5. Mostrar mensaje de éxito
6. Cerrar ventana y actualizar lista

#### Eliminación Forzada
1. Usuario marca checkbox de confirmación
2. Confirmación final con advertencia
3. Realizar eliminación via API
4. Mostrar mensaje de éxito
5. Cerrar ventana y actualizar lista

## Manejo de Errores

### Errores de Red
- **Manejo**: Try-catch en cada operación
- **UI**: Messagebox con mensaje de error
- **Comportamiento**: Ventana permanece abierta

### Errores de Validación
- **Empleado no seleccionado**: Warning messagebox
- **Confirmación requerida**: Warning messagebox
- **Empleado no encontrado**: Error messagebox

### Errores de API
- **Status 404**: "Empleado no encontrado"
- **Status 409**: "Empleado tiene tarjetas asociadas"
- **Status 500**: "Error interno del servidor"

## Beneficios

### Para el Usuario
1. **Claridad**: Opciones claras y bien explicadas
2. **Seguridad**: Múltiples confirmaciones para acciones peligrosas
3. **Flexibilidad**: Diferentes opciones según la situación
4. **Información**: Detalles completos del empleado y sus tarjetas

### Para el Sistema
1. **Integridad**: Previene errores de restricción de clave foránea
2. **Consistencia**: Manejo uniforme de eliminaciones
3. **Auditabilidad**: Registro de todas las operaciones
4. **Mantenibilidad**: Código organizado y reutilizable

## Consideraciones Técnicas

### Dependencias
- `tkinter`: Interfaz gráfica
- `ttk`: Widgets modernos
- `messagebox`: Diálogos de confirmación
- `api_client`: Comunicación con la API

### Rendimiento
- **Carga de empleados**: Asíncrona en segundo plano
- **Verificación de tarjetas**: Automática al abrir ventana
- **Operaciones**: Con indicadores de progreso

### Seguridad
- **Confirmaciones múltiples**: Para acciones irreversibles
- **Validación de entrada**: En todos los campos
- **Manejo de errores**: Robusto y informativo

## Pruebas Recomendadas

### Casos de Prueba
1. **Empleado sin tarjetas**: Verificar eliminación simple
2. **Empleado con tarjetas**: Verificar opciones avanzadas
3. **Transferencia exitosa**: Verificar transferencia de tarjetas
4. **Eliminación forzada**: Verificar eliminación completa
5. **Errores de red**: Verificar manejo de errores
6. **Validaciones**: Verificar mensajes de error apropiados

### Datos de Prueba
- Empleado con 0 tarjetas
- Empleado con 5+ tarjetas activas
- Empleado con tarjetas canceladas
- Empleado con tarjetas mixtas (activas + canceladas)
