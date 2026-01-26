import polars as pl
from sqlalchemy import create_engine, inspect


# 1. Mostrar todas las filas (evita el "...")
pl.Config.set_tbl_rows(-1) 

# 2. Evitar que el texto largo se corte (ej: "Modern_Spani...")
pl.Config.set_fmt_str_lengths(100) 

# 3. (Opcional) Forzar a que la tabla ocupe más ancho en la terminal
pl.Config.set_tbl_width_chars(200)


server = "LAPTOP-6N8CIQUQ" 
database = "polars"
connection_url = f"mssql+pymssql://{server}/{database}"
engine = create_engine(connection_url)

def obtener_schema_tabla_dataframe(nombre_tabla):
    try:
        inspector = inspect(engine)
        columnas = inspector.get_columns(nombre_tabla)
        
        # --- FIX: Convertimos el objeto 'type' a string ANTES de crear el DataFrame para evitar error ---
        for col in columnas:
            col['type'] = str(col['type'])
        
        df_schema = pl.DataFrame(columnas)
        
        # Ahora 'type' ya es un String de Polars, no un Object
        df_vista = df_schema.select([
            pl.col("name").alias("Columna"),
            pl.col("type").alias("Tipo_SQL"),
            pl.col("nullable").alias("Permite_Nulos")
        ])
        
        print(df_vista)
        return df_vista
    except Exception as e:
        print(f"❌ Error: {e}")




