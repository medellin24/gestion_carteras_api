-- Agregar columna metodo_pago a abonos: 'efectivo' | 'consignacion' (idempotente)
ALTER TABLE abonos ADD COLUMN IF NOT EXISTS metodo_pago TEXT NOT NULL DEFAULT 'efectivo';
CREATE INDEX IF NOT EXISTS idx_abonos_metodo_pago ON abonos(metodo_pago);


