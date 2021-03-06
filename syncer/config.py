import os
import sys
from urllib.parse import quote_plus
from datetime import timedelta

basedir = os.path.abspath(os.path.dirname(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(os.getcwd(), os.pardir))

SECRET_KEY = '__SECRET_KEY__'
SQLALCHEMY_DATABASE_URI = 'sqlite:////tmp/test.db'
SQLALCHEMY_ECHO = False
SQLALCHEMY_TRACK_MODIFICATIONS = False
SQLALCHEMY_POOL_RECYCLE = 599

MYSQL_HOST = ''
MYSQL_USER = ''
MYSQL_PASSWORD = ''
MYSQL_PORT = 3306
MYSQL_DB = 'email_sync_jobs'


DTABLE_WEB_SERVICE_URL = 'http://127.0.0.1:8000'

ADMIN_SYNCER_USER = ''
ADMIN_SYNCER_PASSWORD = ''

LOG_DIR = ''

RUN_INFO_DIR = ''

EMAIL_SYNC_MAX_DURATION_SECONDS = 60 * 30
EMAIL_SYNC_CHECK_INTERVAL_SECONDS = 60
EMAIL_SYNC_IMAP_TIMEOUT = None

WEBPACK_LOADER = {
    'STATIC_URL': 'static',
    'BUNDLE_DIR_NAME': os.path.join('/static', 'frontend/'),
    'STATS_FILE': os.path.join(PROJECT_ROOT, 'frontend/webpack-stats.pro.json'),
    'POLL_INTERVAL': 0.1,
    'TIMEOUT': None,
    'IGNORES': []
}

try:
    if os.path.exists('/shared/conf/seatable_syncer_settings.py'):
        sys.path.insert(0, '/shared/conf')
        from seatable_syncer_settings import *
except:
    pass
else:
    if MYSQL_HOST and MYSQL_USER and MYSQL_PASSWORD:
        SQLALCHEMY_DATABASE_URI = "mysql+mysqldb://%s:%s@%s:%s/%s?charset=utf8" % \
            (MYSQL_USER, quote_plus(MYSQL_PASSWORD), MYSQL_HOST, MYSQL_PORT, MYSQL_DB)

try:
    if os.path.exists('local_settings.py'):
        from local_settings import *
except:
    pass
else:
    if MYSQL_HOST and MYSQL_USER and MYSQL_PASSWORD:
        SQLALCHEMY_DATABASE_URI = "mysql+mysqldb://%s:%s@%s:%s/%s?charset=utf8" % \
            (MYSQL_USER, quote_plus(MYSQL_PASSWORD), MYSQL_HOST, MYSQL_PORT, MYSQL_DB)


class Config:
    """Set Flask configuration"""

    # General Config
    SECRET_KEY = SECRET_KEY
    DTABLE_WEB_SERVICE_URL = DTABLE_WEB_SERVICE_URL
    PERMANENT_SESSION_LIFETIME = timedelta(minutes=30)

    # Database
    SQLALCHEMY_DATABASE_URI = SQLALCHEMY_DATABASE_URI
    SQLALCHEMY_ECHO = SQLALCHEMY_ECHO
    SQLALCHEMY_TRACK_MODIFICATIONS = SQLALCHEMY_TRACK_MODIFICATIONS
    # Database:engine options
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_recycle': SQLALCHEMY_POOL_RECYCLE,
    }
    # Admin info
    ADMIN_SYNCER_USER = ADMIN_SYNCER_USER
    ADMIN_SYNCER_PASSWORD = ADMIN_SYNCER_PASSWORD
    
    # webpack
    WEBPACK_LOADER = WEBPACK_LOADER
