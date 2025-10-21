-- Agrega columna timezone a usuarios (zona horaria IANA, ej: 'America/Bogota')
ALTER TABLE usuarios
    ADD COLUMN IF NOT EXISTS timezone TEXT NULL;

-- Valor por defecto sugerido para cuentas nuevas (opcional):
-- UPDATE usuarios SET timezone='UTC' WHERE timezone IS NULL;

-- Nota: la aplicación debe interpretar todas las columnas TIMESTAMP como UTC
-- y convertir a la zona del usuario al serializar. 

