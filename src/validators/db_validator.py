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


def validate_table_schema(
    engine: Engine, tabla: str, schema: str, file_path: str, delimiter: str
) -> None:
    """Raises ValueError if the CSV columns don't match the existing table columns.

    Skips silently when the file is not accessible from Python (server-side COPY).
    """
    from pathlib import Path
    csv_path = Path(file_path)
    if not csv_path.exists():
        return

    try:
        inspector = inspect(engine)
        schema_arg = schema if schema else None
        if not inspector.has_table(tabla, schema=schema_arg):
            return

        db_cols = [col["name"] for col in inspector.get_columns(tabla, schema=schema_arg)]

        with open(csv_path, "r", encoding="utf-8", errors="replace") as f:
            header = f.readline().strip()
        csv_cols = [c.strip().strip('"') for c in header.split(delimiter)]

        if len(db_cols) != len(csv_cols):
            raise ValueError(
                f"Schema mismatch in '{schema}.{tabla}': "
                f"table has {len(db_cols)} columns, CSV has {len(csv_cols)}. "
                f"Drop the table or use a different destination table name."
            )
    except ValueError:
        raise
    except (OperationalError, ProgrammingError, OSError) as e:
        logger.warning("Could not validate schema for %s.%s: %s", schema, tabla, e)


def validate_schema_exists(engine: Engine, schema: str, db_engine: str) -> None:
    """Raises ValueError if the schema doesn't exist in the database.

    MariaDB doesn't use schemas, so it's skipped.
    """
    if not schema or db_engine in ("mariadb", "mysql"):
        return
    try:
        inspector = inspect(engine)
        existing = inspector.get_schema_names()
        if schema not in existing:
            raise ValueError(
                f"El schema '{schema}' no existe en la base de datos. "
                f"Schemas disponibles: {', '.join(existing)}"
            )
    except (OperationalError, ProgrammingError) as e:
        logger.warning("No se pudo validar el schema '%s': %s", schema, e)


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
        logger.error(" Connection or inspection error: %s", e)
        return False
    finally:
        engine_global.dispose()
