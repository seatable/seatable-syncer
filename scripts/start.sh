#!/bin/sh

set -e

# log function
function log() {
    local time=$(date +"%F %T")
    echo "$time $1 "
}

# time zone
if [[ $TIME_ZONE != "" ]]; then
    time_zone=/usr/share/zoneinfo/$TIME_ZONE
    if [[ ! -e $time_zone ]]; then
        echo "invalid time zone"
        exit 1
    else
        ln -snf $time_zone /etc/localtime
        echo "$TIME_ZONE" > /etc/timezone
    fi
fi

# log dir
if [ ! -d "/shared/logs" ]; then
    mkdir -p /shared/logs
fi

export LOG_DIR='/shared/logs'


cd /data/frontend
npm install --no-audit
npm run build

cd /data/syncer
python main.py >> /shared/logs/gevent.log 2>&1 &


wait

sleep 1

#
log "This is a idle script (infinite loop) to keep container running."

function cleanup() {
    kill -s SIGTERM $!
    exit 0
}

trap cleanup SIGINT SIGTERM

while [ 1 ]; do
    sleep 60 &
    wait $!
done

