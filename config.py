import os
import sys
from urllib.parse import quote_plus

basedir = os.path.abspath(os.path.dirname(__file__))

SECRET_KEY = '__SECRET_KEY__'
SQLALCHEMY_DATABASE_URI = 'sqlite:////tmp/test.db'
SQLALCHEMY_ECHO = False
SQLALCHEMY_TRACK_MODIFICATIONS = False

MYSQL_HOST = ''
MYSQL_USER = ''
MYSQL_PASSWORD = ''
MYSQL_PORT = 3306
MYSQL_DB = 'email_sync_jobs'


try:
    if os.path.isfile(os.path.join(basedir, 'sync_settings.py')):
        sys.path.insert(0, os.path.join(basedir, 'sync_settings.py'))
        from sync_settings import *
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

    # Database
    SQLALCHEMY_DATABASE_URI = SQLALCHEMY_DATABASE_URI
    SQLALCHEMY_ECHO = SQLALCHEMY_ECHO
    SQLALCHEMY_TRACK_MODIFICATIONS = SQLALCHEMY_TRACK_MODIFICATIONS
