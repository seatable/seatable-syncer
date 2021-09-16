import logging
import ssl
from datetime import datetime

from seatable_api import SeaTableAPI

from email_sync.email_syncer import sync, ImapMail
from utils import check_api_token_and_resources, check_imap_account
from utils.exceptions import SchedulerJobInvalidException

logger = logging.getLogger(__name__)


def email_sync_job_func(
    api_token,
    dtable_web_service_url,
    email_table_name,
    link_table_name,
    email_server,
    email_user,
    email_password
):
    # check seatable api token
    error_msg = check_api_token_and_resources(api_token, dtable_web_service_url, table_names=[email_table_name, link_table_name])
    if error_msg:
        raise SchedulerJobInvalidException(error_msg)

    # check email login
    error_msg = check_imap_account(email_server, email_user, email_password)
    if error_msg:
        raise SchedulerJobInvalidException(error_msg)

    # sync
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
