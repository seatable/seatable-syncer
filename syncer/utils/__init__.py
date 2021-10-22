import json
import os
import re
import ssl
import logging

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


def get_table_by_seatable(seatable: SeaTableAPI, table_name=None, table_id=None):
    if not table_name and not table_id:
        return None
    metadata = seatable.get_metadata()
    for table in metadata.get('tables', []):
        if table_name and table_name == table.get('name'):
            return table
        if table_id and table_id == table.get('_id'):
            return table
    return None


def check_table_columns(seatable: SeaTableAPI, table_id, required_columns=None, need_create=False):
    """
    check required columns are whether all are satified

    :param table_id: target table id
    :param required_columns: columns required to check
    :param need_create: if there are not required column(s) exist whether create them or not

    return: target_table -> dict or None, error_msg -> str or None
    """
    target_table = get_table_by_seatable(seatable, table_id=table_id)
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
        seatable.insert_column(target_table.get('name'), column_name, ColumnTypes(column_type), column_data=column_data)

    return target_table, None


def check_email_sync_tables(seatable: SeaTableAPI, email_table_id, link_table_id, lang='en'):
    """
    check tables about email-sync job

    We need specific columns with specific name and specific type exists in email_table and link_table in email-sync job.
    So, we wish tables strictly meet the condition.

    On the other hand, in order to facilitate user operation, we shoud allow the tables users pass don't meet these conditions.
    So, we should help user to check these conditions and create tables/columns to make tables meet there conditions to make programe work.

    Conditions:
        1. NOT email_table and NOT link_table
            1) create email_table and link_table and create required columns that doesn't exist in tables
            2) create the link column between them

        2. email_table and NOT link_table
            1) check email_table and create link_table
            2) create required columns that doesn't exist in tables and the link column between them

        3. NOT email_table and link_table
            1) check link_table and check whether Column `Emails` exists or not
            2) create email_table
            3) create required columns that doesn't exist in tables and the link column between them

        4. email_table and link_table
            1) check email_table and link_table
            2) check Column `Emails` in link_table exists or not
            3) create required columns that doesn't exist in tables

    :param seatable: instance of SeaTableAPI
    :param eamil_table_id: id of the table to fill emails
    :param link_table_id: id of the table to fill threads
    :param lang: user lang for creating table

    :return email_table -> dict or None, link_table -> dict or None, error_body -> dict or None, status_code -> int or None
    """
    if (email_table_id or link_table_id) and email_table_id == link_table_id:
        return {'error_msg': 'email_table_id or link_table_id invalid.'}, 400, None, None

    email_table_link_display_column = 'From'

    def reset_email_table_link_column(seatable: SeaTableAPI, email_table, link_table):
        """
        Rename link column in email table to `Threads`.
        This is a soft function, which will not run when `Threads` column exists in email_table.

        Now only reset column name, display column hasn't been updated
        TODO: reset link column display column
        """
        new_email_table = get_table_by_seatable(seatable, table_id=email_table.get('_id'))
        target_column, target_index = None, None
        for index, col in enumerate(new_email_table.get('columns')):
            if col.get('name') == 'Threads':
                logger.info('`Threads` column exists in email table')
                return new_email_table
            if col.get('type') != ColumnTypes.LINK.value:
                continue
            if col['data'].get('table_id') != link_table.get('_id') or col['data'].get('other_table_id') != email_table.get('_id'):
                continue
            target_column = col
            target_index = index
        seatable.rename_column(email_table.get('name'), target_column.get('key'), 'Threads')
        new_email_table['columns'][target_index]['name'] = 'Threads'
        return new_email_table

    if not email_table_id and not link_table_id:
        # create email table
        email_table = create_table(seatable, 'Emails', lang=lang)
        # create link table
        link_table = create_table(seatable, 'Threads', lang=lang)
        # create email table columns
        email_table, error_msg = check_table_columns(seatable, email_table.get('_id'), email_sync_tables_dict['email_table'], True)
        if error_msg:
            return None, None, {'error_msg': error_msg}, 400
        # create link table columns
        link_table, error_msg = check_table_columns(seatable, link_table.get('_id'), email_sync_tables_dict['link_table'], True)
        if error_msg:
            return None, None, {'error_msg': error_msg}, 400
        # create link column between both tables
        seatable.insert_column(link_table.get('name'), 'Emails', ColumnTypes.LINK, column_data={
            'table': link_table.get('name'),
            'other_table': email_table.get('name'),
            'display_column_name': email_table_link_display_column
        })
        # reset link column in email_table
        email_table = reset_email_table_link_column(seatable, email_table, link_table)
    elif email_table_id and not link_table_id:
        # check email table
        email_table, error_msg = check_table_columns(seatable, email_table_id)
        if error_msg:
            return None, None, {'error_msg': error_msg}, 404
        # create link table
        link_table = create_table(seatable, 'Threads', lang=lang)
        # create email table columns
        email_table, error_msg = check_table_columns(seatable, email_table.get('_id'), email_sync_tables_dict['email_table'], True)
        if error_msg:
            return None, None, {'error_msg': error_msg}, 400
        # create link table columns
        link_table, error_msg = check_table_columns(seatable, link_table.get('_id'), email_sync_tables_dict['link_table'], True)
        if error_msg:
            return None, None, {'error_msg': error_msg}, 400
        # create link column between both tables
        seatable.insert_column(link_table.get('name'), 'Emails', ColumnTypes.LINK, column_data={
            'table': link_table.get('name'),
            'other_table': email_table.get('name'),
            'display_column_name': email_table_link_display_column
        })
        # reset link column in email_table
        email_table = reset_email_table_link_column(seatable, email_table, link_table)
    elif not email_table_id and link_table_id:
        # check link table
        link_table, error_msg = check_table_columns(seatable, link_table_id)
        if error_msg:
            return None, None, {'error_msg': error_msg}, 404
        # check Emails column exists or not before create email table
        for col in link_table.get('columns'):
            if col.get('name') == 'Emails':
                return None, None, {'error_msg': 'Column `Emails` exists.'}, 400
        if error_msg:
            return None, None, {'error_msg': error_msg}, 404
        # create email table
        email_table = create_table(seatable, 'Emails', lang=lang)
        # create email table columns
        email_table, error_msg = check_table_columns(seatable, email_table.get('_id'), email_sync_tables_dict['email_table'], True)
        if error_msg:
            return None, None, {'error_msg': error_msg}, 400
        # create link table columns
        link_table, error_msg = check_table_columns(seatable, link_table.get('_id'), email_sync_tables_dict['link_table'], True)
        if error_msg:
            return None, None, {'error_msg': error_msg}, 400
        # create link column between both tables
        seatable.insert_column(link_table.get('name'), 'Emails', ColumnTypes.LINK, column_data={
            'table': link_table.get('name'),
            'other_table': email_table.get('name'),
            'display_column_name': email_table_link_display_column
        })
        # reset link column in email_table
        email_table = reset_email_table_link_column(seatable, email_table, link_table)
    else:
        # check email table
        email_table, error_msg = check_table_columns(seatable, email_table_id)
        if error_msg:
            return None, None, {'error_msg': error_msg}, 404
        # check link table
        link_table, error_msg = check_table_columns(seatable, link_table_id)
        if error_msg:
            return None, None, {'error_msg': error_msg}, 404
        # create link column between both tables
        link_column_exists = False
        for col in link_table.get('columns'):
            if col.get('name') != 'Emails':
                continue
            if col.get('type') != ColumnTypes.LINK.value:
                return None, None, {'error_msg': 'Column `Emails` exists.'}, 400
            if col['data'].get('other_table_id') != email_table.get('_id'):
                return None, None, {'error_msg': 'Column `Emails` exists and its link column is not for email table.'}, 400
            link_column_exists = True
            break
        # create email table columns
        email_table, error_msg = check_table_columns(seatable, email_table.get('_id'), email_sync_tables_dict['email_table'], True)
        if error_msg:
            return None, None, {'error_msg': error_msg}, 400
        # create link table columns
        link_table, error_msg = check_table_columns(seatable, link_table.get('_id'), email_sync_tables_dict['link_table'], True)
        if error_msg:
            return None, None, {'error_msg': error_msg}, 400
        if not link_column_exists:
            seatable.insert_column(link_table.get('name'), 'Emails', ColumnTypes.LINK, column_data={
                'table': link_table.get('name'),
                'other_table': email_table.get('name'),
                'display_column_name': email_table_link_display_column
            })
        # reset link column in email_table
        email_table = reset_email_table_link_column(seatable, email_table, link_table)

    return email_table, link_table, None, None


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
        logger.exception(e)
        logger.error('imap_server: %s, email_user: %s, email_password: %s, login error: %s' % (imap_server, email_user, email_password, e))
        return 'email login error'

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
