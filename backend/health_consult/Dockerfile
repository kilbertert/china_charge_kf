FROM python:3.13-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# 共享依赖(在 backend 根) - build context 为项目根
COPY backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# health_consult 模块自身
COPY backend/health_consult /app/health_consult

# 复用 app_dify(DifyClient 单例 + response_parser 工具)
COPY backend/app_dify /app/app_dify

# 健康合规单一事实源 (compliance_loader 从 /app/shared/compliance.yaml 读)
COPY shared/ /app/shared/

EXPOSE 8013

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD curl -f http://localhost:8013/api/health-consult/health || exit 1

CMD ["uvicorn", "health_consult.main:app", "--host", "0.0.0.0", "--port", "8013"]
