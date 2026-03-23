""" table_creator.py crea tabla en SQL"""
from pathlib import Path
import polars as pl

from src.validators import check_table_exists
from src.log_csv import registrar_log

from src.state_manager.core import get_db_cursor


def get_columns_file(file: str, delimiter: str) -> str:
    """retorna str con campos separados por coma y tipo para DDL"""
    lf = pl.scan_csv(file, separator=delimiter)
    # covierte la lista en un string separado por coma para DDL
    columnas_str = ", ".join(
        [f"[{col}] NVARCHAR(255)" for col in lf.collect_schema().names()])
    return columnas_str


def table_creator(execution_id: str, engine, schema: str, table: str, columns: str):
    """crea la tabla en la base de datos si no existe"""
    if check_table_exists(engine, table, schema):
        registrar_log("table_already_exists", {
                      "execution_id": execution_id, "tabla": table, "schema": schema})
        return

    with get_db_cursor() as cursor:

        cursor.execute(f"CREATE TABLE [{schema}].[{table}] ({columns})")

    registrar_log("table_created", {"tabla": table, "schema": schema})


def table_creator_execute(execution_id: str, engine, schema: str, table_destino: str, file: str, delimiter: str):
    """Llama funciones necesarias para crear tabla"""

    columns = get_columns_file(file, delimiter)
    table_creator(execution_id, engine, schema, table_destino, columns)
