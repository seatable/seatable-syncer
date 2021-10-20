import json
import os
import re
import ssl
import logging
from datetime import datetime

import pytz
from seatable_api import SeaTableAPI
from seatable_api.constants import ColumnTypes
from tzlocal import get_localzone

from config import basedir, Config
from email_sync.email_syncer import ImapMail
from utils.constants import JOB_TYPE_EMAIL_SYNC

logger = logging.getLogger(__name__)


email_sync_tables_file = os.path.join(basedir, 'email_sync', 'tables.json')

if not os.path.isfile(email_sync_tables_file):
    raise Exception(f'{email_sync_tables_file} not found')
with open(email_sync_tables_file, 'r') as f:
    email_sync_tables_dict = json.load(f)


def get_non_duplicated_str(existed_strs, target_str):
    if not existed_strs:
        return target_str
    nos = []
    for s in existed_strs:
        re_target = r'%s\d+' % (re.escape(target_str),)
        if not re.match(re_target, s):
            continue
        nos.append(int(s[len(target_str):]))
    if not nos:
        return target_str + '1'
    nos.sort()
    for index, no in enumerate(nos, start=1):
        if index != no:
            return '%s%s' % (target_str, index)
    return '%s%s' % (target_str, nos[-1] + 1)


def create_table(seatable: SeaTableAPI, table_name, lang='en'):
    """
    create table named table_name

    return table -> dict
    """
    metadata = seatable.get_metadata()
    fake_duplicated_table_names = [table.get('name') for table in metadata.get('tables') if table.get('name').startswith(table_name)]
    table_name = get_non_duplicated_str(fake_duplicated_table_names, table_name)
    return seatable.add_table(table_name, lang=lang)


def check_table_columns(seatable: SeaTableAPI, table_id, required_columns=None, need_create=False):
    """
    check required columns are whether all are satified

    :param table_id: target table id
    :param required_columns: columns required to check
    :param need_create: if there are not required column(s) exist whether create them or not

    return: target_table -> dict or None, error_msg -> str or None
    """
    metadata = seatable.get_metadata()
    target_table = None
    for table in metadata.get('tables'):
        if table.get('_id') == table_id:
            target_table = table
            break
    if not target_table:
        return None, 'Table %s not found.' % (table_id,)

    if not required_columns:
        return target_table, None

    # check all required columns exist or not
    columns_to_be_created = []
    for required_column in required_columns:
        required_column_name, required_column_type = required_column['column_name'], required_column['type']
        required_pass = False
        for col in target_table.get('columns'):
            if col.get('name') != required_column_name:
                continue
            if col.get('type') != required_column_type:
                return target_table, 'Type of column %s is not %s' % (required_column_name, required_column_type)
            else:
                required_pass = True
                break
        if required_pass:
            continue
        else:
            if need_create:
                columns_to_be_created.append(required_column)
            else:
                return target_table, 'Column %s not exists'

    if not need_create:
        return target_table, None

    # create columns
    for column in columns_to_be_created:
        column_type = column.get('type')
        column_name = column.get('column_name')
        column_data = column.get('data')
        print('column_type, column_name, column_data: ', column_type, column_name, column_data)
        seatable.insert_column(target_table.get('name'), column_name, ColumnTypes(column_type), column_data=column_data)

    return target_table, None


def check_tables(existed_tables, target_table_id, required_columns):
    """
    check target table is whether in existed_tables or not
    check required_columns are whether all in target table or not, including column type check
    return: table_existed -> bool, required_pass -> bool, error_msg -> str or None
    """
    for table in existed_tables:
        if table.get('_id') != target_table_id:
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
                    target_table_id, required_column_name, required_column_type)
        return True, True, None
    return False, None, 'table %s not found' % target_table_id


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
        email_table_id = detail.get('email_table_id')
        link_table_id = detail.get('link_table_id')
        imap_server = detail.get('imap_server')
        email_user = detail.get('email_user')
        email_password = detail.get('email_password')
        if not email_table_id:
            return 'email_table_id invalid.'
        if not link_table_id:
            return 'link_table_id invalid.'
        if email_table_id == link_table_id:
            return 'email_table_id or link_table_id invalid.'
        if not all([imap_server, email_user, email_password]):
            return 'imap_server, email_user or email_password invalid.'

        # check email-sync tables and columns in them
        metadata = seatable.get_metadata()
        existed_tables = [table for table in metadata.get('tables', [])]
        _, _, error_msg = check_tables(existed_tables, email_table_id, email_sync_tables_dict['email_table'])
        if error_msg:
            return error_msg
        _, _, error_msg = check_tables(existed_tables, link_table_id, email_sync_tables_dict['link_table'])
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
