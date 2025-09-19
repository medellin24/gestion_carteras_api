-- Normalizar bases.empleado_id para que coincida exactamente con empleados.identificacion
-- Corrige casos donde se perdió el cero a la izquierda al haberse guardado como número

-- Actualiza cuando ambos son numéricos y coinciden por su valor entero
UPDATE bases b
SET empleado_id = e.identificacion
FROM empleados e
WHERE b.empleado_id ~ '^[0-9]+$'
  AND e.identificacion ~ '^[0-9]+$'
  AND b.empleado_id::bigint = e.identificacion::bigint
  AND b.empleado_id <> e.identificacion;

-- Reporte de pendientes (bases sin empleado asociado exacto)
SELECT COUNT(*) AS bases_huerfanas
FROM bases b
LEFT JOIN empleados e ON e.identificacion = b.empleado_id
WHERE e.identificacion IS NULL;
