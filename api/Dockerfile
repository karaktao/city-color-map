FROM python:3.11-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONPATH=/app

# 基础依赖（如不需要可删 git/curl）
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
  && rm -rf /var/lib/apt/lists/*

# 依赖
COPY requirements.docker.txt /app/requirements.docker.txt
RUN pip install --no-cache-dir -r /app/requirements.docker.txt

# 代码
COPY src /app/src
COPY config /app/config

EXPOSE 8000
CMD ["python","-m","uvicorn","src.api_main:app","--host","0.0.0.0","--port","8000"]
