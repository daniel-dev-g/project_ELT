"""db_validator.py Contains functions to validate the database connection,
existence of tables, and permissions. """

import logging
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError, ProgrammingError

logger = logging.getLogger(__name__)


def check_db_connection(engine) -> tuple[bool, str | None]:
    "Validates that the engine can connect and execute a basic query."
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("Database connection established successfully.")
        return True, None
    except OperationalError as e:
        logger.critical("Could not connect to the database. %s", e)
        return False, str(e)


def check_table_exists(engine_global: Engine, tabla: str, schema: str = "dbo") -> bool:
    "Check if the table exists in the database using SQLAlchemy Inspector."
    try:
        inspector = inspect(engine_global)
        schema_arg = schema if schema else None
        if inspector.has_table(tabla, schema=schema_arg):
            logger.info("Table [%s].[%s] exists.", schema, tabla)
            return True
        logger.info("The table [%s].[%s] was not found.", schema, tabla)
        return False

    except (OperationalError, ProgrammingError) as e:
        #  Es mejor lanzar el error o registrarlo en un log real
        logger.error(" Connection or inspection error: %s", e)
        return False
    finally:
        engine_global.dispose()  # Limpia el pool de conexiones
