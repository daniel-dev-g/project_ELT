from charset_normalizer import from_path

def get_encoding(ruta):
    resultado = from_path(ruta).best()
    return resultado.encoding # Ejemplo: 'utf-8' o 'ISO-8859-1'


import csv

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
    columnas_reales = lf.columns
    cantidad_columnas = len(columnas_reales)
    
    # 2. Cantidad de registros (se ejecuta de forma optimizada)
    cantidad_registros = lf.select(pl.len()).collect().item()
    
    return {
        "columnas": columnas_reales,
        "total_columnas": cantidad_columnas,
        "total_filas": cantidad_registros
    }
