FROM python:3.11-slim

WORKDIR /app

COPY smu_mcp.py .

CMD ["python3", "smu_mcp.py"]
