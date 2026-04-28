"""sqlserver_adapter.py"""
import pathlib
import logging
import re
from contextlib import contextmanager

from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy import create_engine
import pyodbc

from src.state_manager.core.adapter_db.database_adapter import DatabaseAdapter

logger = logging.getLogger(__name__)


class SqlServerAdapter(DatabaseAdapter):

    def __init__(self, config: dict):
        self.config = config
        self.engine = self.get_engine(config)

    def _get_connection_string(self, config=None):
        """Genera connection string para pyodbc"""
        if config is None:
            config = self.config

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
            config = self.config

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
        """Verifica si el usuario tiene permisos de BULK INSERT."""
        query = """
            SELECT 1
            WHERE IS_SRVROLEMEMBER('bulkadmin') = 1
            OR HAS_PERMS_BY_NAME(NULL, NULL, 'ADMINISTER BULK OPERATIONS') = 1;
            """

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
                        "The user has BULK INSERT permissions on: %s",
                        server_name
                    )
                    return True

                logger.warning(
                    "The user does NOT have BULK permissions on: %s",
                    server_name
                )
                return False
        except (OperationalError, ProgrammingError) as e:
            logger.error(
                "Technical error while verifying permissions on %s: %s",
                server_name, e
            )
            return False

    def truncate_table(self, schema: str, table: str) -> None:
        if schema:
            sql = f"TRUNCATE TABLE [{schema}].[{table}]"
        else:
            sql = f"TRUNCATE TABLE [{table}]"
        with self.get_db_cursor() as cursor:
            cursor.execute(sql)
        logger.info("TRUNCATE OK: %s.%s", schema, table)

    def bulk_load(self, task: dict) -> int:
        """Upload CSV to SQL Server using BULK INSERT.

        SQL Server lee el archivo directo desde disco sin pasar por Python.
        Si el path es absoluto y no coincide con bulk_path_map, se usa tal cual
        (rutas de servidor en Escenario B).
        """
        file = task['file']
        schema = task['schema']
        table_destination = task['table_destination']
        delimiter = task.get('delimiter', ';')

        if not pathlib.Path(file).is_absolute():
            file = str(pathlib.Path.cwd() / file)

        path_map = self.config.get('bulk_path_map', {})
        host_prefix = path_map.get('host', '') if path_map else ''
        if host_prefix and host_prefix in file:
            file = file.replace(host_prefix, path_map['container'])

        file = str(file)
        logger.info("Path: %s", file)

        sql_query = f"""
        BULK INSERT [{schema}].[{table_destination}]
        FROM '{file}'
        WITH (
            FIELDTERMINATOR = '{delimiter}',
            ROWTERMINATOR = '\\n',
            TABLOCK,
            BATCHSIZE = 100000,
            FIRSTROW = 2
        )
        """

        logger.info("Executing BULK INSERT...")

        try:
            with self.get_db_cursor() as cursor:
                cursor.execute(sql_query)
                rows_affected = cursor.rowcount

            logger.info(
                "BULK INSERT successful - %d inserted rows", rows_affected
            )
            return rows_affected
        except Exception as e:
            logger.error("BULK INSERT failed: %s", str(e))
            raise