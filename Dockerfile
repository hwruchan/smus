FROM python:3.11-slim

WORKDIR /app
COPY . .
RUN pip install -r requirements.txt

# HTTP 서버 포트 노출
EXPOSE 8000

CMD ["python", "lastdance1008.py", "--http"]
