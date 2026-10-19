FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . .

# Run migrations and collectstatic as explicit release steps with deployment settings.
RUN groupadd --system sanoa && useradd --system --gid sanoa sanoa && \
    mkdir -p logs media staticfiles && chown -R sanoa:sanoa /app

USER sanoa

EXPOSE 8000

CMD ["daphne", "-b", "0.0.0.0", "-p", "8000", "sanoa.asgi:application"]
