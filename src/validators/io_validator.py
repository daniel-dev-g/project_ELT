import pathlib
import os


def validate_path(ruta: str, extension: str) -> bool:
    path = pathlib.Path(ruta)

    # 1. ¿Existe?
    if not path.exists():
        raise FileNotFoundError(f"La ruta '{ruta}' no existe.")

    # 2. ¿Es un archivo?
    if not path.is_file():
        raise IsADirectoryError(f"La ruta '{ruta}' es un directorio, se esperaba un archivo.")

    # 3. ¿Extensión correcta? (Usamos ValueError porque la ruta existe pero el valor es incorrecto)
    if path.suffix.lower() != extension.lower():
        raise ValueError(f"El archivo '{ruta}' no tiene la extensión '{extension}'.")

    # 4. ¿Permisos?
    if not os.access(path, os.R_OK):
        raise PermissionError(f"No hay permisos de lectura para '{ruta}'.")
    
    return True


