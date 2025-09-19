-- Paso 1: cambiar tipo y recrear unique sin añadir FK
ALTER TABLE bases DROP CONSTRAINT IF EXISTS bases_empleado_id_fecha_key;
ALTER TABLE bases DROP CONSTRAINT IF EXISTS fk_bases_empleado;
ALTER TABLE bases ALTER COLUMN empleado_id TYPE TEXT USING empleado_id::text;
ALTER TABLE bases ADD CONSTRAINT bases_empleado_id_fecha_key UNIQUE (empleado_id, fecha);
