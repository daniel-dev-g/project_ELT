"""postgres_adapter.py"""
import pathlib
import logging
import psycopg2

from sqlalchemy import create_engine
from contextlib import contextmanager

from src.state_manager.core.adapter_db.database_adapter import DatabaseAdapter
from src.state_manager.core import load_config

logger = logging.getLogger(__name__)


class PostgresAdapter(DatabaseAdapter):

    def __init__(self, config: dict):
        self.config = config
        self.engine = self.get_engine(config)

    def _get_connection_string(self, config=None):
        """Genera connection string DSN para psycopg2"""
        if config is None:
            config = load_config()

        return (
            f"host={config['host']} "
            f"port={config.get('port', 5432)} "
            f"dbname={config['database']} "
            f"user={config['username']} "
            f"password={config['password']}"
        )

    def get_engine(self, config=None):
        """Crea engine SQLAlchemy para Postgres"""
        if config is None:
            config = load_config()

        host = config['host']
        port = config.get('port', 5432)
        database = config['database']
        username = config['username']
        password = config['password']

        connection_url = f"postgresql+psycopg2://{username}:{password}@{host}:{port}/{database}"
        return create_engine(connection_url)

    @contextmanager
    def get_db_cursor(self):
        """Context manager para conexiones psycopg2"""
        conn_str = self._get_connection_string()
        conn = psycopg2.connect(conn_str)
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
        """Verifica si el usuario tiene permisos para ejecutar COPY en el servidor."""
        query = "SELECT pg_has_role(current_user, 'pg_read_server_files', 'MEMBER');"

        try:
            with self.get_db_cursor() as cursor:
                cursor.execute(query)
                result = cursor.fetchone()
                has_permission = result[0] if result else False

                if has_permission:
                    logger.info(
                        "The user has permissions for COPY on host: %s",
                        self.config.get('host')
                    )
                else:
                    logger.warning(
                        "The user does NOT have COPY permissions on host: %s",
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
        """Upload CSV to Postgres using COPY"""

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

        copy_sql = (
            f"COPY {schema}.{table_destination} "
            f"FROM STDIN WITH (FORMAT csv, DELIMITER '{delimiter}', HEADER true)"
        )

        logger.info("Executing COPY...")

        try:
            with self.get_db_cursor() as cursor:
                with open(file, 'r', encoding='utf-8') as f:
                    cursor.copy_expert(copy_sql, f)
                rows_affected = cursor.rowcount

            logger.info("COPY successful - %d inserted rows", rows_affected)
            return rows_affected
        except Exception as e:
            logger.error("COPY failed: %s", str(e))
            raise
