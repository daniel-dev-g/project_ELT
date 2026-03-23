""" Orquesta la carga de datos a SQL Server usando BCP."""
import sys
import time
import logging
from pathlib import Path
import yaml


from src.table_creator import table_creator_execute
from src.csv_analisys import CSVAnalysis
from src.state_manager.core.adapter_db.factory_db import factory_db
from src.log_csv import registrar_log
from src.state_manager import StateManager
from src.validators import (

    check_db_connection,
    check_table_exists,
    validate_path
)
from src.visualization.log_dashboard import generate_latest_dashboard


# Crear carpeta logs si no existe
Path("logs").mkdir(exist_ok=True)

# Configurar root logger antes de cualquier ejecución
_handler = logging.FileHandler("logs/technical.log", encoding="utf-8")
_handler.setFormatter(logging.Formatter(
    "%(asctime)s [%(levelname)s] %(name)s: %(message)s"))

root_logger = logging.getLogger()
root_logger.setLevel(logging.WARNING)
root_logger.addHandler(_handler)


def process_task(
    task: dict,
    db_adapter,
    state: StateManager
) -> tuple[bool, int]:
    """
    Processes a single pipeline task.

    Returns:
        tuple: (success: bool, rows_inserted: int)
    """

    file_id = state.start_file_processing(task['file'], task)
    try:

        check_table_exists(
            db_adapter.engine, task['table_destination'], task['schema'])
        db_adapter.check_bulk_permission()
        validate_path(task['file'], ".csv")

        start_time = time.time()

        result = db_adapter.bulk_load(task)

        duration = time.time() - start_time
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
    start_time = time.time()
    # PHASE 0: Initialize StateManager
    state = StateManager("Carga_ETL_BCP")
    execution_id = state.start_process()

    try:
        # PHASE 1: Read configuration
        with open("config/settings.yaml", "r", encoding="utf-8") as f:
            settings = yaml.safe_load(f)

        db_cfg = settings.get('development', {})

        # Update logging level from YAML
        log_level = db_cfg.get('log_level', 'WARNING')
        root_logger.setLevel(getattr(logging, log_level))
        _handler.setLevel(getattr(logging, log_level))

        # PHASE 2: Database connection
        db_adapter = factory_db(db_cfg)

        if not check_db_connection(db_adapter.engine):
            state.complete_process(status='FAILED')
            sys.exit(1)

        # PHASE 3: File analysis
        with open("config/pipeline.yaml", "r", encoding="utf-8") as f:
            pipeline_cfg = yaml.safe_load(f)

        # PHASE 4: process each task
        total_tasks = 0
        successful_tasks = 0
        failed_tasks = 0
        total_rows = 0

        for task in pipeline_cfg['task']:
            if not task['active']:
                continue

            try:
                table_creator_execute(
                    execution_id=execution_id,
                    engine=db_adapter.engine,
                    schema=task['schema'],
                    table_destino=task['table_destination'],
                    file=task['file'],
                    delimiter=task.get('delimiter', ';')
                )
            except Exception as e:
                registrar_log("table_creation_error",
                              {"table": task['table_destination'], "error": str(e)})
                state.complete_process(status='FAILED')

            total_tasks += 1
            success, rows = process_task(
                task=task,
                db_adapter=db_adapter,
                state=state
            )

            if success:
                successful_tasks += 1
                total_rows += rows
            else:
                failed_tasks += 1

        # Sumary log of the entire process
        try:
            csv_analysis = CSVAnalysis(
                execution_id=execution_id, start_time=start_time)
            csv_analysis.run_csv_analysis()
        except (OSError, ValueError, RuntimeError, AttributeError) as e:
            registrar_log("analysis_error", {
                "execution_id": execution_id,
                "status": "fail",
                "error_type": type(e).__name__,
                "message": str(e),
                "file": str(task['file'])
            })

        # PHASE 5: Close process
        final_status = 'COMPLETED' if failed_tasks == 0 else 'PARTIAL'
        state.complete_process(status=final_status)

        # Log Dashboard generation
        try:

            dashboard_path = generate_latest_dashboard()
            registrar_log("dashboard_generated", {"path": str(dashboard_path)})
        except Exception as e:
            registrar_log("dashboard_error", {"error": str(e)})

    except Exception as e:
        registrar_log("critical_error", {"error": str(e)})
        state.complete_process(status='FAILED')
        sys.exit(1)


if __name__ == "__main__":
    main()
