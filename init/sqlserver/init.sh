#!/bin/bash
# Inicia SQL Server y crea la base de datos definida en SQLSERVER_DB.
# Se ejecuta una sola vez al crear el volumen por primera vez.

# Arranca SQL Server en segundo plano
/opt/mssql/bin/sqlservr &
PID=$!

# Reenvía SIGTERM y SIGINT a SQL Server para que docker stop funcione correctamente
trap "kill $PID" SIGTERM SIGINT

# Espera hasta que SQL Server acepte conexiones
echo "Esperando a que SQL Server esté listo..."
for i in {1..30}; do
    /opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -P "$MSSQL_SA_PASSWORD" -No -Q "SELECT 1" > /dev/null 2>&1
    if [ $? -eq 0 ]; then
        echo "SQL Server listo."
        break
    fi
    echo "  Intento $i/30..."
    sleep 2
done

# Crea la base de datos si no existe
echo "Creando base de datos: $SQLSERVER_DB"
/opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -P "$MSSQL_SA_PASSWORD" -No -Q \
    "IF NOT EXISTS (SELECT name FROM sys.databases WHERE name = '${SQLSERVER_DB}')
     BEGIN
         CREATE DATABASE [${SQLSERVER_DB}]
         PRINT 'Base de datos ${SQLSERVER_DB} creada.'
     END
     ELSE
         PRINT 'Base de datos ${SQLSERVER_DB} ya existe.'"

# Mantiene el contenedor corriendo y espera a SQL Server
wait $PID