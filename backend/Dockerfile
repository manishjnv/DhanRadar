FROM python:3.12-slim

# Create non-root user
RUN groupadd --gid 1001 appgroup && \
    useradd --uid 1001 --gid appgroup --shell /bin/bash --create-home appuser

WORKDIR /app

# Install dependencies as root (into system site-packages) before switching user
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source + migration tooling.
# alembic.ini + alembic/ are required for `alembic upgrade head` to work
# inside the container (script_location=alembic is resolved from /app).
COPY dhanradar/ ./dhanradar/
COPY alembic/ ./alembic/
COPY alembic.ini ./

# Pre-create the CAS scratch dir owned by the runtime user. A shared named
# volume is mounted here in compose (API writes, celery-batch reads/purges);
# Docker seeds an empty named volume from the image dir's ownership, so this
# makes the volume writable by appuser instead of root-owned (EACCES).
RUN mkdir -p /tmp/dhanradar_cas && chown appuser:appgroup /tmp/dhanradar_cas

# Playwright: install Chromium + system deps for ADR-0033(a) SEBI SPA scraping.
# Must run as root before USER switch (apt installs require root).
# ENV (not ARG) so PLAYWRIGHT_BROWSERS_PATH persists into the runtime layer;
# without it, root installs to /root/.cache and appuser looks in ~/.cache → ENOENT.
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
RUN playwright install --with-deps chromium

# Switch to non-root user
USER appuser

EXPOSE 8000

CMD ["uvicorn", "dhanradar.main:app", "--host", "0.0.0.0", "--port", "8000"]
