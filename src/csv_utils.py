""" csv_utils.py """

from pathlib import Path


import polars as pl
from charset_normalizer import from_bytes

# Nota: log_csv.registrar es el módulo personalizado
from src.log_csv import registrar_log

class CSVUtils:
    """Utilidades para análisis de archivos CSV."""
    def __init__(self, path, delimiter, execution_id):
        self.file_path = path
        self.delimiter = delimiter
        self.encoding = self.get_encoding() if self.get_file_exists() else None
        self.execution_id = execution_id

    def get_file_exists(self):
        """Verifica si el archivo existe."""
        return Path(self.file_path).exists()


    def get_extension(self):
        """Obtiene la extensión del archivo."""
        return Path(self.file_path).suffix.lower()


    def get_polars_scan_method(self):
        """Retorna el metodo de lectura de polar segun la extension del archivo."""
        ext = self.get_extension()
        scanners = {
            ".csv": pl.read_csv,
            ".txt": pl.read_csv
        }
        return scanners.get(ext, None)


    def get_encoding(self):
        """Detecta el encoding usando solo los primeros 256 KB del archivo."""
        with open(self.file_path, 'rb') as f:
            sample = f.read(256_000)
        resultado = from_bytes(sample).best()
        if resultado is None or resultado.encoding is None:
            return "utf8"
        if resultado.encoding.lower() in ("utf_8", "utf-8"):
            return "utf8"
        return resultado.encoding

    def metadata_polars(self):
        """Analiza el CSV usando Polars y retorna múltiples métricas."""
        if not self.get_file_exists():
            return {
                "execution_id": self.execution_id,
                "columns_name": [],
                "columns_count": 0,
                "rows_count": 0,
                "success": False,
                "error": f"Archivo no encontrado: {self.file_path}",
            }

        ext = self.get_extension()

        # 1. Definimos los métodos dinámicamente
        scanners = {
            ".csv": pl.scan_csv,
            ".txt": pl.scan_csv
        }

        try:
            kwargs = {}
            if ext in [".csv", ".txt"]:
                kwargs["separator"] = self.delimiter
                encoding = self.encoding or "utf8"
                kwargs["encoding"] = (
                    "utf8" if encoding.lower() in ("utf8", "utf-8") else "utf8-lossy"
                )

            if ext in scanners:
                plscan = scanners[ext](self.file_path, **kwargs)
                schema = plscan.collect_schema()
                column_names = schema.names()
                row_count = plscan.select(pl.len()).collect().item()

                return {
                    "execution_id": self.execution_id,
                    "columns_name": column_names,
                    "columns_count": len(column_names),
                    "rows_count": row_count,
                    "success": True,
                }
        except (pl.exceptions.ComputeError, FileNotFoundError, ValueError) as e:
            registrar_log("analysis_error", {
                "status": "fail",
                "error_type": type(e).__name__,
                "message": str(e),
                "file": str(self.file_path)
            })
            return {
                "execution_id": self.execution_id,
                "columns_name": [],
                "columns_count": 0,
                "rows_count": 0,
                "success": False,
                "error": str(e)
            }

        return {
            "execution_id": self.execution_id,
            "columns_name": [],
            "columns_count": 0,
            "rows_count": 0,
            "success": False,
            "error": f"Extensión no soportada: {self.get_extension()}"
        }






