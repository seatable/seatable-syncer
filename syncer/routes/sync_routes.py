import json
import logging
from datetime import datetime

from apscheduler.triggers.cron import CronTrigger
from flask import current_app as app, request
from flask_cors import cross_origin
from seatable_api import SeaTableAPI
from seatable_api.constants import ColumnTypes

from app import db
from config import Config
from email_sync.email_syncer import sync as sync_emails
from models.sync_models import SyncJobs
from scheduler import scheduler_jobs_manager
from utils import check_api_token_and_resources, email_sync_tables_dict, check_email_sync_tables, utc_datetime_to_isoformat_timestr, check_imap_account
from utils.constants import JOB_TYPE_EMAIL_SYNC

logger = logging.getLogger(__name__)


@app.route('/api/v1/sync-jobs/by-dtables/', methods=['POST'])
@cross_origin()
def sync_jobs_by_dtables_api():
    try:
        data = json.loads(request.data)
    except Exception as e:
        return {'error_msg': 'Bad request.'}, 400

    dtable_uuids = data.get('dtable_uuids')
    if not dtable_uuids or not isinstance(dtable_uuids, list):
        return {'error_msg': 'dtable_uuids invalid.'}, 400
    dtable_uuids = [dtable_uuid.replace('-', '') for dtable_uuid in dtable_uuids]

    try:
        jobs = SyncJobs.query.filter(SyncJobs.dtable_uuid.in_(dtable_uuids)).all()
    except Exception as e:
        logger.error('get jobs by dtablels: %s error: %s', dtable_uuids, e)
        return {'error_msg': 'Internal Server Error.'}, 500

    dtable_sync_jobs_dict = {}
    for job in jobs:
        if job.dtable_uuid not in dtable_sync_jobs_dict:
            dtable_sync_jobs_dict[job.dtable_uuid] = [job.to_dict()]
        else:
            dtable_sync_jobs_dict[job.dtable_uuid].append(job.to_dict())

    return {'dtable_sync_jobs': dtable_sync_jobs_dict}, 200


@app.route('/api/v1/dtables/<dtable_uuid>/sync-jobs/', methods=['POST', 'DELETE'])
@cross_origin()
def sync_jobs_api(dtable_uuid):
    if request.method == 'POST':
        try:
            data = json.loads(request.data)
        except:
            return {'error_msg': 'Bad request.'}, 400

        dtable_uuid = dtable_uuid.replace('-', '')

        name = data.get('name', 'Untitled')
        api_token = data.get('api_token')
        trigger_detail = data.get('trigger_detail')
        job_type = data.get('job_type')
        detail = data.get('detail')
        lang = data.get('lang')
        if not all([name, api_token, trigger_detail, detail, job_type]):
            return {'error_msg': 'Bad request.'}, 400

        if not isinstance(trigger_detail, dict):
            return {'error_msg': 'trigger_detail invalid.'}, 400
        try:
            CronTrigger(**trigger_detail)
        except:
            return {'error_msg': 'trigger_detail invalid.'}, 400

        if not isinstance(detail, dict):
            return {'error_msg': 'detail invalid.'}, 400

        if job_type not in [JOB_TYPE_EMAIL_SYNC]:
            return {'error_msg': 'job_type invalid.'}, 400

        try:
            seatable = SeaTableAPI(api_token, Config.DTABLE_WEB_SERVICE_URL)
            seatable.auth()
        except Exception as e:
            logger.error('seatable auth error: %s', e)
            return {'error_msg': 'api_token invalid.'}, 400

        if job_type == JOB_TYPE_EMAIL_SYNC:
            email_table_id = detail.get('email_table_id')
            link_table_id = detail.get('link_table_id')
            imap_server = detail.get('imap_server')
            email_user = detail.get('email_user')
            email_password = detail.get('email_password')
            if not all([imap_server, email_user, email_password]):
                return {'error_msg': 'imap_server or email_user or email_password invalid.'}, 400
            error_msg = check_imap_account(imap_server, email_user, email_password)
            if error_msg:
                return {'error_msg': error_msg}, 400

            try:
                email_table, link_table, error_body, status_code = check_email_sync_tables(seatable, email_table_id, link_table_id, lang=lang)
            except Exception as e:
                logger.exception(e)
                logger.error('check email sync tables error: %s', e)
                return {'error_msg': 'Internal Server Error.'}, 500

            if error_body and status_code:
                return error_body, status_code

            detail.update({
                'email_table_id': email_table.get('_id'),
                'link_table_id': link_table.get('_id')
            })

        error_msg = check_api_token_and_resources(api_token, Config.DTABLE_WEB_SERVICE_URL, dtable_uuid=dtable_uuid, job_type=job_type, detail=detail)
        if error_msg:
            return {'error_msg': error_msg}, 400

        job = SyncJobs(
            name=name,
            dtable_uuid=dtable_uuid,
            api_token=api_token,
            trigger_detail=json.dumps(trigger_detail),
            job_type=job_type,
            detail=json.dumps(detail)
        )
        try:
            db.session.add(job)
            db.session.commit()
        except Exception as e:
            logger.error('create sync job error: %s', e)
            return {'error_msg': 'Internal Server Error.'}, 500

        try:
            scheduler_jobs_manager.add_job(job)
        except Exception as e:
            logger.exception(e)
            logger.error('add job: %s to scheduler error: %s', job, e)

        return {'sync_job': job.to_dict()}, 200
    else:
        dtable_uuid = dtable_uuid.replace('-', '')
        try:
            jobs = SyncJobs.query.filter(SyncJobs.dtable_uuid == dtable_uuid).all()
        except Exception as e:
            logger.error('query dtable: %s jobs error: %s', dtable_uuid, e)
            return {'error_msg': 'Internal Server Error.'}, 500

        for job in jobs:
            try:
                scheduler_jobs_manager.remove_job(job.job_id)
            except Exception as e:
                logger.error('remove job: %s error: %s', job, e)

        try:
            [db.session.delete(job) for job in jobs]
            db.session.commit()
        except Exception as e:
            logger.error('remove dtable: %s db jobs error: %s', dtable_uuid, e)
            return {'error_msg': 'Internal Server Error.'}, 500

        return {'success': True}, 200


@app.route('/api/v1/dtables/<dtable_uuid>/sync-jobs/<job_id>/', methods=['PUT', 'DELETE'])
@cross_origin()
def sync_job_api(dtable_uuid, job_id):
    if request.method == 'PUT':
        try:
            data = json.loads(request.data)
        except:
            return {'error_msg': 'Bad request.'}, 400

        dtable_uuid = dtable_uuid.replace('-', '')

        name = data.get('name')
        api_token = data.get('api_token')
        trigger_detail = data.get('trigger_detail')
        detail = data.get('detail')
        lang = data.get('lang')

        if trigger_detail:
            if not isinstance(trigger_detail, dict):
                return {'error_msg': 'trigger_detail invalid.'}, 400
            try:
                CronTrigger(**trigger_detail)
            except:
                return {'error_msg': 'trigger_detail invalid.'}, 400

        if detail and not isinstance(detail, dict):
            return {'error_msg': 'detail invalid.'}, 400

        try:
            job = SyncJobs.query.filter(SyncJobs.id == job_id, SyncJobs.dtable_uuid == dtable_uuid.replace('-', '')).first()
        except Exception as e:
            logger.error('query job: %s error: %s', job_id, e)
            return {'error_msg': 'Internal Server Error.'}, 500

        if not job:
            return {'error_msg': 'Job not found.'}, 404

        check_api_token = api_token if api_token else job.api_token
        try:
            seatable = SeaTableAPI(check_api_token, Config.DTABLE_WEB_SERVICE_URL)
            seatable.auth()
        except Exception as e:
            logger.error('seatable auth error: %s', e)
            return {'error_msg': 'api_token invalid.'}, 400

        if detail:
            if job.job_type == JOB_TYPE_EMAIL_SYNC:
                email_table_id = detail.get('email_table_id')
                link_table_id = detail.get('link_table_id')
                imap_server = detail.get('imap_server')
                email_user = detail.get('email_user')
                email_password = detail.get('email_password')
                if not all([imap_server, email_user, email_password]):
                    return {'error_msg': 'imap_server or email_user or email_password invalid.'}, 400
                error_msg = check_imap_account(imap_server, email_user, email_password)
                if error_msg:
                    return {'error_msg': error_msg}, 400

                try:
                    email_table, link_table, error_body, status_code = check_email_sync_tables(seatable, email_table_id, link_table_id, lang=lang)
                except Exception as e:
                    logger.exception(e)
                    logger.error('update job check email sync tables error: %s', e)
                    return {'error_msg': 'Internal Server Error.'}, 500
                if error_body and status_code:
                    return error_body, status_code
                detail.update({
                    'email_table_id': email_table.get('_id'),
                    'link_table_id': link_table.get('_id')
                })

        if name:
            job.name = name
        if api_token:
            job.api_token = api_token
        if trigger_detail:
            job.trigger_detail = json.dumps(trigger_detail)
        if detail:
            final_detail = json.loads(job.detail)
            final_detail.update(detail)
            job.detail = json.dumps(final_detail)

        try:
            db.session.add(job)
            db.session.commit()
        except Exception as e:
            logger.error('update job: %s error: %s', job_id, e)
            return {'error_msg': 'Internal Server Error.'}, 500

        try:
            scheduler_jobs_manager.update_job(job)
        except Exception as e:
            logger.exception(e)
            logger.error('update job: %s in scheduler error: %s', job_id, e)

        return {'sync_job': job.to_dict()}, 200

    if request.method == 'DELETE':
        try:
            job = SyncJobs.query.filter(SyncJobs.id == job_id, SyncJobs.dtable_uuid == dtable_uuid.replace('-', '')).first()
        except Exception as e:
            logger.error('get job: %s error %s', job_id, e)
            return {'error_msg': 'Internal Server Error.'}, 500

        if not job:
            return {'success': True}, 200

        try:
            db.session.delete(job)
            db.session.commit()
        except Exception as e:
            logger.error('remove job: %s error: %s', job, e)
            return {'error_msg': 'Internal Server Error.'}, 500

        try:
            scheduler_jobs_manager.remove_job(job.job_id)
        except Exception as e:
            logger.error('remove job from scheduler error: %s', e)

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

    metadata = seatable.get_metadata()
    existed_tables = [table['name'] for table in metadata.get('tables')]
    if email_table_name in existed_tables:
        return {'error_msg': '%s exists.' % email_table_name}, 400
    if link_table_name in existed_tables:
        return {'error_msg': '%s exists.' % link_table_name}, 400

    try:
        # create emails table and columns
        email_table = seatable.add_table(email_table_name, lang=lang)
        columns = email_sync_tables_dict.get('email_table', [])
        for index, col in enumerate(columns):
            if index == 0:
                seatable.rename_column(email_table_name, '0000', col.get('column_name'))
                continue
            col_name, col_type = col.get('column_name'), col.get('type')
            seatable.insert_column(email_table_name, col_name, ColumnTypes(col_type), column_data=col.get('data'))

        # create links table and columns
        link_table = seatable.add_table(link_table_name, lang=lang)
        columns = email_sync_tables_dict.get('link_table', [])
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


@app.route('/api/v1/sync-jobs/<job_id>/run/', methods=['POST'])
@cross_origin()
def run_sync_job_api(job_id):
    try:
        data = json.loads(request.data)
    except:
        return {'error_msg': 'Bad request.'}, 400

    db_job = SyncJobs.query.filter(SyncJobs.id == job_id).first()
    if not db_job:
        return {'error_msg': 'job not found.'}, 404

    if db_job.job_type == 'email-sync':
        send_date_str = data.get('send_date')
        mode = data.get('mode', 'ON').upper()

        if mode not in ['ON', 'SINCE']:
            return {'error_msg': 'mode invalid.'}, 400
        
        if not send_date_str:
            send_date_str = str(datetime.now().today())
        else:
            try:
                datetime.strptime(send_date_str, '%Y-%m-%d').date()
            except:
                return {'error_msg': 'send_date invalid.'}, 400

        detail = json.loads(db_job.detail)
        imap_server = detail['imap_server']
        email_user = detail['email_user']
        email_password = detail['email_password']
        api_token = db_job.api_token
        dtable_web_service_url = Config.DTABLE_WEB_SERVICE_URL
        email_table_id = detail['email_table_id']
        link_table_id = detail['link_table_id']

        if not all([imap_server, email_user, email_password, api_token, dtable_web_service_url,
                    email_table_id, link_table_id]):
            return {'error_msg': 'Bad request.'}, 400

        try:
            seatable = SeaTableAPI(api_token, dtable_web_service_url)
            seatable.auth()
        except Exception as e:
            logger.error('job: %s auth error: %s' % (db_job.id, e))
            return {'error_msg': 'Internal Server Error.'}, 500

        email_table_name, link_table_name = None, None
        for table in seatable.get_metadata().get('tables', []):
            if email_table_id == table.get('_id'):
                email_table_name = table.get('name')
            if link_table_id == table.get('_id'):
                link_table_name = table.get('name')

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
            logger.error('sync emails imap_server: %s, email_user: %s, dtable_web_service_url: %s, email table: %s, \
                link table: %s, send_date: %s, mode: %s error: %s', imap_server, email_user, dtable_web_service_url, email_table_name, link_table_name, send_date_str, mode, e)
            return {'error_msg': 'Internal Server Error.'}, 500

        last_trigger_time = datetime.utcnow()

        try:
            db_job.last_trigger_time = last_trigger_time
            db.session.add(db_job)
            db.session.commit()
        except Exception as e:
            logger.error('update job: %s last trigger time error: %s', db_job, e)

    return {
        'success': True,
        'last_trigger_time': utc_datetime_to_isoformat_timestr(last_trigger_time),
        'job_id': db_job.id
    }, 200
