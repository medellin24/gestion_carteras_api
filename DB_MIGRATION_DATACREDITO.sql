-- Migración para DataCrédito Interno
-- Ejecutar en la base de datos PostgreSQL

-- 1. Agregar columna para el Historial Compactado (JSON)
-- Guardará el array de objetos compactados de tarjetas antiguas.
ALTER TABLE clientes ADD COLUMN historial_crediticio JSONB DEFAULT '[]'::jsonb;

-- 2. Agregar columna para el Score Global (0-100)
-- Guardará el puntaje calculado para no recalcularlo en cada consulta simple.
ALTER TABLE clientes ADD COLUMN score_global INTEGER DEFAULT 100;

-- 3. Índices recomendados (Opcional, para búsquedas futuras por score)
CREATE INDEX IF NOT EXISTS idx_clientes_score ON clientes(score_global);

