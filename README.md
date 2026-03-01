# DataBridge

> Herramienta de carga masiva de archivos CSV/TXT a SQL Server usando BCP.
> Alternativa simple a Airflow para analistas sin infraestructura DevOps.

## ⚡ Performance
| Files | Rows      | Duration |
|-------|-----------|----------|
| 3     | 480,526   | 2.85s    |

## Features
- YAML-configured pipeline
- BCP bulk load (faster than SQLAlchemy/pandas)
- File metadata analysis with Polars
- Structured JSON audit log
- Interactive HTML dashboard

## Requirements
- Python 3.11+
- SQL Server (Windows Auth)
- BCP utility installed

## Quick Start
```bash
pip install -r requirements.txt
# Edit config/settings.yaml and config/pipeline.yaml
python main.py
```

## Configuration
### settings.yaml
```yaml
development:
  server: "SERVER_NAME"
  database: "DB_NAME"
  log_level: "WARNING"
```

### pipeline.yaml
```yaml
task:
  - name: "Sales Load"
    file: "data/input/sales.csv"
    delimiter: ";"
    table_destination: "sales"
    schema: "dbo"
    active: true
```

## Project Structure
```
DataBridge/
├── config/          # YAML configuration
├── data/input/      # Source files
├── logs/            # JSON audit logs + HTML dashboard
├── src/             # Core modules
│   ├── bulk_loader.py
│   ├── csv_analisys.py
│   ├── validators/
│   └── state_manager/
└── main.py
```

## Architecture
```
CSV/TXT → Polars Analysis → BCP Load → SQL Server
                ↓
         JSON Audit Log → HTML Dashboard
```

## Outputs
| File                  | Description                          |
|-----------------------|--------------------------------------|
| logs/log_*.json       | JSON audit log per execution         |
| logs/log_*.html       | Interactive HTML dashboard           |
| src/metadata.csv      | File-level metrics per execution     |
| src/metadata_detail.csv | Column inventory per execution     |


## Roadmap
- [ ] Post-load stored procedure execution
- [ ] Duration per file in dashboard
- [ ] PostgreSQL support via COPY FROM