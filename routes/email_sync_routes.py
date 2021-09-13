import json
import logging
import os
from datetime import datetime

from flask import current_app as app, request
from flask_cors import cross_origin
from seatable_api import SeaTableAPI
from seatable_api.constants import ColumnTypes

from config import basedir
from email_sync.email_syncer import sync

logger = logging.getLogger(__name__)

table_file = os.path.join(basedir, 'email_sync', 'tables.json')

if not os.path.isfile(table_file):
    raise Exception(f'{table_file} not found')
with open(table_file, 'r') as f:
    tables_dict = json.load(f)


# list sync-emails jobs
# add sync-emails job
# update sync-emails job
# remove sync-emails job


@app.route('/', methods=['GET'])
def index():
    return {'success': True}, 200


# sync emails
@app.route('/sync-emails/', methods=['POST'])
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
@app.route('/sync-email-tables/', methods=['POST'])
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
