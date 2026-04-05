# Dockerfile — FlowELT app
# Incluye ODBC Driver 18 para SQL Server (otros motores no requieren drivers extra)
# Oracle en modo thin (no requiere Instant Client)

FROM python:3.14-slim

# ── Sistema: ODBC para SQL Server ───────────────────────────────────────────
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

# ── uv ──────────────────────────────────────────────────────────────────────
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# ── Dependencias Python ──────────────────────────────────────────────────────
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen

# ── Código fuente ────────────────────────────────────────────────────────────
COPY . .

CMD ["uv", "run", "main.py"]
