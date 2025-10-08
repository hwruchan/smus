FROM python:3.11-slim

WORKDIR /app

# FastMCP 설치 (GitHub에서 직접 설치)
RUN pip install git+https://github.com/jlowin/fastmcp.git

COPY smu_mcp.py .

CMD ["python3", "smu_mcp.py"]
