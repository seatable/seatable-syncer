import json
import pymysql
import logging
import settings
from datetime import datetime
from seatable_api import Base
import os
from uuid import uuid4
import re


logging.basicConfig(
    filename='mysql_sync.log',
    filemode='a',
    format="[%(asctime)s] [%(levelname)s] %(name)s:%(lineno)s %(funcName)s %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)


with open(os.path.join(os.path.dirname(__file__), 'mysql_to_dtable.json'), 'r') as f:
    mysql_to_dtable_dict = json.load(f)

geometry_type_list = ["GEOMETRY", "POINT", "LINESTRING", "POLYGON", "MULTIPOINT", "MULTILINESTRING", "MULTIPOLYGON",
                      "GEOMETRYCOLLECTION"]


def parse_file(base, cell_value):
    if not cell_value:
        return []
    temp_file_name = uuid4().hex
    file_info = base.upload_bytes_file(temp_file_name, cell_value)
    return [file_info]


def parse_multiple_select(cell_value):
    if not cell_value:
        return []
    cell_value = str(cell_value)
    values = cell_value.split(',')
    return [value.strip() for value in values]


def parse_long_text(cell_value):
    if not cell_value:
        return {}
    # copy from dtable-web/frontend/src/components-form/utils/markdown-utils.js
    HREF_REG = r'\[.+\]\(\S+\)|<img src=\S+.+\/>|!\[\]\(\S+\)|<\S+>'
    LINK_REG_1 = r'^\[.+\]\((\S+)\)'
    LINK_REG_2 = r'^<(\S+)>$'
    IMAGE_REG_1 = r'^<img src="(\S+)" .+\/>'
    IMAGE_REG_2 = r'^!\[\]\((\S+)\)'

    cell_value = str(cell_value)
    checked_count = cell_value.count('[x]')
    unchecked_count = cell_value.count('[ ]')
    total = checked_count + unchecked_count

    href_reg = re.compile(HREF_REG)
    preview = href_reg.sub(' ', cell_value)
    preview = preview[:20].replace('\n', ' ')

    images = []
    links = []
    href_list = href_reg.findall(cell_value)
    for href in href_list:
        if re.search(LINK_REG_1, href):
            links.append(re.search(LINK_REG_1, href).group(1))
        elif re.search(LINK_REG_2, href):
            links.append(re.search(LINK_REG_2, href).group(1))
        elif re.search(IMAGE_REG_1, href):
            images.append(re.search(IMAGE_REG_1, href).group(1))
        elif re.search(IMAGE_REG_2, href):
            images.append(re.search(IMAGE_REG_2, href).group(1))

    return {
        'text': cell_value,
        'preview': preview,
        'checklist': {'completed': checked_count, 'total': total},
        'images': images,
        'links': links,
    }


class MysqlSync(object):
    def __init__(self):
        self.conn = pymysql.connect(user=settings.MYSQL_USER, password=settings.MYSQL_PASSWORD,
                                    database=settings.DB_NAME, host=settings.MYSQL_HOST, charset=settings.CHARSET)
        self.cursor = self.conn.cursor(cursor=pymysql.cursors.DictCursor)
        self.base = Base(settings.BASE_API_TOKEN, settings.DTABLE_WEB_SERVICE_URL)
        self.mode = settings.MODE
        self.mysql_table_name = settings.MYSQL_TABLE_NAME
        self.base_table_name = settings.BASE_TABLE_NAME
        self.field_info = None

    def now(self):
        return str(datetime.now())

    def base_auth(self):
        self.base.auth()

    def get_mysql_field_info(self):
        sql = "DESC " + self.mysql_table_name
        self.cursor.execute(sql)
        field_info = self.cursor.fetchall()
        self.field_info = {field['Field']: field['Type'].split('(')[0].upper() for field in field_info}

    def parse_geometry(self, field):
        """
        parse geometry type as text
        :param field:
        :return:
        """
        if self.field_info.get(field) in geometry_type_list:
            return f'astext({field}) as {field}'
        return field

    def get_mysql_data(self):
        sql_fields = [self.parse_geometry(field) for field in self.field_info.keys()]
        sql = "SELECT " + ','.join(sql_fields) + " FROM " + self.mysql_table_name
        if self.mode == "ON":
            sql += " WHERE " + "date(" + settings.DATE_FIELD + ") = date_sub(curdate(),interval 1 day)"
        self.cursor.execute(sql)

        return self.parse_mysql_rows(self.cursor.fetchall())

    def parse_mysql_rows(self, mysql_rows):
        for row in mysql_rows:
            for key in row:
                mysql_field = self.field_info[key]
                base_type = mysql_to_dtable_dict.get(mysql_field)
                cell_value = row[key]

                if base_type == 'text' and cell_value is not None:
                    row[key] = str(cell_value)  # deal time field
                if base_type == 'date':
                    row[key] = str(cell_value)
                elif base_type == 'long-text':
                    row[key] = parse_long_text(cell_value)
                elif base_type == 'multiple-select':
                    row[key] = parse_multiple_select(cell_value)
                elif base_type == 'file':
                    row[key] = parse_file(self.base, cell_value)

        return mysql_rows

    def sync(self):
        print(self.now(), 'Start sync mysql')
        logger.info('start syncing: %s', self.now())
        try:
            self.base_auth()
            self.get_mysql_field_info()
            mysql_data = self.get_mysql_data()
            self.base.batch_append_rows(self.base_table_name, mysql_data)
        except Exception as e:
            logger.exception(e)
            logger.error('sync mysql error: %s', e)
        finally:
            self.conn.close()
            self.cursor.close()


if __name__ == '__main__':
    mysqlSync = MysqlSync()
    mysqlSync.sync()
