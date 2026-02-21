# 1. 호환성이 가장 좋은 Python 3.10 버전을 사용합니다.
FROM python:3.10-slim

# 작업 디렉토리 설정
WORKDIR /app

# 2. 필수 빌드 도구 설치 (vectorbt 및 pandas 설치 시 컴파일러가 필요할 수 있음)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    python3-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# 3. 패키지 목록 복사 및 설치
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 4. 소스 코드 복사
COPY . .

# 5. 실행 명령어
CMD ["python", "src/main.py"]