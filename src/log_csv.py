""" log_csv.py """

import logging
import json
from datetime import datetime
from pathlib import Path


# Crear carpeta logs si no existe
Path("logs").mkdir(exist_ok=True)

# Crear logger específico para JSON (no usa el root logger)
json_logger = logging.getLogger('json_audit')
json_logger.setLevel(logging.INFO)
json_logger.propagate = False  # NO propagar al root logger

# Generar nombre de archivo
timestamp_id = datetime.now().strftime("%Y%m%d_%H%M%S")
nombre_log = f"logs/log_{timestamp_id}.json"

# Configurar handler específico para este logger
json_handler = logging.FileHandler(nombre_log, encoding='utf-8')
json_handler.setLevel(logging.INFO)
json_handler.setFormatter(logging.Formatter('%(message)s'))

# Agregar handler al logger
json_logger.addHandler(json_handler)


def registrar_log(evento, contenido):
    """
    Registra un evento en formato JSON.

    Args:
        evento: Nombre del evento (ej: 'analisis_inicial')
        contenido: Diccionario con los detalles del evento
    """
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "evento": evento,
        "detalles": contenido
    }
    json_logger.info(json.dumps(log_entry, ensure_ascii=False))


def get_log_filename():
    """Retorna el nombre del archivo de log actual."""
    return nombre_log


def get_log_path():
    """Retorna el Path completo al archivo de log actual."""
    return Path(nombre_log).absolute()
