import json
import os
import ssl
import logging

import pytz
from seatable_api import SeaTableAPI
from tzlocal import get_localzone

from config import basedir
from email_sync.email_syncer import ImapMail

logger = logging.getLogger(__name__)


table_file = os.path.join(basedir, 'email_sync', 'tables.json')

if not os.path.isfile(table_file):
    raise Exception(f'{table_file} not found')
with open(table_file, 'r') as f:
    required_tables_dict = json.load(f)


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


def check_api_token_and_resources(api_token, dtable_web_service_url, dtable_uuid=None, email_table_name=None, link_table_name=None):
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

    # check email-sync tables and columns in them
    if email_table_name or link_table_name:
        metadata = seatable.get_metadata()
        existed_tables = [table for table in metadata.get('tables', [])]
        for table in existed_tables:
            if email_table_name and table.get('name') == email_table_name:
                _, _, error_msg = _check_tables(existed_tables, email_table_name, required_tables_dict['email_table'])
                if error_msg:
                    return error_msg
            if link_table_name and table.get('name') == link_table_name:
                _, _, error_msg = _check_tables(existed_tables, link_table_name, required_tables_dict['link_table'])
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
