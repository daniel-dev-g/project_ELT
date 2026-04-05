""" Orquesta la carga de datos la base de datos."""
import os
import sys
import time
import uuid
import logging
from pathlib import Path
import yaml
from dotenv import load_dotenv


from src.table_creator import table_creator_execute
from src.csv_analisys import CSVAnalysis
from src.state_manager.core.adapter_db.factory_db import factory_db
from src.log_csv import registrar_log
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


def process_task(task: dict, db_adapter, execution_id: str) -> tuple[bool, int]:
    """
    Processes a single pipeline task.

    Returns:
        tuple: (success: bool, rows_inserted: int)
    """
    file_path = task['file']
    table = task['table_destination']
    schema = task['schema']

    registrar_log("file_start", {
        "execution_id": execution_id,
        "file": str(file_path),
        "destination_table": table,
        "schema": schema
    })

    start_time = time.time()
    try:
        check_table_exists(db_adapter.engine, table, schema)
        db_adapter.check_bulk_permission()
        validate_path(file_path, ".csv")

        result = db_adapter.bulk_load(task)
        duration = round(time.time() - start_time, 2)
        rows_inserted = result if isinstance(result, int) and result > 0 else 0

        if rows_inserted > 0:
            registrar_log("file_success", {
                "execution_id": execution_id,
                "file": str(file_path),
                "destination_table": table,
                "schema": schema,
                "rows_inserted": rows_inserted,
                "duration_seconds": duration
            })
            return True, rows_inserted

        registrar_log("file_failed", {
            "execution_id": execution_id,
            "file": str(file_path),
            "destination_table": table,
            "schema": schema,
            "error": "No rows inserted",
            "duration_seconds": duration
        })
        return False, 0

    except (FileNotFoundError, IsADirectoryError, ValueError, PermissionError) as e:
        registrar_log("file_failed", {
            "execution_id": execution_id,
            "file": str(file_path),
            "destination_table": table,
            "schema": schema,
            "error": str(e),
            "duration_seconds": round(time.time() - start_time, 2)
        })
        return False, 0
    except Exception as e:  # pylint: disable=broad-exception-caught
        registrar_log("file_failed", {
            "execution_id": execution_id,
            "file": str(file_path),
            "destination_table": table,
            "schema": schema,
            "error": str(e),
            "duration_seconds": round(time.time() - start_time, 2)
        })
        return False, 0


def _run_tasks(pipeline_cfg: dict, db_adapter, execution_id: str) -> dict:
    """Executes all active tasks in the pipeline. Returns summary counters."""
    total_tasks = 0
    successful_tasks = 0
    failed_tasks = 0
    total_rows = 0
    last_task = None

    for task in pipeline_cfg['task']:
        if not task['active']:
            continue

        last_task = task

        try:
            table_creator_execute(
                execution_id=execution_id,
                engine=db_adapter.engine,
                schema=task['schema'],
                table_destino=task['table_destination'],
                file=task['file'],
                delimiter=task.get('delimiter', ';')
            )
        except Exception as e:  # pylint: disable=broad-exception-caught
            registrar_log("table_creation_error",
                          {"table": task['table_destination'], "error": str(e)})
            raise

        total_tasks += 1
        success, rows = process_task(task=task, db_adapter=db_adapter, execution_id=execution_id)

        if success:
            successful_tasks += 1
            total_rows += rows
        else:
            failed_tasks += 1

    return {
        "total_tasks": total_tasks,
        "successful_tasks": successful_tasks,
        "failed_tasks": failed_tasks,
        "total_rows": total_rows,
        "last_task": last_task
    }


def main():
    """ Entry point of the program """
    start_time = time.time()
    execution_id = str(uuid.uuid4())

    registrar_log("process_start", {"execution_id": execution_id})

    try:
        # PHASE 1: Read configuration
        load_dotenv()
        with open("config/settings.yaml", "r", encoding="utf-8") as f:
            settings = yaml.safe_load(os.path.expandvars(f.read()))

        db_cfg = settings.get('development', {})
        log_level = db_cfg.get('log_level', 'WARNING')
        root_logger.setLevel(getattr(logging, log_level))
        _handler.setLevel(getattr(logging, log_level))

        # PHASE 2: Database connection
        db_adapter = factory_db(db_cfg)
        if not check_db_connection(db_adapter.engine):
            registrar_log("process_failed", {
                "execution_id": execution_id,
                "error": "Could not connect to database"
            })
            sys.exit(1)

        # PHASE 3: Read pipeline and process tasks
        with open("config/pipeline.yaml", "r", encoding="utf-8") as f:
            pipeline_cfg = yaml.safe_load(f)

        summary = _run_tasks(pipeline_cfg, db_adapter, execution_id)

        # PHASE 4: CSV analysis summary
        try:
            CSVAnalysis(execution_id=execution_id, start_time=start_time).run_csv_analysis()
        except (OSError, ValueError, RuntimeError, AttributeError) as e:
            last_file = str(summary["last_task"]["file"]) if summary["last_task"] else "unknown"
            registrar_log("analysis_error", {
                "execution_id": execution_id,
                "error_type": type(e).__name__,
                "message": str(e),
                "file": last_file
            })

        # PHASE 5: Close process
        final_status = 'COMPLETED' if summary["failed_tasks"] == 0 else 'PARTIAL'
        registrar_log("process_complete", {
            "execution_id": execution_id,
            "status": final_status,
            "total_tasks": summary["total_tasks"],
            "successful_tasks": summary["successful_tasks"],
            "failed_tasks": summary["failed_tasks"],
            "total_rows": summary["total_rows"],
            "duration_seconds": round(time.time() - start_time, 2)
        })

    except Exception as e:  # pylint: disable=broad-exception-caught
        registrar_log("process_failed", {"execution_id": execution_id, "error": str(e)})

    finally:
        try:
            dashboard_path = generate_latest_dashboard()
            registrar_log("dashboard_generated", {"path": str(dashboard_path)})
        except Exception as e:  # pylint: disable=broad-exception-caught
            registrar_log("dashboard_error", {"error": str(e)})


if __name__ == "__main__":
    main()
