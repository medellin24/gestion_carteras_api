-- Añade modalidad de pago a tarjetas (default diario)
-- Ejecutar una vez en la BD (PostgreSQL).

ALTER TABLE tarjetas
ADD COLUMN IF NOT EXISTS modalidad_pago VARCHAR(20) NOT NULL DEFAULT 'diario';

-- Normalizar registros antiguos si llegaron a existir con NULL (por seguridad)
UPDATE tarjetas
SET modalidad_pago = 'diario'
WHERE modalidad_pago IS NULL;


