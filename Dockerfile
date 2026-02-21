FROM python:3.11-slim

WORKDIR /app

# 필요한 패키지 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 소스 코드 복사
COPY . .

# 메인 스크립트 실행 (src/main.py가 실행점일 경우)
CMD ["python", "src/main.py"]