from psycopg2 import pool
import psycopg2
import time
from contextlib import contextmanager
import logging

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DatabasePool:
    _pool = None

    @classmethod
    def initialize(cls, minconn=1, maxconn=10, **db_config):
        """Inicializa el pool de conexiones"""
        try:
            # Opciones de socket/keepalive (si el server las soporta)
            db_config.setdefault('connect_timeout', 10)
            # sslmode ya viene desde DB_CONFIG si aplica
            cls._pool = pool.SimpleConnectionPool(
                minconn=minconn,
                maxconn=maxconn,
                **db_config
            )
            logger.info(f"Pool de conexiones inicializado. Min: {minconn}, Max: {maxconn}")
        except Exception as e:
            logger.error(f"Error al inicializar el pool de conexiones: {e}")
            raise

    @classmethod
    @contextmanager
    def get_cursor(cls):
        conn = None
        cursor = None
        try:
            # Intentar hasta 2 reintentos si la conexión viene caída
            attempts = 0
            last_exc = None
            while attempts < 2:
                try:
                    conn = cls._pool.getconn()
                    # Verificar conexión viva
                    try:
                        with conn.cursor() as _c:
                            _c.execute('SELECT 1')
                            _ = _c.fetchone()
                    except Exception:
                        # Reconectar si la conexión está rota
                        try:
                            conn.close()
                        except Exception:
                            pass
                        # Crear una nueva conexión cruda y ponerla en el pool
                        new_conn = psycopg2.connect(**cls._pool._kwargs)
                        conn = new_conn
                    cursor = conn.cursor()
                    break
                except Exception as e:
                    last_exc = e
                    attempts += 1
                    time.sleep(0.5)
            if cursor is None and last_exc:
                raise last_exc
            yield cursor
            conn.commit()
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Error en operación de BD: {e}")
            raise
        finally:
            if cursor:
                cursor.close()
            if conn:
                try:
                    cls._pool.putconn(conn)
                except Exception:
                    try:
                        conn.close()
                    except Exception:
                        pass

    @classmethod
    def close_all(cls):
        """Cierra todas las conexiones del pool"""
        if cls._pool:
            cls._pool.closeall()
            logger.info("Pool de conexiones cerrado") 