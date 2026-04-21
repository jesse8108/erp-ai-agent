# docker/Dockerfile - ERP AI Agent 应用镜像
#
# 基础镜像选择:
# - python:3.12-slim-bookworm: 稳定、小、ARM64 原生支持
# - 不用 alpine: psycopg[binary] 在 musl libc 上编译更慢
#
# 构建策略: 多阶段构建，减小最终镜像体积（dev 可忽略，prod 很重要）

FROM python:3.12-slim-bookworm AS builder

# 安装系统依赖（编译 psycopg 等需要）
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# 先拷贝 requirements.txt 再装包，利用 Docker 层缓存
COPY requirements.txt .

# 装到独立的 venv 便于多阶段构建
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ============== 运行阶段 ==============
FROM python:3.12-slim-bookworm AS runtime

# 只装运行时需要的（不含 gcc）
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 从 builder 复制 venv
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/code

WORKDIR /code

# 非 root 用户运行（安全最佳实践）
RUN groupadd -r app && useradd -r -g app app && \
    chown -R app:app /code

USER app

# 拷贝应用代码（docker-compose 中通过 volume 挂载会覆盖，但生产用得上）
COPY --chown=app:app ./app ./app
COPY --chown=app:app ./alembic ./alembic
COPY --chown=app:app ./alembic.ini ./alembic.ini

# 健康检查端点
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
