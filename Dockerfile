FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    python3 python3-pip \
    ruby ruby-dev \
    curl \
    git \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js 20
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs

RUN npm install -g nyc

WORKDIR /app

COPY requirements.txt .
RUN pip3 install -r requirements.txt --break-system-packages

COPY pipeline/ ./pipeline/

CMD ["python3", "pipeline/main.py"]
