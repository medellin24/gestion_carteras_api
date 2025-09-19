BEGIN;

-- Eliminar constraint único si existe
ALTER TABLE bases DROP CONSTRAINT IF EXISTS bases_empleado_id_fecha_key;

-- Cambiar tipo a TEXT
ALTER TABLE bases
    ALTER COLUMN empleado_id TYPE TEXT USING empleado_id::text;

-- Recrear constraint único
ALTER TABLE bases
    ADD CONSTRAINT bases_empleado_id_fecha_key UNIQUE (empleado_id, fecha);

-- Eliminar FK previa si existiera
ALTER TABLE bases DROP CONSTRAINT IF EXISTS fk_bases_empleado;

-- Crear FK hacia empleados(identificacion)
ALTER TABLE bases
    ADD CONSTRAINT fk_bases_empleado FOREIGN KEY (empleado_id)
    REFERENCES empleados(identificacion) ON DELETE RESTRICT;

COMMIT;
