""" df_utils.py """

from pathlib import Path
import polars as pl


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