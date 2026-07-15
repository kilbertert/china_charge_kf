FROM python:3.13-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# 共享依赖(在 backend 根)
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# charge_consult 模块自身
COPY charge_consult /app/charge_consult

# 复用 app_dify(DifyClient 单例 + response_parser 工具)
COPY app_dify /app/app_dify

EXPOSE 8014

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD curl -f http://localhost:8014/api/charge-consult/health || exit 1

CMD ["uvicorn", "charge_consult.main:app", "--host", "0.0.0.0", "--port", "8014"]