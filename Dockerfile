FROM python:3.11-slim

WORKDIR /app

# 의존성 설치
RUN pip install --no-cache-dir flask flask-cors pymysql

# 애플리케이션 코드 복사
COPY smu_mcp.py .

# 포트 노출
EXPOSE 8000

# 서버 실행
CMD ["python", "smu_mcp.py"]

