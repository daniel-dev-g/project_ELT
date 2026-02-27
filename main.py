""" Orquesta la carga de datos a SQL Server usando BCP."""
import sys
import time
import logging
from pathlib import Path

import yaml
from src.csv_analisys import run_csv_analysis
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
# Crear carpeta logs si no existe
Path("logs").mkdir(exist_ok=True)

# Configurar root logger antes de cualquier ejecución
_handler = logging.FileHandler("logs/technical.log", encoding="utf-8")
_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))

root_logger = logging.getLogger()
root_logger.setLevel(logging.WARNING)  # default hasta leer YAML
root_logger.addHandler(_handler)


def main():
    """ Punto de entrada principal del programa """

    # FASE 0: Inicializar StateManager
    state = StateManager("Carga_ETL_BCP")
    execution_id = state.start_process()

    try:
        # FASE 1: Leer configuración
        with open("config/settings.yaml", "r", encoding="utf-8") as f:
            settings = yaml.safe_load(f)

        db_cfg        = settings.get('development', {})
        db_cfg_db     = db_cfg['database']
        db_cfg_server = db_cfg['server']
        log_level = db_cfg.get('log_level', 'WARNING')

        # Actualizar nivel según YAML
        root_logger.setLevel(getattr(logging, log_level))
        _handler.setLevel(getattr(logging, log_level))

        # FASE 2: Conexión a base de datos
        engine_global = create_engine_db(db_cfg)

        if not check_db_connection(engine_global):
            state.complete_process(status='FAILED')
            sys.exit(1)

        # FASE 3: Análisis de archivos
        with open("config/pipeline.yaml", "r", encoding="utf-8") as f:
            pipeline_cfg = yaml.safe_load(f)

        run_csv_analysis(execution_id=execution_id)

        # FASE 4: Ciclo de carga
        total_tasks     = 0
        successful_tasks = 0
        failed_tasks    = 0

        for task in pipeline_cfg['task']:
            if not task['active']:
                continue

            # file_id disponible antes del try → siempre disponible en except
            file_id = state.start_file_processing(task['file'], task)

            try:
                check_table_exists(engine_global, task['table_destination'], task['schema'])
                check_bulk_permission(engine_global)
                validate_path(task['file'], ".csv")

                total_tasks += 1
                start_time = time.time()

                result = sqlserver_bcp_windows(
                    ruta_csv=task['file'],
                    schema=task['schema'],
                    tabla=task['table_destination']
                )

                duration      = time.time() - start_time
                rows_inserted = result if isinstance(result, int) and result > 0 else 0

                if rows_inserted > 0:
                    state.complete_file_processing(file_id, rows_inserted, duration)
                    successful_tasks += 1
                else:
                    state.fail_file_processing(file_id, "No se insertaron filas")
                    failed_tasks += 1

            except (FileNotFoundError, IsADirectoryError, ValueError, PermissionError) as e:
                failed_tasks += 1
                state.fail_file_processing(file_id, str(e))

            except Exception as e:
                failed_tasks += 1
                state.fail_file_processing(file_id, str(e))

        # FASE 5: Cerrar proceso
        final_status = 'COMPLETED' if failed_tasks == 0 else 'PARTIAL'
        state.complete_process(status=final_status)

    except Exception as e:
        registrar_log("critical_error", {"error": str(e)})
        state.complete_process(status='FAILED')
        sys.exit(1)


if __name__ == "__main__":
    main()
