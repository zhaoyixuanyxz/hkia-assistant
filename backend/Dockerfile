ARG PYTHON_IMAGE=python:3.11-slim
ARG PIP_INDEX_URL=https://pypi.org/simple

FROM ${PYTHON_IMAGE}

ARG PIP_INDEX_URL

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml /app/pyproject.toml
COPY README.md /app/README.md
COPY alembic.ini /app/alembic.ini
COPY app /app/app
COPY alembic /app/alembic
COPY scripts /app/scripts

RUN pip install --no-cache-dir --upgrade pip -i "${PIP_INDEX_URL}" && \
    pip install --no-cache-dir . -i "${PIP_INDEX_URL}"

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
