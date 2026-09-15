# ClickHouse's official MCP server from PyPI, instrumented so its queries appear in ClickStack
# (the pattern from ClickHouse/examples clickstack/librechat-llm-observability).
FROM python:3.13.9-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY --from=ghcr.io/astral-sh/uv:0.9.3 /uv /usr/local/bin/uv
RUN uv pip install --system --no-cache mcp-clickhouse==0.6.0 opentelemetry-distro==0.65b0 \
    opentelemetry-exporter-otlp==1.44.0 opentelemetry-instrumentation-urllib3==0.65b0 \
    opentelemetry-instrumentation-starlette==0.65b0
EXPOSE 8000
CMD ["opentelemetry-instrument", "python", "-m", "mcp_clickhouse.main"]
