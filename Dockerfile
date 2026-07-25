FROM python:3.12-slim

WORKDIR /app
RUN mkdir -p /app/uploads

# Node.js + pre-installed Wikipedia MCP (avoids npx cold-start failures in containers)
RUN apt-get update && apt-get install -y --no-install-recommends nodejs npm && \
    npm install -g wiki-mcp@latest && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir torch==2.2.2 --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir -r requirements.txt


COPY app/ ./app/
COPY alembic/ ./alembic/
COPY alembic.ini .

COPY tests/ ./tests/
COPY pytest.ini .





CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
