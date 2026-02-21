# 1. 안정적인 3.10 풀 이미지를 사용합니다.
FROM python:3.10

WORKDIR /app

# 2. 필수 빌드 도구 및 git 설치 (GitHub 설치를 위해 필수)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    git \
    && rm -rf /var/lib/apt/lists/*

# 3. 환경 고정 (pandas, numpy 선설치)
RUN pip install --no-cache-dir "numpy==1.23.5" "pandas==1.5.3"

# 4. 나머지 패키지 강제 설치 (requirements.txt에 적힌 GitHub 주소 활용)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 5. 소스 코드 복사
COPY . .

# 6. 실행
CMD ["python", "src/main.py"]