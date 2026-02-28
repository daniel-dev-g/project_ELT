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
root_logger.setLevel(logging.WARNING)
root_logger.addHandler(_handler)


def process_task(
    task: dict,
    engine_global,
    state: StateManager
) -> tuple[bool, int]:
    """
    Processes a single pipeline task.

    Returns:
        tuple: (success: bool, rows_inserted: int)
    """
    file_id = state.start_file_processing(task['file'], task)

    try:
        check_table_exists(engine_global, task['table_destination'], task['schema'])
        check_bulk_permission(engine_global)
        validate_path(task['file'], ".csv")

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
            return True, rows_inserted

        state.fail_file_processing(file_id, "No rows inserted")
        return False, 0

    except (FileNotFoundError, IsADirectoryError, ValueError, PermissionError) as e:
        state.fail_file_processing(file_id, str(e))
        return False, 0

    except Exception as e:
        state.fail_file_processing(file_id, str(e))
        return False, 0


def main():
    """ Entry point of the program """

    # PHASE 0: Initialize StateManager
    state = StateManager("Carga_ETL_BCP")
    execution_id = state.start_process()

    try:
        # PHASE 1: Read configuration
        with open("config/settings.yaml", "r", encoding="utf-8") as f:
            settings = yaml.safe_load(f)

        db_cfg        = settings.get('development', {})

        # Update logging level from YAML
        log_level = db_cfg.get('log_level', 'WARNING')
        root_logger.setLevel(getattr(logging, log_level))
        _handler.setLevel(getattr(logging, log_level))

        # PHASE 2: Database connection
        engine_global = create_engine_db(db_cfg)
        if not check_db_connection(engine_global):
            state.complete_process(status='FAILED')
            sys.exit(1)

        # PHASE 3: File analysis
        with open("config/pipeline.yaml", "r", encoding="utf-8") as f:
            pipeline_cfg = yaml.safe_load(f)

        run_csv_analysis(execution_id=execution_id)

        # PHASE 4: Load cycle
        total_tasks      = 0
        successful_tasks = 0
        failed_tasks     = 0
        total_rows       = 0

        for task in pipeline_cfg['task']:
            if not task['active']:
                continue

            total_tasks += 1
            success, rows = process_task(
                task=task,
                engine_global=engine_global,
                state=state
            )

            if success:
                successful_tasks += 1
                total_rows += rows
            else:
                failed_tasks += 1

        # PHASE 5: Close process
        final_status = 'COMPLETED' if failed_tasks == 0 else 'PARTIAL'
        state.complete_process(status=final_status)

    except Exception as e:
        registrar_log("critical_error", {"error": str(e)})
        state.complete_process(status='FAILED')
        sys.exit(1)


if __name__ == "__main__":
    main()