"""mysql_adapter.py"""
import pathlib
import stat as stat_module
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
        """Verifica privilegio FILE para LOAD DATA INFILE usando SHOW GRANTS."""
        try:
            with self.get_db_cursor() as cursor:
                cursor.execute("SHOW GRANTS FOR CURRENT_USER()")
                grants = cursor.fetchall()

            has_permission = any(
                'FILE' in str(row) for row in grants
            )
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

    def truncate_table(self, schema: str, table: str) -> None:
        if schema:
            sql = f"TRUNCATE TABLE `{schema}`.`{table}`"
        else:
            sql = f"TRUNCATE TABLE `{table}`"
        with self.get_db_cursor() as cursor:
            cursor.execute(sql)
        logger.info("TRUNCATE OK: %s.%s", schema, table)

    def _check_file_access(self, server_path: str, app_path: str | None = None) -> None:
        """Pre-flight check: verifica que el servidor MySQL pueda leer el archivo.

        server_path: ruta que usará el servidor MySQL (puede ser ruta de contenedor).
        app_path:    ruta visible desde este proceso Python; si difiere de server_path
                     (modo Docker con path_map) solo se verifica existencia local y
                     se omiten las comprobaciones de permisos/AppArmor.

        Detecta los tres problemas más comunes en instalaciones locales:
        secure_file_priv activo, permisos insuficientes en el archivo o sus
        directorios padres, y AppArmor bloqueando el acceso desde /home/.
        """
        local_path = pathlib.Path(app_path if app_path is not None else server_path)
        docker_mode = app_path is not None and app_path != server_path

        # 1. secure_file_priv — siempre se comprueba (consulta al servidor)
        try:
            with self.get_db_cursor() as cursor:
                cursor.execute("SHOW VARIABLES LIKE 'secure_file_priv'")
                row = cursor.fetchone()
            sfp = row[1] if row else ''
            if sfp:
                raise ValueError(
                    f"secure_file_priv='{sfp}' bloquea el acceso a '{server_path}'.\n"
                    "Agrega en /etc/mysql/mysql.conf.d/mysqld.cnf bajo [mysqld]:\n"
                    "  secure_file_priv=\n"
                    "Luego ejecuta: sudo systemctl restart mysql"
                )
        except ValueError:
            raise
        except Exception:
            pass

        # 2. Existencia del archivo — usando la ruta visible desde este proceso
        try:
            if not local_path.exists():
                raise ValueError(f"Archivo no encontrado: '{server_path}'")
        except ValueError:
            raise
        except OSError:
            pass

        # 3. Permisos y AppArmor — solo en instalación local (no Docker)
        if docker_mode:
            return

        try:
            if not (local_path.stat().st_mode & stat_module.S_IROTH):
                raise ValueError(
                    f"El servidor MySQL no puede leer '{server_path}'.\n"
                    "El proceso mysqld corre como usuario 'mysql' y necesita permiso de lectura.\n"
                    f"Ejecuta:  chmod o+r '{server_path}'"
                )

            for parent in reversed(list(local_path.parents)):
                if str(parent) == '/':
                    continue
                if not (parent.stat().st_mode & stat_module.S_IXOTH):
                    raise ValueError(
                        f"El servidor MySQL no puede acceder al directorio '{parent}'.\n"
                        f"Ejecuta:  chmod o+x '{parent}'"
                    )
                if parent == local_path.parent:
                    break
        except ValueError:
            raise
        except OSError:
            pass

        apparmor_profile = pathlib.Path('/etc/apparmor.d/usr.sbin.mysqld')
        if apparmor_profile.exists() and str(local_path).startswith('/home/'):
            try:
                content = apparmor_profile.read_text(encoding='utf-8')
                parent_str = str(local_path.parent)
                if parent_str not in content and '/home/' not in content:
                    raise ValueError(
                        f"AppArmor está bloqueando el acceso de MySQL a '{server_path}'.\n"
                        "Agrega en /etc/apparmor.d/usr.sbin.mysqld (antes del último }):\n"
                        f"  {local_path.parent}/ r,\n"
                        f"  {local_path.parent}/** r,\n"
                        "Luego ejecuta: sudo apparmor_parser -r /etc/apparmor.d/usr.sbin.mysqld"
                    )
            except ValueError:
                raise
            except Exception:
                pass

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

        app_path = file  # ruta visible desde este proceso Python
        path_map = self.config.get('bulk_path_map', {})
        host_prefix = path_map.get('host', '') if path_map else ''
        if host_prefix and host_prefix in file:
            file = file.replace(host_prefix, path_map['container'])

        server_path = file  # ruta que usará el servidor MySQL/MariaDB
        logger.info("Path: %s", server_path)
        self._check_file_access(server_path, app_path if app_path != server_path else None)

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
                cursor.execute("SET foreign_key_checks=0")
                cursor.execute("SET unique_checks=0")
                cursor.execute(load_sql)
                rows_affected = cursor.rowcount
                cursor.execute("SET foreign_key_checks=1")
                cursor.execute("SET unique_checks=1")

            logger.info(
                "LOAD DATA successful - %d inserted rows", rows_affected
            )
            return rows_affected
        except Exception as e:
            logger.error("LOAD DATA failed: %s", str(e))
            raise
