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

| Archivos | Volumen total | Filas      | Duración   | Motor      | Método |
|----------|---------------|------------|------------|------------|--------|
| 3        | ~2 GB         | 12.787.201 | 2 min 44s  | SQL Server | `BULK INSERT` |
| 3        | ~2 GB         | 12.787.201 | 5 min 01s  | PostgreSQL | `COPY FROM STDIN` |
| 3        | ~2 GB         | 12.787.201 | 2 min 04s  | MySQL/MariaDB | `LOAD DATA LOCAL INFILE` |
| 3        | < 10 MB       | 480.526    | 4.3 seg    | SQL Server | `BULK INSERT` |

> Hardware: Intel Core i3-1005G1 / 11 GB RAM / Ubuntu Linux / SO en disco externo USB 2.0.
> La diferencia entre motores se debe al método de carga: SQL Server lee directo desde disco, PostgreSQL recibe el stream desde Python.

### Detalle — prueba con archivo de 2 GB

| Parámetro  | SQL Server | PostgreSQL |
|---|---|---|
| OS | Ubuntu Linux | Ubuntu Linux |
| Hardware | Intel Core i3-1005G1 @ 1.20GHz / 11 GB RAM | Intel Core i3-1005G1 @ 1.20GHz / 11 GB RAM |
| Contenedor | `mcr.microsoft.com/mssql/server:2022-latest` | `postgres:16` |
| Python | Local (fuera de Docker) | Local (fuera de Docker) |
| Archivos | `tripdata_2015-01.csv` (2.0 GB) + 2 archivos pequeños | ídem |
| Método | `BULK INSERT` con `TABLOCK` + `BATCHSIZE=100000` | `COPY FROM STDIN` vía psycopg2 |
| Duración | 2 min 44 seg | 5 min 01 seg |

> SQL Server no pasa los datos por Python — lee directamente desde disco vía bind mount `./data:/data`.
> PostgreSQL recibe el stream desde Python vía socket, lo que agrega overhead pero evita dependencias de ruta en el contenedor.

**Nota sobre los tiempos de PostgreSQL:** estas mediciones representan el **peor escenario posible** — SO corriendo desde disco externo USB 2.0 y PostgreSQL en Docker con overlay filesystem. En condiciones reales de producción (PostgreSQL en servidor dedicado o servicio gestionado como RDS/Cloud SQL), los tiempos serían significativamente menores y comparables a SQL Server, ya que `COPY FROM '/ruta/archivo.csv'` leería directo desde disco sin pasar por Python ni capas de virtualización.

---

## Bases de datos soportadas

| Motor      | Método de carga nativa     |
|------------|----------------------------|
| SQL Server | `BULK INSERT`              |
| PostgreSQL | `COPY FROM` (server-side)  |
| MySQL      | `LOAD DATA LOCAL INFILE`   |
| IBM Db2    | `SYSPROC.ADMIN_CMD(LOAD)`  |
| Oracle     | `sqlldr` + `.ctl` dinámico |

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

### Arquitectura con lineage (roadmap)

El lineage no puede inyectarse durante la carga nativa — el archivo se transfiere tal cual para preservar el rendimiento. Se agrega en un paso SQL posterior, dentro de la base de datos.

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
- Soporte multi-base de datos (5 motores)
- Infraestructura de bases de datos contenerizada con Docker

---

## Dashboard de ejecución

Generado automáticamente al finalizar cada ejecución:

- Timeline del pipeline
- Eventos detallados por tarea
- Seguimiento de errores
- Métricas por archivo
- Resumen de ejecución con `execution_id`

---

## Quickstart

### Prerrequisitos

- Python 3.14+
- [uv](https://docs.astral.sh/uv/)
- Docker + Docker Compose

### 1. Clonar repositorio

```bash
git clone https://github.com/daniel-dev-g/project_ELT.git
cd project_ELT
```

### 2. Instalar dependencias

```bash
uv sync
```

### 3. Configurar variables de entorno

```bash
cp .env.example .env
```

Editar `.env` con las credenciales del motor elegido.

### 4. Seleccionar motor de base de datos

Descomentar el bloque correspondiente en `config/settings.yaml`.

### 5. Agregar archivos de entrada

```
data/input/archivo.csv
```

### 6. Configurar pipeline

```yaml
# config/pipeline.yaml
task:
  - name: "Carga de Clientes"
    file: "data/input/clientes.csv"
    delimiter: ";"
    table_destination: "clientes"
    schema: "dbo"
    active: true
```

### 7. Levantar base de datos

```bash
docker compose --profile sqlserver up sqlserver -d
# o postgres, mysql, db2, oracle
```

### 8. Ejecutar

```bash
uv run main.py
```

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
| Carga masiva nativa en lugar de ORM | Rendimiento — SQL Server/Postgres leen directo del disco |
| Configuración YAML | Simplicidad y reproducibilidad sin tocar código |
| `execution_id` por ejecución | Trazabilidad completa entre logs, dashboard y técnico |
| Docker solo para bases de datos | El overhead de contenedorizar Python no aporta en desarrollo |
| Polars en lugar de pandas | Velocidad y bajo consumo de memoria en análisis |

---

## Estado de pruebas por motor

| Motor | Estado | Método |
|---|---|---|
| SQL Server | Probado | `BULK INSERT` |
| PostgreSQL | Probado | `COPY FROM STDIN` |
| MySQL / MariaDB | Probado | `LOAD DATA LOCAL INFILE` |
| IBM Db2 | Pendiente | `SYSPROC.ADMIN_CMD(LOAD)` |
| Oracle | Pendiente | `sqlldr` + `.ctl` dinámico |

---

## Roadmap

- [ ] Validar carga en MySQL
- [ ] Validar carga en IBM Db2
- [ ] Validar carga en Oracle
- [ ] Módulo de profiling (nulos, cardinalidad, tipos)
- [ ] Motor de reglas de calidad configurables en YAML
- [ ] **Lineage a nivel de fila** — escritura de logs en tabla BD + paso SQL post-carga que adjunta columnas `_execution_id`, `_source_file` y `_load_timestamp` a los datos en capa raw (ver diseño abajo)
- [ ] Integración con Prefect (orquestación)
- [ ] Análisis asistido por IA (opcional)

### Diseño: Lineage a nivel de fila

La carga nativa (BULK INSERT / COPY / LOAD DATA) no permite inyectar columnas adicionales durante la transferencia — el archivo se lee tal cual. El lineage se agrega en un paso SQL posterior, dentro de la base de datos, sin pasar datos por Python.

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
    raw_destination: "raw.clientes"  # ejecuta el paso SQL de lineage automáticamente
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