FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir \
    "fastapi>=0.115" \
    "uvicorn[standard]>=0.34" \
    "pydantic>=2.10" \
    "pydantic-settings>=2.7" \
    "prometheus-client>=0.21"
COPY aps/ ./aps/
RUN useradd -r -s /bin/false aps && chown -R aps:aps /app
USER aps
EXPOSE 9090
CMD ["uvicorn", "aps.main:app", "--host", "0.0.0.0", "--port", "9090", "--workers", "1", "--limit-concurrency", "50", "--timeout-keep-alive", "5"]
