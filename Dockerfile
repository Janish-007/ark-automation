FROM python:3.10-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    wget curl gnupg unzip fonts-liberation libnss3 libatk-bridge2.0-0 \
    libxss1 libasound2 libx11-xcb1 libgtk-3-0 libdrm2 libgbm1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN pip install playwright && playwright install --with-deps

COPY . .

RUN chmod +x entrypoint.sh

ENTRYPOINT ["bash", "entrypoint.sh"]
