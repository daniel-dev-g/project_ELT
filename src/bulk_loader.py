import pathlib
import pyodbc
from src.state_manager.core.database import get_connection_string

def sqlserver_bcp_windows(ruta_csv, servidor, base_datos, schema, tabla):
    """Carga CSV a SQL Server usando BULK INSERT (mejor que BCP CLI)"""
    # Convertir a ruta absoluta
    if not pathlib.Path(ruta_csv).is_absolute():
        ruta_csv = pathlib.Path.cwd() / ruta_csv
    
    ruta_csv = str(ruta_csv)  # Convertir a string para SQL
    print(f"   📍 Ruta completa: {ruta_csv}")
    print(f"   🔍 Existe: {pathlib.Path(ruta_csv).exists()}")
    
    # VERIFICAR QUE EL ARCHIVO EXISTE
    if not pathlib.Path(ruta_csv).exists():
        print(f"❌ Error: Archivo no encontrado: {ruta_csv}")
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
    
    print(f"   🔧 Ejecutando BULK INSERT...")
    
    try:
        conn_str = get_connection_string()
        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()
        cursor.execute(sql_query)
        rows_affected = cursor.rowcount  # Obtener número de filas insertadas
        conn.commit()
        cursor.close()
        conn.close()
        print(f"✅ BULK INSERT exitoso - {rows_affected} filas insertadas")
        return rows_affected
    except Exception as e:
        print(f"❌ BULK INSERT falló")
        print(f"   Error: {str(e)}")
        return 0

