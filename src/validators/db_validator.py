from sqlalchemy import create_engine, inspect, text
import urllib


def check_db_connection(engine) -> bool:
    """Valida que el engine puede conectarse y ejecutar una consulta básica."""
    try:
        with engine.connect() as conn:
            # Ejecuta una consulta ligera para verificar el enlace
            conn.execute(text("SELECT 1"))
        print("✅ Conexión a la base de datos establecida correctamente.")
        return True 
    except Exception as e:
        print(f"❌ Error crítico: No se pudo conectar a la base de datos. {e}")
        return False

        
def check_table_exists(engine_global: str, tabla: str, schema: str = "dbo") -> bool:
    try:
        inspector = inspect(engine_global)
        # has_table es el estándar de SQLAlchemy 2.0+
        if inspector.has_table(tabla, schema=schema):
            print(f"✅ La tabla [{schema}].[{tabla}] existe.")
            return True
        else:
            print(f"⚠️ La tabla [{schema}].[{tabla}] no fue encontrada.")
            return False
            
    except Exception as e:
        #  Es mejor lanzar el error o registrarlo en un log real
        print(f"❌ Error de conexión o inspección: {e}")
        return False
    finally:
        engine_global.dispose() # Limpia el pool de conexiones

import re

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
                print(f"✅ El usuario tiene permisos para BULK INSERT en el servidor: {server_name}")
                return True
            else:
                print(f"❌ El usuario NO tiene permisos de BULK en el servidor: {server_name}")
                return False
    except Exception as e:
        print(f"❌ Error técnico al verificar permisos en {server_name}: {e}")
        return False



