"""Validación de rutas de archivos."""
import pathlib
import os


def validate_path(ruta: str, extension: str) -> bool:
    """Valida que la ruta sea un archivo accesible con la extensión esperada.

    Devuelve False si el archivo no existe desde el contenedor —
    puede ser una ruta de servidor (Escenario B). El motor DB valida en su lado.
    Lanza excepción solo para errores que el usuario debe corregir.
    """
    path = pathlib.Path(ruta)

    if not path.exists():
        return False

    if not path.is_file():
        raise IsADirectoryError(
            f"La ruta '{ruta}' es un directorio, se esperaba un archivo."
        )

    if path.suffix.lower() != extension.lower():
        raise ValueError(
            f"El archivo '{ruta}' no tiene la extensión '{extension}'."
        )

    if not os.access(path, os.R_OK):
        raise PermissionError(
            f"No hay permisos de lectura para '{ruta}'."
        )

    return True