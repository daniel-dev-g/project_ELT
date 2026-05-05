""" validator.py Contains functions to validate the database connection,
existence of tables, and permissions. """

import logging
import re
from sqlalchemy import  inspect, text
from sqlalchemy.exc import OperationalError, ProgrammingError

logger = logging.getLogger(__name__)


def check_db_connection(engine) -> bool:
    "Validates that the engine can connect and execute a basic query."
    try:
        with engine.connect() as conn:
            # Ejecuta una consulta ligera para verificar el enlace
            conn.execute(text("SELECT 1"))
        logger.info("Database connection established successfully.")
        return True
    except OperationalError as e:
        logger.critical(" Could not connect to the database. %s", e)
        return False


def check_table_exists(engine_global: str, schema: str , tabla: str ) -> bool:
    "Check if the table exists in the database using SQLAlchemy Inspector."
    try:
        inspector = inspect(engine_global)
        # has_table es el estándar de SQLAlchemy 2.0+
        if inspector.has_table(tabla, schema=schema):
            logger.info("Table [%s].[%s] exists.", schema, tabla)
            return True
        else:
            logger.warning("The table [%s].[%s] was not found.", schema, tabla)
            return False

    except (OperationalError, ProgrammingError) as e:
        #  Es mejor lanzar el error o registrarlo en un log real
        logger.error(" Connection or inspection error: %s", e)
        return False



def check_bulk_permission(engine_global) -> bool:
    """
    Verifica si el usuario actual tiene permisos de BULK INSERT en el servidor.
    """
    query = """
    SELECT 1
    WHERE IS_SRVROLEMEMBER('bulkadmin') = 1
       OR HAS_PERMS_BY_NAME(NULL, NULL, 'ADMINISTER BULK OPERATIONS') = 1;
    """

    # Intentar extraer el nombre del servidor para un log limpio
    # Si .host es None (común en odbc_connect), buscamos en la cadena de conexión
    server_name = engine_global.url.host
    if not server_name:
        params = engine_global.url.query.get('odbc_connect', '')
        match = re.search(r"SERVER=([^;]+)", params, re.IGNORECASE)
        server_name = match.group(1) if match else "SQL Server"

    try:
        with engine_global.connect() as connection:
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
