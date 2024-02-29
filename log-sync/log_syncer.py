#!/usr/bin/env python3

import re
import time
import json
import redis
from datetime import datetime
from seatable_api import Base

from settings import server_url, api_token, table_name, filebeat_key, \
    redis_host, redis_port, redis_db, redis_password


DATETIME_MATCH_1 = r'^(\d{4}-\d{1,2}-\d{1,2}\s\d{1,2}:\d{1,2}:\d{1,2})'
DATETIME_MATCH_2 = r'^(\d{4}-\d{1,2}-\d{1,2}T\d{1,2}:\d{1,2}:\d{1,2})'
DATETIME_MATCH_3 = r'^\[(\d{4}-\d{1,2}-\d{1,2}\s\d{1,2}:\d{1,2}:\d{1,2})'
DATETIME_MATCH_4 = r'^\[(\d{4}-\d{1,2}-\d{1,2}T\d{1,2}:\d{1,2}:\d{1,2})'


class LogSyncer(object):

    def __init__(self):
        self.base = Base(api_token, server_url)
        self.r = redis.Redis(
            host=redis_host, port=redis_port, db=redis_db, password=redis_password)
        self.batch_count = 10

    def now(self):
        return str(datetime.now())

    def count(self):
        return self.r.llen(filebeat_key)

    def base_auth(self):
        while True:
            try:
                self.base.auth()
                break
            except Exception as e:
                print(self.now(), type(e), e)
                time.sleep(30)

    def send(self, logs):
        rows = []
        for log in logs:
            logs = json.loads(log)
            msg = logs['message']
            if re.match(DATETIME_MATCH_1, msg):
                log_time = re.match(DATETIME_MATCH_1, msg).group(1)
            elif re.match(DATETIME_MATCH_2, msg):
                log_time = re.match(DATETIME_MATCH_2, msg).group(1).replace('T', ' ')
            elif re.match(DATETIME_MATCH_3, msg):
                log_time = re.match(DATETIME_MATCH_3, msg).group(1)
            elif re.match(DATETIME_MATCH_4, msg):
                log_time = re.match(DATETIME_MATCH_4, msg).group(1).replace('T', ' ')
            else:
                log_time = self.now()
            msg = '```\n' + msg + '\n```'
            service = '-'.join(logs['tags'])
            print(self.now(), service, log_time)

            row_data = {
                'Service': service,
                'Time': log_time,
                'Log': msg
            }
            rows.append(row_data)
        self.base.big_data_insert_rows(table_name, rows)

    def start(self):
        print(self.now(), 'Logs count:', self.count())
        self.base.auth()

        while True:
            try:
                logs = self.r.lpop(filebeat_key, self.batch_count)
                if not logs:
                    time.sleep(30)
                    continue

                self.send(logs)
                time.sleep(0.5)
            except ConnectionError as e:
                print(self.now(), type(e), e)
                time.sleep(30)
                self.base_auth()
            except redis.exceptions.ConnectionError as e:
                print(self.now(), type(e), e)
                time.sleep(30)
            except Exception as e:
                print(self.now(), type(e), e)
                time.sleep(30)


if __name__ == '__main__':
    log_syncer = LogSyncer()
    log_syncer.start()
