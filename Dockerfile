FROM python:3.11-slim

WORKDIR /app
COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir .
COPY config ./config

ENV PRECIOS_CONFIG_DIR=/app/config/tenants
EXPOSE 8000
CMD ["uvicorn", "precios.main:app", "--host", "0.0.0.0", "--port", "8000"]
