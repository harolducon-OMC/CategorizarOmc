FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
RUN useradd --create-home --uid 10001 appuser
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY core ./core
COPY alembic.ini ./alembic.ini
COPY alembic ./alembic
USER appuser
EXPOSE 8000
# Producción: sin --reload (docker-compose lo activa solo en desarrollo). Respeta $PORT si la plataforma lo define.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
