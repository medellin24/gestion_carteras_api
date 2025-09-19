BEGIN;
ALTER TABLE usuarios DROP CONSTRAINT IF EXISTS usuarios_empleado_identificacion_fkey;
ALTER TABLE usuarios
    ADD CONSTRAINT usuarios_empleado_identificacion_fkey
    FOREIGN KEY (empleado_identificacion)
    REFERENCES empleados(identificacion)
    ON DELETE CASCADE;
COMMIT;
