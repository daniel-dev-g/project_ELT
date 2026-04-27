"""mysql_adapter.py"""
import pathlib
import logging
import pymysql

from sqlalchemy import create_engine
from contextlib import contextmanager

from src.state_manager.core.adapter_db.database_adapter import DatabaseAdapter

logger = logging.getLogger(__name__)


class MySQLAdapter(DatabaseAdapter):

    def __init__(self, config: dict):
        self.config = config
        self.engine = self.get_engine(config)

    def _get_connection_params(self, config=None) -> dict:
        """Retorna parámetros de conexión para pymysql"""
        if config is None:
            config = self.config

        return {
            'host': config['host'],
            'port': int(config.get('port', 3306)),
            'database': config['database'],
            'user': config['username'],
            'password': config['password'],
        }

    def get_engine(self, config=None):
        """Crea engine SQLAlchemy para MySQL"""
        if config is None:
            config = self.config

        host = config['host']
        port = int(config.get('port', 3306))
        database = config['database']
        username = config['username']
        password = config['password']

        connection_url = (
            f"mysql+pymysql://{username}:{password}@{host}:{port}/{database}"
        )
        return create_engine(connection_url)

    @contextmanager
    def get_db_cursor(self):
        """Context manager para conexiones pymysql"""
        params = self._get_connection_params()
        conn = pymysql.connect(**params)
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
        """Verifica privilegio FILE para LOAD DATA INFILE."""
        query = (
            "SELECT File_priv FROM mysql.user WHERE User = CURRENT_USER()"
        )

        try:
            with self.get_db_cursor() as cursor:
                cursor.execute(query)
                result = cursor.fetchone()
                has_permission = result is not None and result[0] == 'Y'

                if has_permission:
                    logger.info(
                        "The user has FILE permissions on host: %s",
                        self.config.get('host')
                    )
                else:
                    logger.warning(
                        "The user does NOT have FILE permissions on host: %s",
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
        """Upload CSV to MariaDB using server-side LOAD DATA INFILE.

        MariaDB lee el archivo directo desde disco sin pasar por Python.
        Requiere bulk_path_map en settings.yaml para traducir la ruta del
        contenedor Python a la ruta accesible por el servidor MariaDB.
        Requiere privilegio FILE y secure_file_priv="" en MariaDB.
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

        logger.info("Path: %s", file)

        if schema:
            table_ref = f"`{schema}`.`{table_destination}`"
        else:
            table_ref = f"`{table_destination}`"

        load_sql = f"""
            LOAD DATA INFILE '{file}'
            INTO TABLE {table_ref}
            FIELDS TERMINATED BY '{delimiter}'
            LINES TERMINATED BY '\\n'
            IGNORE 1 ROWS
        """

        logger.info("Executing LOAD DATA INFILE...")

        try:
            with self.get_db_cursor() as cursor:
                cursor.execute(load_sql)
                rows_affected = cursor.rowcount

            logger.info(
                "LOAD DATA successful - %d inserted rows", rows_affected
            )
            return rows_affected
        except Exception as e:
            logger.error("LOAD DATA failed: %s", str(e))
            raise
