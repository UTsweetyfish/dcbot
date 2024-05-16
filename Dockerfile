FROM debian:unstable-slim

RUN echo 'deb-src http://deb.debian.org/debian unstable main' >> /etc/apt/sources.list && \
    apt-get update && apt-get install -y --no-install-recommends \
    python3-wheel \
    python3-pip \
    python3-venv


ENV PYTHONDONTWRITEBYTECODE=1

WORKDIR /app
RUN python3 -m venv /app/venv && \
    /app/venv/bin/pip install -U matrix-nio aiofiles

ENV PATH="/app/venv/bin/:$PATH"
ENV PYTHONUNBUFFERED=1

COPY . /app/

RUN mv /app/docker-entrypoint.sh /

ENTRYPOINT [ "/docker-entrypoint.sh" ]

CMD [ "python3", "bot.py" ]

# credentials.json required by bot.py for Matrix Login
# config.ini and *.pem are required by update.py for GitHub
# cache.pkl is not needed