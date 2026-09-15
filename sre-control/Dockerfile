# Built from the repo root so the image carries the workshop SQL the tools run.
FROM docker:28-cli AS docker-cli

FROM python:3.13.9-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 WORKSHOP_SQL=/app/workshop
# The docker CLI and compose plugin let the runner redeploy a release, exactly as an operator would.
COPY --from=docker-cli /usr/local/bin/docker /usr/local/bin/docker
COPY --from=docker-cli /usr/local/libexec/docker/cli-plugins/docker-compose /usr/local/libexec/docker/cli-plugins/docker-compose
COPY --from=ghcr.io/astral-sh/uv:0.9.3 /uv /usr/local/bin/uv

WORKDIR /app
COPY sre-control/pyproject.toml sre-control/pyproject.toml
COPY sre-control/sre_control sre-control/sre_control
RUN uv pip install --system --no-cache ./sre-control opentelemetry-instrumentation-urllib3==0.65b0 \
    opentelemetry-instrumentation-fastapi==0.65b0
COPY workshop /app/workshop

EXPOSE 8090
CMD ["opentelemetry-instrument", "python", "-m", "sre_control.main"]
