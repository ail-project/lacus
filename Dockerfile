FROM python:3.11

RUN apt-get update && apt-get -y install ffmpeg libavcodec-extra

WORKDIR /build/lacus
COPY . .
RUN pip install --upgrade pip && pip install poetry
RUN python3 -m pip config --user set global.timeout 150
RUN poetry install
RUN poetry run playwright install-deps
RUN poetry run playwright install --with-deps
RUN echo LACUS_HOME="`pwd`" >> .env
RUN poetry run update --init

CMD poetry run start_website