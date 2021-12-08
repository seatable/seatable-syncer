from gevent import monkey; monkey.patch_all()
import logging
import os

logging.basicConfig(
    filename=os.path.join(os.environ.get('LOG_DIR', ''), 'sync_server.log'),
    filemode='a',
    format="[%(asctime)s] [%(levelname)s] %(name)s:%(lineno)s %(funcName)s %(message)s",
    level=logging.INFO
)

import pymysql
pymysql.install_as_MySQLdb()

from app import app
from scheduler import scheduler_jobs_manager

scheduler_jobs_manager.load_jobs()
scheduler_jobs_manager.start()

from gevent.pywsgi import WSGIServer

if __name__ == '__main__':
    WSGIServer(('0.0.0.0', 5066), app).serve_forever()
