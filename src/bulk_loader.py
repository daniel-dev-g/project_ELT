import pathlib
import subprocess

def sqlserver_bcp_windows(ruta_csv, servidor, base_datos, schema, tabla):
    # Convertir a ruta absoluta
    if not pathlib.Path(ruta_csv).is_absolute():
        ruta_csv = pathlib.Path.cwd() / ruta_csv
        print(f"ruta del archivo CSV : {pathlib.Path.cwd()}")
    # VERIFICAR QUE EL ARCHIVO EXISTE
    if not pathlib.Path(ruta_csv).exists():
        print(f"❌ Error: Archivo no encontrado: {ruta_csv}")
        print(f"   Directorio actual: {pathlib.Path.cwd()}")
        return False
    
    # Comando con comillas
    cmd = f'bcp {base_datos}.{schema}.{tabla} in "{ruta_csv}" -S {servidor} -T -c -t ";" -r "\\n" -F 2'
    
    # Capturar output para debug
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, encoding='utf-8')
    
    # Debug
    if result.returncode != 0:
        print(f"❌ BCP falló (code: {result.returncode})")
        print(f"   Error: {result.stderr}")
    
    return result.returncode == 0

