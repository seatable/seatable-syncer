import argparse
from datetime import datetime
import json
import logging

import pymysql
from apscheduler.triggers.cron import CronTrigger
from seatable_api import SeaTableAPI

logging.basicConfig(
    format="[%(asctime)s] [%(levelname)s] %(name)s:%(lineno)s %(funcName)s %(message)s",
    level=logging.DEBUG
)
pymysql.install_as_MySQLdb()

from app import SyncJobs, app
from config import Config
from email_sync.email_syncer import sync as sync_emails
from utils import check_imap_account, check_table_columns, email_sync_tables_dict
from utils.constants import JOB_TYPE_EMAIL_SYNC

logger = logging.getLogger(__name__)


def debug_email_sync_job(db_job: SyncJobs, send_date_str: str=None):
    detail = json.loads(db_job.detail)
    trigger_detail = json.loads(db_job.trigger_detail)

    imap_server = detail.get('imap_server')
    email_user = detail.get('email_user')
    email_password = detail.get('email_password')
    error_msg = check_imap_account(imap_server, email_user, email_password)
    if error_msg:
        logger.error('job: %s, detail: %s, email login error: %s', db_job, detail, error_msg)
        return

    try:
        CronTrigger(**trigger_detail)
    except Exception as e:
        logger.error('job: %s trigger error: %s', db_job, e)
        return

    email_table_id, link_table_id = detail.get('email_table_id'), detail.get('link_table_id')
    if not email_table_id or not link_table_id:
        logger.error('email_table_id: %s, link_table_id: %s invalid.', email_table_id, link_table_id)
        return

    try:
        seatable = SeaTableAPI(db_job.api_token, Config.DTABLE_WEB_SERVICE_URL)
        seatable.auth()
    except Exception as e:
        logger.error('job: %s, api_token: %s, dtable_web_service_url: %s auth error: %s', db_job, db_job.api_token, Config.DTABLE_WEB_SERVICE_URL, e)
        return

    try:
        email_table, error_msg = check_table_columns(seatable, email_table_id, email_sync_tables_dict['email_table'])
        if error_msg:
            logger.error('check email table error: %s', error_msg)
            return
        logger.info('email_table: %s found and is valid, table_name is: %s', email_table_id, email_table.get('name'))
        link_table, error_msg = check_table_columns(seatable, link_table_id, email_sync_tables_dict['link_table'])
        if error_msg:
            logger.error('check link table error: %s', error_msg)
            return
        logger.info('link_table: %s found and is valid, table_name is: %s', link_table_id, link_table.get('name'))
    except Exception as e:
        logger.exception(e)
        logger.error('debug job: %s error: %s', db_job, e)
        return

    logger.info('job: %s check settings successfully!', db_job)

    if not send_date_str:
        return

    logger.info('job: %s start checking run job process', db_job)
    api_token = db_job.api_token
    dtable_web_service_url = Config.DTABLE_WEB_SERVICE_URL
    email_table_name = email_table.get('name')
    link_table_name = link_table.get('name')
    mode = 'since'
    try:
        sync_emails(send_date_str,
                    api_token,
                    dtable_web_service_url,
                    email_table_name,
                    link_table_name,
                    imap_server,
                    email_user,
                    email_password,
                    mode=mode)
    except Exception as e:
        logger.exception(e)
        logger.error('job: %s run error: %s', db_job, e)
    else:
        logger.info('job: %s check sync emails successfully!', db_job)
        logger.info('job: %s sync emails sent from: %s up to date successfully!', db_job, send_date_str)


def main():
    global parser

    args = parser.parse_args()
    job_id = args.job_id
    send_date_str = args.send_date

    if send_date_str:
        try:
            datetime.strptime(send_date_str, '%Y-%m-%d')
        except:
            logger.error('send-date invalid, process will exit')
            exit(-1)

    db_job = SyncJobs.query.filter(SyncJobs.id == job_id).first()
    if not db_job:
        logger.error('job: %s not found.', job_id)
        return
    if not db_job.is_valid:
        logger.warning('job: %s is_valid: %s', db_job, db_job.is_valid)
    logger.info('job: %s', db_job)
    logger.debug('detail: %s', db_job.detail)
    logger.debug('trigger_detail: %s', db_job.trigger_detail)
    if db_job.job_type == JOB_TYPE_EMAIL_SYNC:
        debug_email_sync_job(db_job, send_date_str=send_date_str)
    logger.info('job: %s debug all end!', db_job)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--job-id', required=True, type=int, help='job id')
    parser.add_argument('--send-date', required=False, type=str, help='sync date')
    with app.app_context():
        main()
