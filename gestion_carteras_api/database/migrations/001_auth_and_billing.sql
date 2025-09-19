-- Tablas mínimas para cuentas administrativas y usuarios

CREATE TABLE IF NOT EXISTS cuentas_admin (
    id SERIAL PRIMARY KEY,
    nombre TEXT NOT NULL,
    estado_suscripcion TEXT NOT NULL DEFAULT 'activa', -- activa | vencida | suspendida
    plan TEXT NULL,
    fecha_inicio TIMESTAMP NULL,
    fecha_fin TIMESTAMP NULL
);

-- Añadir cuenta_id a empleados para asociarlos a una cuenta administrativa
ALTER TABLE empleados
    ADD COLUMN IF NOT EXISTS cuenta_id INTEGER REFERENCES cuentas_admin(id);

-- Tabla de usuarios para autenticación
CREATE TABLE IF NOT EXISTS usuarios (
    id SERIAL PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('admin','cobrador')),
    cuenta_id INTEGER NULL REFERENCES cuentas_admin(id),
    empleado_identificacion TEXT NULL REFERENCES empleados(identificacion),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Índices útiles
CREATE INDEX IF NOT EXISTS idx_empleados_cuenta_id ON empleados(cuenta_id);
CREATE INDEX IF NOT EXISTS idx_usuarios_role ON usuarios(role);


