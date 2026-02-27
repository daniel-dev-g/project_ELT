""" csv_analisys.py """

from datetime import datetime
from pathlib import Path

import polars as pl
import yaml
from charset_normalizer import from_path

# Nota: log_csv.registrar es el módulo personalizado
from src.log_csv import registrar_log


def get_pipeline_files():
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
        {
            "status": "success",
            "cantidad": len(archivos),
            "archivos": [a["file"].name for a in archivos],
        },
    )
    return archivos


def get_file_exists(file_path):
    """Verifica si el archivo existe."""
    return Path(file_path).exists()


def get_extension(file_path):
    """Obtiene la extensión del archivo."""
    return Path(file_path).suffix.lower()


def get_polars_scan_method(file_path):
    """Retorna el metodo de lectura de polar segun la extension del archivo."""
    ext = get_extension(file_path)
    scanners = {
        ".csv": pl.read_csv,
        ".txt": pl.read_csv,
        ".parquet": pl.read_parquet,
        ".json": pl.read_json,
        ".jsonl": pl.read_json,
        ".ipc": pl.read_ipc,
        ".arrow": pl.read_ipc,
    }
    return scanners.get(ext, None)


def get_encoding(file_path):
    """Detecta el encoding del archivo."""
    resultado = from_path(file_path).best()
    if resultado.encoding.lower() in ("utf_8", "utf-8"):
        return "utf8"
    return resultado.encoding


def metadata_polars(file_path, delimiter, encoding, execution_id=None):
    """Analiza el CSV usando Polars y retorna múltiples métricas."""
    if not get_file_exists(file_path):
        return {
            "execution_id": execution_id,
            "columns_name": [],
            "columns_count": 0,
            "rows_count": 0,
            "success": False,
            "error": f"Archivo no encontrado: {file_path}",
        }

    ext = get_extension(file_path)

    # 1. Definimos los métodos dinámicamente
    scanners = {
        ".csv": pl.scan_csv,
        ".txt": pl.scan_csv,
        ".parquet": pl.scan_parquet,
        ".jsonl": pl.scan_ndjson,
        ".ipc": pl.scan_ipc,
        ".arrow": pl.scan_ipc,
    }

    try:
        kwargs = {}
        if ext in [".csv", ".txt"]:
            kwargs["separator"] = delimiter
            kwargs["encoding"] = (
                "utf8" if encoding.lower() in ("utf8", "utf-8") else "utf8-lossy"
            )

        if ext in scanners:
            plscan = scanners[ext](file_path, **kwargs)
            schema = plscan.collect_schema()
            column_names = schema.names()
            row_count = plscan.select(pl.len()).collect().item()

            return {
                "execution_id": execution_id,
                "columns_name": column_names,
                "columns_count": len(column_names),
                "rows_count": row_count,
                "success": True,
            }
    except (pl.ComputeError, FileNotFoundError, ValueError) as e:
        registrar_log("analysis_error", {
            "status": "fail",
            "error_type": type(e).__name__,
            "message": str(e),
            "file": str(file_path)
        })
        return {
            "execution_id": execution_id,
            "columns_name": [],
            "columns_count": 0,
            "rows_count": 0,
            "success": False,
            "error": str(e)
        }

    return {
        "execution_id": execution_id,
        "columns_name": [],
        "columns_count": 0,
        "rows_count": 0,
        "success": False,
        "error": str(e)
    }



def analyze_single_file(file_path, delimiter=None, execution_id=None):
    """Analiza un archivo y retorna metadatos."""
    file = Path(file_path)
    metadata = {
        "execution_id": execution_id,
        "file_name": file.name,
        "file_path": str(file),
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
        "extension": file.suffix.lower() if file.suffix else None,
        "analyzed_at": datetime.now().isoformat(),
    }

    if not file.exists():
        registrar_log("file_not_found", {"status": "error", "path": str(file_path)})
        metadata["error"] = "Archivo no encontrado"
        return metadata

    metadata["exists"] = True

    try:
        file_stat = file.stat()
        metadata["file_size_bytes"] = file_stat.st_size
        metadata["file_size_mb"] = round(file_stat.st_size / (1024 * 1024), 2)
        metadata["last_modified"] = datetime.fromtimestamp(file_stat.st_mtime).isoformat()

        if metadata["file_size_bytes"] > 0:
            if metadata["extension"] in [".csv", ".txt"]:
                metadata["encoding"] = get_encoding(file)

            csv_analysis = metadata_polars(
                file, metadata["delimiter"], metadata["encoding"], execution_id=execution_id

            )
            metadata["columns_name"] = csv_analysis["columns_name"]
            metadata["columns_count"] = csv_analysis["columns_count"]
            metadata["rows_count"] = csv_analysis["rows_count"]
            metadata["valid_csv"] = csv_analysis["success"]
        else:
            metadata["error"] = "Archivo vacío"

    except (OSError, ValueError, RuntimeError, AttributeError) as e:
        registrar_log("analysis_error", {
            "status": "fail",
            "error_type": type(e).__name__,
            "message": str(e),
            "file": str(file_path)
        })
        metadata["error"] = f"Error durante el análisis: {type(e).__name__} - {str(e)}"


    return metadata

def create_metadata_dataframe(file_metadata_list):
    """
    Convierte lista de diccionarios a DataFrame de Polars.
    """
    if not file_metadata_list:
        return pl.DataFrame(schema={
            "execution_id": pl.Utf8,
            "file_name": pl.Utf8,
            "file_path": pl.Utf8,
            "exists": pl.Boolean,
            "valid_csv": pl.Boolean,
            "file_size_mb": pl.Float64,
            "file_size_bytes": pl.Int64,
            "encoding": pl.Utf8,
            "delimiter": pl.Utf8,
            "columns_name": pl.List(pl.Utf8),
            "columns_count": pl.UInt32,
            "rows_count": pl.UInt32,
            "last_modified": pl.Utf8,
            "extension": pl.Utf8,
            "analyzed_at": pl.Utf8,
            "error": pl.Utf8,
            "analysis_error": pl.Utf8
        })

    return pl.DataFrame(file_metadata_list)

def export_metadata(df, output_path , output_path_detail):

    """Exporta los metadatos a diferentes formatos."""

     # 1. Convertir a objeto Path
    path = Path(output_path).with_suffix(".csv")
    path_detail = Path(output_path_detail).with_suffix(".csv")

    # CSV (legible para humanos)
    df.select(pl.all().exclude("columns_name")).write_csv(path)
    #Se expande hacia abajo el nombre del archivo junto a las columnas
    df.select(
        pl.col("execution_id"),
        pl.col("file_name"),
        pl.col("columns_name")
    ).explode("columns_name").write_csv(path_detail)
    # Guardar columnas como texto separado por comas



def run_csv_analysis(execution_id=None):
    """Ejecuta el análisis de archivos CSV definidos en el pipeline."""
    # creamos diccioanrio para metadata de cada archivo, con el mismo esquema de llaves para consistencia del DataFrame
    all_metadata = []
    for file in get_pipeline_files():
        all_metadata.append(analyze_single_file(file_path=file['file'], delimiter=file['delimiter'], execution_id=execution_id))


    df_metadata = create_metadata_dataframe(all_metadata)
    print (df_metadata)
    # archivo actual
    current_file = Path(__file__).resolve()
    metadata_path = current_file.parent.parent / "src" / "metadata"
    metadata_path_detail = current_file.parent.parent / "src" / "metadata_detail"
    print (metadata_path)
    export_metadata(df_metadata, output_path=metadata_path, output_path_detail=metadata_path_detail)


if __name__ == "__main__":

    run_csv_analysis()
