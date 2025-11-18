-- Migration: Normalize tarjetas.fecha_creacion to TIMESTAMP WITHOUT TIME ZONE (UTC)
-- Safe to run once. Review in staging before production.

BEGIN;

-- 1) Ensure column uses TIMESTAMP WITHOUT TIME ZONE
--    If it's already timestamp, this is a no-op conversion.
ALTER TABLE tarjetas
ALTER COLUMN fecha_creacion TYPE timestamp WITHOUT TIME ZONE
USING (
  CASE
    WHEN pg_typeof(fecha_creacion) = 'date'::regtype
      THEN (fecha_creacion::timestamp)
    ELSE (fecha_creacion::timestamp)
  END
);

-- 2) Set a UTC-based default for future inserts
ALTER TABLE tarjetas
  ALTER COLUMN fecha_creacion SET DEFAULT (now() AT TIME ZONE 'utc');

-- 3) Optional: shift historical rows that are exactly midnight to avoid local day-edge issues
--    Uncomment if you need to avoid -05 falling into the previous day visually.
--    Test first; this is opinionated.
-- UPDATE tarjetas
-- SET fecha_creacion = fecha_creacion + INTERVAL '12 hours'
-- WHERE date_part('hour', fecha_creacion) = 0
--   AND date_part('minute', fecha_creacion) = 0
--   AND date_part('second', fecha_creacion) = 0;

-- 4) Index to speed up daily queries by empleado and date range
CREATE INDEX IF NOT EXISTS idx_tarjetas_emp_fecha
  ON tarjetas (empleado_identificacion, fecha_creacion);

COMMIT;

-- How to run:
-- psql "postgresql://USER:PASS@HOST:PORT/DBNAME" -f DB_MIGRATION_TARJETAS_TIMESTAMP.sql


