FROM python:3.10

WORKDIR /app
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir "numpy==1.23.5" "pandas==1.5.3"

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# 🌟 실행 경로를 src/core/main.py로 수정
CMD ["python", "src/core/main.py"]