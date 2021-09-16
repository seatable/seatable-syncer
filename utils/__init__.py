import ssl

from seatable_api import SeaTableAPI

from email_sync.email_syncer import ImapMail


def check_api_token_and_resources(api_token, dtable_web_service_url, dtable_uuid=None, table_names=None):
    """
    check api token and names
    return invalid message or None
    """
    try:
        seatable = SeaTableAPI(api_token, dtable_web_service_url)
        seatable.auth()
    except Exception as e:
        return 'api_token: %s, dtable_web_service_url: %s' % (api_token, dtable_web_service_url)

    if dtable_uuid and seatable.dtable_uuid.replace('-', '') != dtable_uuid.replace('-', ''):
        return 'api_token: %s is not for dtable_uuid: %s' % (api_token, dtable_uuid)

    if table_names and isinstance(table_names, list):
        metadata = seatable.get_metadata()
        existed_table_names = [table.get('name') for table in metadata.get('tables', [])]
        for table_name in table_names:
            if table_name not in existed_table_names:
                return 'table: %s not found' % (table_name,)

    return None


def check_imap_account(imap_server, email_user, email_password):
    try:
        imap = ImapMail(imap_server, email_user, email_password, ssl_context=ssl.SSLContext(ssl.PROTOCOL_TLSv1_2))
        imap.client()
        imap.login()
    except Exception as e:
        return 'imap_server: %s, email_user: %s, email_password: %s, login error: %s' % (imap_server, email_user, email_password, e)

    return None
