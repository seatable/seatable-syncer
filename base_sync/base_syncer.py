import time
import pymysql
import logging
import settings
from datetime import datetime
from seatable_api import Base

logging.basicConfig(
    filename='base_syncer.log',
    filemode='a',
    format="[%(asctime)s] [%(levelname)s] %(name)s:%(lineno)s %(funcName)s %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)


def get_dtables(base, mode, cursor, table_name, date=None):
    sql = "SELECT uuid,name,creator,created_at,workspace_id FROM dtables"
    if mode == 'ON':
        if not date:
            date = 'curdate()'
        else:
            date = "'%s'" % date
        sql += " WHERE DATE(created_at) = DATE_SUB(%s,interval 1 day)" % date
    mysql_rows = []
    step = 1000
    i = 0
    while True:
        query_sql = sql + f" LIMIT {i * step},{step}"
        cursor.execute(query_sql)
        rows = cursor.fetchall()
        time.sleep(0.5)
        mysql_rows += rows
        if len(rows) < step:
            break
        i += 1

    step = 100
    dtable_base_rows = {}
    for i in range(0, len(mysql_rows), step):
        query_str = ', '.join([f"'{row['uuid']}'" for row in mysql_rows[i: i + step]])
        query_sql = f"select uuid from `{table_name}` where uuid in ({query_str})"
        id_rows = fixed_sql_query(base, query_sql)
        dtable_base_rows.update({row['uuid']: True for row in id_rows})
    mysql_rows = [get_row(row) for row in mysql_rows if not dtable_base_rows.get(row['uuid'])]

    return mysql_rows


def get_row(row):
    row['created_at'] = str(row.get('created_at'))
    return row


def fixed_sql_query(seatable, sql):
    try:
        return seatable.query(sql)
    except TypeError:
        return []


def sync(mode, table_name, username, password, db_name, host, charset, api_token, dtable_web_service_url, date=None):
    conn = pymysql.connect(user=username, password=password, database=db_name, host=host, charset=charset)
    cursor = conn.cursor(cursor=pymysql.cursors.DictCursor)
    logger.info('connect mysql successfully!')

    base = Base(api_token, dtable_web_service_url)
    base.auth()
    logger.info('api_token: %s, dtable_web_service_url: %s auth successfully!', api_token, dtable_web_service_url)

    mysql_rows = get_dtables(base, mode, cursor, table_name, date=date)
    logger.info(f'fetch {len(mysql_rows)} bases')
    step = 1000
    for i in range(0, len(mysql_rows), step):
        base.batch_append_rows(table_name, mysql_rows[i: i + step])


def main():
    date = ''
    if settings.MODE == "ON":
        try:
            if settings.DATE:
                date = str(datetime.strptime(settings.DATE, '%Y-%m-%d').date())
            else:
                date = str(datetime.today().date())
        except Exception as e:
            logger.error('date: %s invalid, should be %%Y-%%m-%%d', settings.DATE)
            return

    try:
        sync(
            mode=settings.MODE,
            table_name=settings.BASE_TABLE_NAME,
            username=settings.MYSQL_USER,
            password=settings.MYSQL_PASSWORD,
            db_name=settings.DB_NAME,
            host=settings.MYSQL_HOST,
            charset=settings.CHARSET,
            api_token=settings.BASE_API_TOKEN,
            dtable_web_service_url=settings.DTABLE_WEB_SERVICE_URL,
            date=date)
    except Exception as e:
        logger.exception(e)
        logger.error('sync base error: %s', e)


if __name__ == '__main__':
    main()
