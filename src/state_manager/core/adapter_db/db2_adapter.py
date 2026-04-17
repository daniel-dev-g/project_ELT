"""db2_adapter.py"""
import pathlib
import logging
import ibm_db_dbi

from sqlalchemy import create_engine
from contextlib import contextmanager

from src.state_manager.core.adapter_db.database_adapter import DatabaseAdapter

logger = logging.getLogger(__name__)


class Db2Adapter(DatabaseAdapter):

    def __init__(self, config: dict):
        self.config = config
        self.engine = self.get_engine(config)

    def _get_connection_string(self, config=None):
        """Genera connection string DSN para ibm_db"""
        if config is None:
            config = self.config

        return (
            f"DATABASE={config['database']};"
            f"HOSTNAME={config['host']};"
            f"PORT={config.get('port', 50000)};"
            f"PROTOCOL=TCPIP;"
            f"UID={config['username']};"
            f"PWD={config['password']};"
        )

    def get_engine(self, config=None):
        """Crea engine SQLAlchemy para IBM Db2"""
        if config is None:
            config = self.config

        host = config['host']
        port = config.get('port', 50000)
        database = config['database']
        username = config['username']
        password = config['password']

        connection_url = f"db2+ibm_db://{username}:{password}@{host}:{port}/{database}"
        return create_engine(connection_url)

    @contextmanager
    def get_db_cursor(self):
        """Context manager para conexiones ibm_db_dbi"""
        conn_str = self._get_connection_string()
        conn = ibm_db_dbi.connect(conn_str, '', '')
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
        """Verifica si el usuario tiene privilegios LOAD en Db2."""
        query = """
            SELECT PRIVILEGE FROM SYSIBMADM.PRIVILEGES
            WHERE AUTHID = CURRENT USER AND PRIVILEGE = 'LOAD'
            FETCH FIRST 1 ROWS ONLY
        """

        try:
            with self.get_db_cursor() as cursor:
                cursor.execute(query)
                result = cursor.fetchone()
                has_permission = result is not None

                if has_permission:
                    logger.info(
                        "The user has LOAD permissions on host: %s",
                        self.config.get('host')
                    )
                else:
                    logger.warning(
                        "The user does NOT have LOAD permissions on host: %s",
                        self.config.get('host')
                    )
                return has_permission
        except Exception as e:
            logger.error(
                "Technical error while verifying permissions on %s: %s",
                self.config.get('host'), e
            )
            return False

    def bulk_load(self, task: dict) -> int:
        """Upload CSV to IBM Db2 using SYSPROC.ADMIN_CMD LOAD"""

        file = task['file']
        schema = task['schema']
        table_destination = task['table_destination']
        delimiter = task.get('delimiter', ';')

        if not pathlib.Path(file).is_absolute():
            file = str(pathlib.Path.cwd() / file)

        if not pathlib.Path(file).exists():
            logger.error("Error: File not found: %s", file)
            raise FileNotFoundError(f"File not found: {file}")

        logger.info("Path: %s", file)

        # ADMIN_CMD permite ejecutar el comando LOAD desde SQL
        load_cmd = (
            f"LOAD FROM '{file}' OF DEL "
            f"MODIFIED BY coldel{delimiter} skiprows=1 "
            f"INSERT INTO {schema}.{table_destination}"
        )

        load_sql = f"CALL SYSPROC.ADMIN_CMD('{load_cmd}')"

        logger.info("Executing LOAD via ADMIN_CMD...")

        try:
            with self.get_db_cursor() as cursor:
                cursor.execute(load_sql)
                rows_affected = cursor.rowcount

            logger.info("LOAD successful - %d inserted rows", rows_affected)
            return rows_affected
        except Exception as e:
            logger.error("LOAD failed: %s", str(e))
            raise
