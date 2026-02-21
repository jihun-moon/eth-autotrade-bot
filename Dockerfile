# 1. 빌드 도구가 모두 포함된 3.10 이미지를 사용합니다.
FROM python:3.10

WORKDIR /app

# 파이썬 출력이 버퍼링 없이 즉시 터미널에 찍히도록 설정합니다.
ENV PYTHONUNBUFFERED=1

# 2. 시스템 업데이트 및 필수 도구 설치
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# 3. 핵심 라이브러리(numpy, pandas)를 먼저 설치해서 환경을 고정합니다.
RUN pip install --no-cache-dir "numpy==1.23.5" "pandas==1.5.3"

# 4. 나머지 패키지 설치 (위에서 설정한 zip 링크를 통해 pandas-ta 강제 설치)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 5. 소스 코드 복사
COPY . .

# 6. 실행 명령어
CMD ["python", "src/main.py"]