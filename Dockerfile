FROM python:3.7-alpine

VOLUME [ "/shared" ]
WORKDIR /data

# Install dependencies
# gcc libc-dev linux-headers are libs and tools for uwsgi building
# clear not required data at the end to reduce image size
RUN set -e; \
    apk add --virtual .build-deps \
    gcc \
    libc-dev \
    linux-headers \
; \
apk del .build-deps;

RUN apk add tzdata;
