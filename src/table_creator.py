""" table_creator.py crea tabla en SQL"""
from pathlib import Path
import polars as pl

from src.validators import check_table_exists
from src.log_csv import registrar_log


def _quote(name: str, db_engine: str) -> str:
    """Retorna el identificador con el quoting correcto según el motor."""
    if db_engine == 'sqlserver':
        return f"[{name}]"
    elif db_engine in ('mysql', 'mariadb'):
        return f"`{name}`"
    else:  # postgres, db2, oracle — estándar ANSI SQL
        return f'"{name}"'


def get_columns_file(file: str, delimiter: str, db_engine: str) -> str:
    """Retorna str con campos separados por coma y tipo para DDL"""
    lf = pl.scan_csv(file, separator=delimiter)
    columnas_str = ", ".join(
        [f"{_quote(col, db_engine)} VARCHAR(255)" for col in lf.collect_schema().names()])
    return columnas_str


def table_creator(execution_id: str, engine, schema: str, table: str, columns: str, db_engine: str):
    """Crea la tabla en la base de datos si no existe"""
    if check_table_exists(engine, table, schema):
        registrar_log("table_already_exists", {
                      "execution_id": execution_id, "tabla": table, "schema": schema})
        return

    table_q = _quote(table, db_engine)
    table_ref = (
        f"{_quote(schema, db_engine)}.{table_q}" if schema else table_q
    )

    with engine.begin() as conn:
        conn.exec_driver_sql(f"CREATE TABLE {table_ref} ({columns})")

    registrar_log("table_created", {"tabla": table, "schema": schema})


def table_creator_execute(execution_id: str, engine, schema: str, table_destino: str, file: str, delimiter: str, db_engine: str):
    """Llama funciones necesarias para crear tabla"""
    columns = get_columns_file(file, delimiter, db_engine)
    table_creator(execution_id, engine, schema, table_destino, columns, db_engine)