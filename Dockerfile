# 1. vectorbt와 pandas-ta의 호환성이 가장 좋은 3.10 버전을 사용합니다.
FROM python:3.10-slim

WORKDIR /app

# 2. 빌드에 필요한 시스템 도구 설치
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    git \
    && rm -rf /var/lib/apt/lists/*

# 3. pip 업그레이드
RUN pip install --no-cache-dir --upgrade pip

# 4. 의존성 충돌의 핵심인 pandas와 numpy를 먼저 설치 (vectorbt 호환 버전)
RUN pip install --no-cache-dir "pandas<2.0.0" "numpy<1.24"

# 5. 패키지 목록 복사 및 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 6. 소스 코드 복사
COPY . .

# 7. 실행 명령어
CMD ["python", "src/main.py"]