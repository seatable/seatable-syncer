# seatable
BASE_API_TOKEN = ''
DTABLE_WEB_SERVICE_URL = ''
LANG = ''

# mysql
MYSQL_USER = ''
MYSQL_PASSWORD = ''
MYSQL_PORT = 3306
MYSQL_HOST = ''
DB_NAME = ''
CHARSET = 'utf8'
MYSQL_TABLE_NAME = ''

MODE = 'ALL'  # ALL or ON
DATE_FIELD = ''
UNIQUE_FIELD = ''  # primary key or unique key


import os
import sys

if os.path.isfile(os.path.join(os.path.dirname(__file__), 'mysql_syncer_settings.py')):
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'mysql_syncer_settings.py'))
    try:
        from mysql_syncer_settings import *
    except:
        pass
