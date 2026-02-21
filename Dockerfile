# 1. 모든 빌드 도구가 포함된 안정적인 3.10 풀 이미지를 사용합니다.
FROM python:3.10

WORKDIR /app

# 2. 패키지 설치 전 시스템 업데이트
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# 3. 의존성 충돌 방지를 위해 pandas와 numpy를 먼저 설치합니다.
RUN pip install --no-cache-dir "numpy==1.23.5" "pandas==1.5.3"

# 4. 나머지 패키지 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 5. 소스 코드 복사
COPY . .

# 6. 실행
CMD ["python", "src/main.py"]