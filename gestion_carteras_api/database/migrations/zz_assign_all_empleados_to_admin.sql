-- Asignar todos los empleados a la cuenta del admin indicado
UPDATE empleados
SET cuenta_id = (
    SELECT cuenta_id FROM usuarios WHERE username='jorgeale17@hotmail.com' AND role='admin' LIMIT 1
)
WHERE (SELECT cuenta_id FROM usuarios WHERE username='jorgeale17@hotmail.com' AND role='admin' LIMIT 1) IS NOT NULL;

-- Reporte post-actualización
SELECT COUNT(*) AS total_empleados,
       (SELECT cuenta_id FROM usuarios WHERE username='jorgeale17@hotmail.com' AND role='admin' LIMIT 1) AS cuenta_asignada
FROM empleados;
