## Regla de Timezone: creación, guardado, filtro y visualización

Objetivo: Evitar desfases de día y asegurar consistencia entre backend, UI de escritorio y frontend al trabajar con zonas horarias.

### Fuente de timezone
- Usar siempre la timezone del usuario obtenida del JWT del login (`principal.timezone`).
- Si no existe o falla `ZoneInfo`, usar `'UTC'` como fallback.
- Asegurar `tzdata` instalada en entornos donde sea necesario.

### Creación e importación (tarjetas nuevas)
- Si `fecha_creacion` llega sin timezone (naive), interpretarla como hora local del usuario (timezone del token).
- Si llega solo fecha (sin hora), construir `hh:mm:ss = 12:00:00` en la zona local para minimizar riesgos de bordes.
- Convertir a UTC y guardar como `TIMESTAMP` sin tz en la base (UTC naive).

### Guardado en base de datos
- Columnas `TIMESTAMP` (ej. `fecha_creacion`): guardar siempre en UTC naive.
- Columnas `DATE` (ej. `fecha_cancelacion`): guardar como fecha de día local; no aplicar conversiones de tz.

### Filtros por día
- El parámetro `fecha` (YYYY-MM-DD) representa el día LOCAL del usuario.
- Para filtrar `TIMESTAMP` (p.ej. tarjetas nuevas):
  1) Construir límites locales `[00:00:00, 23:59:59.999]` en la tz del usuario.
  2) Convertir ambos a UTC.
  3) Aplicar filtro `BETWEEN start_utc AND end_utc` sobre la columna UTC naive.
- Para filtrar `DATE` (p.ej. tarjetas canceladas): igualdad directa `fecha_cancelacion = fecha_local` (sin conversiones).

### Visualización (UI/Frontend/Escritorio)
- Preferir que el backend devuelva un campo `fecha` ya normalizado al día local cuando sea útil.
- Si no hay `fecha`, los clientes deben convertir `fecha_creacion` (UTC naive) a la timezone del usuario antes de formatear.
- Inicializar calendarios y pickers con “hoy” en la timezone del usuario, no con la del sistema.

### Endpoints afectados (referencia)
- Creación de tarjeta (aceptar naive como local y convertir a UTC naive).
- Tarjetas nuevas del día (filtro por rango UTC derivado de día local).
- Tarjetas canceladas del día (filtro por igualdad de `DATE`).
- Resumen de liquidación (usar reglas anteriores para cada bloque: abonos, base del día, préstamos, gastos, nuevas, canceladas).

### Logging
- En desarrollo, se pueden usar prints para depurar.
- En staging/producción, no dejar prints de depuración.

### Pruebas recomendadas
- Crear tarjetas cerca de medianoche local (21:00–23:59) y validar que aparezcan bajo el día local esperado.
- Verificar importación masiva desde Excel: fechas sin hora se interpretan como 12:00 local, se guardan en UTC naive y se filtran correctamente por día local.


