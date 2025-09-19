-- Asignar cuenta_id a empleados sin cuenta usando el cuenta_id del admin dado
UPDATE empleados
SET cuenta_id = (
    SELECT cuenta_id FROM usuarios WHERE username = 'jorgeale17@hotmail.com' AND role='admin' LIMIT 1
)
WHERE cuenta_id IS NULL;

-- Reporte: cuántos aún quedan sin cuenta
SELECT COUNT(*) AS empleados_sin_cuenta_restantes FROM empleados WHERE cuenta_id IS NULL;
