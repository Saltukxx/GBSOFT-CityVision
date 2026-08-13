FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt pyproject.toml README.md ./
COPY src ./src
COPY configs ./configs
COPY scripts ./scripts

RUN pip install --no-cache-dir -r requirements.txt && pip install --no-cache-dir -e .

ENV PYTHONPATH=/app/src
ENTRYPOINT ["python", "scripts/run_pipeline.py"]
