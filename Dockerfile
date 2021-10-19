FROM python:3.7-alpine

ENV SYNC_VERSION=

VOLUME [ "/shared" ]
WORKDIR /data

# Install dependencies
RUN apk add libc-dev gcc linux-headers build-base tzdata python3-dev libffi-dev musl-dev make

RUN pip install gevent
COPY syncer syncer
COPY scripts scripts

RUN pip install -r syncer/requirements.txt

CMD [ "/bin/sh", "scripts/start.sh" ]