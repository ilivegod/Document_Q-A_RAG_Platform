FROM python:3.12-slim

WORKDIR /app
RUN mkdir -p /app/uploads

COPY requirements.txt .
RUN pip install --no-cache-dir torch==2.2.2 --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir -r requirements.txt


COPY app/ ./app/
COPY alembic/ ./alembic/
COPY alembic.ini .

COPY tests/ ./tests/
COPY pytest.ini .





CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
