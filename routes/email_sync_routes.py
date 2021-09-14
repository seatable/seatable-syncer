import json
import logging
import os
from datetime import datetime
from uuid import UUID

from apscheduler.triggers.cron import CronTrigger
from flask import current_app as app, request
from flask_cors import cross_origin
from seatable_api import SeaTableAPI
from seatable_api.constants import ColumnTypes

from app import db
from config import basedir
from email_sync.email_syncer import sync
from models.email_sync_models import EmailSyncJobs
from scheduler import scheduler_jobs_manager
from utils.constants import EMAIL_SYNC_JOB_PREFIX

logger = logging.getLogger(__name__)

table_file = os.path.join(basedir, 'email_sync', 'tables.json')

if not os.path.isfile(table_file):
    raise Exception(f'{table_file} not found')
with open(table_file, 'r') as f:
    tables_dict = json.load(f)


# list running email_sync jobs
@app.route('/api/v1/running/email-sync-jobs/', methods=['GET'])
def running_email_sync_jobs_api():
    jobs = scheduler_jobs_manager.get_jobs()
    return {'jobs': jobs}, 200


# list email_sync jobs and add new eamil sync job
@app.route('/api/v1/email-sync-jobs/', methods=['GET', 'POST', 'DELETE'])
@cross_origin()
def email_sync_jobs_api():
    # TODO: some resource check, such as api-token
    if request.method == 'GET':
        dtable_uuid = request.args.get('dtable_uuid')
        if not dtable_uuid:
            return {'error_msg': 'dtable_uuid invalid.'}, 400
        try:
            dtable_uuid = UUID(dtable_uuid).hex
        except:
            return {'error_msg': 'dtable_uuid invalid.'}, 400
        jobs = EmailSyncJobs.query.filter(EmailSyncJobs.dtable_uuid == dtable_uuid).all()
        job_list = []
        for job in jobs:
            job_list.append(job.to_dict())
        return {'email_sync_job_list': job_list}, 200

    elif request.method == 'POST':
        try:
            data = json.loads(request.data)
        except:
            return {'error_msg': 'Bad request.'}, 400

        name = data.get('name')
        dtable_uuid = data.get('dtable_uuid')
        api_token = data.get('api_token')
        cron_expr = data.get('cron_expr')
        imap_server = data.get('imap_server')
        email_user = data.get('email_user')
        email_password = data.get('email_password')
        email_table_name = data.get('email_table_name')
        link_table_name = data.get('link_table_name')

        if not all([name, dtable_uuid, api_token, imap_server, email_user, email_password, email_table_name, link_table_name]):
            return {'error_msg': 'Bad request.'}, 400

        try:
            dtable_uuid = UUID(dtable_uuid).hex
        except:
            return {'error_msg': 'dtable_uuid invalid.'}, 400

        try:
            CronTrigger.from_crontab(cron_expr)
        except:
            return {'error_msg': 'cron_expr error.'}, 400

        job = EmailSyncJobs(
            name=name,
            dtable_uuid=dtable_uuid,
            api_token=api_token,
            cron_expr=cron_expr,
            imap_server=imap_server,
            email_user=email_user,
            email_password=email_password,
            email_table_name=email_table_name,
            link_table_name=link_table_name
        )
        try:
            db.session.add(job)
            db.session.commit()
        except Exception as e:
            logger.error('add job: %s error: %s', job, e)
            return {'error_msg': 'Internal Server Error.'}, 500

        try:
            scheduler_jobs_manager.add_email_sync_job(job)
        except Exception as e:
            logger.error('add scheduler-email-sync-job: %s, error: %s', job, e)

        return {'email_sync_job': job.to_dict()}, 200

    else:
        dtable_uuid = request.args.get('dtable_uuid')
        if not dtable_uuid:
            return {'error_msg': 'dtable_uuid invalid.'}, 400
        try:
            dtable_uuid = UUID(dtable_uuid).hex
        except:
            return {'error_msg': 'dtable_uuid invalid.'}, 400
        try:
            jobs = EmailSyncJobs.query.filter(EmailSyncJobs.dtable_uuid == EmailSyncJobs).all()
        except Exception as e:
            logger.error('checkout dtable: %s email-sync-jobs error: %s', dtable_uuid, e)
            return {'error_msg': 'Internal Server Error.'}, 500

        try:
            [scheduler_jobs_manager.remove_job(job.job_id) for job in jobs]
        except Exception as e:
            logger.error('remove dtable: %s scheduler-email-sync-jobs error: %s', dtable_uuid, e)

        try:
            EmailSyncJobs.query.filter(EmailSyncJobs.dtable_uuid == EmailSyncJobs).delete()
        except Exception as e:
            logger.error('delete dtable: %s email-sync-jobs error: %s', dtable_uuid, e)
            return {'error_msg': 'Internal Server Error.'}, 500

        return {'success': True}, 200


# update email_sync job and remove email_sync job
@app.route('/api/v1/email-sync-jobs/<job_id>/', methods=['PUT', 'DELETE'])
@cross_origin()
def email_sync_job_api(job_id):
    # TODO: some resource check, such as api-token
    if request.method == 'PUT':
        try:
            data = json.loads(request.data)
        except:
            return {'error_msg': 'Bad request.'}, 400

        name = data.get('name')
        api_token = data.get('api_token')
        cron_expr = data.get('cron_expr')
        imap_server = data.get('imap_server')
        email_user = data.get('email_user')
        email_password = data.get('email_password')
        email_table_name = data.get('email_table_name')
        link_table_name = data.get('link_table_name')

        try:
            job = EmailSyncJobs.query.filter(id=job_id).first()
            if not job:
                return {'error_msg': 'Job not found.'}, 404
        except Exception as e:
            logger.error('get job: %s error: %s', job_id, e)
            return {'error_msg': 'Internal Server Error.'}, 500

        if name:
            job.name = name
        if api_token:
            job.api_token = api_token
        if cron_expr:
            try:
                CronTrigger.from_crontab(cron_expr)
            except:
                return {'error_msg': 'cron_expr invalid.'}, 400
            job.cron_expr = cron_expr
        if imap_server:
            job.imap_server = imap_server
        if email_user:
            job.email_user = email_user
        if email_password:
            job.email_password = email_password
        if email_table_name:
            job.email_table_name = email_table_name
        if link_table_name:
            job.link_table_name = link_table_name

        try:
            db.session.commit()
        except Exception as e:
            logger.error('update job: %s, error: %s', job, e)
            return {'error_msg': 'Internal Server Error.'}, 500

        try:
            scheduler_jobs_manager.update_email_sync_job(job)
        except Exception as e:
            logger.error('update sheduler-email-sync-job: %s, error: %s', job, e)

        return {'email_sync_job': job.to_dict()}, 200

    else:
        try:
            EmailSyncJobs.query.filter(id=job_id).delete()
            db.session.commit()
        except Exception as e:
            logger.error('delete job: %s error: %s', job_id, e)
            return {'error_msg': 'Internal Server Error.'}, 500

        try:
            scheduler_jobs_manager.remove_job(job_id, prefix=EMAIL_SYNC_JOB_PREFIX)
        except Exception as e:
            logger.error('remove job: %s error: %s', job_id, e)

        return {'success': True}, 200


# sync emails
@app.route('/api/v1/sync-emails/', methods=['POST'])
@cross_origin()
def sync_emails_api():
    try:
        data = json.loads(request.data)
    except:
        return {'error_msg': 'Bad request.'}, 400

    email_server = data.get('email_server')
    email_user = data.get('email_user')
    email_password = data.get('email_password')
    api_token = data.get('api_token')
    dtable_web_service_url = data.get('dtable_web_service_url')
    email_table_name = data.get('email_table_name')
    link_table_name = data.get('link_table_name')

    send_date_str = data.get('send_date')
    mode = data.get('mode', 'ON')

    if not all([email_server, email_user, email_password, api_token, dtable_web_service_url,
                email_table_name, link_table_name]):
        return {'error_msg': 'Bad request.'}, 400
    if not send_date_str:
        send_date_str = str(datetime.now().today())
    else:
        try:
            datetime.strptime(send_date_str, '%Y-%m-%d').date()
        except:
            return {'error_msg': 'send_date invalid.'}, 400

    try:
        sync(send_date_str,
             api_token,
             dtable_web_service_url,
             email_table_name,
             link_table_name,
             email_server,
             email_user,
             email_password,
             mode=mode)
    except Exception as e:
        logger.exception(e)
        logger.error('sync emails email_server: %s, email_user: %s, dtable_web_service_url: %s, email table: %s, \
            link table: %s, send_date: %s, mode: %s error: %s', email_server, email_user, dtable_web_service_url, email_table_name, link_table_name, send_date_str, mode, e)
        return {'error_msg': 'Internal Server Error.'}, 500

    return {'success': True}, 200


# create sync-email tables
@app.route('/api/v1/email-sync-tables/', methods=['POST'])
@cross_origin()
def add_sync_tables_api():
    try:
        data = json.loads(request.data)
    except:
        return {'error_msg': 'Bad request.'}, 400

    api_token = data.get('api_token')
    dtable_web_service_url = data.get('dtable_web_service_url')
    email_table_name = data.get('email_table_name')
    link_table_name = data.get('link_table_name')
    lang = data.get('lang')

    if not all([api_token, dtable_web_service_url]):
        return {'error_msg': 'api_token or dtable_web_service_url invalid.'}, 400

    lang = lang if lang else 'en'
    email_table_name = email_table_name if email_table_name else 'Emails'
    link_table_name = link_table_name if link_table_name else 'Threads'

    try:
        seatable = SeaTableAPI(api_token, dtable_web_service_url)
        seatable.auth()
    except Exception as e:
        logger.error('auth seatable-api error: %s', e)
        return {'error_msg': 'api_token or dtable_web_service_url invalid.'}, 400

    try:
        # create emails table and columns
        email_table = seatable.add_table(email_table_name, lang=lang)
        columns = tables_dict.get('email_table', [])
        for index, col in enumerate(columns):
            if index == 0:
                seatable.rename_column(email_table_name, '0000', col.get('column_name'))
                continue
            col_name, col_type = col.get('column_name'), col.get('type')
            seatable.insert_column(email_table_name, col_name, ColumnTypes(col_type), column_data=col.get('data'))

        # create links table and columns
        link_table = seatable.add_table(link_table_name, lang=lang)
        columns = tables_dict.get('link_table', [])
        for index, col in enumerate(columns):
            if index == 0:
                seatable.rename_column(link_table_name, '0000', col.get('column_name'))
                continue
            col_name, col_type = col.get('column_name'), col.get('type')
            seatable.insert_column(link_table_name, col_name, ColumnTypes(col_type), column_data=col.get('data'))

        # add link columns between email/table tables
        seatable.insert_column(link_table_name, 'Emails', ColumnTypes.LINK, column_data={
            'table': link_table_name,
            'other_table': email_table_name
        })
        seatable.rename_column(email_table_name, link_table_name, 'Threads')
    except Exception as e:
        logger.exception(e)
        logger.error('init email sync tables api_token: %s, dtable_web_service_url: %s,  email_table_name: %s, link_table_name: %s, lang: %s, error: %s', 
                     api_token, dtable_web_service_url, email_table_name, link_table_name, lang, e)
        return {'error_msg': 'Internal Server Error.'}, 500

    return {
        'email_table_name': email_table_name,
        'link_table_name': link_table_name,
    }, 200
