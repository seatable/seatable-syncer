FROM python:3.7-alpine

VOLUME [ "/shared" ]
WORKDIR /data

RUN apk add python3-dev 
RUN apk add libffi-dev
RUN apk add gcc
RUN apk add musl-dev
RUN apk add make
RUN apk add libevent-dev
RUN apk add build-base

COPY sync_server.py .
COPY tables.json .
COPY email_syncer.py .
COPY settings.py .
COPY requirements.txt .
COPY start.sh .

RUN pip3 install -r requirements.txt

CMD sh start.sh
