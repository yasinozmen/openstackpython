# ============================================================================
# Build Stage
# ============================================================================
FROM python:3.11-slim AS builder

WORKDIR /app

# Sistem bağımlılıkları (build için gerekli, network retry ile)
RUN apt-get clean && \
    rm -rf /var/lib/apt/lists/* && \
    apt-get update --fix-missing || true && \
    apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    libssl-dev \
    2>/dev/null || echo "Package installation skipped"

# Python bağımlılıklarını user dizinine yükle
COPY requirements.txt .
RUN pip install --user --no-cache-dir --upgrade pip && \
    pip install --user --no-cache-dir -r requirements.txt

# ============================================================================
# Runtime Stage
# ============================================================================
FROM python:3.11-slim

# Metadata
LABEL maintainer="openstackyasin"
LABEL description="OpenStack Management API - Multi-stage Production Build"
LABEL version="1.0.0"

WORKDIR /app

# Build stage'den sadece Python paketlerini kopyala
COPY --from=builder /root/.local /root/.local

# Uygulama kodunu kopyala
COPY app ./app
COPY utils ./utils
COPY data ./data

# .env dosyasını kopyala (varsa)
COPY .env* ./

# .local/bin'i PATH'e ekle
ENV PATH=/root/.local/bin:$PATH

# Gerekli dizinleri oluştur
RUN mkdir -p data utils logs && \
    chmod -R 755 /app

# Port aç
EXPOSE 8001

# Health check ekle
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8001/health').read()" || exit 1

# Uvicorn ile başlat
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001", "--workers", "1"]