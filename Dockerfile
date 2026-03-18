<<<<<<< HEAD
# ── Stage 1: Build dependencies ───────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt


# ── Stage 2: Runtime ──────────────────────────────────────────────────────────
FROM python:3.11-slim

WORKDIR /app

# Install only runtime dependencies (Playwright Chromium needs these)
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Playwright/Chromium runtime deps
    libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 \
    libcups2 libdrm2 libxkbcommon0 libxcomposite1 \
    libxdamage1 libxrandr2 libgbm1 libpango-1.0-0 \
    libcairo2 libasound2 libxshmfence1 \
    # Fonts
    fonts-liberation fonts-noto-cjk \
    # Utilities
    curl && \
    rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Install Playwright Chromium only (skip Firefox/WebKit to save space)
RUN playwright install chromium && \
    playwright install-deps chromium 2>/dev/null || true

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p data reports

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Expose ports: 8000 (API) and 8501 (Streamlit)
EXPOSE 8000 8501

# Start script
COPY start.sh /start.sh
RUN chmod +x /start.sh

CMD ["/start.sh"]
=======
# ── Stage 1: Build dependencies ───────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /app

# Install uv
RUN pip install uv

# Copy pyproject.toml and lock file first for better caching
COPY pyproject.toml uv.lock* ./

# Install dependencies using uv (sync mode)
RUN uv sync --frozen --no-dev


# ── Stage 2: Runtime ──────────────────────────────────────────────────────────
FROM python:3.11-slim

WORKDIR /app

# Install only runtime dependencies (Playwright Chromium needs these)
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Playwright/Chromium runtime deps
    libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 \
    libcups2 libdrm2 libxkbcommon0 libxcomposite1 \
    libxdamage1 libxrandr2 libgbm1 libpango-1.0-0 \
    libcairo2 libasound2 libxshmfence1 \
    # Fonts
    fonts-liberation fonts-noto-cjk \
    # Utilities
    curl && \
    rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /root/.local /root/.local
COPY --from=builder /app /app

# Add uv to PATH
ENV PATH="/root/.local/bin:$PATH"

# Install Playwright Chromium only (skip Firefox/WebKit to save space)
RUN playwright install chromium && \
    playwright install-deps chromium 2>/dev/null || true

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p data reports

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Expose ports: 8000 (API) and 8501 (Streamlit)
EXPOSE 8000 8501

# Start script
COPY start.sh /start.sh
RUN chmod +x /start.sh

CMD ["/start.sh"]
>>>>>>> c8b6483 (updated the report and fixed bugs)
