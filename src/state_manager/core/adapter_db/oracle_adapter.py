"""oracle_adapter.py

Carga masiva mediante SQL*Loader (sqlldr), herramienta nativa de Oracle.
Requiere Oracle Instant Client (thick mode) con sqlldr disponible en el PATH
o indicando 'instant_client_dir' en el config YAML.

Modos de conexión:
  - thin mode  (por defecto): Python puro, sin Oracle Instant Client.
  - thick mode: activa añadiendo 'instant_client_dir' en el config YAML.
                Ejemplo:
                  instant_client_dir: "/opt/oracle/instantclient_21_13"
"""
import pathlib
import logging
import subprocess
import tempfile
import re
import oracledb

from sqlalchemy import create_engine
from contextlib import contextmanager

from src.state_manager.core.adapter_db.database_adapter import DatabaseAdapter

logger = logging.getLogger(__name__)


class OracleAdapter(DatabaseAdapter):

    def __init__(self, config: dict):
        self.config = config
        self._init_oracle_client(config)
        self.engine = self.get_engine(config)

    def _init_oracle_client(self, config: dict):
        """Activa thick mode si se indica instant_client_dir en el config."""
        instant_client_dir = config.get('instant_client_dir')
        if instant_client_dir:
            oracledb.init_oracle_client(lib_dir=instant_client_dir)
            logger.info("Oracle thick mode activado desde: %s", instant_client_dir)
        else:
            logger.info("Oracle thin mode activado (sin Instant Client)")

    def _get_dsn(self, config=None) -> str:
        """Genera DSN para oracledb"""
        if config is None:
            config = self.config

        return oracledb.makedsn(
            config['host'],
            config.get('port', 1521),
            service_name=config['service_name']
        )

    def get_engine(self, config=None):
        """Crea engine SQLAlchemy para Oracle"""
        if config is None:
            config = self.config

        host = config['host']
        port = config.get('port', 1521)
        service_name = config['service_name']
        username = config['username']
        password = config['password']

        connection_url = (
            f"oracle+oracledb://{username}:{password}"
            f"@{host}:{port}/?service_name={service_name}"
        )
        return create_engine(connection_url)

    @contextmanager
    def get_db_cursor(self):
        """Context manager para conexiones oracledb"""
        config = self.config
        dsn = self._get_dsn(config)
        conn = oracledb.connect(
            user=config['username'],
            password=config['password'],
            dsn=dsn
        )
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
        """Verifica si el usuario tiene privilegios para SQL*Loader."""
        query = """
            SELECT PRIVILEGE FROM USER_SYS_PRIVS
            WHERE PRIVILEGE IN ('CREATE TABLE', 'CREATE ANY TABLE')
            FETCH FIRST 1 ROWS ONLY
        """

        try:
            with self.get_db_cursor() as cursor:
                cursor.execute(query)
                result = cursor.fetchone()
                has_permission = result is not None

                if has_permission:
                    logger.info(
                        "The user has bulk permissions on host: %s",
                        self.config.get('host')
                    )
                else:
                    logger.warning(
                        "The user does NOT have bulk permissions on host: %s",
                        self.config.get('host')
                    )
                return has_permission
        except Exception as e:
            logger.error(
                "Technical error while verifying permissions on %s: %s",
                self.config.get('host'), e
            )
            return False

    def _build_ctl(self, ctl_path: str, data_path: str, schema: str,
                   table: str, delimiter: str):
        """Genera el archivo .ctl de control para SQL*Loader."""
        ctl_content = (
            f"LOAD DATA\n"
            f"INFILE '{data_path}'\n"
            f"APPEND INTO TABLE {schema}.{table}\n"
            f"FIELDS TERMINATED BY '{delimiter}'\n"
            f"OPTIONALLY ENCLOSED BY '\"'\n"
            f"TRAILING NULLCOLS\n"
            f"(\n"
            f"  FILLER_ROW FILLER  -- omite encabezado\n"
            f")\n"
        )
        pathlib.Path(ctl_path).write_text(ctl_content, encoding='utf-8')

    def bulk_load(self, task: dict) -> int:
        """Upload CSV to Oracle using SQL*Loader (sqlldr)"""

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

        config = self.config
        username = config['username']
        password = config['password']
        host = config['host']
        port = config.get('port', 1521)
        service_name = config['service_name']
        userid = f"{username}/{password}@{host}:{port}/{service_name}"

        with tempfile.TemporaryDirectory() as tmpdir:
            ctl_path = str(pathlib.Path(tmpdir) / "load.ctl")
            log_path = str(pathlib.Path(tmpdir) / "load.log")
            bad_path = str(pathlib.Path(tmpdir) / "load.bad")

            self._build_ctl(ctl_path, file, schema, table_destination, delimiter)

            cmd = [
                "sqlldr",
                f"userid={userid}",
                f"control={ctl_path}",
                f"log={log_path}",
                f"bad={bad_path}",
                "skip=1",           # omite fila de encabezado
                "direct=true",      # direct path para mejor rendimiento
            ]

            logger.info("Executing SQL*Loader...")

            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode not in (0, 2):  # 2 = warnings aceptables
                logger.error("SQL*Loader failed (code %d): %s", result.returncode, result.stdout)
                raise RuntimeError(f"SQL*Loader failed with code {result.returncode}")

            # Extraer filas cargadas desde el log
            rows_affected = 0
            log_text = pathlib.Path(log_path).read_text(encoding='utf-8', errors='replace')
            match = re.search(r'(\d+) Rows successfully loaded', log_text)
            if match:
                rows_affected = int(match.group(1))

            logger.info("SQL*Loader successful - %d inserted rows", rows_affected)
            return rows_affected
