import json
import time

import pymysql
import logging
import settings
from datetime import datetime, timedelta
from seatable_api import Base
import os
from bs4 import BeautifulSoup
import markdown
import re


logging.basicConfig(
    filename='mysql_syncer.log',
    filemode='a',
    format="[%(asctime)s] [%(levelname)s] %(name)s:%(lineno)s %(funcName)s %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)


with open(os.path.join(os.path.dirname(__file__), 'mysql_to_dtable.json'), 'r') as f:
    mysql_to_dtable_dict = json.load(f)


class DataUtil(object):
    def __init__(self, base, mode, table_name, unique_field, username, password, db_name, host, charset):
        self.conn = pymysql.connect(user=username, password=password, database=db_name, host=host, charset=charset)
        self.cursor = self.conn.cursor(cursor=pymysql.cursors.DictCursor)
        self.base = base
        self.mode = mode
        self.table_name = table_name
        self.field_info = None
        self.unique_field = unique_field

    def now(self):
        return str(datetime.now())

    def get_mysql_field_info(self):
        sql = "DESC " + self.table_name
        self.cursor.execute(sql)
        field_info = self.cursor.fetchall()
        self.field_info = {field['Field']: field['Type'].split('(')[0].upper() for field in field_info}

    def get_base_unique_rows(self):
        return fixed_sql_query(self.base, f"select {self.unique_field} from `{self.table_name}`")

    def check_base(self):
        base_count_info = fixed_sql_query(self.base, f"select count(*) as base_count from `{self.table_name}`")
        return True if base_count_info[0].get('base_count') else False

    def get_mysql_row_count(self):
        count_sql = "SELECT COUNT(*) AS total_count FROM " + self.table_name
        self.cursor.execute(count_sql)
        return self.cursor.fetchone().get('total_count')

    def get_mysql_data(self):
        sql = "SELECT " + ','.join(["`%s`" % key for key in self.field_info.keys()]) + " FROM " + self.table_name
        if self.mode == 'ON':
            sql += " WHERE " + "DATE(`" + settings.DATE_FIELD + "`) = date_sub(curdate(),interval 1 day)"
        mysql_rows = []
        step = 1000
        i = 0
        while True:
            query_sql = sql + f" LIMIT {i*step},{step}"
            self.cursor.execute(query_sql)
            rows = self.cursor.fetchall()
            time.sleep(0.5)
            mysql_rows += rows
            if len(rows) < step:
                break
            i += 1
        if self.mode == 'ON':
            unique_rows = [row[self.unique_field] for row in self.get_base_unique_rows()]
            mysql_rows = [row for row in mysql_rows if row[self.unique_field] not in unique_rows]

        return self.parse_mysql_rows(mysql_rows)

    def parse_mysql_rows(self, mysql_rows):
        for row in mysql_rows:
            for key in row:
                mysql_field = self.field_info[key]
                base_type = mysql_to_dtable_dict.get(mysql_field)
                cell_value = row[key]

                if isinstance(cell_value, datetime) or isinstance(cell_value, timedelta):
                    row[key] = str(cell_value)
                elif base_type == 'long-text':
                    row[key] = parse_long_text(cell_value)
                elif base_type == 'multiple-select':
                    row[key] = parse_multiple_select(cell_value)
                elif base_type == 'single-select' and cell_value is None:
                    row[key] = ''

        return mysql_rows

    def close(self):
        self.conn.close()
        self.cursor.close()


def parse_multiple_select(cell_value):
    if not cell_value:
        return []
    cell_value = str(cell_value)
    values = cell_value.split(',')
    return [value.strip() for value in values]


def get_preview_info(preview_content):
    bf = BeautifulSoup(preview_content, features="lxml")
    links = []
    images = []
    checked_count = 0
    unchecked_count = 0
    for link in bf.find_all(name='a'):
        links.append(link.attrs.get('href'))
    for img in bf.find_all(name='img'):
        images.append(img.attrs.get('src'))
    for check_text in bf.find_all(name='li'):
        if check_text.text.startswith('[x]'):
            checked_count += 1
        elif check_text.text.startswith('[ ]'):
            unchecked_count += 1

    return links, images, checked_count, unchecked_count


def parse_long_text(cell_value):
    if not cell_value:
        return {}
    preview_content = markdown.markdown(cell_value)
    links, images, checked_count, unchecked_count = get_preview_info(preview_content)
    total = checked_count + unchecked_count

    HREF_REG = r'\[.+\]\(\S+\)|<img src=\S+.+\/>|!\[\]\(\S+\)|<\S+>'
    href_reg = re.compile(HREF_REG)
    preview = href_reg.sub(' ', cell_value)
    preview = preview[:20].replace('\n', ' ')
    return {
            'text': cell_value,
            'preview': preview,
            'checklist': {'completed': checked_count, 'total': total},
            'images': images,
            'links': links,
        }


def fixed_sql_query(seatable, sql):
    try:
        return seatable.query(sql)
    except TypeError:
        return []


def get_mysql_rows(base, mode, table_name, unique_field, username, password, db_name, host, charset):
    mysql_data = DataUtil(base, mode, table_name, unique_field, username, password, db_name, host, charset)
    try:
        if mode == 'ALL':
            if mysql_data.check_base():
                logger.error(f'base table {table_name} should be empty if mode is ALL')
                return []

        mysql_data.get_mysql_field_info()
        if mysql_to_dtable_dict[mysql_data.field_info[mysql_data.unique_field]] not in ('number', 'text'):
            logger.error('unique field type error')
            return []
        return mysql_data.get_mysql_data()
    except Exception as e:
        logger.exception(e)
    finally:
        mysql_data.close()


def sync(api_token,
         dtable_web_service_url,
         mode,
         table_name,
         unique_field,
         username,
         password,
         db_name,
         host,
         charset):
    try:
        base = Base(settings.BASE_API_TOKEN, settings.DTABLE_WEB_SERVICE_URL)
        base.auth()
        logger.debug('api_token: %s, dtable_web_service_url: %s auth successfully!', api_token, dtable_web_service_url)

        mysql_rows = get_mysql_rows(base, mode, table_name, unique_field, username, password, db_name, host, charset)
        logger.info(f'fetch {len(mysql_rows)} mysql rows')
        base.batch_append_rows(settings.MYSQL_TABLE_NAME, mysql_rows)
    except Exception as e:
        logger.exception(e)
        logger.error('sync mysql error: %s', e)


def main():
    try:
        sync(settings.BASE_API_TOKEN, settings.DTABLE_WEB_SERVICE_URL, settings.MODE, settings.MYSQL_TABLE_NAME,
             settings.UNIQUE_FIELD, settings.MYSQL_USER, settings.MYSQL_PASSWORD, settings.DB_NAME,
             settings.MYSQL_HOST, settings.CHARSET)
    except Exception as e:
        logger.exception(e)
        logger.error('sync mysql error: %s', e)


if __name__ == '__main__':
    main()
