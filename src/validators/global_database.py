#database.py
import urllib.parse
from sqlalchemy import create_engine

def create_engine_db(config: dict):
    # Usamos llaves triples {{{ }}} para escapar las llaves del Driver ODBC en la f-string
    params = urllib.parse.quote_plus(
        f"DRIVER={{{config['driver']}}};"
        f"SERVER={config['server']};"
        f"DATABASE={config['database']};"
        f"Trusted_Connection={config.get('trusted_connection', 'yes')};"
        f"Encrypt={config.get('encrypt', 'no')};"
    )
    connection_url = f"mssql+pyodbc:///?odbc_connect={params}"
    
    # Retornamos el engine. SQLAlchemy se encarga de gestionar la conexión.
    return create_engine(connection_url, echo=False)
