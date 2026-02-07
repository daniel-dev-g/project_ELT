import csv
from charset_normalizer import from_path
from pathlib import Path 
import logging
from log_csv import registrar



def get_encoding(ruta):
    resultado = from_path(ruta).best()
    if resultado.encoding.lower() in( 'utf_8', 'utf-8' ):
        return 'utf8'
    else:
        return resultado.encoding # Devuelve el encoding detectado si no es UTF-8
        

def detect_delimiter(ruta, encoding):
    with open(ruta, 'r', encoding=encoding) as f:
        muestra = f.read(2048) # Leemos solo el inicio para analizar
        dialect = csv.Sniffer().sniff(muestra)
        return dialect.delimiter # Devuelve ',' o ';' o '\t'

import polars as pl

def validate_csv_structure(ruta, sep, encoding_detectado):
    # Usamos scan_csv para una inspección rápida (Lazy)
    lf = pl.scan_csv(ruta, separator=sep, encoding=encoding_detectado)
    
    # 1. Cantidad de columnas y nombres

    columnas_reales = lf.collect_schema().names()
    cantidad_columnas = len(columnas_reales)
    
    # 2. Cantidad de registros (se ejecuta de forma optimizada)
    cantidad_registros = lf.select(pl.len()).collect().item()
    
    return {
        "columnas": columnas_reales,
        "total_columnas": cantidad_columnas,
        "total_filas": cantidad_registros
    }

def main():

    # 1. Configuración: nombre del archivo y nivel de importancia
    logging.basicConfig(
    filename='mi_registro.log', 
    level=logging.INFO,
    format='%(asctime)s - %(message)s' # Opcional: añade la hora a cada línea
)
    try:
        
        project_root = Path(__file__).parent.parent  # Sube 2 niveles
        ruta_csv = project_root / "data" / "input" / "cliente.csv"
       
        if not ruta_csv.exists():
            raise FileNotFoundError(f"El archivo no existe: {ruta_csv}")
        
        # Paso 1: Detectar encoding
        encoding_detectado = get_encoding(ruta_csv)
              
        # Paso 2: Detectar delimitador
        delimitador = detect_delimiter(ruta_csv, encoding_detectado)
       
        # Paso 3: Validar estructura del CSV
        resultado_validacion = validate_csv_structure(ruta_csv, delimitador, encoding_detectado)
       
        registrar("analisis_inicial", {
        "archivo_origen": str(ruta_csv),
        "encoding": encoding_detectado,
        "delimitador": delimitador        
        })

        registrar("estadisticas_carga", {
        "columnas": resultado_validacion['columnas'],
        "total_filas": resultado_validacion['total_filas'],
        "total_columnas": resultado_validacion['total_columnas']
        })


    except Exception as e:
        logging.error(f"Error durante el análisis del CSV: {e}")
if __name__ == "__main__":
    main()  