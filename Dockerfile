# Smithery build container for MCP server
FROM python:3.11-slim

WORKDIR /app

COPY smu_mcp.py .
COPY requirements.txt .

RUN apt-get update && apt-get install -y --no-install-recommends build-essential \
    && pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt \
    && apt-get remove -y build-essential \
    && apt-get autoremove -y && rm -rf /var/lib/apt/lists/*

CMD ["python3", "smu_mcp.py"]
