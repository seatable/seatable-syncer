import argparse
from datetime import datetime, timedelta
import logging
import ssl
import sys
import time
from uuid import uuid4

from seatable_api.constants import ColumnTypes

import settings
from imapclient import IMAPClient
from email.parser import Parser
from email.header import decode_header
from seatable_api import SeaTableAPI

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
        message_id = envelope.message_id.decode()
        email_dict['Subject'] = envelope.subject.decode()
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


def query_table_rows(seatable, table_name, fields='*', conditions='', all=True):
    where_conditions = f"where {conditions}" if conditions else ''
    if all:
        result = fixed_sql_query(seatable, f"select count(*) from {table_name} {where_conditions}")[0]
        count = result['COUNT(*)']
    else:
        count = 100
    return fixed_sql_query(seatable, f"select {fields} from {table_name} {where_conditions} limit {count}")


def sync_email(email_list, seatable, email_table_name):
    # get all email-rows from email table
    email_rows = query_table_rows(seatable, email_table_name, all=True)
    # sort emails fetched by imap client
    email_list = sorted(email_list, key=lambda x: datetime.strptime(x['Date'], '%Y-%m-%d %H:%M:%S'))
    # fill email_list threads
    email_list = update_link_info(email_list, email_rows)
    seatable.batch_append_rows(email_table_name, email_list)


def str_2_datetime(s: str):
    format_str = '%Y-%m-%dT%H:%M:%S'
    if '+' in s:
        s = s[:s.find('+')]
    return datetime.strptime(s, format_str)


def update_links(send_time, seatable, email_table_name, link_table_name):
    metadata = seatable.get_metadata()
    table_info = {table['name']: table['_id'] for table in metadata['tables']}
    table_id = table_info[link_table_name]
    other_table_id = table_info[email_table_name]

    thread_rows = query_table_rows(seatable, link_table_name, all=True)
    email_rows = query_table_rows(seatable, email_table_name, conditions=f"`Date`>='{send_time}'")

    row_id_list = []  # thread_row._ids to be updated links
    # Threads table origin link info
    other_rows_ids_map = {row['_id']: row['Link'] for row in thread_rows}
    # for update Last Updated
    threads_need_update_date_row_list = []
    # email table subject has already in threads table
    has_dealed_row_list = []
    for thread_row in thread_rows:
        last_date = ''
        for email_row in email_rows:
            if thread_row['Thread ID'] == email_row['Thread ID']:
                has_dealed_row_list.append(email_row['_id'])

                threads_last_time = str_2_datetime(thread_row['Last Updated'])
                email_time = str_2_datetime(email_row['Date'])

                # update threads Last Updated if email time > threads time
                if threads_last_time < email_time:
                    last_date = email_row['Date']
                if thread_row['_id'] not in row_id_list:
                    row_id_list.append(thread_row['_id']) # thread_row._id to be updated

                # update table link's other_rows of other table
                if not other_rows_ids_map.get(thread_row['_id'], []):
                    other_rows_ids_map[thread_row['_id']] = thread_row['Link'] + [email_row['_id']]
                else:
                    if email_row['_id'] not in other_rows_ids_map[thread_row['_id']]:
                        other_rows_ids_map[thread_row['_id']].append(email_row['_id'])

        if last_date:  # last_date is updated
            update_last_date_row_info = {'row_id': thread_row['_id'], "row": {'Last Updated': last_date}}
            threads_need_update_date_row_list.append(update_last_date_row_info)

    need_insert_rows = list(filter(lambda x: x['_id'] not in has_dealed_row_list, email_rows))  # email_rows not linked to threads

    insert_row_dict = {}  # {thread_id: [date, subject]}
    row_message_ids_map = {}  # {thread_id: [email_row._id...]}
    for row in need_insert_rows:
        # update date if Thread ID exist
        if insert_row_dict.get(row['Thread ID']) and insert_row_dict[row['Thread ID']][0] < row['Date']:
            insert_row_dict[row['Thread ID']] = [row['Date'], row['Subject']]
        if not insert_row_dict.get(row['Thread ID']):
            insert_row_dict[row['Thread ID']] = [row['Date'], row['Subject']]

        # get row_subject_ids_map for update links
        if not row_message_ids_map.get(row['Thread ID'], []):
            row_message_ids_map[row['Thread ID']] = [row['_id']]
        else:
            row_message_ids_map[row['Thread ID']].append(row['_id'])

    new_row_id_list = []  # [thread_row._id...]
    new_other_rows_ids_map = {}  # {thread_row._id: [email_row._id...]}
    if insert_row_dict:
        insert_thread_rows = [{'Thread ID': row, 'Last Updated': insert_row_dict[row][0], 'Subject': insert_row_dict[row][1]} for row in insert_row_dict]
        # subject and 'Last Updated' insert threads table
        seatable.batch_append_rows(link_table_name, insert_thread_rows)

        # get new threads table row_id_list and other_rows_ids_map
        new_thread_rows = query_table_rows(seatable, link_table_name, conditions=f"`Last Updated` >= '{send_time}'")
        for row in new_thread_rows:
            new_row_id_list.append(row['_id'])
            if row['Thread ID'] in row_message_ids_map:
                new_other_rows_ids_map[row['_id']] = row_message_ids_map[row['Thread ID']]

    row_id_list = list(set(new_row_id_list + row_id_list))
    other_rows_ids_map.update(new_other_rows_ids_map)
    link_id = seatable.get_column_link_id(link_table_name, 'Link', view_name=None)

    seatable.batch_update_links(link_id, table_id, other_table_id, row_id_list, other_rows_ids_map)
    seatable.batch_update_rows(link_table_name, threads_need_update_date_row_list)


def get_emails(send_date, mode='ON'):
    imap = ImapMail(settings.EMAIL_SERVER, settings.EMAIL_USER, settings.EMAIL_PASSWORD, ssl_context=ssl.SSLContext(ssl.PROTOCOL_TLSv1_2))
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


def update_link_info(email_list, email_rows):
    message2thread = {email['Message ID']: email['Thread ID'] for email in email_rows}
    email_list = [email for email in email_list if email['Message ID'] not in message2thread]
    email_dict = {email['Message ID']: email['Reply to Message ID'] for email in email_list}

    for email in email_dict:
        reply_to_id = email_dict[email]
        if reply_to_id in message2thread:
            message2thread[email] = message2thread[reply_to_id]
        else:
            thread_id = uuid4().hex
            message2thread[email] = thread_id

    for email in email_list:
        email['Thread ID'] = message2thread[email['Message ID']]
    return email_list


def sync(send_date, mode=None):
    emails = get_emails(send_date, mode=mode)  # get emails sent in send_date
    if not emails:
        return
    seatable = SeaTableAPI(settings.TEMPLATE_BASE_API_TOKEN, settings.DTABLE_WEB_SERVICE_URL)
    seatable.auth()
    try:
        sync_email(emails, seatable, settings.EMAIL_TABLE_NAME)
        update_links(send_date, seatable, settings.EMAIL_TABLE_NAME, settings.LINK_TABLE_NAME)
    except Exception as e:
        logger.exception(e)
        logger.error('sync-emails update-links error: %s', e)


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
        sync(send_date, mode=mode)
        return

    try:
        while True:
            try:
                logger.info('start syncing: %s', datetime.now())
                sync((datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d'), mode='SINCE')
                time.sleep(interval)
            except Exception as e:
                logger.error('cron sync error: %s', e)
                time.sleep(interval)
    except (KeyboardInterrupt, SystemExit):
        exit(0)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--date', required=False, type=str, help='sync date')
    parser.add_argument('--mode', required=False, type=str, help='since or on, default on')
    parser.add_argument('--interval', required=False, type=int, help='interval(hour) of loop sync')
    main()
