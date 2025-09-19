-- Script de ejemplo para crear una cuenta y usuarios iniciales

-- Crear una cuenta administrativa por defecto
INSERT INTO cuentas_admin (nombre, estado_suscripcion, plan, fecha_inicio)
VALUES ('Cuenta Demo', 'activa', 'standard', NOW())
ON CONFLICT DO NOTHING;

-- Tomar id de la primera cuenta
WITH c AS (
  SELECT id FROM cuentas_admin ORDER BY id ASC LIMIT 1
)
-- Crear usuario admin con password temporal 'admin123' (reemplazar hash en aplicación)
INSERT INTO usuarios (username, password_hash, role, cuenta_id, is_active)
SELECT 'admin', '$2b$12$use_app_hash_here', 'admin', c.id, TRUE FROM c
ON CONFLICT (username) DO NOTHING;


