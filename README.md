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

| Archivos | Volumen total | Filas      | Duración   | Motor      | Método | Disco |
|----------|---------------|------------|------------|------------|--------|-------|
| 3        | ~2 GB         | 13.229.475 | 31.2s      | PostgreSQL | `COPY FROM` | NVMe interno |
| 3        | ~2 GB         | 13.229.475 | 40.05s     | SQL Server | `BULK INSERT` | NVMe interno |
| 3        | ~2 GB         | 13.229.475 | 76.24s     | MariaDB    | `LOAD DATA INFILE` | NVMe interno |

> Hardware: Intel Core i3-1005G1 @ 1.20GHz / 11 GB RAM / Ubuntu Linux / NVMe interno.
> Todos los motores medidos en las mismas condiciones de hardware.

### Detalle — prueba con ~2 GB / 13 millones de filas (NVMe)

| Parámetro  | PostgreSQL | SQL Server | MariaDB |
|---|---|---|---|
| OS | Ubuntu Linux | Ubuntu Linux | Ubuntu Linux |
| Hardware | i3-1005G1 / 11 GB RAM | i3-1005G1 / 11 GB RAM | i3-1005G1 / 11 GB RAM |
| Disco | NVMe interno | NVMe interno | NVMe interno |
| Contenedor | `postgres:16` | `mcr.microsoft.com/mssql/server:2022-latest` | `mariadb:11` |
| Python | Local (fuera de Docker) | Local (fuera de Docker) | Local (fuera de Docker) |
| Método | `COPY FROM` server-side | `BULK INSERT` con `TABLOCK` + `BATCHSIZE=100000` | `LOAD DATA INFILE` server-side |
| Filas | 13.229.475 | 13.229.475 | 13.229.475 |
| Duración | **31.2 seg** | 40.05 seg | 76.24 seg |
| Throughput | **~424.000 filas/seg** | ~330.000 filas/seg | ~173.000 filas/seg |

> Todos los motores leen directo desde disco vía bind mount `./data:/data` — sin pasar datos por Python.
> La diferencia entre motores refleja la eficiencia interna de cada motor para ingesta masiva.
> Las pruebas se realizaron con configuración por defecto de cada motor, sin tuning adicional. Los resultados pueden mejorar con ajustes de memoria, paralelismo o parámetros de escritura propios de cada BD.

---

## Bases de datos soportadas

| Motor      | Método de carga nativa     |
|------------|----------------------------|
| SQL Server | `BULK INSERT`              |
| PostgreSQL | `COPY FROM STDIN`          |
| MySQL      | `LOAD DATA LOCAL INFILE`   |

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

El linaje no puede inyectarse durante la carga nativa — el archivo se transfiere tal cual para preservar el rendimiento. Se agrega en un paso SQL posterior, dentro de la base de datos.

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

FlowELT soporta dos escenarios. El único requisito en ambos es **Docker + Docker Compose**.

| | Escenario A | Escenario B |
|---|---|---|
| **Cuándo usarlo** | Quiero probar FlowELT sin tener una BD instalada | Ya tengo una BD en mi servidor o red |
| **Qué levanta Docker** | App Python + base de datos | Solo app Python |
| **Archivos CSV** | Dentro de `./data/input/` | `./data/input/` o tu propio directorio |
| **Comando** | `docker compose --profile <motor> up` | `docker compose --profile standalone up` |

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

> Para el Escenario A **no necesitas editar el `.env`**. Los valores de ejemplo son suficientes
> para que Docker cree y configure la base de datos automáticamente.
> Solo edítalo si quieres usar credenciales propias.

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

Abre `config/settings.yaml` y descomenta el bloque del motor que elegiste.

**Ejemplo con PostgreSQL:**

```yaml
development:
  db_engine: postgres
  default_schema: "public"
  host: "${POSTGRES_HOST}"
  port: "${POSTGRES_PORT}"
  database: ${POSTGRES_DB}
  username: ${POSTGRES_USER}
  password: ${POSTGRES_PASSWORD}
  bulk_path_map:
    host: "${BULK_PATH_HOST}"
    container: "${BULK_PATH_CONTAINER}"
  log_level: "INFO"
```

> Solo necesitas descomentar el bloque. Los valores entre `${}` vienen del `.env`.

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

Edita `.env` con los datos de tu base de datos existente.

**Ejemplo con PostgreSQL en `192.168.1.50`:**

```env
POSTGRES_HOST=192.168.1.50
POSTGRES_PORT=5432
POSTGRES_USER=mi_usuario
POSTGRES_PASSWORD=mi_password
POSTGRES_DB=mi_base
```

### Paso 4 — Configurar las rutas de archivos

FlowELT corre dentro de un contenedor Docker, y tu BD corre fuera. Ambos deben poder ver los mismos archivos CSV — desde perspectivas distintas.

**Opción B1 — usar el directorio `./data/input/` del proyecto**

Pon tus archivos en `data/input/` y configura en `.env`:

```env
BULK_PATH_HOST=/app/data
BULK_PATH_CONTAINER=/ruta/absoluta/del/proyecto/data
```

> `BULK_PATH_HOST` es la ruta que ve el contenedor Python (siempre `/app/data`).
> `BULK_PATH_CONTAINER` es la ruta que ve tu BD — la carpeta `data/` de este proyecto
> expresada como ruta absoluta en tu máquina. Puedes obtenerla con `pwd` dentro del proyecto.

**Opción B2 — usar tu propio directorio de datos**

Si tus archivos están en otro lugar de tu máquina, define `USER_DATA_PATH`:

```env
USER_DATA_PATH=/home/usuario/mis_datos

BULK_PATH_HOST=/app/user_data
BULK_PATH_CONTAINER=/home/usuario/mis_datos
```

> `USER_DATA_PATH` monta tu directorio dentro del contenedor en `/app/user_data`.
> `BULK_PATH_CONTAINER` debe ser la misma ruta que ve tu BD (si está en la misma máquina, coincide con `USER_DATA_PATH`).

### Paso 5 — Agregar tus archivos CSV

- **Opción B1:** copia los archivos en `data/input/`
- **Opción B2:** tus archivos ya están en `USER_DATA_PATH`

### Paso 6 — Configurar el pipeline

**Opción B1** — usa el mismo path que en Escenario A:

```yaml
file: "data/input/clientes.csv"
```

**Opción B2** — usa el prefijo `user_data/`:

```yaml
file: "user_data/clientes.csv"
```

Edita el resto de campos igual que en el Escenario A (Paso 4).

### Paso 7 — Seleccionar el motor de base de datos

Igual que en el Escenario A (Paso 5): descomenta el bloque correspondiente en `config/settings.yaml`.

### Paso 8 — Ejecutar

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
| Carga masiva nativa en lugar de ORM | Rendimiento — la BD lee directo del disco sin pasar datos por Python |
| Configuración YAML | Simplicidad y reproducibilidad sin tocar código |
| `execution_id` por ejecución | Trazabilidad completa entre logs, dashboard y técnico |
| Docker para app y opcionalmente para la BD | La app Python siempre corre en Docker. La BD puede ser contenerizada (Escenario A — demo) o existente en el servidor del usuario (Escenario B — producción) |
| `bulk_path_map` en configuración | Desacopla la ruta de Python de la ruta de la BD — funciona igual en desarrollo (Docker), servidor único o red de empresa |
| Polars en lugar de pandas | Velocidad y bajo consumo de memoria en análisis de metadatos |

---

## Estado de pruebas por motor

| Motor | Estado | Método | Lee directo del disco |
|---|---|---|---|
| SQL Server | Probado | `BULK INSERT` | Sí |
| PostgreSQL | Probado | `COPY FROM` | Sí |
| MariaDB | Probado | `LOAD DATA INFILE` | Sí |

---

## Roadmap

- [ ] Módulo de profiling (nulos, cardinalidad, tipos)
- [ ] Motor de reglas de calidad configurables en YAML
- [ ] **Linaje a nivel de fila** — escritura de logs en tabla BD + paso SQL post-carga que adjunta columnas `_execution_id`, `_source_file` y `_load_timestamp` a los datos en capa raw (ver diseño abajo)
- [ ] Integración con Prefect (orquestación)
- [ ] Análisis asistido por IA (opcional)

### Diseño: Linaje a nivel de fila

La carga nativa (BULK INSERT / COPY / LOAD DATA) no permite inyectar columnas adicionales durante la transferencia — el archivo se lee tal cual. El linaje se agrega en un paso SQL posterior, dentro de la base de datos, sin pasar datos por Python.

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