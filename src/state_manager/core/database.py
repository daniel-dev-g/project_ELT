""" database.py - Módulo para manejo de conexiones a la base de datos y carga de configuración """

from contextlib import contextmanager
import os
import pyodbc
from sqlalchemy import inspect, create_engine
from src.state_manager.core.query_loader import create_query_loader
from src.state_manager.core.db_config_loader import load_config


def get_engine(config=None):
    """Crea engine SQLAlchemy para SQL Server"""
    if config is None:
        config = load_config()

    conn_str = get_connection_string(config)
    connection_url = f"mssql+pyodbc:///?odbc_connect={conn_str}"

    return create_engine(connection_url)


def get_connection_string(config=None):
    """Genera connection string para pyodbc"""
    if config is None:
        config = load_config()

    driver = config.get('driver', 'ODBC Driver 17 for SQL Server')

    params = {
        'DRIVER': f'{{{driver}}}',
        'SERVER': config['server'],
        'DATABASE': config['database'],
        'UID': config.get('username', ''),
        'PWD': config.get('password', ''),
        'Trusted_Connection': config.get('trusted_connection', 'no'),
        'Encrypt': config.get('encrypt', 'no')
    }
    conn_str = ';'.join([f'{k}={v}' for k, v in params.items()])
    return conn_str


@contextmanager
def get_db_cursor():
    """Context manager para conexiones pyodbc"""
    conn_str = get_connection_string()
    conn = pyodbc.connect(conn_str)
    cursor = conn.cursor()
    try:
        yield cursor
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()


def get_metadata_schema():
    """Retorna schema """
    config = load_config()
    return config.get('metadata', {}).get('schema', 'etl_log')


def get_queries():
    """Obtiene cargador de queries con schema correcto"""
    schema = get_metadata_schema()
    return create_query_loader(schema)


def table_exists(engine, tabla: str, schema: str) -> bool:
    inspector = inspect(engine)
    return inspector.has_table(tabla, schema=schema)
