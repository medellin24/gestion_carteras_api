-- Paso 2: normalizar valores y reinstalar FK

-- Trimear espacios accidentales
UPDATE bases SET empleado_id = TRIM(empleado_id);

-- Reporte
SELECT COUNT(*) AS bases_sin_empleado
FROM bases b
LEFT JOIN empleados e ON e.identificacion = b.empleado_id
WHERE e.identificacion IS NULL;

-- Reinstalar FK (solo si no hay huérfanas)
ALTER TABLE bases DROP CONSTRAINT IF EXISTS fk_bases_empleado;
ALTER TABLE bases ADD CONSTRAINT fk_bases_empleado FOREIGN KEY (empleado_id)
REFERENCES empleados(identificacion) ON DELETE RESTRICT;
