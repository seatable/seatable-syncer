import json
import logging
import time
from datetime import datetime, timedelta

import pytz
from tzlocal import get_localzone  # tzlocal is depend by apscheduler
from seatable_api.main import SeaTableAPI

from app import app
from email_sync.email_syncer import sync
from models.sync_models import SyncJobs
from utils import check_api_token_and_resources, check_imap_account
from utils.exceptions import SchedulerJobInvalidException

logger = logging.getLogger(__name__)


def email_sync_job_func(
    db_job_id,
    dtable_web_service_url
):
    with app.app_context():
        db_job = SyncJobs.query.filter(SyncJobs.id == db_job_id).first()
    if not db_job:
        raise SchedulerJobInvalidException('email sync db_job: %s not found' % db_job_id)
    api_token = db_job.api_token
    try:
        detail = json.loads(db_job.detail)
    except Exception as e:
        raise SchedulerJobInvalidException('email sync db_job: %s detail: %s invalid error: %s' % (db_job, db_job.detail, e))
    # check seatable api token
    error_msg = check_api_token_and_resources(api_token, dtable_web_service_url, job_type='email-sync', detail=detail, check_imap=False)
    if error_msg:
        raise SchedulerJobInvalidException(error_msg)

    imap_server = detail['imap_server']
    email_user = detail['email_user']
    email_password = detail['email_password']
    email_table_id = detail['email_table_id']
    link_table_id = detail['link_table_id']

    # check email login
    try_count = 3
    error_msg = None
    imap = None
    while try_count:
        imap, error_msg = check_imap_account(imap_server, email_user, email_password, return_imap=True)
        if imap and not error_msg:
            break
        else:
            try_count -= 1
            logger.error('email account: %s login error: %s, left try_count: %s (retry in 10s)', email_user, error_msg, try_count)
            if try_count:
                time.sleep(10)
    if error_msg:
        raise SchedulerJobInvalidException(error_msg)

    seatable = SeaTableAPI(api_token, dtable_web_service_url)
    seatable.auth()

    email_table_name, link_table_name = None, None
    for table in seatable.get_metadata().get('tables', []):
        if email_table_id == table.get('_id'):
            email_table_name = table.get('name')
        if link_table_id == table.get('_id'):
            link_table_name = table.get('name')

    if not (email_table_name and link_table_name):
        raise SchedulerJobInvalidException('email_table: %s or link_table: %s not exists' % (email_table_id, link_table_id))

    mode = 'ON'
    date_str = str(datetime.today().date())
    last_day_str = str((datetime.today() - timedelta(days=1)).date())
    # last_trigger_time in database is UTC time, so need to convert it to localzone datetime
    if str(pytz.utc.localize(db_job.last_trigger_time).astimezone(get_localzone()).date()) == last_day_str:
        mode = 'SINCE'
        date_str = last_day_str

    # sync
    sync(
        date_str,
        api_token,
        dtable_web_service_url,
        email_table_name,
        link_table_name,
        imap_server,
        email_user,
        email_password,
        imap=imap,
        mode=mode
    )
