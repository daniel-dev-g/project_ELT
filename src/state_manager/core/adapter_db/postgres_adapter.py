"""postgres_adapter.py"""
import pathlib
import logging
from sqlalchemy import create_engine
import pyodbc

from src.state_manager.core.adapter_db.database_adapter import DatabaseAdapter
from src.state_manager.core import load_config
from contextlib import contextmanager


class PostgresAdapter(DatabaseAdapter):

    def __init__(self, config: dict):
        self.config = config
        self.engine = self.get_engine(config)

    def _get_connection_string(self, config=None):
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

    def get_engine(self, config=None):
        """Crea engine SQLAlchemy para Postgres"""
        if config is None:
            config = load_config()

        conn_str = self._get_connection_string(config)
        connection_url = f"mssql+pyodbc:///?odbc_connect={conn_str}"

        return create_engine(connection_url)

    @contextmanager
    def get_db_cursor(self):
        """Context manager para conexiones pyodbc"""
        conn_str = self._get_connection_string()
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

    def check_bulk_permission(self):
        pass

    def bulk_load(self, task: dict) -> int:
        """Upload CSV to SQL Server using BULK INSERT """

        file = task['file']
        schema = task['schema']
        table_destination = task['table_destination']
        delimiter = task.get('delimiter', ';')

        # Convertir a ruta absoluta
        if not pathlib.Path(file).is_absolute():
            file = pathlib.Path.cwd() / file

        file = str(file)  # Convertir a string para SQL
        logging.info("Path: %s", file)
        logging.info("Path File Exist: %s", pathlib.Path(file).exists())

        # VERIFICAR QUE EL ARCHIVO EXISTE
        if not pathlib.Path(file).exists():
            logging.error("Error: File not found: %s", file)
            raise FileNotFoundError(f"File not found: {file}")

        # Usar BULK INSERT desde T-SQL (mejor manejo de caracteres especiales)
        sql_query = f"""
        BULK INSERT [{schema}].[{table_destination}]
        FROM '{file}'
        WITH (
            FIELDTERMINATOR = '{delimiter}',
            ROWTERMINATOR = '\\n',
            FIRSTROW = 2,
            CODEPAGE = '65001'
        )
        """

        logging.info("Executing BULK INSERT...")

        try:
            conn_str = self._get_connection_string()
            conn = pyodbc.connect(conn_str)
            cursor = conn.cursor()
            cursor.execute(sql_query)
            rows_affected = cursor.rowcount  # Obtener número de filas insertadas
            conn.commit()
            cursor.close()
            conn.close()
            logging.info(
                "BULK INSERT successful - %d inserted rows", rows_affected)
            return rows_affected
        except Exception as e:
            logging.error("BULK INSERT failed: %s", str(e))
        raise
