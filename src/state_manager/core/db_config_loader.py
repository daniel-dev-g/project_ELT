"""carga configuracion de base de datos desde setting.yaml"""
import os
import yaml


def load_config():
    """Carga configuración desde settings.yaml"""
    # Get the project root by going up from src/state_manager/core/
    project_root = os.path.abspath(os.path.join(
        os.path.dirname(__file__), '../../../'))
    config_path = os.path.join(project_root, 'config/settings.yaml')
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)['development']
