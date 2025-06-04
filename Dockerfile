FROM ubuntu:24.04

# Build dependencies
RUN apt-get update && apt-get -y install build-essential curl git python3 tmux

RUN mkdir -p /app

WORKDIR /app

# Install Valkey
RUN git clone https://github.com/valkey-io/valkey.git

WORKDIR /app/valkey

RUN git checkout 8.0 && make

WORKDIR /app

# Install lacus
RUN git clone https://github.com/ail-project/lacus.git

RUN curl -sSL https://install.python-poetry.org | python3 -
ENV PATH="/root/.local/bin:${PATH}"

WORKDIR /app/lacus

RUN poetry install && poetry run playwright install-deps

RUN echo LACUS_HOME="`pwd`" >> .env

RUN poetry run update --init

RUN apt-get install -y supervisor

COPY ./supervisord/supervisord.conf /supervisord/supervisord.conf

COPY ./entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]