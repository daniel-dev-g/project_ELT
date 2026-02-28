# src/state_manager/core/manager.py
"""
state_manager.core.manager - Clase StateManager para seguimiento de procesos ETL
"""
import logging
import uuid
import os
from src.state_manager.core.database import get_db_cursor, get_queries
logger = logging.getLogger(__name__)

class StateManager:
    """Track archivos activos: {file_id: file_name}"""
    def __init__(self, process_name: str = "ETL_Process"):
        self.process_name = process_name
        self.queries = get_queries()
        self.execution_id = None
        self.active_files = {}

    def start_process(self) -> str:
        """Inicia nuevo proceso ETL"""
        self.execution_id = str(uuid.uuid4())

        with get_db_cursor() as cursor:
            cursor.execute(
                self.queries['insert_process'],
                (self.execution_id,)
            )


        logger.info("Process file '%s' started: %s", self.process_name, self.execution_id)
        return self.execution_id

    def start_file_processing(self, file_path: str, task_info: dict) -> int:
        """
        Registra inicio de procesamiento de archivo.

        Args:
            file_path: Ruta completa del archivo
            task_info: Diccionario con info de la tarea desde pipeline.yaml

        Returns:
            file_id: ID único del registro del archivo
        """
        if not self.execution_id:
            raise RuntimeError("Debe iniciar proceso primero con start_process()")

        file_name = os.path.basename(file_path)
        file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0

        with get_db_cursor() as cursor:
            cursor.execute(
                self.queries['insert_file'],
                (self.execution_id,
                 file_path,
                 file_name,
                 file_size,
                 task_info['table_destination'],
                 task_info['schema'])
            )

            # Obtener ID generado del OUTPUT
            result = cursor.fetchone()
            file_id = result[0] if result else None

            if file_id is None:
                raise RuntimeError("No se pudo obtener file_id del INSERT")

        # Track archivo activo
        self.active_files[file_id] = file_name

        logger.info("Starting file: %s", file_name)
        return file_id

    def complete_file_processing(self, file_id: int, rows_inserted: int, duration_seconds: float):
        """
        Marca archivo como procesado exitosamente.

        Args:
            file_id: ID del archivo (retornado por start_file_processing)
            rows_inserted: Cantidad de filas insertadas
            duration_seconds: Duración del procesamiento en segundos
        """
        if file_id not in self.active_files:
            raise ValueError(f"file_id {file_id} no es un archivo activo")

        with get_db_cursor() as cursor:
            cursor.execute(
                self.queries['update_file_success'],
                (rows_inserted, int(duration_seconds), file_id)
            )

        # Remover de archivos activos
        file_name = self.active_files.pop(file_id)
        logger.info("%s: %d filas insertadas en %.2fs", file_name, rows_inserted, duration_seconds)

    def fail_file_processing(self, file_id: int, error_message: str):
        """
        Marca archivo como fallado.

        Args:
            file_id: ID del archivo
            error_message: Mensaje de error (se trunca si es muy largo)
        """
        if file_id not in self.active_files:
            raise ValueError(f"file_id {file_id} no es un archivo activo")

        # Truncar mensaje si es muy largo
        if error_message and len(error_message) > 4000:
            error_message = error_message[:4000] + "... [truncado]"

        with get_db_cursor() as cursor:
            cursor.execute(
                self.queries['update_file_failed'],
                (error_message, file_id)
            )

        # Remover de archivos activos
        file_name = self.active_files.pop(file_id)
        error_preview = error_message[:100] + "..." if len(error_message) > 100 else error_message
        logger.error("File %s: failed: %s", file_name, error_preview)

    def complete_process(self, status: str = 'COMPLETED') -> str:
        """
        Completa el proceso actual con estadísticas.

        Args:
            status: Estado final ('COMPLETED', 'FAILED', 'CANCELLED')

        Returns:
            execution_id: ID del proceso completado
        """
        if not self.execution_id:
            raise RuntimeError("No hay proceso activo")

        # Verificar si hay archivos activos (no completados)
        if self.active_files:
            logging.warning("Warning: %d files still active", len(self.active_files))

        with get_db_cursor() as cursor:
            # Obtener estadísticas del proceso
            cursor.execute(self.queries['select_file_stats'], (self.execution_id,))
            stats = cursor.fetchone()

            # Actualizar proceso principal
            cursor.execute(
                self.queries['update_process_complete'],
                (status,
                 stats[0]
                 if stats else 0, stats[1]
                 if stats else 0, stats[2]
                 if stats else 0, stats[3]
                 if stats else 0, self.execution_id
                 )
            )

        logger.info(
            "Process '%s' completed with status '%s': %s",
             self.process_name, status, self.execution_id
             )
        return self.execution_id

    def get_process_summary(self, execution_id: str = None):
        """
        Obtiene resumen de un proceso.

        Args:
            execution_id: ID del proceso (default: proceso actual)

        Returns:
            Tupla con datos del proceso o None si no existe
        """
        target_id = execution_id or self.execution_id

        if not target_id:
            raise ValueError("No hay execution_id especificado")

        with get_db_cursor() as cursor:
            cursor.execute(self.queries['select_process_summary'], (target_id,))
            return cursor.fetchone()

    def check_tables_exist(self) -> bool:
        """
        Verifica que las tablas de metadata existan.

        Returns:
            True si ambas tablas existen, False en caso contrario
        """
        with get_db_cursor() as cursor:
            try:
                # Verificar process_history
                cursor.execute(
                    self.queries['check_table_exists'],
                    (self.queries.schema, 'process_history')
                )
                process_exists = cursor.fetchone() is not None

                # Verificar file_history
                cursor.execute(
                    self.queries['check_table_exists'],
                    (self.queries.schema, 'file_history')
                )
                file_exists = cursor.fetchone() is not None

                return process_exists and file_exists

            except Exception:
                return False

    def __repr__(self):
        status = f"execution_id={self.execution_id}" if self.execution_id else "no iniciado"
        active = f", {len(self.active_files)} archivos activos" if self.active_files else ""
        return f"StateManager(process='{self.process_name}', {status}{active})"

    def __enter__(self):
        """Support for context manager: with StateManager() as state:"""
        self.start_process()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager cleanup"""
        if exc_type is not None:
            # Error ocurrió
            self.complete_process('FAILED')
        else:
            self.complete_process('COMPLETED')


# Ejemplo de uso y prueba
if __name__ == "__main__":
    print("🧪 Probando StateManager...")
    print("=" * 50)

    try:
        # Crear instancia
        state = StateManager("TestProcess")
        print(f"✅ StateManager creado: {state}")

        # Verificar tablas
        if state.check_tables_exist():
            print("✅ Tablas de metadata existen")
        else:
            print("❌ Tablas de metadata NO existen")
            print("   Ejecuta los CREATE TABLE en SQL Server")
            exit(1)

        # Iniciar proceso
        execution_id = state.start_process()
        print(f"✅ Proceso iniciado: {execution_id}")

        # Simular procesamiento de archivo
        task_info = {
            'table_destination': 'test_table',
            'schema': 'dbo'
        }

        file_id = state.start_file_processing(
            file_path="C:\\test\\archivo.csv",
            task_info=task_info
        )
        print(f"✅ Archivo registrado: file_id={file_id}")

        # Simular éxito
        state.complete_file_processing(
            file_id=file_id,
            rows_inserted=1000,
            duration_seconds=45.5
        )

        # Completar proceso
        state.complete_process('COMPLETED')

        # Obtener resumen
        summary = state.get_process_summary()
        if summary:
            print(f"\n📊 Resumen del proceso:")
            print(f"  Execution ID: {summary[0]}")
            print(f"  Estado: {summary[3]}")
            print(f"  Archivos totales: {summary[4]}")
            print(f"  Exitosos: {summary[5]}")
            print(f"  Fallados: {summary[6]}")
            print(f"  Filas totales: {summary[7]}")

        print("\n" + "=" * 50)
        print("✅ Prueba completada exitosamente")

    except Exception as e:
        print(f"❌ Error durante la prueba: {e}")
        import traceback
        traceback.print_exc()
