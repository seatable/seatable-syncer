import json
import time
from datetime import datetime

import redis
from seatable_api import Base

from settings import server_url, api_token, table_name, cds_stats_key, \
    redis_host, redis_port, redis_db, redis_password


class CommonDatasetStatsSyncer:
    def __init__(self):
        self.base = Base(api_token, server_url)
        self.r = redis.Redis(
            host=redis_host, port=redis_port, db=redis_db, password=redis_password)
        self.batch_count = 10
        self.wait_timout = 30

    def count(self):
        return self.r.llen(cds_stats_key)

    def now(self):
        return str(datetime.now())

    def base_auth(self):
        while True:
            try:
                self.base.auth()
                break
            except Exception as e:
                print(self.now(), type(e), e)
                time.sleep(30)

    def send(self, items):
        rows = []
        for item in items:
            try:
                item = json.loads(item)
            except:
                continue
            rows.append({
                'org_id': item.get('org_id'),
                'dataset_id': item.get('dataset_id'),
                'src_dtable_uuid': item.get('src_dtable_uuid'),
                'src_table_id': item.get('src_table_id'),
                'src_view_id': item.get('src_view_id'),
                'dst_dtable_uuid': item.get('dst_dtable_uuid'),
                'dst_table_id': item.get('dst_table_id'),
                'import_or_sync': item.get('import_or_sync'),
                'operator': item.get('operator'),
                'started_at': str(datetime.fromisoformat(item.get('started_at'))),
                'finished_at': str(datetime.fromisoformat(item.get('finished_at'))),
                'to_be_appended_rows_count': item.get('to_be_appended_rows_count') or 0,
                'to_be_updated_rows_count': item.get('to_be_updated_rows_count') or 0,
                'to_be_deleted_rows_count': item.get('to_be_deleted_rows_count') or 0,
                'appended_rows_count': item.get('appended_rows_count') or 0,
                'updated_rows_count': item.get('updated_rows_count') or 0,
                'deleted_rows_count': item.get('deleted_rows_count') or 0,
                'columns_count': item.get('columns_count') or 0,
                'link_formula_columns_count': item.get('link_formula_columns_count') or 0,
                'is_success': item.get('is_success') or False,
                'error': item.get('error')
            })
        self.base.big_data_insert_rows(table_name, rows)

    def start(self):
        print(self.now(), 'Logs count:', self.count())
        self.base.auth()

        while True:
            try:
                start = time.time()
                while True:
                    if self.r.llen(cds_stats_key) > self.batch_count or time.time() - start > self.wait_timout:
                        break
                    time.sleep(5)
                items = self.r.lpop(cds_stats_key, self.batch_count)
                if not items:
                    time.sleep(30)
                    continue

                self.send(items)
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
                self.base_auth()
                time.sleep(30)


if __name__ == '__main__':
    cds_stats_syncer = CommonDatasetStatsSyncer()
    cds_stats_syncer.start()
