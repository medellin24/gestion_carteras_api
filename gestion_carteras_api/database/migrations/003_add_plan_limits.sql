-- Añade límites de plan y periodo de prueba a cuentas_admin
ALTER TABLE cuentas_admin
    ADD COLUMN IF NOT EXISTS max_empleados INTEGER DEFAULT 1,
    ADD COLUMN IF NOT EXISTS trial_until DATE NULL;


