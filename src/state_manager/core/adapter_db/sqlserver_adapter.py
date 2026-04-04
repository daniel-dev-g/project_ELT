"""sqlserver_adapter.py"""
import pathlib
import logging
import re
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy import create_engine
import pyodbc

from src.state_manager.core.adapter_db.database_adapter import DatabaseAdapter
from src.state_manager.core import load_config
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class SqlServerAdapter(DatabaseAdapter):

    def __init__(self, config: dict):
        self.config = config
        self.engine = self.get_engine(config)

    def _get_connection_string(self, config=None):
        """Genera connection string para pyodbc"""
        if config is None:
            config = load_config()

        driver = config['driver']

        params = {
            'DRIVER': f'{{{driver}}}',
            'SERVER': config['server'],
            'DATABASE': config['database'],
            'UID': config.get('username', ''),
            'PWD': config.get('password', ''),
            'Trusted_Connection': config.get('trusted_connection', 'no'),
            'Encrypt': config.get('encrypt', 'no')
        }

        return ';'.join([f'{k}={v}' for k, v in params.items()])

    def get_engine(self, config=None):
        """Crea engine SQLAlchemy para SQL Server"""
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

    def check_bulk_permission(self) -> bool:
        """Verifica si el usuario actual tiene permisos de BULK INSERT en el servidor."""
        query = """
            SELECT 1
            WHERE IS_SRVROLEMEMBER('bulkadmin') = 1
            OR HAS_PERMS_BY_NAME(NULL, NULL, 'ADMINISTER BULK OPERATIONS') = 1;
            """

        # Intentar extraer el nombre del servidor para un log limpio
        # Si .host es None (común en odbc_connect), buscamos en la cadena de conexión
        server_name = self.engine.url.host
        if not server_name:
            params = self.engine.url.query.get('odbc_connect', '')
            if isinstance(params, tuple):
                params = params[0] if params else ''
            match = re.search(r"SERVER=([^;]+)", params, re.IGNORECASE)
            server_name = match.group(1) if match else "SQL Server"

        try:
            with self.engine.connect() as connection:
                result = connection.exec_driver_sql(query).fetchone()

                if result:
                    logger.info(
                        "The user has permissions for BULK INSERT on the server: %s",
                        server_name
                    )
                    return True
                else:
                    logger.warning(
                        "The user does NOT have BULK permissions on the server: %s",
                        server_name)
                    return False
        except (OperationalError, ProgrammingError) as e:
            logger.error(
                "Technical error while verifying permissions on %s: %s",
                server_name, e
            )
            return False

    def bulk_load(self, task: dict) -> int:
        """Upload CSV to SQL Server using BULK INSERT """

        file = task['file']
        schema = task['schema']
        table_destination = task['table_destination']
        delimiter = task.get('delimiter', ';')

        # Convertir a absoluta primero
        if not pathlib.Path(file).is_absolute():
            file = str(pathlib.Path.cwd() / file)

        # Luego mapear al path del contenedor
        path_map = self.config.get('bulk_path_map', {})
        if path_map:
            file = file.replace(path_map['host'], path_map['container'])
            # no verificamos existencia — el archivo está dentro del contenedor
        else:
            # solo verificar si no hay mapeo (archivo local)
            if not pathlib.Path(file).exists():
                logging.error("Error: File not found: %s", file)
                raise FileNotFoundError(f"File not found: {file}")

        file = str(file)
        logging.info("Path: %s", file)

        # Usar BULK INSERT desde T-SQL (mejor manejo de caracteres especiales)
        sql_query = f"""
        BULK INSERT [{schema}].[{table_destination}]
        FROM '{file}'
        WITH (
            FIELDTERMINATOR = '{delimiter}',
            ROWTERMINATOR = '\\n',
            FIRSTROW = 2
        )
        """

        logging.info("Executing BULK INSERT...")

        try:
            with self.get_db_cursor() as cursor:
                cursor.execute(sql_query)
                rows_affected = cursor.rowcount

            logging.info(
                "BULK INSERT successful - %d inserted rows", rows_affected)
            return rows_affected
        except Exception as e:
            logging.error("BULK INSERT failed: %s", str(e))
            raise
