import json
import os
import ssl
import logging
from datetime import datetime

import pytz
from seatable_api import SeaTableAPI
from tzlocal import get_localzone

from config import basedir
from email_sync.email_syncer import ImapMail
from utils.constants import JOB_TYPE_EMAIL_SYNC

logger = logging.getLogger(__name__)


email_sync_tables_file = os.path.join(basedir, 'email_sync', 'tables.json')

if not os.path.isfile(email_sync_tables_file):
    raise Exception(f'{email_sync_tables_file} not found')
with open(email_sync_tables_file, 'r') as f:
    email_sync_tables_dict = json.load(f)


def _check_tables(existed_tables, target_table_name, required_columns):
    """
    check target table is whether in existed_tables or not
    check required_columns are whether all in target table or not, including column type check
    return: table_existed -> bool, required_pass -> bool, error_msg -> str or None
    """
    for table in existed_tables:
        if table.get('name') != target_table_name:
            continue
        for required_column in required_columns:
            required_column_name, required_column_type = required_column['column_name'], required_column['type']
            required_pass = False
            for column in table.get('columns', []):
                if required_column_name == column.get('name') and required_column_type == column.get('type'):
                    required_pass = True
                    break
            if not required_pass:
                return True, required_pass, 'table `%s` has no `%s` column or column type is not \'%s\'' % (
                    target_table_name, required_column_name, required_column_type)
        return True, True, None
    return False, False, 'table %s not found' % target_table_name


def check_api_token_and_resources(api_token, dtable_web_service_url, dtable_uuid=None, job_type=None, detail=None):
    """
    check api token and names
    return invalid message or None
    """
    # check api token
    try:
        seatable = SeaTableAPI(api_token, dtable_web_service_url)
        seatable.auth()
    except Exception as e:
        return 'api_token: %s, invalid' % (api_token,)

    # check dtable_uuid is whether valid or not
    if dtable_uuid and seatable.dtable_uuid.replace('-', '') != dtable_uuid.replace('-', ''):
        return 'api_token: %s is not for dtable_uuid: %s' % (api_token, dtable_uuid)

    if job_type == JOB_TYPE_EMAIL_SYNC and detail:
        email_table_name = detail.get('email_table_name')
        link_table_name = detail.get('link_table_name')
        imap_server = detail.get('imap_server')
        email_user = detail.get('email_user')
        email_password = detail.get('email_password')
        if not email_table_name:
            return 'email_table_name invalid.'
        if not link_table_name:
            return 'link_table_name invalid.'
        if email_table_name == link_table_name:
            return 'email_table_name or link_table_name invalid.'
        if not all([imap_server, email_user, email_password]):
            return 'imap_server, email_user or email_password invalid.'

        # check email-sync tables and columns in them
        metadata = seatable.get_metadata()
        existed_tables = [table for table in metadata.get('tables', [])]
        _, _, error_msg = _check_tables(existed_tables, email_table_name, email_sync_tables_dict['email_table'])
        if error_msg:
            return error_msg
        _, _, error_msg = _check_tables(existed_tables, link_table_name, email_sync_tables_dict['link_table'])
        if error_msg:
            return error_msg

        error_msg = check_imap_account(imap_server, email_user, email_password)
        if error_msg:
            return error_msg

    return None


def check_imap_account(imap_server, email_user, email_password):
    try:
        imap = ImapMail(imap_server, email_user, email_password, ssl_context=ssl.SSLContext(ssl.PROTOCOL_TLSv1_2))
        imap.client()
        imap.login()
    except Exception as e:
        return 'imap_server: %s, email_user: %s, email_password: %s, login error: %s' % (imap_server, email_user, email_password, e)

    return None


def utc_datetime_to_isoformat_timestr(utc_datetime):
    if not utc_datetime:
        return ''
    try:
        # The second way of building a localized time is by converting an existing
        # localized time using the standard astimezone() method:
        utc_datetime = utc_datetime.replace(microsecond=0)
        utc_datetime = pytz.utc.localize(utc_datetime)
        isoformat_timestr = utc_datetime.astimezone(get_localzone()).isoformat()
        return isoformat_timestr
    except Exception as e:
        logger.error(e)
        return ''
