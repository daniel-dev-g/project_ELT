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
df = pd.read_csv("archivo.csv")          # carga todo a RAM
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

| Archivos | Volumen total | Filas      | Duración   | Motor      | Escenario | Método | Disco |
|----------|---------------|------------|------------|------------|-----------|--------|-------|
| 4        | ~2 GB         | 13.229.516 | 31.2s      | PostgreSQL | A (Docker) | `COPY FROM` | NVMe interno |
| 4        | ~2 GB         | 13.229.516 | 31.73s     | SQL Server | A (Docker) | `BULK INSERT` | NVMe interno |
| 4        | ~2 GB         | 13.229.516 | 59.25s     | MariaDB    | B (local)  | `LOAD DATA INFILE` | NVMe interno |

> Hardware: Intel Core i3-1005G1 @ 1.20GHz / 11 GB RAM / Ubuntu Linux / NVMe interno.
> PostgreSQL y SQL Server en Escenario A (Docker completo). MariaDB en Escenario B (BD local, app en Docker).

### Detalle — prueba con ~2 GB / 13 millones de filas (NVMe)

| Parámetro  | PostgreSQL | SQL Server | MariaDB |
|---|---|---|---|
| OS | Ubuntu Linux | Ubuntu Linux | Ubuntu Linux |
| Hardware | i3-1005G1 / 11 GB RAM | i3-1005G1 / 11 GB RAM | i3-1005G1 / 11 GB RAM |
| Disco | NVMe interno | NVMe interno | NVMe interno |
| Contenedor | `postgres:16` | `mcr.microsoft.com/mssql/server:2022-latest` | MariaDB 10.11 en host |
| Python | Docker (Escenario A) | Docker (Escenario A) | Docker, red host (Escenario B) |
| Método | `COPY FROM` server-side | `BULK INSERT` con `TABLOCK` + `BATCHSIZE=100000` | `LOAD DATA INFILE` server-side |
| Filas | 13.229.516 | 13.229.516 | 13.229.516 |
| Duración | **31.2 seg** | **31.73 seg** | 59.25 seg |
| Throughput | **~424.000 filas/seg** | **~417.000 filas/seg** | ~223.000 filas/seg |

> PostgreSQL y SQL Server medidos en Escenario A (BD contenerizada, Python en Docker).
> MariaDB medido en Escenario B (BD local en host, Python en contenedor con `network_mode: host`).
> Todos los motores leen directo desde disco — sin pasar datos por Python.
> Las pruebas se realizaron con configuración por defecto de cada motor, sin tuning adicional. Los resultados pueden mejorar con ajustes de memoria, paralelismo o parámetros de escritura propios de cada BD.

---

## Bases de datos soportadas

| Motor      | Método de carga nativa     |
|------------|----------------------------|
| SQL Server | `BULK INSERT`              |
| PostgreSQL | `COPY FROM`                |
| MariaDB    | `LOAD DATA INFILE`         |

---

## Arquitectura

### Flujo actual

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

### Arquitectura con linaje (roadmap)

El linaje no puede inyectarse durante la carga nativa — el archivo se transfiere tal cual para preservar el rendimiento. El diseño propuesto lo agrega en un paso SQL posterior, dentro de la base de datos, sin pasar datos por Python. **Esta funcionalidad aún no está implementada.**

```
Archivos CSV / TXT
        │
        ▼
┌─────────────────────────────────────────────────┐
│                   LANDING                        │
│                                                  │
│  BULK INSERT / COPY / LOAD DATA                  │
│                                                  │
│  ┌──────────────────┐   ┌──────────────────────┐ │
│  │ landing.clientes │   │ bd_logs              │ │
│  │ (datos puros)    │   │ execution_id         │ │
│  │                  │   │ task_id              │ │
│  │ col_1, col_2 ... │   │ source_file          │ │
│  └──────────────────┘   │ load_timestamp       │ │
│                         │ rows_inserted        │ │
│                         └──────────────────────┘ │
└─────────────────────┬───────────────────────────┘
                      │  SQL post-carga (JOIN)
                      ▼
┌─────────────────────────────────────────────────┐
│                     RAW                          │
│                                                  │
│  ┌─────────────────────────────────────────────┐ │
│  │ raw.clientes                                │ │
│  │                                             │ │
│  │ col_1, col_2 ...   ← datos originales       │ │
│  │ _execution_id      ← trazabilidad           │ │
│  │ _source_file       ← origen del archivo     │ │
│  │ _load_timestamp    ← momento de carga       │ │
│  └─────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────┘
```

Cada fila en `raw` puede responder: *¿de qué archivo viene? ¿cuándo se cargó? ¿en qué ejecución?*

---

## Características principales

- Pipelines configurables con YAML
- Carga masiva nativa por motor de base de datos
- Análisis de archivos con Polars
- Dashboard HTML interactivo por ejecución
- Logging estructurado con `execution_id` único por ejecución
- Soporte multi-base de datos (3 motores)
- Despliegue contenerizado con Docker — app Python y opcionalmente la base de datos

---

## Dashboard de ejecución

Generado automáticamente al finalizar cada ejecución:

- Timeline del pipeline
- Eventos detallados por tarea
- Seguimiento de errores
- Métricas por archivo
- Resumen de ejecución con `execution_id`

---

## Escenarios de despliegue

| | Escenario A | Escenario B |
|---|---|---|
| **Cuándo usarlo** | Quiero probar FlowELT sin tener una BD instalada | Ya tengo una BD en mi servidor o red |
| **Requisito** | Docker + Docker Compose | Ninguno *(GUI en desarrollo)* — hoy: Docker |
| **Interfaz** | Línea de comandos | GUI con drag & drop *(en desarrollo)* — hoy: YAML + `.env` |
| **Archivos CSV** | Dentro de `./data/input/` | Ruta absoluta en tu máquina o red |
| **Qué levanta** | App Python + base de datos en Docker | Solo el ejecutable nativo |

---

## Quickstart — Escenario A (Demo completo)

> Levanta FlowELT y una base de datos sin instalar nada adicional.

### Paso 1 — Clonar el repositorio

```bash
git clone https://github.com/daniel-dev-g/project_ELT.git
cd project_ELT
```

### Paso 2 — Crear el archivo de configuración

```bash
cp .env.example .env
```

> Los valores del `.env.example` son suficientes para que Docker cree y configure la base de datos automáticamente.
> El motor por defecto es PostgreSQL — en el Paso 5 lo puedes cambiar.

### Paso 3 — Agregar tus archivos CSV

Copia tus archivos dentro de `data/input/`:

```
data/
└── input/
    ├── clientes.csv
    └── ventas.csv
```

### Paso 4 — Configurar el pipeline

Edita `config/pipeline.yaml`. Cada bloque `task` define una carga:

```yaml
task:
  - name: "Carga de Clientes"
    file: "data/input/clientes.csv"   # relativo a la raíz del proyecto
    delimiter: ";"                     # separador del CSV
    encoding: "utf8"
    table_destination: "clientes"      # nombre de la tabla destino
    schema: "public"                   # esquema (public en Postgres, dbo en SQL Server)
    crear_tabla_si_no_existe: true
    active: true
```

### Paso 5 — Seleccionar el motor de base de datos

Edita `.env` y define `DB_ENGINE` con el motor que quieres usar:

```env
DB_ENGINE=postgres     # o sqlserver, o mariadb
```

> `config/settings.yaml` contiene los tres motores preconfigurados. No necesitas editarlo.

### Paso 6 — Ejecutar

```bash
# PostgreSQL
docker compose --profile postgres up

# SQL Server
docker compose --profile sqlserver up

# MariaDB
docker compose --profile mysql up
```

Docker construye la imagen, levanta la BD, espera que esté lista y ejecuta la carga.
Al terminar verás en `logs/` el dashboard HTML y el log estructurado de la ejecución.

---

## Quickstart — Escenario B (BD externa)

> Usa FlowELT con una base de datos que ya tienes instalada.

### Paso 1 — Clonar el repositorio

```bash
git clone https://github.com/daniel-dev-g/project_ELT.git
cd project_ELT
```

### Paso 2 — Crear el archivo de configuración

```bash
cp .env.example .env
```

### Paso 3 — Configurar la conexión a tu BD

Edita `.env` con el motor que usas y las credenciales de tu base de datos.

**MariaDB:**
```env
DB_ENGINE=mariadb
MARIADB_HOST=127.0.0.1
MARIADB_PORT=3306
MARIADB_USER=mi_usuario
MARIADB_PASSWORD=mi_password
MARIADB_DB=mi_base
```

**PostgreSQL:**
```env
DB_ENGINE=postgres
POSTGRES_HOST=127.0.0.1
POSTGRES_PORT=5432
POSTGRES_USER=mi_usuario
POSTGRES_PASSWORD=mi_password
POSTGRES_DB=mi_base
```

**SQL Server:**
```env
DB_ENGINE=sqlserver
SQLSERVER_HOST=127.0.0.1
SQLSERVER_PORT=1433
SQLSERVER_USER=mi_usuario
SQLSERVER_PASSWORD=mi_password
SQLSERVER_DB=mi_base
```

> El contenedor usa `network_mode: host`, por lo que `127.0.0.1` apunta directamente
> a tu máquina — no necesitas configurar IPs externas ni reglas de firewall.

### Paso 4 — Permisos de carga directa en tu BD

Cada motor requiere una configuración mínima para leer archivos directamente desde disco.

**MariaDB** — `LOAD DATA INFILE` requiere:

4a — Eliminar restricción de ruta en `/etc/mysql/mariadb.conf.d/50-server.cnf`:

```ini
[mysqld]
secure_file_priv = ""
```

```bash
sudo systemctl restart mariadb
```

4b — Dar privilegio FILE al usuario:

```bash
sudo mariadb -e "GRANT FILE ON *.* TO 'tu_usuario'@'%'; FLUSH PRIVILEGES;"
```

**PostgreSQL** — `COPY FROM` requiere que el usuario sea superusuario o tenga el rol `pg_read_server_files`:

```sql
GRANT pg_read_server_files TO mi_usuario;
```

**SQL Server** — `BULK INSERT` requiere el permiso `ADMINISTER BULK OPERATIONS` o el rol `bulkadmin`:

```sql
EXEC sp_addrolemember 'bulkadmin', 'mi_usuario';
```

### Paso 5 — Configurar el pipeline

Los archivos pueden estar en cualquier lugar de tu máquina — no necesitas moverlos.
Usa la ruta absoluta directamente en cada tarea:

```yaml
task:
  - name: "Carga de Clientes"
    file: "/home/usuario/datos/clientes.csv"      # ruta absoluta en tu máquina
    delimiter: ";"
    encoding: "utf8"
    table_destination: "clientes"
    schema: "public"      # public → PostgreSQL | dbo → SQL Server | "" → MariaDB
    crear_tabla_si_no_existe: true
    active: true

  - name: "Carga ventas red"
    file: "/mnt/servidor/ventas/ventas_2024.csv"  # ruta de red también funciona
    delimiter: ";"
    encoding: "utf8"
    table_destination: "ventas"
    schema: "public"
    crear_tabla_si_no_existe: true
    active: true
```

> La base de datos lee los archivos directamente desde disco usando la ruta que le indicas.
> No necesitas mover los archivos ni configurar rutas adicionales en `.env`.

### Paso 6 — Ejecutar

```bash
docker compose --profile standalone up
```

Solo se levanta el contenedor Python. Tu BD no se toca ni se reinicia.

---

## Outputs

| Archivo         | Descripción                            |
|-----------------|----------------------------------------|
| `log_*.json`    | Log estructurado de ejecución          |
| `log_*.html`    | Dashboard HTML interactivo             |
| `technical.log` | Log técnico interno                    |

Todos los outputs comparten el mismo `execution_id` para trazabilidad completa.

---

## Flujo del proceso

```
1. Lectura de configuración YAML
2. Validación de conexión y permisos BULK
3. Creación de tabla (si no existe)
4. Análisis de archivos con Polars
5. Carga masiva nativa
6. Generación de logs estructurados y dashboard HTML
```

---

## Tecnologías

| Componente    | Tecnología       |
|---------------|------------------|
| Lenguaje      | Python 3.14      |
| Análisis      | Polars           |
| Configuración | YAML             |
| Logging       | JSON estructurado|
| Visualización | HTML Dashboard   |
| Contenedores  | Docker + Compose |
| Gestión deps  | uv               |

---

## Decisiones de diseño

| Decisión | Razón |
|---|---|
| Carga masiva nativa en lugar de ORM | Rendimiento — la BD lee directo del disco sin pasar datos por Python (`BULK INSERT`, `COPY FROM`, `LOAD DATA INFILE`) |
| Configuración YAML | Simplicidad y reproducibilidad sin tocar código |
| `execution_id` por ejecución | Trazabilidad completa entre logs, dashboard y técnico |
| Docker para app y opcionalmente para la BD | La app Python siempre corre en Docker. La BD puede ser contenerizada (Escenario A — demo) o existente en el servidor del usuario (Escenario B — producción) |
| `DB_ENGINE` en `.env` | Selecciona el motor sin tocar `settings.yaml` — los tres motores están siempre configurados |
| `bulk_path_map` en configuración | Desacopla la ruta de Python de la ruta de la BD — funciona igual en desarrollo (Docker), servidor único o red de empresa |
| Rutas absolutas por tarea en `pipeline.yaml` | Los archivos pueden estar dispersos en disco o red — cada tarea apunta directamente a su ruta real |
| Polars en lugar de pandas | Velocidad y bajo consumo de memoria en análisis de metadatos |

---

## Estado de pruebas por motor

| Motor | Estado | Escenario probado | Método | Lee directo del disco |
|---|---|---|---|---|
| SQL Server | Probado | A (Docker) | `BULK INSERT` | Sí |
| PostgreSQL | Probado | A (Docker) | `COPY FROM` | Sí |
| MariaDB | Probado | A (Docker) + B (local) | `LOAD DATA INFILE` | Sí |

---

## Interfaz gráfica (en desarrollo)

La configuración actual de Escenario B — archivos YAML, variables de entorno y Docker — está pensada para perfiles técnicos. Para usuarios sin experiencia en herramientas de desarrollo, se está construyendo una interfaz gráfica de escritorio que elimina Docker del Escenario B por completo.

**El usuario descargará un ejecutable** (`.exe` en Windows, `.app` en macOS, binario en Linux) y lo abrirá directamente — sin instalar Python, Docker ni ninguna dependencia.

**Lo que permitirá hacer:**

- Seleccionar archivos CSV con drag & drop desde cualquier carpeta del equipo o red
- Elegir el motor de base de datos desde un menú desplegable
- Ingresar las credenciales de conexión en un formulario visual
- Configurar y ejecutar el pipeline sin tocar ningún archivo de configuración
- Ver el resultado de la carga en tiempo real

El motor de carga (adaptadores por BD, carga masiva nativa) es el mismo — la interfaz es una capa visual encima que gestiona la configuración internamente.

**Stack:** [Flet](https://flet.dev) (Python + Flutter) + PyInstaller para el empaquetado.

> Esta funcionalidad está en desarrollo y aún no está disponible.

---

## Roadmap

- [ ] **Interfaz gráfica** (Flet + PyInstaller) — ejecutable nativo para Escenario B sin Docker; drag & drop, selección de motor y credenciales en formulario visual (ver sección anterior)
- [ ] Módulo de profiling (nulos, cardinalidad, tipos)
- [ ] Motor de reglas de calidad configurables en YAML
- [ ] **Linaje a nivel de fila** — escritura de logs en tabla BD + paso SQL post-carga que adjunta columnas `_execution_id`, `_source_file` y `_load_timestamp` a los datos en capa raw (ver diseño abajo)
- [ ] Integración con Airflow o Prefect (orquestación)
- [ ] Análisis asistido por IA (opcional)

### Diseño: Linaje a nivel de fila

La carga nativa (BULK INSERT / COPY / LOAD DATA) no permite inyectar columnas adicionales durante la transferencia — el archivo se lee tal cual. El diseño propuesto agrega el linaje en un paso SQL posterior, dentro de la base de datos, sin pasar datos por Python. **Esta funcionalidad aún no está implementada** — el diseño a continuación describe cómo se puede implementar.

**Flujo propuesto:**

```
PASO 1 — Carga nativa (sin cambios)
CSV ──► BULK INSERT / COPY ──► landing.clientes   ← datos puros
                             ──► bd_logs           ← execution_id, task_id, source_file, timestamp, rows

PASO 2 — SQL post-carga (dentro de la BD)
INSERT INTO raw.clientes
SELECT
    c.*,
    l.execution_id      AS _execution_id,
    l.source_file       AS _source_file,
    l.load_timestamp    AS _load_timestamp
FROM landing.clientes c
JOIN bd_logs l ON l.task_id = '<task_id_actual>'
```

**Configuración propuesta en `pipeline.yaml`:**

```yaml
task:
  - name: "Carga clientes"
    file: "data/input/clientes.csv"
    table_destination: "landing.clientes"
    log_to_db: true              # escribe execution_id en tabla bd_logs dentro de la BD
    raw_destination: "raw.clientes"  # ejecuta el paso SQL de linaje automáticamente
    active: true
```

Esto permite responder en cualquier momento:
```sql
-- ¿De qué archivo viene esta fila?
SELECT _source_file, _load_timestamp FROM raw.clientes WHERE id = 123
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