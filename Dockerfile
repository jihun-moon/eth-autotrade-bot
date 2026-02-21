# 1. pandas-ta와 vectorbt의 최신 호환성을 위해 3.11을 사용합니다.
FROM python:3.11-slim

WORKDIR /app

# 2. 빌드에 필요한 최소한의 도구 설치
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# 3. 패키지 설치 (pip 자체부터 최신화)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 4. 소스 코드 복사
COPY . .

# 5. 실행
CMD ["python", "src/main.py"]