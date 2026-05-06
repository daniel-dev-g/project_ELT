# FlowELT

![Python](https://img.shields.io/badge/Python-3.14-blue?logo=python)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker)
![uv](https://img.shields.io/badge/uv-package%20manager-purple)
![License](https://img.shields.io/badge/license-MIT-green)

> Motor ELT ligero y de alto rendimiento para entornos on-premise.
> Diseñado para simplicidad, observabilidad y flujos reales de ingeniería de datos.

---

## ¿Qué es FlowELT?

**FlowELT** es un motor ELT configurable que permite la carga masiva de archivos planos (CSV/TXT) hacia múltiples motores de bases de datos utilizando sus herramientas nativas de alto rendimiento.

> **Proveer una alternativa simple, reproducible y observable a herramientas de datos complejas.**

---

## ¿Por qué FlowELT?

El patrón habitual en pipelines de datos con Python:

```python
# Lo que se ve en producción
df = pd.read_csv("archivo.csv")             # carga todo a RAM
df.to_sql("tabla", engine, chunksize=1000)  # inserta fila por fila
```

Funciona para volúmenes pequeños. Cuando el archivo crece, el proceso pasa de minutos a horas.

**FlowELT propone un enfoque distinto:**

- Carga masiva nativa por motor de base de datos (sin pasar datos por Python)
- Configuración declarativa mediante YAML
- Compatibilidad total con entornos on-premise
- Observabilidad integrada — logs estructurados + dashboard HTML por ejecución
- Sin dependencias de orquestadores pesados

---

## Rendimiento

| Archivos | Volumen total | Filas      | Duración   | Motor      | Escenario  | Método               |
|----------|---------------|------------|------------|------------|------------|----------------------|
| 4        | ~2 GB         | 13.229.516 | 31.2s      | PostgreSQL | A (Docker) | `COPY FROM`          |
| 4        | ~2 GB         | 13.229.516 | 31.73s     | SQL Server | A (Docker) | `BULK INSERT`        |
| 4        | ~2 GB         | 13.229.516 | 59.25s     | MariaDB    | B (local)  | `LOAD DATA INFILE`   |

> Hardware: Intel Core i3-1005G1 @ 1.20GHz / 11 GB RAM / Ubuntu Linux / NVMe interno.

---

## Bases de datos soportadas

| Motor      | Método de carga nativa  |
|------------|-------------------------|
| PostgreSQL | `COPY FROM`             |
| SQL Server | `BULK INSERT`           |
| MariaDB    | `LOAD DATA INFILE`      |
| MySQL 8    | `LOAD DATA INFILE`      |

---

## Modos de uso

| | Opción A — Docker | Opción B — Local |
|---|---|---|
| **Cuándo usarlo** | Pruebas, demo, sin BD instalada | BD propia en red o máquina local |
| **Requisito** | Docker + Docker Compose | Python 3.14 + uv |
| **Interfaz** | CLI (`main.py` en contenedor) | GUI visual (`gui.py`) |
| **Archivos CSV** | Dentro de `./data/input/` | Cualquier ruta de tu máquina |
| **BD** | Contenerizada (A) o externa (A-standalone) | La tuya, sin Docker |

---

## Opción A — Docker

### Prerrequisitos

- [Docker](https://docs.docker.com/get-docker/) + Docker Compose

### Paso 1 — Clonar

```bash
git clone https://github.com/daniel-dev-g/project_ELT.git
cd project_ELT
```

### Paso 2 — Configurar entorno

```bash
cp .env.example .env
```

Los valores del `.env.example` son suficientes para el Escenario A — Docker crea y configura la BD automáticamente.

### Paso 3 — Seleccionar motor

Edita `.env`:

```env
DB_ENGINE=postgres     # postgres | sqlserver | mariadb
```

### Paso 4 — Agregar archivos CSV

```
data/
└── input/
    ├── clientes.csv
    └── ventas.csv
```

### Paso 5 — Configurar pipeline

Edita `config/pipeline.yaml`:

```yaml
_defaults:
  schema: "public"          # public → PostgreSQL | dbo → SQL Server | "" → MariaDB / MySQL
  delimiter: ";"
  crear_tabla_si_no_existe: true
  truncate_before_load: false
  active: true

task:
  - name: "Carga clientes"
    file: "data/input/clientes.csv"   # relativo a la raíz del proyecto
    delimiter: ";"
    encoding: "utf8"
    table_destination: "clientes"
    schema: "public"
    crear_tabla_si_no_existe: true
    truncate_before_load: false       # true = vacía la tabla antes de cargar
    active: true
```

> **Requisito:** Los archivos CSV deben incluir fila de encabezado (primera fila = nombres de columnas).
> El pipeline la usa para inferir el esquema al crear la tabla y para configurar la carga masiva.
> Un archivo sin encabezado producirá errores de esquema o datos corruptos.

### Paso 6 — Ejecutar

```bash
# PostgreSQL
docker compose --profile postgres up

# SQL Server
docker compose --profile sqlserver up

# MariaDB 11
docker compose --profile mariadb up

# MySQL 8
docker compose --profile mysql8 up
```

Docker construye la imagen, levanta la BD, espera que esté lista y ejecuta la carga.
Al terminar verás en `logs/` el dashboard HTML y el log estructurado.

> **Primera ejecución o tras actualizar el proyecto:** agrega `--build` para forzar la reconstrucción de la imagen:
> ```bash
> docker compose --profile postgres up --build
> ```

#### Puertos expuestos (para conectar con DBeaver u otro cliente)

| Motor      | Puerto local |
|------------|-------------|
| PostgreSQL | `5433`      |
| SQL Server | `1433`      |
| MariaDB 11 | `3307`      |
| MySQL 8    | `3308`      |

### Variante — BD externa (standalone)

Si ya tienes una BD instalada en tu servidor, usa el perfil `standalone`.
El contenedor Python se conecta a tu BD sin levantarla:

```bash
# Configura en .env las credenciales de tu BD externa
docker compose --profile standalone up
```

> Usa `network_mode: host`, por lo que `127.0.0.1` apunta directamente a tu máquina.

#### Permisos requeridos por motor

**PostgreSQL** — el usuario necesita `pg_read_server_files` o ser superusuario:

```sql
GRANT pg_read_server_files TO mi_usuario;
```

> Si los archivos están en la misma máquina que la app, FlowELT usa `COPY FROM STDIN`
> (client-side) y no requiere este permiso.

**SQL Server** — rol `bulkadmin` o permiso `ADMINISTER BULK OPERATIONS`:

```sql
EXEC sp_addrolemember 'bulkadmin', 'mi_usuario';
```

**MariaDB** — privilegio `FILE` + `secure_file_priv` vacío:

```ini
# /etc/mysql/mariadb.conf.d/50-server.cnf
[mysqld]
secure_file_priv=
```

```bash
sudo systemctl restart mariadb
sudo mariadb -e "GRANT FILE ON *.* TO 'tu_usuario'@'%'; FLUSH PRIVILEGES;"
```

---

## Opción B — Instalación local (GUI)

Corre FlowELT directamente en tu máquina con la interfaz gráfica.
No requiere Docker.

### Prerrequisitos

- Python 3.14
- [uv](https://docs.astral.sh/uv/getting-started/installation/)

```bash
# Instalar uv (Linux / macOS)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows (PowerShell)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

- **Solo si usas SQL Server**: ODBC Driver 18

```bash
# Ubuntu / Debian
curl -fsSL https://packages.microsoft.com/keys/microsoft.asc \
  | sudo gpg --dearmor -o /usr/share/keyrings/microsoft.gpg
echo "deb [arch=amd64 signed-by=/usr/share/keyrings/microsoft.gpg] \
  https://packages.microsoft.com/debian/12/prod bookworm main" \
  | sudo tee /etc/apt/sources.list.d/mssql-release.list
sudo apt-get update
sudo ACCEPT_EULA=Y apt-get install -y msodbcsql18 unixodbc-dev
```

- **Solo si usas MySQL 8 o MariaDB local**: configuración para `LOAD DATA INFILE`

**1. Instalar MySQL:**
```bash
sudo apt update
sudo apt install -y mysql-server
sudo systemctl enable --now mysql
sudo mysql_secure_installation
```

**2. Configurar `secure_file_priv` y `local_infile`:**

Edita `/etc/mysql/mysql.conf.d/mysqld.cnf` y agrega bajo `[mysqld]`:

```ini
[mysqld]
secure_file_priv=
local_infile=1
```

```bash
sudo systemctl restart mysql
```

**3. Crear base de datos y usuario:**

```bash
sudo mysql -u root -p <<'EOF'
CREATE DATABASE IF NOT EXISTS flowelt_demo;
CREATE USER 'admin'@'localhost' IDENTIFIED WITH mysql_native_password BY 'tu_password';
GRANT ALL PRIVILEGES ON flowelt_demo.* TO 'admin'@'localhost';
GRANT FILE ON *.* TO 'admin'@'localhost';
FLUSH PRIVILEGES;
EOF
```

**4. Permisos sobre los archivos CSV:**

El servidor MySQL corre como el usuario de sistema `mysql` y no puede leer archivos en carpetas personales sin permisos explícitos:

```bash
chmod o+x /home/$USER
chmod o+x /home/$USER/Documentos   # ajusta al directorio donde estén los CSV
chmod o+r /home/$USER/Documentos/*.csv
```

**5. AppArmor (Ubuntu):**

AppArmor restringe qué rutas puede leer MySQL. Si los CSV están en `/home/`, agrega una excepción:

```bash
sudo nano /etc/apparmor.d/usr.sbin.mysqld
```

Agrega antes del último `}`:
```
  /home/*/Documentos/ r,
  /home/*/Documentos/** r,
```

```bash
sudo apparmor_parser -r /etc/apparmor.d/usr.sbin.mysqld
```

> **Detección automática:** FlowELT verifica estos requisitos antes de cada carga y muestra un mensaje accionable si algo falla — `secure_file_priv` activo, permisos insuficientes o AppArmor bloqueando el acceso.

### Paso 1 — Clonar

```bash
git clone https://github.com/daniel-dev-g/project_ELT.git
cd project_ELT
```

### Paso 2 — Instalar dependencias

```bash
uv sync
```

### Paso 3 — Configurar entorno

```bash
cp .env.example .env
```

Edita `.env` con las credenciales de tu BD:

**PostgreSQL:**
```env
DB_ENGINE=postgres
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=mi_usuario
POSTGRES_PASSWORD=mi_password
POSTGRES_DB=mi_base
```

**SQL Server:**
```env
DB_ENGINE=sqlserver
SQLSERVER_HOST=localhost
SQLSERVER_PORT=1433
SQLSERVER_USER=mi_usuario
SQLSERVER_PASSWORD=mi_password
SQLSERVER_DB=mi_base
```

**MariaDB:**
```env
DB_ENGINE=mariadb
MARIADB_HOST=localhost
MARIADB_PORT=3306
MARIADB_USER=mi_usuario
MARIADB_PASSWORD=mi_password
MARIADB_DB=mi_base
```

**MySQL 8:**
```env
DB_ENGINE=mysql
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=mi_usuario
MYSQL_PASSWORD=mi_password
MYSQL_DB=mi_base
```

> Los puertos `3307` y `3308` son solo para los contenedores Docker (para no chocar con una instalación local). Una instalación local de MariaDB o MySQL siempre usa el puerto `3306`.

### Paso 4 — Lanzar la GUI

> **Nota:** Si previamente ejecutaste la Opción A (Docker), el directorio `logs/` puede pertenecer a `root` y la GUI no podrá escribir logs. Corrígelo antes de continuar:
> ```bash
> sudo chown -R $USER:$USER logs/
> ```

```bash
uv run python gui.py
```

La interfaz permite:

- Conectar a cualquier motor con un formulario visual
- Agregar archivos CSV desde cualquier carpeta del equipo
- Configurar tabla destino, esquema, delimitador y opciones por archivo
- Guardar el pipeline en `config/pipeline.yaml`
- Ejecutar la carga y ver el resultado en pantalla
- Abrir el dashboard HTML de la ejecución con un clic

![GUI](screenshot.png)

### Alternativa — CLI sin GUI

Si prefieres la línea de comandos, configura `config/pipeline.yaml` manualmente y ejecuta:

```bash
uv run main.py
```

---

## Arquitectura

```
Archivos CSV / TXT
        │
        ▼
┌───────────────────┐
│  Capa validación  │  conexión, tablas, permisos BULK
└────────┬──────────┘
         │
         ▼
┌───────────────────┐
│  Análisis Polars  │  metadata, tipos, estadísticas
└────────┬──────────┘
         │
         ▼
┌───────────────────┐
│  Motor de carga   │  BULK INSERT / COPY / LOAD DATA
│  (nativo por BD)  │
└────────┬──────────┘
         │
         ▼
┌───────────────────┐
│  Observabilidad   │  JSON estructurado + Dashboard HTML
└───────────────────┘
```

---

## Outputs

| Archivo          | Descripción                           |
|------------------|---------------------------------------|
| `log_*.json`     | Log estructurado de ejecución         |
| `log_*.html`     | Dashboard HTML interactivo            |
| `technical.log`  | Log técnico interno                   |

Todos los outputs comparten el mismo `execution_id` para trazabilidad completa.

---

## Tecnologías

| Componente    | Tecnología        |
|---------------|-------------------|
| Lenguaje      | Python 3.14       |
| GUI           | Flet (Flutter)    |
| Análisis      | Polars            |
| Configuración | YAML + .env       |
| Logging       | JSON estructurado |
| Visualización | HTML Dashboard    |
| Contenedores  | Docker + Compose  |
| Gestión deps  | uv                |

---

## Decisiones de diseño

| Decisión | Razón |
|---|---|
| Carga masiva nativa en lugar de ORM | Rendimiento — la BD lee directo del disco sin pasar datos por Python |
| Configuración YAML | Simplicidad y reproducibilidad sin tocar código |
| `execution_id` por ejecución | Trazabilidad completa entre logs, dashboard y técnico |
| `bulk_path_map` | Desacopla la ruta de Python de la ruta de la BD en Docker |
| Polars en lugar de pandas | Velocidad y bajo consumo de memoria en análisis de metadatos |
| Factory pattern para adaptadores | Desacoplamiento de motores — mismo pipeline, distinta BD |

---

## Estado de pruebas

| Motor      | Estado   | Escenario probado       | Método               |
|------------|----------|-------------------------|----------------------|
| PostgreSQL | Probado  | A (Docker) + B (local)  | `COPY FROM` / STDIN  |
| SQL Server | Probado  | A (Docker)              | `BULK INSERT`        |
| MariaDB    | Probado  | A (Docker) + B (local)  | `LOAD DATA INFILE`   |

---

## Roadmap

- [x] **Interfaz gráfica** (Flet) — formulario de conexión, selector de archivos, ejecución visual, dashboard integrado
- [ ] Empaquetado como ejecutable nativo (PyInstaller) — sin Python ni dependencias
- [ ] Módulo de profiling (nulos, cardinalidad, tipos)
- [ ] Motor de reglas de calidad configurables en YAML
- [ ] **Linaje a nivel de fila** — columnas `_execution_id`, `_source_file`, `_load_timestamp` en capa raw via SQL post-carga
- [ ] Integración con Airflow o Prefect

---

## Arquitectura con linaje (roadmap)

La carga nativa no permite inyectar columnas adicionales durante la transferencia. El diseño propuesto lo agrega en un paso SQL posterior, dentro de la BD, sin pasar datos por Python.

```
PASO 1 — Carga nativa (sin cambios)
CSV ──► BULK INSERT / COPY ──► landing.clientes   ← datos puros

PASO 2 — SQL post-carga (dentro de la BD)
INSERT INTO raw.clientes
SELECT c.*, l.execution_id AS _execution_id,
            l.source_file  AS _source_file,
            l.load_timestamp AS _load_timestamp
FROM landing.clientes c
JOIN bd_logs l ON l.task_id = '<task_id_actual>'
```

---

## Objetivo del proyecto

FlowELT no busca ser un producto comercial.

Su propósito es demostrar prácticas reales de ingeniería de datos, explorar patrones escalables de ELT y construir una alternativa ligera a herramientas complejas — evidenciando decisiones de ingeniería, no solo código.

---

## Autor

**Daniel Guevara**
Data Engineer | Python | SQL | GCP | Santiago, Chile

- GitHub: [daniel-dev-g](https://github.com/daniel-dev-g)
- LinkedIn: [daniel-guevara](https://www.linkedin.com/in/daniel-guevara-2a64a479/)

---

> *Las herramientas de ingeniería de datos deberían ser simples, transparentes y eficientes — no complejas por defecto.*