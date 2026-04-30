# Dockerfile — FlowELT
#
# Imagen de la aplicación para los escenarios A (Docker completo) y standalone.
# Incluye ODBC Driver 18 porque SQL Server lo requiere en tiempo de ejecución;
# PostgreSQL y MariaDB no necesitan drivers de sistema adicionales.

FROM python:3.14-slim

# ── Sistema: ODBC Driver 18 para SQL Server ──────────────────────────────────
# Se instala el repositorio oficial de Microsoft y el driver en una sola capa
# para minimizar el tamaño de la imagen.
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl gnupg2 unixodbc-dev \
    && curl -fsSL https://packages.microsoft.com/keys/microsoft.asc \
        | gpg --dearmor -o /usr/share/keyrings/microsoft.gpg \
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/microsoft.gpg] \
        https://packages.microsoft.com/debian/12/prod bookworm main" \
        > /etc/apt/sources.list.d/mssql-release.list \
    && apt-get update \
    && ACCEPT_EULA=Y apt-get install -y --no-install-recommends msodbcsql18 \
    && rm -rf /var/lib/apt/lists/*

# ── uv (gestor de dependencias) ──────────────────────────────────────────────
# Se copia el binario desde la imagen oficial; no requiere instalación adicional.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# ── Dependencias Python ──────────────────────────────────────────────────────
# pyproject.toml y uv.lock se copian antes del código fuente para aprovechar
# la caché de capas: si el código cambia pero las dependencias no, esta capa
# no se reconstruye.
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen

# ── Código fuente ────────────────────────────────────────────────────────────
COPY . .

# ── Arranque ─────────────────────────────────────────────────────────────────
# chmod corre DESPUÉS de main.py para que los archivos creados durante la
# ejecución (JSON, HTML) también queden accesibles por el usuario del host.
CMD ["sh", "-c", "uv run main.py; chmod -R a+rw /app/logs /app/config 2>/dev/null"]
