# 1. 빌드 도구가 포함된 3.10 풀 이미지를 사용합니다.
FROM python:3.10

WORKDIR /app

# 2. 필수 빌드 도구 설치
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# 3. 패키지 설치 (pandas와 numpy를 먼저 고정)
RUN pip install --no-cache-dir "numpy==1.23.5" "pandas==1.5.3"

# 4. 나머지 패키지 설치 (pandas-ta를 찾기 위해 --pre 옵션 추가)
COPY requirements.txt .
RUN pip install --no-cache-dir --pre -r requirements.txt

# 5. 소스 코드 복사
COPY . .

# 6. 실행
CMD ["python", "src/main.py"]