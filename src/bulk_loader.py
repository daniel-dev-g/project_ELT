""" Module to load data into SQL Server using BULK INSERT """
import pathlib
import logging
import pyodbc
from src.state_manager.core.database import get_connection_string

def sqlserver_bcp_windows(ruta_csv, schema, tabla):
    """Upload CSV to SQL Server using BULK INSERT """

    # Convertir a ruta absoluta
    if not pathlib.Path(ruta_csv).is_absolute():
        ruta_csv = pathlib.Path.cwd() / ruta_csv

    ruta_csv = str(ruta_csv)  # Convertir a string para SQL
    logging.info("Path: %s", ruta_csv)
    logging.info("Path File Exist: %s", pathlib.Path(ruta_csv).exists())

    # VERIFICAR QUE EL ARCHIVO EXISTE
    if not pathlib.Path(ruta_csv).exists():
        logging.error("Error: File not found: %s", ruta_csv)
        return False

    # Usar BULK INSERT desde T-SQL (mejor manejo de caracteres especiales)
    sql_query = f"""
    BULK INSERT [{schema}].[{tabla}]
    FROM '{ruta_csv}'
    WITH (
        FIELDTERMINATOR = ';',
        ROWTERMINATOR = '\\n',
        FIRSTROW = 2,
        CODEPAGE = '65001'
    )
    """

    logging.info("Executing BULK INSERT...")

    try:
        conn_str = get_connection_string()
        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()
        cursor.execute(sql_query)
        rows_affected = cursor.rowcount  # Obtener número de filas insertadas
        conn.commit()
        cursor.close()
        conn.close()
        logging.info("BULK INSERT successful - %d inserted rows", rows_affected)
        return rows_affected
    except Exception as e:
        logging.error("BULK INSERT failed")
        logging.error("   Error: %s", str(e))
        return 0

