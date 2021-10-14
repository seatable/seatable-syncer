import logging
from datetime import datetime

from email_sync.email_syncer import sync
from utils import check_api_token_and_resources, check_imap_account
from utils.exceptions import SchedulerJobInvalidException

logger = logging.getLogger(__name__)


def email_sync_job_func(
    api_token,
    dtable_web_service_url,
    detail
):
    # check seatable api token
    error_msg = check_api_token_and_resources(api_token, dtable_web_service_url, job_type='email-sync', detail=detail)
    if error_msg:
        raise SchedulerJobInvalidException(error_msg)

    imap_server = detail['imap_server']
    email_user = detail['email_user']
    email_password = detail['email_password']
    email_table_name = detail['email_table_name']
    link_table_name = detail['link_table_name']

    # check email login
    error_msg = check_imap_account(imap_server, email_user, email_password)
    if error_msg:
        raise SchedulerJobInvalidException(error_msg)

    # sync
    sync(
        str(datetime.today().date()),
        api_token,
        dtable_web_service_url,
        email_table_name,
        link_table_name,
        imap_server,
        email_user,
        email_password,
        mode='ON'
    )
