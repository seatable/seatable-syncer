import json
import pymysql
import logging
import settings
from datetime import datetime, timedelta
from seatable_api import Base
import os
from bs4 import BeautifulSoup
import markdown


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

    def get_unique_rows(self):
        return fixed_sql_query(self.base, f"select {self.unique_field} from `{self.table_name}`")

    def get_mysql_data(self):
        unique_rows = ','.join([str(row[self.unique_field]) for row in self.get_unique_rows()])

        sql = "SELECT " + ','.join(["`%s`" % key for key in self.field_info.keys()]) + " FROM " + self.table_name
        if self.mode == "ON":
            sql += " WHERE " + "date(`" + settings.DATE_FIELD + "`) = date_sub(curdate(),interval 1 day)"
            if unique_rows:
                sql += "AND `%s` not in (%s)" % (self.unique_field, unique_rows)

        if unique_rows and self.mode == 'ALL':
            sql += " WHERE `%s` not in (%s)" % (self.unique_field, unique_rows)
        self.cursor.execute(sql)

        return self.parse_mysql_rows(self.cursor.fetchall())

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
    for link in bf.find_all(name='a'):
        links.append(link.attrs.get('href'))
    for img in bf.find_all(name='img'):
        images.append(img.attrs.get('src'))

    return links, images


def parse_long_text(cell_value):
    if not cell_value:
        return {}
    preview_content = markdown.markdown(cell_value)
    links, images = get_preview_info(preview_content)
    checked_count = cell_value.count('[x]')
    unchecked_count = cell_value.count('[ ]')
    total = checked_count + unchecked_count

    return {
            'text': cell_value,
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
        mysql_data.get_mysql_field_info()
        if mysql_to_dtable_dict[mysql_data.field_info[mysql_data.unique_field]] not in ('number', 'text'):
            logger.error('unique field type error')
        mysql_rows = mysql_data.get_mysql_data()
    except Exception as e:
        logger.exception(e)
    else:
        return mysql_rows
    finally:
        mysql_data.close()
    return []


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
