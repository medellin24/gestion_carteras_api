import os
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context

# Cargar configuración de logging desde alembic.ini
config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# No usamos metadata autogenerada (psycopg2 directo en la app)
target_metadata = None

def get_database_url() -> str:
    url = os.getenv("DATABASE_URL", "").strip()
    if url:
        return url
    # Construir desde variables por separado si no hay DATABASE_URL
    host = os.getenv("DB_HOST", "")
    name = os.getenv("DB_NAME", "")
    user = os.getenv("DB_USER", "")
    password = os.getenv("DB_PASSWORD", "")
    port = os.getenv("DB_PORT", "5432")
    if all([host, name, user, password]):
        return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{name}"
    raise RuntimeError("DATABASE_URL no definida y variables DB_* incompletas para Alembic")

def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url") or get_database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = configuration.get("sqlalchemy.url") or get_database_url()

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()


