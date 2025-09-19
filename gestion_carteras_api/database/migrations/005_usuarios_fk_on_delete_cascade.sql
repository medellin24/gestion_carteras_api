BEGIN;

-- Eliminar FK anterior si existe (nombre estándar)
ALTER TABLE usuarios DROP CONSTRAINT IF EXISTS usuarios_empleado_identificacion_fkey;

-- Crear FK con ON DELETE SET NULL
ALTER TABLE usuarios
    ADD CONSTRAINT usuarios_empleado_identificacion_fkey
    FOREIGN KEY (empleado_identificacion)
    REFERENCES empleados(identificacion)
    ON DELETE SET NULL;

COMMIT;
