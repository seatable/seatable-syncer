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
from config import basedir, Config
from email_sync.email_syncer import sync
from models.email_sync_models import EmailSyncJobs
from scheduler import scheduler_jobs_manager
from utils import check_api_token_and_resources, check_imap_account
from utils.constants import EMAIL_SYNC_JOB_PREFIX

logger = logging.getLogger(__name__)

table_file = os.path.join(basedir, 'email_sync', 'tables.json')

if not os.path.isfile(table_file):
    raise Exception(f'{table_file} not found')
with open(table_file, 'r') as f:
    tables_dict = json.load(f)


# list running email_sync jobs
@app.route('/api/v1/email-sync/running-jobs/', methods=['GET'])
def running_email_sync_jobs_api():
    jobs = scheduler_jobs_manager.get_jobs()
    return {'jobs': jobs}, 200


# list email_sync jobs by dtable_uuids
@app.route('/api/v1/email-sync/jobs-by-dtable-uuids/', methods=['POST'])
@cross_origin()
def list_email_sync_jobs_api():
    try:
        data = json.loads(request.data)
    except:
        return {'error_msg': 'Bad request.'}, 400
    dtable_uuids = data.get('dtable_uuids')
    if not dtable_uuids or not isinstance(dtable_uuids, list):
        return {'error_msg': 'dtable_uuids request.'}, 400

    jobs = EmailSyncJobs.query.filter(EmailSyncJobs.dtable_uuid.in_(dtable_uuids)).all()
    email_sync_job_list, index_flags = [], {}
    for job in jobs:
        if job.dtable_uuid not in index_flags:
            index_flags[job.dtable_uuid] = len(email_sync_job_list)
            email_sync_job_list.append({
                'dtable_uuid': job.dtable_uuid,
                'job_list': [job.to_dict()]
            })
        else:
            email_sync_job_list[index_flags[job.dtable_uuid]]['job_list'].append(job.to_dict())

    return {'email_sync_job_list': email_sync_job_list}, 200


# list email_sync jobs by dtable_uuid and add new eamil sync job
@app.route('/api/v1/email-sync/jobs/', methods=['GET', 'POST', 'DELETE'])
@cross_origin()
def email_sync_jobs_api():
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

        name = data.get('name', 'Untitled')
        dtable_uuid = data.get('dtable_uuid')
        api_token = data.get('api_token')
        schedule_detail = data.get('schedule_detail')
        imap_server = data.get('imap_server')
        email_user = data.get('email_user')
        email_password = data.get('email_password')
        email_table_name = data.get('email_table_name')
        link_table_name = data.get('link_table_name')

        if not all([name, dtable_uuid, api_token, imap_server, email_user, email_password, email_table_name, link_table_name, schedule_detail]):
            return {'error_msg': 'Bad request.'}, 400

        try:
            dtable_uuid = UUID(dtable_uuid).hex
        except:
            return {'error_msg': 'dtable_uuid invalid.'}, 400

        if not isinstance(schedule_detail, dict):
            return {'error_msg': 'schedule_detail invalid.'}, 400
        try:
            CronTrigger(**schedule_detail)
        except:
            return {'error_msg': 'schedule_detail error.'}, 400

        error_msg = check_api_token_and_resources(api_token, Config.DTABLE_WEB_SERVICE_URL, dtable_uuid=dtable_uuid, email_table_name=email_table_name, link_table_name=link_table_name)
        if error_msg:
            return {'error_msg': error_msg}, 400

        error_msg = check_imap_account(imap_server, email_user, email_password)
        if error_msg:
            return {'error_msg': 'imap_server email_user email_password invalid, please reset again.'}, 400

        job = EmailSyncJobs(
            name=name,
            dtable_uuid=dtable_uuid,
            api_token=api_token,
            schedule_detail=json.dumps(schedule_detail),
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
@app.route('/api/v1/email-sync/jobs/<job_id>/', methods=['PUT', 'DELETE'])
@cross_origin()
def email_sync_job_api(job_id):
    if request.method == 'PUT':
        try:
            data = json.loads(request.data)
        except:
            return {'error_msg': 'Bad request.'}, 400

        name = data.get('name')
        api_token = data.get('api_token')
        schedule_detail = data.get('schedule_detail')
        imap_server = data.get('imap_server')
        email_user = data.get('email_user')
        email_password = data.get('email_password')
        email_table_name = data.get('email_table_name')
        link_table_name = data.get('link_table_name')

        try:
            job = EmailSyncJobs.query.filter(EmailSyncJobs.id == job_id).first()
            if not job:
                return {'error_msg': 'Job not found.'}, 404
        except Exception as e:
            logger.error('get job: %s error: %s', job_id, e)
            return {'error_msg': 'Internal Server Error.'}, 500

        if name:
            job.name = name
        if api_token:
            job.api_token = api_token
        if schedule_detail:
            if not isinstance(schedule_detail, dict):
                return {'error_msg': 'schedule_detail error.'}, 400
            try:
                CronTrigger(**schedule_detail)
            except:
                return {'error_msg': 'schedule_detail invalid.'}, 400
            job.schedule_detail = json.dumps(schedule_detail)
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

        error_msg = check_api_token_and_resources(job.api_token, Config.DTABLE_WEB_SERVICE_URL, dtable_uuid=job.dtable_uuid, email_table_name=email_table_name, link_table_name=link_table_name)
        if error_msg:
            return {'error_msg': error_msg}, 400

        error_msg = check_imap_account(job.imap_server, job.email_user, job.email_password)
        if error_msg:
            return {'error_msg': 'imap_server, email_user or email_password invalid, please reset again.'}, 400

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
            EmailSyncJobs.query.filter(EmailSyncJobs.id == job_id).delete()
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
@app.route('/api/v1/email-sync/run-job/<job_id>/', methods=['POST'])
@cross_origin()
def sync_emails_api(job_id):
    try:
        data = json.loads(request.data)
    except:
        return {'error_msg': 'Bad request.'}, 400

    send_date_str = data.get('send_date')
    mode = data.get('mode', 'ON').upper()
    dtable_uuid = data.get('dtable_uuid')

    if not dtable_uuid:
        return {'error_msg': 'dtable_uuid invalid.'}, 400
    if mode not in ['ON', 'SINCE']:
        return {'error_msg': 'mode invalid.'}, 400
    
    if not send_date_str:
        send_date_str = str(datetime.now().today())
    else:
        try:
            datetime.strptime(send_date_str, '%Y-%m-%d').date()
        except:
            return {'error_msg': 'send_date invalid.'}, 400

    db_job = EmailSyncJobs.query.filter(EmailSyncJobs.id == job_id).first()
    if not db_job:
        return {'error_msg': 'job not found.'}, 404
    if db_job.dtable_uuid.replace('-', '') != dtable_uuid.replace('-', ''):
        return {'error_msg': 'Permission denied.'}, 403

    imap_server = db_job.imap_server
    email_user = db_job.email_user
    email_password = db_job.email_password
    api_token = db_job.api_token
    dtable_web_service_url = Config.DTABLE_WEB_SERVICE_URL
    email_table_name = db_job.email_table_name
    link_table_name = db_job.link_table_name

    if not all([imap_server, email_user, email_password, api_token, dtable_web_service_url,
                email_table_name, link_table_name]):
        return {'error_msg': 'Bad request.'}, 400

    try:
        sync(send_date_str,
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
        logger.error('sync emails imap_server: %s, email_user: %s, dtable_web_service_url: %s, email table: %s, \
            link table: %s, send_date: %s, mode: %s error: %s', imap_server, email_user, dtable_web_service_url, email_table_name, link_table_name, send_date_str, mode, e)
        return {'error_msg': 'Internal Server Error.'}, 500

    return {'success': True}, 200


# create sync-email tables
@app.route('/api/v1/email-sync/tables/', methods=['POST'])
@cross_origin()
def add_sync_tables_api():
    try:
        data = json.loads(request.data)
    except:
        return {'error_msg': 'Bad request.'}, 400

    api_token = data.get('api_token')
    email_table_name = data.get('email_table_name')
    link_table_name = data.get('link_table_name')
    lang = data.get('lang')

    if not api_token:
        return {'error_msg': 'api_token invalid.'}, 400

    lang = lang if lang else 'en'
    email_table_name = email_table_name if email_table_name else 'Emails'
    link_table_name = link_table_name if link_table_name else 'Threads'

    try:
        seatable = SeaTableAPI(api_token, Config.DTABLE_WEB_SERVICE_URL)
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
                     api_token, Config.DTABLE_WEB_SERVICE_URL, email_table_name, link_table_name, lang, e)
        return {'error_msg': 'Internal Server Error.'}, 500

    return {
        'email_table_name': email_table_name,
        'link_table_name': link_table_name,
    }, 200
