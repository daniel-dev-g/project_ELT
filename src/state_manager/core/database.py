""" database.py - Módulo para manejo de conexiones a la base de datos y carga de configuración """

from contextlib import contextmanager
import os
import pyodbc
import yaml
from sqlalchemy import  inspect, create_engine
from src.state_manager.core.query_loader import create_query_loader


def load_config():
    """Carga configuración desde settings.yaml"""
    # Get the project root by going up from src/state_manager/core/
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../'))
    config_path = os.path.join(project_root, 'config/settings.yaml')
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)['development']

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
        
        'Trusted_Connection': config.get('trusted_connection', 'yes'),
        'Encrypt': config.get('encrypt', 'no')
    }

    return ';'.join([f'{k}={v}' for k, v in params.items()])

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
