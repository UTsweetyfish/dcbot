# FROM debian:unstable-slim
FROM debian:testing-slim

RUN echo 'deb-src http://deb.debian.org/debian unstable main' >> /etc/apt/sources.list && \
    apt-get update && apt-get -y dist-upgrade && \
    apt-get install -y --no-install-recommends \
    dctrl-tools \
    devscripts \
    dpkg-dev \
    git \
    python3-apt \
    python3-debian \
    python3-pip \
    python3-venv \
    python3-wheel \
    wget


ENV PYTHONDONTWRITEBYTECODE=1

WORKDIR /app
RUN python3 -m venv --system-site-packages /app/venv && \
    /app/venv/bin/pip install -U \
    aiofiles \
    cryptography \
    matrix-nio \
    PyJWT \
    requests

ENV PATH="/app/venv/bin/:$PATH"
ENV PYTHONUNBUFFERED=1

COPY . /app/

RUN mv /app/docker-entrypoint.sh /

ENTRYPOINT [ "/docker-entrypoint.sh" ]

CMD [ "python3", "bot.py" ]

# credentials.json required by bot.py for Matrix Login
# config.ini and *.pem are required by update.py for GitHub
# cache.pkl is not needed