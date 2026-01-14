# Multi-stage build to keep the final image small
# First stage: install dependencies

FROM python:3.11-slim AS builder

WORKDIR /app
COPY requirements.txt .

# install to user dir so we can copy it to the final image
RUN pip install --no-cache-dir --user -r requirements.txt


# Second stage: just the runtime stuff we need
FROM python:3.11-slim

WORKDIR /app

# grab the installed packages from the builder stage
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

# copy our actual code
COPY app/ ./app/

EXPOSE 8080

# basic health check - kubernetes/docker can use this
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/healthz')" || exit 1

# fire it up
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
