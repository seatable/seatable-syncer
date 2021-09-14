from datetime import datetime

from email_sync.email_syncer import sync


def email_sync_job_func(
    api_token,
    dtable_web_service_url,
    email_table_name,
    link_table_name,
    email_server,
    email_user,
    email_password
):
    sync(
        str(datetime.today().date()),
        api_token,
        dtable_web_service_url,
        email_table_name,
        link_table_name,
        email_server,
        email_user,
        email_password,
        mode='ON'
    )
