# seatable
BASE_API_TOKEN = ''
DTABLE_WEB_SERVICE_URL = ''

# mysql
MYSQL_USER = ''
MYSQL_PASSWORD = ''
MYSQL_PORT = 3306
MYSQL_HOST = ''
DB_NAME = ''
CHARSET = 'utf8'
BASE_TABLE_NAME = ''

MODE = ''  # ALL or ON
DATE = ''  # only for ON mode, if empty or None default today


import os
import sys

if os.path.isfile(os.path.join(os.path.dirname(__file__), 'base_syncer_settings.py')):
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'base_syncer_settings.py'))
    try:
        from base_syncer_settings import *
    except:
        pass