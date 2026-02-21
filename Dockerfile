# 1. vectorbt 및 pandas-ta와 가장 호환성이 좋은 3.9 버전을 사용합니다.
FROM python:3.9-slim

# 작업 디렉토리 설정
WORKDIR /app

# 2. 필수 빌드 도구 및 git 설치
# 일부 패키지 컴파일 및 설치를 위해 필요합니다.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    python3-dev \
    gcc \
    git \
    && rm -rf /var/lib/apt/lists/*

# 3. 의존성 충돌 방지를 위해 핵심 라이브러리 선설치
# vectorbt가 요구하는 특정 버전을 먼저 고정합니다.
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir "numpy<1.21" "pandas<1.4"

# 4. 나머지 패키지 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 5. 전체 소스 코드 복사
COPY . .

# 6. 실행 명령어
CMD ["python", "src/main.py"]