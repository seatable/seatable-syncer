import argparse
from datetime import datetime, timedelta
import logging
import ssl
import sys
import time
from uuid import uuid4

from seatable_api import SeaTableAPI
from seatable_api.constants import ColumnTypes

from imapclient import IMAPClient
from email.parser import Parser
from email.header import decode_header

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
        try:
            self.server = IMAPClient(self.serveraddress, self.port, timeout=self.timeout, ssl_context=self.ssl_context)
            if '163.com' in self.serveraddress:
                self.server.id_({"name": "IMAPClient", "version": "2.1.0"})
            logger.info('connected success')
        except BaseException as e:
            logger.exception(e)
            logger.error(e)

    def login(self):
        try:
            self.server.login(self.user, self.passwd)
        except BaseException as e:
            logger.error(e)

    @staticmethod
    def decode_str(s):
        value, charset = decode_header(s)[0]
        if charset:
            value = value.decode(charset)
        return value

    @staticmethod
    def guess_charset(msg):
        charset = msg.get_charset()
        if charset is None:
            content_type = msg.get('Content-Type', '').lower()
            pos = content_type.find('charset=')
            if pos >= 0:
                charset = content_type[pos + 8:].strip()
        return charset

    @staticmethod
    def get_reply_to(msg):
        value = msg.get('In-Reply-To', '').strip().lower()[1:-1]
        return value

    def get_content(self, msg):
        content = ''
        for part in msg.walk():
            if part.is_multipart():
                continue
            content_type = part.get_content_type()
            charset = self.guess_charset(part)
            # if attachment continue
            if part.get_filename() != None:
                continue
            email_content_type = ''
            if content_type == 'text/plain':
                email_content_type = 'text'
            elif content_type == 'text/html':
                continue
            if charset:
                try:
                    content = part.get_payload(decode=True).decode(charset)
                except LookupError:
                    content = part.get_payload()
                    logger.info('unknown encoding: %s' % charset)
                except Exception as e:
                    logger.error(e)
            if email_content_type == '':
                continue
        return content

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
        data = self.server.fetch(mail, ['ENVELOPE'])
        envelope = data[mail][b'ENVELOPE']
        send_time = envelope.date
        sender = envelope.sender
        send_to = envelope.to
        cc = envelope.cc
        message_id = envelope.message_id.decode() if envelope.message_id else ''
        email_dict['Subject'] = envelope.subject.decode() if envelope.subject else ''
        if mode == 'ON' and send_time.date() != send_date:
            return
        if mode == 'SINCE' and send_time.date() < send_date:
            return
        parse_address = lambda x: (x.mailbox.decode() if x.mailbox else '') + '@' + (x.host.decode() if x.host else '')
        email_dict['From'] = parse_address(sender[0])
        to_address = ','.join([parse_address(to) for to in send_to])
        cc_address = ','.join([parse_address(to) for to in cc]) if cc else ''
        msg_dict = self.server.fetch(mail, ['BODY[]'])
        mail_body = msg_dict[mail][b'BODY[]']
        msg = Parser().parsestr(mail_body.decode())
        content = self.get_content(msg)

        in_reply_to = self.get_reply_to(msg)
        email_dict['To'] = to_address.rstrip(',')
        email_dict['Reply to Message ID'] = in_reply_to
        email_dict['UID'] = str(mail)
        email_dict['Message ID'] = message_id.strip().lower()[1:-1]
        email_dict['cc'] = cc_address.rstrip(',')
        email_dict['Content'] = content
        email_dict['Date'] = datetime.strftime(send_time, '%Y-%m-%d %H:%M:%S')

        return email_dict

    def get_email_list(self, send_date, mode='ON'):
        send_date = datetime.strptime(send_date, '%Y-%m-%d').date()
        total_email_list = []
        for send_box in ['INBOX', 'Sent Items']:
            self.server.select_folder(send_box, readonly=True)
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
        result = fixed_sql_query(seatable, f"select count(*) from {table_name} {where_conditions}")[0]
        limit = result['COUNT(*)']
        if limit == 0:
            return []
    else:
        limit = 100 if not limit else limit
    return fixed_sql_query(seatable, f"select {fields} from {table_name} {where_conditions} limit {limit}")


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


def get_emails(send_date, email_server, email_user, email_password, mode='ON'):
    """
    return: email list, [email1, email2...], email is without thread id
    """
    imap = ImapMail(email_server, email_user, email_password, ssl_context=ssl.SSLContext(ssl.PROTOCOL_TLSv1_2))
    imap.client()
    imap.login()
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
                                       fields='`Thread ID`, `_id`',
                                       conditions=conditions,
                                       all=False,
                                       limit=step)
        thread_id_row_id_dict.update({row['Thread ID']: row['_id'] for row in thread_rows})

    # batch update Last Updated
    to_be_updated_last_updated_rows = [{
        'row_id': thread_id_row_id_dict[key],
        'row': {'Last Updated': value['Last Updated']}
    } for key, value in to_be_updated_thread_dict.items()]
    seatable.batch_update_rows(link_table_name, to_be_updated_last_updated_rows)

    # fill email in email_list with row id
    email_list = fill_email_list_with_row_id(seatable, email_table_name, email_list)
    email_dict = {email['Message ID']: email for email in email_list}
    # add link
    link_id = seatable.get_column_link_id(link_table_name, 'Emails', view_name=None)
    for key, value in to_be_updated_thread_dict.items():
        thread_id = key
        row_id = thread_id_row_id_dict[thread_id]
        for message_id in value['message_ids']:
            seatable.add_link(link_id, link_table_name, email_table_name, row_id, email_dict[message_id]['_id'])


def sync(send_date,
         api_token,
         dtable_web_service_url,
         email_table_name,
         link_table_name,
         email_server,
         email_user,
         email_password,
         mode='ON'):
    try:
        # get emails on send_date
        email_list = sorted(get_emails(send_date, email_server, email_user, email_password, mode=mode), key=lambda x: str_2_datetime(x['Date']))
        if not email_list:
            return

        logger.info(f'fetch {len(email_list)} emails')

        seatable = SeaTableAPI(api_token, dtable_web_service_url)
        seatable.auth()

        # update thread id of emails
        email_list, new_thread_rows, to_be_updated_thread_dict = update_email_thread_ids(seatable, email_table_name, send_date, email_list)
        logger.info(f'need to be inserted {len(email_list)} emails')
        logger.info(f'need to be inserted {len(new_thread_rows)} thread rows')
        if not email_list:
            return

        # insert new emails
        seatable.batch_append_rows(email_table_name, email_list)
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