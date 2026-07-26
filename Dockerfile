FROM python:3.12-slim

# Keep Python lean and unbuffered for clean container logs.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install deps first for better layer caching.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# SQLite lives on a mounted volume so briefs survive restarts/redeploys.
ENV DATABASE_URL=sqlite:////data/cadence.db
VOLUME ["/data"]

# Hosts inject $PORT; default to 8000 locally.
ENV PORT=8000
EXPOSE 8000

CMD ["python", "run.py"]
