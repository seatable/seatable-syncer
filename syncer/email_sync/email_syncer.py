import argparse
import logging
import ssl
import sys
import time
from datetime import datetime, timedelta
from uuid import uuid4

from seatable_api import SeaTableAPI

from imapclient import IMAPClient
from email.parser import Parser
from email.header import decode_header
from email.utils import parseaddr, parsedate_to_datetime, decode_rfc2231, decode_params
from tzlocal import get_localzone


logging.basicConfig(
    filename='email_sync.log',
    filemode='a',
    format="[%(asctime)s] [%(levelname)s] %(name)s:%(lineno)s %(funcName)s %(message)s",
    level=logging.INFO
)

logger = logging.getLogger(__name__)


class ImapMail(object):
    def __init__(self, serveraddress, user, passwd, port=None, timeout=None, ssl_context=None):
        self.serveraddress = serveraddress
        self.user = user
        self.passwd = passwd
        self.port = port
        self.timeout = timeout
        self.ssl_context = ssl_context
        self.server = None

    def client(self):
        self.server = IMAPClient(self.serveraddress, self.port, timeout=self.timeout, ssl_context=self.ssl_context)
        if '163.com' in self.serveraddress:
            self.server.id_({"name": "IMAPClient", "version": "2.1.0"})
        logger.info('connected success')

    def login(self):
        self.server.login(self.user, self.passwd)

    @staticmethod
    def decode_str(s):
        value, charset = decode_header(s)[0]
        if charset:
            value = value.decode(charset)
        return value

    def get_content(self, msg):
        content = ''
        for part in msg.walk():
            if part.is_multipart():
                continue
            # if attachment continue
            if part.get_filename() is not None:
                continue

            content_type = part.get_content_type()
            if content_type == 'text/plain':
                charset = part.get_content_charset()
                if charset:
                    try:
                        content = part.get_payload(decode=True).decode(charset)
                    except LookupError:
                        content = part.get_payload()
                        logger.info('unknown encoding: %s' % charset)
                    except UnicodeDecodeError:
                        content = part.get_payload()
                        logger.info('%s can\'t decode unicode' % charset)
                    except Exception as e:
                        logger.error(e)
                else:
                    content = part.get_payload()
        return content

    def get_attachments(self, msg):
        file_list = []
        for part in msg.walk():
            filename = part.get_filename()
            if filename is not None:
                filename = self.decode_str(filename)
                data = part.get_payload(decode=True)
                file_list.append({'file_name': filename, 'file_data': data})
        return file_list

    def get_email_header(self, msg):
        header_info = {}
        for header in ['From', 'To', 'CC', 'Subject', 'Message-ID', 'In-Reply-To', 'Date']:
            value = msg.get(header, '')
            if value:
                if header == 'Subject':
                    value = self.decode_str(value)
                elif header == 'Date':
                    value = parsedate_to_datetime(value).astimezone(get_localzone()).isoformat().replace('T', ' ')[:-6]
                elif header in ['From', 'To', 'CC']:
                    value = ','.join([parseaddr(val)[1] for val in value.split(',')])
                elif header in ['Message-ID', 'In-Reply-To']:
                    # remove '<' and '>'
                    value = value.strip().lower()[1:-1]
            header_info[header] = value

        return header_info

    def get_email_results(self, send_date, mode='ON'):
        td = timedelta(days=1)
        before_send_date = send_date - td
        after_send_date = send_date + td
        if mode == 'ON':
            today_results = self.server.search(['ON', send_date])
            before_results = self.server.search(['ON', before_send_date])
            after_results = self.server.search(['ON', after_send_date])
            return before_results + today_results + after_results
        elif mode == 'SINCE':
            return self.server.search(['SINCE', before_send_date])
        return []

    def gen_email_dict(self, mail, send_date, mode):
        email_dict = {}
        msg_dict = self.server.fetch(mail, ['BODY[]'])
        mail_body = msg_dict[mail][b'BODY[]']
        msg = Parser().parsestr(mail_body.decode())

        header_info = self.get_email_header(msg)
        send_time = header_info.get('Date')
        send_time = datetime.strptime(send_time, '%Y-%m-%d %H:%M:%S')

        if mode == 'ON' and send_time.date() != send_date:
            return
        if mode == 'SINCE' and send_time.date() < send_date:
            return

        if not header_info['From']:
            logger.warning('account: %s message: %s no sender!', self.user, mail)
        if not header_info['To']:
            logger.warning('account: %s message: %s no recipient!', self.user, mail)
        content = self.get_content(msg)
        email_dict['Content'] = content
        email_dict['Attachment'] = self.get_attachments(msg)
        email_dict['UID'] = str(mail)
        email_dict['From'] = header_info.get('From')
        email_dict['To'] = header_info.get('To')
        email_dict['Subject'] = header_info.get('Subject')
        email_dict['Message ID'] = header_info.get('Message-ID')
        email_dict['Reply to Message ID'] = header_info.get('In-Reply-To')
        email_dict['cc'] = header_info.get('CC')
        email_dict['Date'] = header_info.get('Date')

        return email_dict

    def get_email_list(self, send_date, mode='ON'):
        send_date = datetime.strptime(send_date, '%Y-%m-%d').date()
        total_email_list = []
        for send_box in ['INBOX', 'Sent Items']:
            logger.debug('start to get user: %s emails from box: %s', self.user, send_box)
            try:
                self.server.select_folder(send_box, readonly=True)
            except Exception as e:
                logger.warning('user: %s select email folder: %s error: %s', self.user, send_box, e)
                continue
            results = self.get_email_results(send_date, mode=mode)
            for mail in results:
                try:
                    email_dict = self.gen_email_dict(mail, send_date, mode)
                    if email_dict:
                        total_email_list.append(email_dict)
                except Exception as e:
                    logger.exception(e)
                    logger.error('parse email error: %s', e)
        return total_email_list

    def close(self):
        self.server.logout()


def fixed_sql_query(seatable, sql):
    try:
        return seatable.query(sql)
    except TypeError:
        return []


def query_table_rows(seatable, table_name, fields='*', conditions='', all=True, limit=None):
    where_conditions = f"where {conditions}" if conditions else ''
    if all:
        result = fixed_sql_query(seatable, f"select count(*) from `{table_name}` {where_conditions}")[0]
        limit = result['COUNT(*)']
        if limit == 0:
            return []
    else:
        limit = 100 if not limit else limit
    return fixed_sql_query(seatable, f"select {fields} from `{table_name}` {where_conditions} limit {limit}")


def str_2_datetime(s: str):
    if '+' in s:
        s = s[:s.find('+')]
    formats = ['%Y-%m-%dT%H:%M:%S', '%Y-%m-%dT%H:%M:%SZ', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%Y-%m-%d']
    for f in formats:
        try:
            return datetime.strptime(s, f)
        except:
            pass
    raise Exception(f"date {s} can't be transfered to datetime")


def get_emails(send_date, email_server, email_user, email_password, imap: ImapMail=None, mode='ON'):
    """
    return: email list, [email1, email2...], email is without thread id
    """
    if not imap:
        imap = ImapMail(email_server, email_user, email_password, ssl_context=ssl.SSLContext(ssl.PROTOCOL_TLSv1_2))
        imap.client()
        logger.debug('imap: %s client successfully!', email_server)
        imap.login()
        logger.debug('email_server: %s email_user: %s, password: %s login imap client successfully!', email_server, email_user, email_password)
    try:
        email_list = imap.get_email_list(send_date, mode=mode)
    except Exception as e:
        logger.exception(e)
    else:
        return email_list
    finally:
        imap.close()
    return []


def update_email_thread_ids(seatable, email_table_name, send_date, email_list):
    """
    return: email list, [email1, email2...], email is with thread id
    """
    # get email rows in last 30 days and generate message-thread dict {`Message ID`: `Thread ID`}
    last_month_day = (str_2_datetime(send_date) - timedelta(days=30)).strftime('%Y-%m-%d')
    email_rows = query_table_rows(seatable, email_table_name,
                                  fields='`Message ID`, `Thread ID`',
                                  conditions=f"Date>='{last_month_day}'")
    message2thread = {email['Message ID']: email['Thread ID'] for email in email_rows}
    email_list = [email for email in email_list if email['Message ID'] not in message2thread]

    # no_thread_reply_message_ids is the list of new emails' reply-ids who are not in last 30 days
    no_thread_reply_message_ids = []
    for email in email_list:
        if email['Reply to Message ID'] and email['Reply to Message ID'] not in message2thread:
            no_thread_reply_message_ids.append(email['Reply to Message ID'])
    if no_thread_reply_message_ids:
        step = 100
        for i in range(0, len(no_thread_reply_message_ids), step):
            message_ids_str = ', '.join([f"'{message_id}'" for message_id in no_thread_reply_message_ids[i: i+step]])
            conditions = f"`Message ID`in ({message_ids_str})"
            earlier_email_rows = query_table_rows(seatable, email_table_name,
                                                  fields='`Message ID`, `Thread ID`',
                                                  conditions=conditions,
                                                  all=False,
                                                  limit=step)
            for email in earlier_email_rows:
                message2thread[email['Message ID']] = email['Thread ID']

    new_thread_rows = []
    to_be_updated_thread_dict = {}
    # update email thread id
    for email in email_list:
        reply_to_id = email['Reply to Message ID']
        message_id = email['Message ID']
        if reply_to_id in message2thread:  # checkout thread id from old message2thread
            thread_id = message2thread[reply_to_id]
            message2thread[message_id] = thread_id
            if thread_id in to_be_updated_thread_dict:
                # update Last Updated
                if str_2_datetime(email['Date']) > str_2_datetime(to_be_updated_thread_dict[thread_id]['Last Updated']):
                    to_be_updated_thread_dict[thread_id]['Last Updated'] = email['Date']
                # append email message id
                to_be_updated_thread_dict[thread_id]['message_ids'].append(message_id)
            else:
                to_be_updated_thread_dict[thread_id] = {
                    'Last Updated': email['Date'],
                    'message_ids': [message_id]
                }
        else:  # generate new thread id
            thread_id = uuid4().hex
            message2thread[message_id] = thread_id
            new_thread_rows.append({
                'Subject': email['Subject'],
                'Last Updated': email['Date'],
                'Thread ID': thread_id
            })
            to_be_updated_thread_dict[thread_id] = {
                'Last Updated': email['Date'],
                'message_ids': [message_id]
            }
        email['Thread ID'] = message2thread[message_id]

    return email_list, new_thread_rows, to_be_updated_thread_dict


def fill_email_list_with_row_id(seatable, email_table_name, email_list):
    step = 100
    message_id_row_id_dict = {}  # {message_id: row._id}
    for i in range(0, len(email_list), step):
        message_ids_str = ', '.join([f"'{email['Message ID']}'" for email in email_list[i: i+step]])
        conditions = f'`Message ID` in ({message_ids_str})'
        email_rows = query_table_rows(seatable, email_table_name,
                                      fields='`_id`, `Message ID`',
                                      conditions=conditions,
                                      all=False,
                                      limit=step)
        message_id_row_id_dict.update({row['Message ID']: {
            '_id': row['_id'],
        } for row in email_rows})
    for email in email_list:
        email['_id'] = message_id_row_id_dict[email['Message ID']]['_id']
    return email_list


def get_thread_email_ids(thread_row_emails):
    if thread_row_emails is None:
        return []
    return [email['row_id'] for email in thread_row_emails]


def update_threads(seatable: SeaTableAPI, email_table_name, link_table_name, email_list, to_be_updated_thread_dict):
    """
    update thread table
    email_list: list of email
    to_be_updated_thread_dict: {thread_id: {'Last Updated': 'YYYY-MM-DD', 'message_ids': [message_id1, message_id2...]}}
    """
    to_be_updated_thread_ids = list(to_be_updated_thread_dict.keys())
    thread_id_row_id_dict = {}
    step = 100
    for i in range(0, len(to_be_updated_thread_ids), step):
        thread_ids_str = ', '.join([f"'{thread_id}'" for thread_id in to_be_updated_thread_ids[i: i+step]])
        conditions = f"`Thread ID` in ({thread_ids_str})"
        thread_rows = query_table_rows(seatable, link_table_name,
                                       fields='`Thread ID`, `_id`, `Emails`',
                                       conditions=conditions,
                                       all=False,
                                       limit=step)
        thread_id_row_id_dict.update({row['Thread ID']: [row['_id'], get_thread_email_ids(row.get('Emails'))] for row in thread_rows})

    # batch update Last Updated
    to_be_updated_last_updated_rows = [{
        'row_id': thread_id_row_id_dict[key][0],
        'row': {'Last Updated': value['Last Updated']}
    } for key, value in to_be_updated_thread_dict.items()]
    seatable.batch_update_rows(link_table_name, to_be_updated_last_updated_rows)

    # fill email in email_list with row id
    email_list = fill_email_list_with_row_id(seatable, email_table_name, email_list)
    email_dict = {email['Message ID']: email for email in email_list}
    # add link
    link_id = seatable.get_column_link_id(link_table_name, 'Emails', view_name=None)

    other_rows_ids_map = {}
    row_id_list = []

    for thread_id, value in to_be_updated_thread_dict.items():
        row_id = thread_id_row_id_dict[thread_id][0]
        row_id_list.append(row_id)
        other_rows_ids_map[row_id] = thread_id_row_id_dict[thread_id][1]
        for message_id in value['message_ids']:
            other_rows_ids_map[row_id].append(email_dict[message_id]['_id'])

    tables = seatable.get_metadata()
    table_info = {table['name']: table['_id'] for table in tables['tables']}
    link_table_id = table_info[link_table_name]
    email_table_id = table_info[email_table_name]

    seatable.batch_update_links(link_id, link_table_id, email_table_id, row_id_list, other_rows_ids_map)


def update_emails(seatable, email_table_name, email_list):
    """
    update email table
    email_list: list of email
    """
    to_be_updated_attachments_dict = {email['Message ID']: email['Attachment'] for email in email_list if
                                      email['Attachment']}
    to_be_updated_message_ids = list(to_be_updated_attachments_dict.keys())

    message_id_row_id_dict = {}
    step = 100
    for i in range(0, len(to_be_updated_message_ids), step):
        message_ids_str = ', '.join([f"'{message_id}'" for message_id in to_be_updated_message_ids[i: i + step]])
        conditions = f"`Message ID` in ({message_ids_str})"
        email_rows = query_table_rows(seatable, email_table_name,
                                      fields='`Message ID`, `_id`',
                                      conditions=conditions,
                                      all=False,
                                      limit=step)
        message_id_row_id_dict.update({row['Message ID']: row['_id'] for row in email_rows})

    message_id_attachment_dict = {}
    for email_message_id in to_be_updated_attachments_dict:
        attachments = to_be_updated_attachments_dict[email_message_id]
        attachment_list = []
        for attachment_info_dict in attachments:
            attachment_list.append(attachment_info_dict)
        message_id_attachment_dict[email_message_id] = attachment_list

    to_be_updated_attachment_rows = [{
        'row_id': message_id_row_id_dict[key],
        'row': {'Attachment': value}
    } for key, value in message_id_attachment_dict.items()]

    # update attachment rows
    seatable.batch_update_rows(email_table_name, to_be_updated_attachment_rows)


def upload_attachments(seatable: SeaTableAPI, email_list):
    for email in email_list:
        file_list = email.pop('Attachment', [])
        file_info_list = []
        for file in file_list:
            file_name = file.get('file_name')
            file_data = file.get('file_data')
            try:
                file_info = seatable.upload_bytes_file(file_name, file_data)
                file_info_list.append(file_info)
            except Exception as e:
                logger.error('upload email: %s attachment: %s error: %s', email.get('Message ID'), file_name, e)
        email['Attachment'] = file_info_list
    return email_list


def sync(send_date,
         api_token,
         dtable_web_service_url,
         email_table_name,
         link_table_name,
         email_server,
         email_user,
         email_password,
         imap=None,
         mode='ON'):
    try:
        seatable = SeaTableAPI(api_token, dtable_web_service_url)
        seatable.auth()
        logger.debug('api_token: %s, dtable_web_service_url: %s auth successfully!', api_token, dtable_web_service_url)

        # get emails on send_date
        email_list = sorted(get_emails(send_date, email_server, email_user, email_password, imap=imap, mode=mode), key=lambda x: str_2_datetime(x['Date']))
        if not email_list:
            return

        logger.info(f'fetch {len(email_list)} emails')

        # update thread id of emails
        email_list, new_thread_rows, to_be_updated_thread_dict = update_email_thread_ids(seatable, email_table_name, send_date, email_list)
        logger.info(f'need to be inserted {len(email_list)} emails')
        logger.info(f'need to be inserted {len(new_thread_rows)} thread rows')
        if not email_list:
            return

        # upload attachments
        email_list = upload_attachments(seatable, email_list)
        # insert new emails
        seatable.batch_append_rows(email_table_name, email_list)

        # wait several seconds for dtable-db
        time.sleep(2)
        # update attachment
        update_emails(seatable, email_table_name, email_list)
        # insert new thread rows
        if new_thread_rows:
            seatable.batch_append_rows(link_table_name, new_thread_rows)

        # wait several seconds for dtable-db
        time.sleep(3)

        # update threads Last Updated and Emails
        update_threads(seatable, email_table_name, link_table_name, email_list, to_be_updated_thread_dict)
    except Exception as e:
        logger.exception(e)
        logger.error('sync and update link error: %s', e)


def main():
    args = parser.parse_args()
    send_date = args.date
    mode = args.mode if args.mode else 'ON'
    interval = args.interval * 60 * 60 if args.interval and args.interval > 0 else 6 * 60 * 60

    if mode and mode.upper() not in ('ON', 'SINCE'):
        print("mode can be 'ON' or 'SINCE'", file=sys.stderr)
        exit(-1)
    mode = mode.upper()
    if send_date:
        sync(send_date,
             api_token=settings.TEMPLATE_BASE_API_TOKEN,
             dtable_web_service_url=settings.DTABLE_WEB_SERVICE_URL,
             email_table_name=settings.EMAIL_TABLE_NAME,
             link_table_name=settings.LINK_TABLE_NAME,
             email_server=settings.EMAIL_SERVER,
             email_user=settings.EMAIL_USER,
             email_password=settings.EMAIL_PASSWORD,
             mode=mode)
        return

    try:
        while True:
            try:
                logger.info('start syncing: %s', datetime.now())
                sync((datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d'),
                     api_token=settings.TEMPLATE_BASE_API_TOKEN,
                     dtable_web_service_url=settings.DTABLE_WEB_SERVICE_URL,
                     email_table_name=settings.EMAIL_TABLE_NAME,
                     link_table_name=settings.LINK_TABLE_NAME,
                     email_server=settings.EMAIL_SERVER,
                     email_user=settings.EMAIL_USER,
                     email_password=settings.EMAIL_PASSWORD,
                     mode='SINCE')
                time.sleep(interval)
            except Exception as e:
                logger.error('cron sync error: %s', e)
                time.sleep(interval)
    except (KeyboardInterrupt, SystemExit):
        exit(0)


if __name__ == "__main__":
    import settings
    parser = argparse.ArgumentParser()
    parser.add_argument('--date', required=False, type=str, help='sync date')
    parser.add_argument('--mode', required=False, type=str, help='since or on, default on')
    parser.add_argument('--interval', required=False, type=int, help='interval(hour) of periodically sync')
    main()
