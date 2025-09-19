-- Un cobrador activo por empleado por cuenta
CREATE UNIQUE INDEX IF NOT EXISTS ux_cobrador_unico_por_empleado
ON usuarios (cuenta_id, empleado_identificacion)
WHERE role = 'cobrador' AND is_active = TRUE;
