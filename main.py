""" Orquesta la carga de datos a SQL Server usando BCP."""
import sys
import time

import yaml
from src.csv_analisys import metadata_polars, run_csv_analysis
from src.log_csv import registrar_log
from src.bulk_loader import sqlserver_bcp_windows
from src.state_manager import StateManager
from src.validators import (
    create_engine_db,
    check_db_connection,
    check_table_exists,
    check_bulk_permission,
    validate_path
)


def main():
    """ Punto de entrada principal del programa """

    #  FASE 0: Inicializar StateManager ANTES del try
    #  Si esto falla, no hay nada que hacer
    state = StateManager("Carga_ETL_BCP")
    execution_id = state.start_process()

    # Fase análisis — execution_id ya disponible
    run_csv_analysis(execution_id=execution_id)
    try:
        print("Inicio de la carga de datos a SQL Server usando BCP...")

        #-----------------------------------------------------------------------#
        #     FASE 1. Leer el YAML una sola vez al inicio con setting de DB
        #-----------------------------------------------------------------------#
        with open("config/settings.yaml", "r", encoding="utf-8") as f:
            settings = yaml.safe_load(f)

        # 1. Acceder al nivel 'development'
        # Usamos .get() por seguridad: si no existe 'development', devuelve un diccionario vacío
        db_cfg = settings.get('development', {})

        # Extraer datos de conexión
        db_cfg_db = db_cfg['database']
        db_cfg_server = db_cfg['server']

        #------------------------------------------------------------#
        #           FAS 2. CREAR EL ENGINE GLOBAL
        #------------------------------------------------------------#
        engine_global = create_engine_db(db_cfg)


        #------------------------------------------------------------#
        # --- FASE 3: Validaciones de Infraestructura
        #------------------------------------------------------------#
        if not check_db_connection(engine_global):
            sys.exit(1) # Detiene todo si no hay conexión




        #------------------------------------------------------------#
        # --- FASE 5: Ciclo de carga de datos
        #------------------------------------------------------------#
        with open("config/pipeline.yaml", "r", encoding="utf-8") as f:
            pipeline_cfg = yaml.safe_load(f)


        total_tasks = 0
        successful_tasks = 0
        failed_tasks = 0

        for task in pipeline_cfg['task']:
            if task['active']:
                print(f"\nIniciando task: {task['name']}")
                 # Registrar inicio del archivo
                 # file_id disponible para TODO el proceso de este archivo
                file_id = state.start_file_processing(task['file'], task)

                try:
                    # --- Análisis metadata (ya tienes file_id disponible) ---
                    metadata = metadata_polars(task['file'], task['delimiter'], task['encoding'])
                    registrar_log("metadata", {
                        "file_id": file_id,          # ← asociado al proceso
                        "execution_id": execution_id, # ← asociado al proceso padre
                        **metadata
                    })

                    # --- Log de columnas (ya tienes file_id disponible) ---
                    registrar_log("columns", {
                        "file_id": file_id,
                        "execution_id": execution_id,
                        "columns": metadata["columns_name"]
                    })


                    # Validaciones previas
                    check_table_exists(engine_global, task['table_destination'], task['schema'])
                    check_bulk_permission(engine_global)
                    validate_path(task['file'], ".csv")

                    total_tasks += 1
                    start_time = time.time()

                    # Cargar datos usando BCP
                    result = sqlserver_bcp_windows(
                        ruta_csv=task['file'],
                        servidor=db_cfg_server,
                        base_datos=db_cfg_db,
                        schema=task['schema'],
                        tabla=task['table_destination']
                    )


                    duration = time.time() - start_time

                    # Datos insertados (result es el número de filas)
                    rows_inserted = result if isinstance(result, int) and result > 0 else 0

                    # Registrar éxito si se insertaron filas
                    if rows_inserted > 0:
                        state.complete_file_processing(file_id, rows_inserted, duration)
                        successful_tasks += 1
                    else:
                        state.fail_file_processing(file_id, "No se insertaron filas")
                        failed_tasks += 1

                except (FileNotFoundError, IsADirectoryError, ValueError, PermissionError) as e:
                    print(f"❌ Error de validación: {e}")
                    failed_tasks += 1
                    if 'file_id' in locals():
                        state.fail_file_processing(file_id, str(e))
                except Exception as e:
                    print(f"💥 Error inesperado: {e}")
                    failed_tasks += 1
                    if 'file_id' in locals():
                        state.fail_file_processing(file_id, str(e))

        # Finalizar proceso
        state.complete_process(status='COMPLETED')

        print(f"\n{'='*50}")
        print(f"📊 Resumen: {successful_tasks}/{total_tasks} tareas exitosas")

    except Exception as e:
        # Para cualquier otro error inesperado (conexión BD, etc)
        print(f"💥 Error inesperado: {e}")

if __name__ == "__main__":
    main()
