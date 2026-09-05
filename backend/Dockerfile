FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Sistem bagimliliklari (asyncpg/psycopg derlemesi ve saglik kontrolu icin curl)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# NOT: pip install -e . oncesinde tum kaynak kopyalanmali — pyproject.toml'daki
# [tool.setuptools.packages.find] "app*" paketini diskte arar; app/ henuz yoksa
# (sadece pyproject.toml kopyalanmissa) build hata verir. Bu, Docker layer
# cache'inden (bagimlilik degismedigi surece pip adimini atlama) feragat eder
# ama basit ve dogru kalir — proje bu asamada sik degisiyor, cache kazanci
# marjinal.
COPY . .
RUN pip install --upgrade pip && pip install -e .

EXPOSE 8000

# Varsayilan komut api icindir; worker servisi compose'da command override eder.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
