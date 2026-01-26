from logging import config
import sys
import yaml
from src.validators.database import create_engine_db
from src.bulk_loader import sqlserver_bcp_windows
from src.validators.io_validador import valida_ruta
from src.validators.db_validador import  validar_conexion_db, valida_existencia_tabla, valida_permiso_bulk

# main.py
def main():

    try:
        print("Inicio de la carga de datos a SQL Server usando BCP...")

        # --- FASE 1. Leer el YAML una sola vez al inicio 
        with open("config/settings.yaml", "r", encoding="utf-8") as f:
            settings = yaml.safe_load(f)
        
        # 1. Acceder al nivel 'development'
        # Usamos .get() por seguridad: si no existe 'development', devuelve un diccionario vacío
        db_cfg = settings.get('development', {})
        
        # Extraer datos de conexión        
        db_cfg_db = db_cfg['database'] 
        db_cfg_server = db_cfg['server']
        

      # 2. CREAR EL ENGINE GLOBAL
        engine_global = create_engine_db(db_cfg)   
     
      # --- FASE 3: Validaciones de Infraestructura 
        if not validar_conexion_db(engine_global):
            sys.exit(1) # Detiene todo si no hay conexión
          
        # --- FASE 4: Ciclo de carga de datos
        with open("config/pipeline.yaml", "r", encoding="utf-8") as f:
            pipeline_cfg = yaml.safe_load(f)
        
        for task in pipeline_cfg['task']:
            if task['active']:
                print(f"\nIniciando task: {task['name']}")

                valida_existencia_tabla(engine_global, task['table_destination'], task['schema'])    
                valida_permiso_bulk(engine_global)
                valida_ruta(task['file'], ".csv")  
               
                # Cargar datos usando BCP
                sqlserver_bcp_windows(
                        ruta_csv=task['file'],
                        servidor= db_cfg_server,
                        base_datos=db_cfg_db,
                        schema=task['schema'],
                        tabla=task['table_destination']
                    )

    except (FileNotFoundError, IsADirectoryError, ValueError, PermissionError) as e:
        # Mostramos solo el mensaje del error, sin el Traceback
        print(f"❌ Error de validación: {e}")
    except Exception as e:
        # Para cualquier otro error inesperado (conexión BD, etc)
        print(f"💥 Error inesperado: {e}") 
    
if __name__ == "__main__":
    main()