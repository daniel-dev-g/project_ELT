"""llama a la base de datos segun lo indicado en yaml"""

from src.state_manager.core.adapter_db.database_adapter import DatabaseAdapter
from src.state_manager.core.adapter_db.sqlserver_adapter import SqlServerAdapter
from src.state_manager.core.adapter_db.postgres_adapter import PostgresAdapter

def factory_db(config: dict) -> DatabaseAdapter:

    match  config['db_engine']:
        case 'sqlserver':
            return SqlServerAdapter(config)
        case 'postgres':
            return PostgresAdapter(config)
        case _:
            raise ValueError(
                f"db_engine '{config['db_engine']}' not supported")
