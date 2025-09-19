-- Corregir empleado_id en bases usando coincidencia numérica con empleados.identificacion
UPDATE bases b
SET empleado_id = e.identificacion
FROM empleados e
WHERE b.empleado_id ~ '^[0-9]+$'
  AND e.identificacion ~ '^[0-9]+$'
  AND b.empleado_id::bigint = e.identificacion::bigint
  AND b.empleado_id <> e.identificacion;

-- Verificar cuántas quedan huérfanas después del fix
SELECT COUNT(*) AS bases_huerfanas_restantes
FROM bases b
LEFT JOIN empleados e ON e.identificacion = b.empleado_id
WHERE e.identificacion IS NULL;
