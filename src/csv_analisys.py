""" csv_analisys.py """
from datetime import datetime
from pathlib import Path
import time
import yaml


# Nota: log_csv.registrar es el módulo personalizado
from src.log_csv import registrar_log
from src.csv_utils import CSVUtils
from src.df_utils import create_metadata_dataframe, export_metadata

class CSVAnalysis:
    """Clase para análisis de archivos CSV."""
    def __init__(self, execution_id:str, start_time:float):

        self.execution_id = execution_id
        self.start_time = start_time


    def get_pipeline_files(self):
        """Obtiene archivos activos desde el YAML de configuración."""
        current_file = Path(__file__).resolve()
        ruta_yaml = current_file.parent.parent / "config" / "pipeline.yaml"

        if not ruta_yaml.exists():
            registrar_log("ruta_yaml", {"archivo no existe": ruta_yaml})
            raise FileNotFoundError(f"El archivo YAML no existe: {ruta_yaml}")

        with open(ruta_yaml, "r", encoding="utf-8") as f:
            pipeline_cfg = yaml.safe_load(f)


        archivos = []
        base_path = ruta_yaml.parent.parent

        for task in pipeline_cfg.get("task", []):
            if task.get("active", False):
                archivo_relativo = task["file"]
                archivo_absoluto = (base_path / archivo_relativo).resolve()
                archivos.append(
                    {"file": archivo_absoluto, "delimiter": task.get("delimiter", ";")}
                )

        registrar_log(
            "pipeline_init",
            {   "execution_id": self.execution_id,
                "status": "success",
                "cantidad": len(archivos),
                "archivos": [a["file"].name for a in archivos],
            },
        )
        return archivos

    def analyze_single_file(self, path, delimiter,csv_utils):
        """Analiza un archivo y retorna metadatos."""

        metadata = {
            "execution_id": self.execution_id,
            "file_name": path.name,
            "file_path": str(path),
            "exists": False,
            "valid_csv": False,
            "error": None,
            "analysis_error": None,
            "file_size_mb": None,
            "file_size_bytes": None,
            "encoding": None,
            "delimiter": delimiter,
            "columns_name": [],
            "columns_count": 0,
            "rows_count": 0,
            "last_modified": None,
            "extension": path.suffix.lower() if path.suffix else None,
            "analyzed_at": datetime.now().isoformat(),
        }
        if not path.exists():
            registrar_log(
                "file_not_found",
                { "execution_id": self.execution_id,"status": "error", "path": str(path)}
            )
            metadata["error"] = "Archivo no encontrado"
            return metadata
        metadata["exists"] = True
        try:
            file_stat = path.stat()
            metadata["file_size_bytes"] = file_stat.st_size
            metadata["file_size_mb"] = round(file_stat.st_size / (1024 * 1024), 2)
            metadata["last_modified"] = datetime.fromtimestamp(file_stat.st_mtime).isoformat()
            if metadata["file_size_bytes"] > 0:
                if metadata["extension"] in [".csv", ".txt"]:
                    metadata["encoding"] = csv_utils.get_encoding()
                csv_analysis = csv_utils.metadata_polars(
                )
                metadata["columns_name"] = csv_analysis["columns_name"]
                metadata["columns_count"] = csv_analysis["columns_count"]
                metadata["rows_count"] = csv_analysis["rows_count"]
                metadata["valid_csv"] = csv_analysis["success"]
                # log
                registrar_log( "file_analysis", {"execution_id": self.execution_id,
                                                "rows": metadata["rows_count"],
                                                "file": str(Path(path).name)} )
            else:
                metadata["error"] = "Archivo vacío"
        except (OSError, ValueError, RuntimeError, AttributeError) as e:
            registrar_log("analysis_error", {
                "execution_id": self.execution_id,
                "status": "fail",
                "error_type": type(e).__name__,
                "message": str(e),
                "file": str(path)
            })
            metadata["error"] = f"Error durante el análisis: {type(e).__name__} - {str(e)}"

        return metadata

    def run_csv_analysis(self):
        """Ejecuta el análisis de archivos CSV definidos en el pipeline."""
        # creamos diccioanrio para metadata de cada archivo, con el mismo esquema de llaves para consistencia del DataFrame
        all_metadata = []
        total_rows = 0  # ← acumulador local

        for file in self.get_pipeline_files():

            csv_utils = CSVUtils(file["file"], file["delimiter"], self.execution_id)  # ← instancia de utilidad para análisis CSV
            all_metadata.append(
                self.analyze_single_file(file["file"], file["delimiter"],csv_utils)
            )

            total_rows += all_metadata[-1].get("rows_count", 0)  # ✅ solo el último archivo agregado

        # Resumen final — después de leer todos los archivos
        registrar_log("pipeline_summary", {
            "execution_id": self.execution_id,
            "total_files": len(all_metadata),
            "total_rows": total_rows,
            "files_ok": sum(1 for m in all_metadata if m.get("valid_csv")),
            "files_error": sum(1 for m in all_metadata if not m.get("valid_csv")),
            "duration_seconds": round(time.time() - self.start_time, 2)
        })

        df_metadata = create_metadata_dataframe(all_metadata)
        current_file = Path(__file__).resolve()
        metadata_path = current_file.parent.parent / "src" / "metadata"
        metadata_path_detail = current_file.parent.parent / "src" / "metadata_detail"
        export_metadata(df_metadata, output_path=metadata_path, output_path_detail=metadata_path_detail)





