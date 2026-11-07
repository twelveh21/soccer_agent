# 生产镜像只安装运行依赖；密钥始终由 docker compose 的环境文件注入。
FROM python:3.13-slim
WORKDIR /app
COPY agent_base/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
# 以非 root 用户运行 Web 与 Worker，降低上传文件或第三方依赖被利用后的容器权限。
RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser \
    && mkdir -p /app/data && chown -R appuser:appgroup /app
COPY --chown=appuser:appgroup . /app
ENV PYTHONPATH=/app
EXPOSE 8000
USER appuser
CMD ["uvicorn", "service.app:app", "--host", "0.0.0.0", "--port", "8000"]
