-- Agrega columnas de control de permisos diarios a empleados
-- descargar (boolean), subir (boolean), fecha_accion (date)
-- Inicialización recomendada: descargar = TRUE, subir = FALSE, fecha_accion = (CURRENT_DATE - 1)

BEGIN;

ALTER TABLE empleados
  ADD COLUMN IF NOT EXISTS descargar boolean NOT NULL DEFAULT TRUE;

ALTER TABLE empleados
  ADD COLUMN IF NOT EXISTS subir boolean NOT NULL DEFAULT FALSE;

ALTER TABLE empleados
  ADD COLUMN IF NOT EXISTS fecha_accion date NOT NULL DEFAULT (CURRENT_DATE - 1);

COMMIT;


