# FlowELT

> Herramienta ETL en Python para carga masiva de archivos CSV hacia múltiples motores de base de datos.
> Pipeline configurable por YAML, con log estructurado y dashboard de ejecución interactivo.
> Alternativa ligera a SSIS y Airflow para analistas que necesitan cargas masivas sin infraestructura DevOps.

---

## ⚡ Rendimiento

| Archivos | Filas   | Duración |
| -------- | ------- | -------- |
| 3        | 480.526 | 4.3s     |

> Carga realizada con BULK INSERT sobre SQL Server en entorno local.

---

## 🗄️ Bases de datos soportadas

| Motor      | Herramienta de carga         | Imagen Docker                                |
| ---------- | ---------------------------- | -------------------------------------------- |
| SQL Server | `BULK INSERT`                | `mcr.microsoft.com/mssql/server:2022-latest` |
| PostgreSQL | `COPY FROM STDIN`            | `postgres:16`                                |
| MySQL      | `LOAD DATA LOCAL INFILE`     | `mysql:8`                                    |
| IBM Db2    | `SYSPROC.ADMIN_CMD(LOAD)`    | `ibmcom/db2`                                 |
| Oracle     | `sqlldr` + `.ctl` dinámico   | `gvenzl/oracle-free`                         |

---

## 📊 Dashboard de ejecución

[**→ Ver Dashboard Interactivo ←**](https://htmlpreview.github.io/?https://github.com/daniel-dev-g/project_ELT/blob/main/logs/log_20260302_174109.html)

<p align="center">
  <img src="screenshot.png" alt="Dashboard de monitorización" width="800">
</p>

---

## 🚀 Instalación

### Requisitos previos

- [Git](https://git-scm.com/)
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (incluye Docker Compose)

No se requiere instalar Python, uv ni drivers de base de datos — todo corre dentro del contenedor.

---

### Paso 1 — Clonar el repositorio

```bash
git clone https://github.com/daniel-dev-g/project_ELT.git
cd project_ELT
```

---

### Paso 2 — Configurar credenciales Docker

Copia el archivo de ejemplo y completa las contraseñas para los contenedores:

```bash
cp .env.example .env
```

Edita `.env`:

```env
SQLSERVER_PASSWORD=TuPasswordSeguro123
POSTGRES_USER=admin
POSTGRES_PASSWORD=TuPassword
POSTGRES_DB=demo_db
# ... resto de motores
```

> `.env` nunca se sube al repositorio (está en `.gitignore`).

---

### Paso 3 — Configurar la conexión de la app

Edita `config/settings.yaml`. El archivo ya viene con la estructura completa — solo debes completar `username` y `password` del motor que usarás, y dejar los demás comentados:

```yaml
development:
  db_engine: sqlserver
  server: "localhost,1433"
  database: "demo_db"
  username: "sa"
  password: "TuPasswordSeguro123"
  ...
```

Para usar otro motor, comenta el bloque activo y descomenta el correspondiente (postgres, mysql, db2 u oracle).

---

### Paso 4 — Agregar archivos CSV

Copia tus archivos CSV a la carpeta `data/input/`:

```bash
data/
└── input/
    ├── clientes.csv
    ├── productos.csv
    └── ventas.csv
```

---

### Paso 5 — Configurar el pipeline

Edita `config/pipeline.yaml` para declarar qué archivos cargar y a qué tablas:

```yaml
task:
  - name: "Carga de Clientes"
    file: "data/input/clientes.csv"
    delimiter: ";"
    table_destination: "clientes"
    schema: "dbo"
    active: true
```

---

### Paso 6 — Levantar y ejecutar

```bash
docker compose --profile sqlserver up
```

Reemplaza `sqlserver` por el motor que configuraste: `postgres`, `mysql`, `db2` u `oracle`.

Docker levanta el motor de base de datos y la app FlowELT en secuencia. Al finalizar se generan en la carpeta `logs/`:

- `log_TIMESTAMP.json` — log estructurado de la ejecución
- `log_TIMESTAMP.html` — dashboard HTML interactivo
- `technical.log` — log técnico interno

---

## 📁 Estructura del proyecto

```
project_ELT/
├── config/
│   ├── settings.yaml          # Conexión y motor activo (editar username/password)
│   └── pipeline.yaml          # Tareas de carga (qué archivos, a qué tablas)
├── data/
│   └── input/                 # Archivos CSV/TXT de entrada (agregar aquí)
├── logs/                      # Logs JSON y dashboard HTML (generados en ejecución)
├── src/
│   ├── state_manager/
│   │   └── core/
│   │       └── adapter_db/    # Adapters por motor (sqlserver, postgres, mysql, db2, oracle)
│   ├── csv_analisys.py        # Análisis de archivos con Polars
│   ├── log_csv.py             # Registro de auditoría JSON
│   ├── table_creator.py       # Creación automática de tablas
│   └── validators/            # Validaciones de conexión y archivos
├── Dockerfile                 # Imagen Python con dependencias y ODBC Driver
├── docker-compose.yml         # Orquestación de motores con profiles
├── main.py                    # Punto de entrada
└── pyproject.toml             # Dependencias Python
```

---

## 📊 Outputs

| Archivo                   | Descripción                                          |
| ------------------------- | ---------------------------------------------------- |
| `logs/log_*.json`         | Log de auditoría por ejecución con `execution_id`    |
| `logs/log_*.html`         | Dashboard HTML interactivo                           |
| `logs/technical.log`      | Log técnico interno (DEBUG/INFO/WARNING/ERROR)       |
| `src/metadata.csv`        | Métricas por archivo (filas, encoding, tamaño)       |
| `src/metadata_detail.csv` | Inventario de columnas por archivo                   |

Todos los outputs comparten `execution_id` para trazabilidad completa entre ejecuciones.

---

## 🧠 Flujo del proceso

```
CSV/TXT → Validación → Análisis (Polars) → Bulk Load (motor nativo)
                                                       ↓
                                           JSON Log → Dashboard HTML
```

1. Lectura de `pipeline.yaml` y `settings.yaml`
2. Validación de conexión al motor de base de datos
3. Creación automática de tabla destino si no existe
4. Análisis de archivos con Polars (encoding, columnas, filas)
5. Carga masiva con la herramienta nativa del motor
6. Generación de log JSON y dashboard HTML

---

## 🛠️ Tecnologías

| Componente    | Tecnología                              |
| ------------- | --------------------------------------- |
| Lenguaje      | Python 3.14                             |
| Carga masiva  | Herramienta nativa por motor            |
| Análisis      | Polars                                  |
| Configuración | YAML                                    |
| Auditoría     | JSON + Dashboard HTML                   |
| Contenedores  | Docker + Docker Compose (profiles)      |
| Gestión deps  | uv                                      |

---

## 🧭 Roadmap

- [x] Soporte SQL Server via `BULK INSERT`
- [x] Soporte PostgreSQL via `COPY FROM STDIN`
- [x] Soporte IBM Db2 via `SYSPROC.ADMIN_CMD(LOAD)`
- [x] Soporte MySQL via `LOAD DATA LOCAL INFILE`
- [x] Soporte Oracle via `sqlldr` + `.ctl`
- [x] Contenerización con Docker (docker-compose con profiles por motor)

---

## 👨‍💻 Autor

**Daniel Guevara**
Data Engineer | GCP | SQL | Python | Santiago, Chile

- LinkedIn: [linkedin.com/in/daniel-guevara](https://www.linkedin.com/in/daniel-guevara-2a64a479/)
- GitHub: [github.com/daniel-dev-g](https://github.com/daniel-dev-g)
