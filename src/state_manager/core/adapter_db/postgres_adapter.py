"""postgres_adapter.py"""
import pathlib
import logging
from contextlib import contextmanager

import psycopg2
from sqlalchemy import create_engine

from src.state_manager.core.adapter_db.database_adapter import DatabaseAdapter

logger = logging.getLogger(__name__)


class PostgresAdapter(DatabaseAdapter):

    def __init__(self, config: dict):
        self.config = config
        self.engine = self.get_engine(config)

    def _get_connection_string(self, config=None):
        """Genera connection string DSN para psycopg2"""
        if config is None:
            config = self.config

        return (
            f"host={config['host']} "
            f"port={config['port']} "
            f"dbname={config['database']} "
            f"user={config['username']} "
            f"password={config['password']}"
        )

    def get_engine(self, config=None):
        """Crea engine SQLAlchemy para Postgres"""
        if config is None:
            config = self.config

        host = config['host']
        port = int(config['port'])
        database = config['database']
        username = config['username']
        password = config['password']

        connection_url = (
            f"postgresql+psycopg2://{username}:{password}"
            f"@{host}:{port}/{database}"
        )
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
        """Verifica si el usuario tiene permisos para COPY en el servidor."""
        query = (
            "SELECT pg_has_role("
            "current_user, 'pg_read_server_files', 'MEMBER');"
        )

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
        """Upload CSV to Postgres.

        - Escenario B (nativo): archivo accesible localmente → COPY FROM STDIN
          (client-side, sin restricciones de permisos del servidor).
        - Escenario A (Docker): ruta de servidor → COPY FROM file (server-side).
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
        logger.info("Executing COPY FROM...")

        local_path = pathlib.Path(file)
        if local_path.exists():
            # Client-side COPY: Python abre el archivo y lo envía vía STDIN.
            # No requiere pg_read_server_files ni acceso del servidor al FS.
            copy_sql = (
                f'COPY "{schema}"."{table_destination}" '
                f"FROM STDIN WITH ("
                f"FORMAT csv, DELIMITER '{delimiter}', HEADER true)"
            )
            try:
                with self.get_db_cursor() as cursor:
                    with open(local_path, 'rb') as fh:
                        cursor.copy_expert(copy_sql, fh)
                    rows_affected = cursor.rowcount
                logger.info("COPY STDIN successful - %d inserted rows", rows_affected)
                return rows_affected
            except Exception as e:
                logger.error("COPY STDIN failed: %s", str(e))
                raise
        else:
            # Server-side COPY: ruta accesible sólo desde el proceso PostgreSQL.
            copy_sql = (
                f'COPY "{schema}"."{table_destination}" '
                f"FROM '{file}' WITH ("
                f"FORMAT csv, DELIMITER '{delimiter}', HEADER true)"
            )
            try:
                with self.get_db_cursor() as cursor:
                    cursor.execute(copy_sql)
                    rows_affected = cursor.rowcount
                logger.info("COPY FROM successful - %d inserted rows", rows_affected)
                return rows_affected
            except Exception as e:
                logger.error("COPY FROM failed: %s", str(e))
                raise