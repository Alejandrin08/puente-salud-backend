# Servicio gateway de Puente Salud
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8000
WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
RUN useradd --create-home --uid 10001 puente
USER puente
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --retries=5 CMD python -c "import os,urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ[\"PORT\"]}/health')"
# Host vacío = todas las interfaces, IPv4 e IPv6 (healthcheck de Railway por IPv4, red privada por IPv6)
CMD ["sh", "-c", "uvicorn app.main:app --host \"${HOST:-}\" --port ${PORT}"]
