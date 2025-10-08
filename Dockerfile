FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY smu_mcp.py .

CMD ["python3", "smu_mcp.py"]
