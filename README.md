# DataBridge — ELT con Python y SQL Server

## 🚀 Descripción
DataBridge es una herramienta ELT (Extract, Load, Transform) desarrollada en Python que automatiza la carga y procesamiento de archivos CSV/TXT hacia una base de datos SQL Server.

El pipeline es configurable mediante archivos YAML, permite cargas eficientes usando utilidades nativas y genera logs estructurados junto a un dashboard de ejecución.

Este proyecto demuestra un flujo de ingeniería de datos reproducible y orientado a automatización.

---

## 📌 Problema que resuelve
Las cargas manuales de datos desde archivos planos suelen ser lentas, poco auditables y difíciles de mantener.

Este proyecto permite:
- Automatizar cargas masivas de datos
- Definir pipelines reutilizables mediante configuración
- Registrar ejecución y errores de forma estructurada
- Separar lógica de negocio y configuración
- Facilitar monitoreo y trazabilidad de procesos

---

## 🛠️ Tecnologías utilizadas
- Python 3
- SQL Server
- YAML para configuración
- BCP Utility para carga eficiente de datos
- Polars para análisis de archivos
- Logs en formato JSON
- Dashboard HTML de ejecución

---

## 🧠 Flujo del proceso ELT

Archivo CSV/TXT
↓
Validación de estructura
↓
Análisis de datos con Polars
↓
Carga masiva a SQL Server (BCP)
↓
Registro de ejecución en logs JSON
↓
Generación de dashboard HTML


---

## 📦 Requisitos
Antes de ejecutar el proyecto debes tener instalado:

- Python 3.11 o superior
- SQL Server (local o remoto)
- BCP Utility disponible en el sistema
- Acceso a una base de datos de pruebas

---

## ⚙️ Instalación

### 1. Clonar repositorio
```bash
git clone https://github.com/daniel-dev-g/project_ELT.git
cd project_ELT


2. Crear entorno virtual
python -m venv venv

Activar entorno:
Windows
venv\Scripts\activate

Linux / Mac
source venv/bin/activate

3. Instalar dependencias
pip install -r requirements.txt
```

## 🔧 Configuración
Editar archivos de configuración según tu entorno:
config/settings.yaml
config/pipeline.yaml

Ejemplo de configuración de conexión:
database:
  server: localhost
  name: demo_db
  user: user
  password: password

## ▶️ Ejecución del pipeline
python main.py

Al finalizar se generarán:
- Logs de ejecución en formato JSON
- Reporte HTML con resumen del proceso

---

📁 Estructura del proyecto
Reporte HTML con resumen del proceso
```
project_ELT/
├── config/ # Configuración YAML
│ ├── settings.yaml
│ └── pipeline.yaml
├── data/
│ └── input/ # Archivos de entrada
├── logs/ # Logs y dashboard HTML
├── src/ # Código fuente
├── main.py # Punto de entrada
└── requirements.txt
```

🎯 Características principales

Arquitectura configurable

Separación de configuración y lógica

Carga eficiente de datos a SQL Server

Registro estructurado de ejecución

Pipeline reproducible

Preparado para extensión a otros motores de base de datos

🧭 Posibles mejoras futuras

Soporte para PostgreSQL y BigQuery

Métricas de rendimiento por etapa

Ejecución programada

Integración con almacenamiento en la nube

Contenerización con Docker

👨‍💻 Autor

Daniel XXXX
Data Engineer | Backend Cloud Developer
Santiago, Chile

LinkedIn: www.linkedin.com/in/daniel-xxxx