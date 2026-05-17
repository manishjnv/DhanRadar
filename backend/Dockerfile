FROM python:3.12-slim

# Create non-root user
RUN groupadd --gid 1001 appgroup && \
    useradd --uid 1001 --gid appgroup --shell /bin/bash --create-home appuser

WORKDIR /app

# Install dependencies as root (into system site-packages) before switching user
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY dhanradar/ ./dhanradar/

# Switch to non-root user
USER appuser

EXPOSE 8000

CMD ["uvicorn", "dhanradar.main:app", "--host", "0.0.0.0", "--port", "8000"]
