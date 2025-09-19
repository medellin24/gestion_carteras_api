-- Diagnóstico de calidad de datos (solo lectura)
-- Cuenta NULLs y FKs huérfanas relevantes para tarjetas/abonos/clientes

SELECT 
    'tarjetas_nulls' AS section,
    SUM(CASE WHEN monto IS NULL THEN 1 ELSE 0 END) AS tarjetas_monto_null,
    SUM(CASE WHEN interes IS NULL THEN 1 ELSE 0 END) AS tarjetas_interes_null,
    SUM(CASE WHEN cuotas IS NULL THEN 1 ELSE 0 END) AS tarjetas_cuotas_null,
    SUM(CASE WHEN fecha_creacion IS NULL THEN 1 ELSE 0 END) AS tarjetas_fecha_creacion_null,
    SUM(CASE WHEN cliente_identificacion IS NULL THEN 1 ELSE 0 END) AS tarjetas_cliente_id_null,
    SUM(CASE WHEN empleado_identificacion IS NULL THEN 1 ELSE 0 END) AS tarjetas_empleado_id_null,
    SUM(CASE WHEN numero_ruta IS NULL THEN 1 ELSE 0 END) AS tarjetas_numero_ruta_null
FROM tarjetas;

SELECT 'tarjetas_cliente_huerfana' AS section, COUNT(*) AS count
FROM tarjetas t
LEFT JOIN clientes c ON c.identificacion = t.cliente_identificacion
WHERE c.identificacion IS NULL;

SELECT 'abonos_nulls' AS section,
    SUM(CASE WHEN monto IS NULL THEN 1 ELSE 0 END) AS abonos_monto_null,
    SUM(CASE WHEN fecha IS NULL THEN 1 ELSE 0 END) AS abonos_fecha_null,
    SUM(CASE WHEN tarjeta_codigo IS NULL THEN 1 ELSE 0 END) AS abonos_tarjeta_codigo_null
FROM abonos;

SELECT 'abonos_tarjeta_huerfana' AS section, COUNT(*) AS count
FROM abonos a
LEFT JOIN tarjetas t ON t.codigo = a.tarjeta_codigo
WHERE t.codigo IS NULL;

SELECT 'tarjetas_empleado_huerfana' AS section, COUNT(*) AS count
FROM tarjetas t
LEFT JOIN empleados e ON e.identificacion = t.empleado_identificacion
WHERE e.identificacion IS NULL;
