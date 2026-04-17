# Configuración Docker — FlowELT

## Archivos

| Archivo | Para qué sirve |
|---|---|
| `Dockerfile` | Define la imagen de la app para producción |
| `docker-compose.yml` | Levanta las bases de datos en contenedores |

Docker solo se usa para las bases de datos. La app Python corre directamente en la máquina local.

---

## Arquitectura de contenedores

```
docker-compose.yml
├── servicio: sqlserver    (contenedor SQL Server)  ── volumen: sqlserver_data
├── servicio: postgres     (contenedor PostgreSQL)  ── volumen: postgres_data
├── servicio: mysql        (contenedor MySQL)       ── volumen: mysql_data
├── servicio: db2          (contenedor IBM Db2)     ── volumen: db2_data
└── servicio: oracle       (contenedor Oracle)      ── volumen: oracle_data
```

Cada motor tiene su propio volumen para persistir datos entre reinicios.

### Ejemplo con SQL Server

```
Tu máquina
├── Python local (uv run) ──── localhost:1433 ────► contenedor: sqlserver
└── VSCode debugger                                   volumen: sqlserver_data
```

La app se conecta a la base de datos por `localhost` usando el puerto expuesto por Docker.

---

## Flujo de trabajo

```
Terminal del host                  VSCode
─────────────────────────────      ──────────────────────────────────
Levanta la base de datos           Desarrolla y depura Python

docker compose --profile \         F5  →  ejecuta y depura main.py
  sqlserver up sqlserver -d        uv run main.py
                                   uv add <paquete>
docker compose down                uv sync
```

### Bases de datos disponibles

```bash
docker compose --profile sqlserver up sqlserver -d
docker compose --profile postgres  up postgres  -d
docker compose --profile mysql     up mysql     -d
docker compose --profile db2       up db2       -d
docker compose --profile oracle    up oracle    -d
```

---

## docker-compose.yml

Orquesta los contenedores de bases de datos.

```yaml
services:
  app:
    profiles: [sqlserver, postgres, mysql, db2, oracle]
```
El servicio `app` está definido pero solo se usa en producción. En desarrollo la app corre localmente.

```yaml
    env_file: .env
```
Carga las variables de entorno desde `.env` (passwords, nombres de BD, etc.).

```yaml
    volumes:
      - ./data:/app/data
      - ./config:/app/config
      - ./logs:/app/logs
```
Bind mounts — conectan carpetas locales con carpetas dentro del contenedor:
- `data/` — CSVs de entrada que procesa la app
- `config/` — archivos `settings.yaml` y `pipeline.yaml`
- `logs/` — logs generados por la app, visibles en el host

```yaml
  sqlserver:
    profiles: [sqlserver]
    image: mcr.microsoft.com/mssql/server:2022-latest
```
Imagen oficial de SQL Server 2022. Solo se levanta con `--profile sqlserver`.

```yaml
    ports:
      - "1433:1433"
```
Expone el puerto de SQL Server al host. La app local se conecta por `localhost:1433`.

```yaml
    volumes:
      - sqlserver_data:/var/opt/mssql
      - ./data:/data
```
- `sqlserver_data` — volumen nombrado gestionado por Docker, persiste los datos entre reinicios
- `./data:/data` — los CSVs son accesibles dentro del contenedor (necesario para BULK INSERT)

```yaml
volumes:
  sqlserver_data:
  postgres_data:
  ...
```
Declara los volúmenes nombrados. Persisten aunque el contenedor se elimine.

---

## Dockerfile

Define la imagen de la app para producción. No se usa en desarrollo local.

```dockerfile
FROM python:3.14-slim
```
Imagen base oficial de Python 3.14 slim (liviana, sin herramientas innecesarias).

```dockerfile
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl gnupg2 unixodbc-dev \
```
Instala herramientas para agregar el repositorio de Microsoft:
- `curl` — descarga archivos desde URLs
- `gnupg2` — verifica la firma del repositorio
- `unixodbc-dev` — cabeceras que necesita pyodbc para compilarse

```dockerfile
    && curl -fsSL https://packages.microsoft.com/keys/microsoft.asc \
        | gpg --dearmor -o /usr/share/keyrings/microsoft.gpg \
```
Descarga la clave pública de Microsoft y la convierte al formato binario que apt reconoce.

```dockerfile
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/microsoft.gpg] \
        https://packages.microsoft.com/debian/12/prod bookworm main" \
        > /etc/apt/sources.list.d/mssql-release.list \
```
Registra el repositorio de Microsoft en apt para poder instalar el driver ODBC.

```dockerfile
    && ACCEPT_EULA=Y apt-get install -y --no-install-recommends msodbcsql18 \
```
Instala el driver ODBC 18 de Microsoft. `ACCEPT_EULA=Y` acepta la licencia automáticamente.

```dockerfile
    && rm -rf /var/lib/apt/lists/*
```
Elimina la caché de apt para reducir el tamaño de la imagen.

```dockerfile
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
```
Copia el binario de `uv` desde su imagen oficial. Más rápido que instalarlo con pip.

```dockerfile
WORKDIR /app
```
Establece `/app` como directorio de trabajo.

```dockerfile
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen
```
Copia los archivos de dependencias e instala. Al separarlo del `COPY . .`, Docker cachea esta capa — si el código cambia pero las dependencias no, no reinstala nada.

```dockerfile
COPY . .
```
Copia el código fuente.

```dockerfile
CMD ["uv", "run", "main.py"]
```
Comando por defecto al arrancar el contenedor en producción.
