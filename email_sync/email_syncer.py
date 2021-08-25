import argparse
import json
import re

import settings
import datetime
import logging
from datetime import datetime, timedelta
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
    def __init__(self, serveraddress, user, passwd, port=None, timeout=None):
        self.serveraddress = serveraddress
        self.user = user
        self.passwd = passwd
        self.port = port
        self.timeout = timeout
        self.server = None

    def client(self):
        try:
            self.server = IMAPClient(self.serveraddress, self.port, timeout=self.timeout)
            logger.info('connected success')
        except BaseException as e:
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

    def get_email_list(self, send_date):
        send_date = datetime.strptime(send_date, '%Y-%m-%d').date()
        td = timedelta(days=1)
        before_send_date = send_date - td
        total_email_list = []
        for send_box in ['INBOX', 'Sent Items']:
            self.server.select_folder(send_box, readonly=True)
            r_result = self.server.search(['ON', send_date])
            f_result = self.server.search(['ON', before_send_date])
            result = f_result + r_result
            for mail in result:
                email_dict = {}
                data = self.server.fetch(mail, ['ENVELOPE'])
                envelope = data[mail][b'ENVELOPE']
                send_time = envelope.date
                sender = envelope.sender
                send_to = envelope.to
                cc = envelope.cc
                message_id = envelope.message_id.decode()
                email_dict['Subject'] = envelope.subject.decode()
                if send_time.date() != send_date:
                    continue
                email_dict['From'] = sender[0].mailbox.decode() + '@' + sender[0].host.decode()
                to_address = ''
                for to in send_to:
                    to_address += to.mailbox.decode() + '@' + to.host.decode() + ','
                cc_address = ''
                if cc:
                    for c in cc:
                        cc_address += c.mailbox.decode() + '@' + c.host.decode() + ','
                msg_dict = self.server.fetch(mail, ['BODY[]'])
                mail_body = msg_dict[mail][b'BODY[]']
                msg = Parser().parsestr(mail_body.decode())
                content = self.get_content(msg)

                in_reply_to = self.get_reply_to(msg)
                email_dict['To'] = to_address.rstrip(',')
                email_dict['In_Reply_To'] = in_reply_to
                email_dict['UID'] = str(mail)
                email_dict['Message_ID'] = message_id.strip().lower()[1:-1]
                email_dict['cc'] = cc_address.rstrip(',')
                email_dict['Content'] = content
                email_dict['Date'] = datetime.strftime(send_time, '%Y-%m-%d %H:%M:%S')
                total_email_list.append(email_dict)
        return total_email_list

    def close(self):
        self.server.logout()


def sync_email(email_list):
    seatable = SeaTableAPI(settings.TEMPLATE_BASE_API_TOKEN, settings.DTABLE_WEB_SERVICE_URL)
    seatable.auth()
    email_rows = seatable.list_rows(settings.EMAIL_TABLE_NAME, view_name=settings.EMAIL_TABLE_VIEW)

    email_dict = {email['Message_ID']: email['In_Reply_To'] for email in email_list}
    local_email_dict = {email['Message_ID']: email['In_Reply_To'] for email in email_rows}
    email_dict.update(local_email_dict)
    linked_dict = get_link_info(email_dict)
    for email in email_list:
        for link_message_id in linked_dict:
            if email['Message_ID'] in linked_dict[link_message_id]:
                email['Linked_Message_ID'] = link_message_id
    seatable.batch_append_rows(settings.EMAIL_TABLE_NAME, email_list)


def update_links(send_time):
    seatable = SeaTableAPI(settings.TEMPLATE_BASE_API_TOKEN, settings.DTABLE_WEB_SERVICE_URL)
    seatable.auth()

    table_info = seatable.get_metadata()
    table_info = {table['name']: table['_id'] for table in table_info['tables']}
    table_id = table_info[settings.LINK_TABLE_NAME]
    other_table_id = table_info[settings.EMAIL_TABLE_NAME]

    thread_rows = seatable.list_rows(settings.LINK_TABLE_NAME, view_name=settings.LINK_TABLE_VIEW)
    date_param = "Date like %s%%" % send_time
    email_rows = seatable.filter(settings.EMAIL_TABLE_NAME, date_param, view_name=settings.EMAIL_TABLE_VIEW)

    row_id_list = []
    # Threads table origin link info
    other_rows_ids_map = {row['_id']: row['Link'] for row in thread_rows}
    # for update last time
    threads_need_update_date_row_list = []
    # email table subject has already in threads table
    has_dealed_row_list = []
    for thread_row in thread_rows:
        last_date = ''
        for email_row in email_rows:
            if thread_row['Linked_Message_ID'] == email_row['Linked_Message_ID']:
                has_dealed_row_list.append(email_row['_id'])
                threads_last_time = datetime.strptime(thread_row.get('Last time', '1970-01-01 00:00:00'), '%Y-%m-%d %H:%M:%S')
                email_time = datetime.strptime(email_row['Date'], '%Y-%m-%d %H:%M:%S')
                # update threads last time if email time > threads time
                if threads_last_time < email_time:
                    last_date = email_row['Date']
                if thread_row['_id'] not in row_id_list:
                    row_id_list.append(thread_row['_id'])
                if not other_rows_ids_map.get(thread_row['_id'], []):
                    other_rows_ids_map[thread_row['_id']] = thread_row['Link'] + [email_row['_id']]
                else:
                    if email_row['_id'] not in other_rows_ids_map[thread_row['_id']]:
                        other_rows_ids_map[thread_row['_id']].append(email_row['_id'])

        if last_date:
            update_last_date_row_info = {'row_id': thread_row['_id'], "row": {'Last time': last_date}}
            threads_need_update_date_row_list.append(update_last_date_row_info)

    need_insert_rows = filter(lambda x: x['_id'] not in has_dealed_row_list, email_rows)

    insert_row_dict = {}
    row_message_ids_map = {}
    for row in need_insert_rows:
        # update date if Linked_Message_ID exist
        if insert_row_dict.get(row['Linked_Message_ID']) and insert_row_dict[row['Linked_Message_ID']][0] < row['Date']:
            insert_row_dict[row['Linked_Message_ID']] = [row['Date'], row['Subject']]
        if not insert_row_dict.get(row['Linked_Message_ID']):
            insert_row_dict[row['Linked_Message_ID']] = [row['Date'], row['Subject']]

        # get row_subject_ids_map for update links
        if not row_message_ids_map.get(row['Linked_Message_ID'], []):
            row_message_ids_map[row['Linked_Message_ID']] = [row['_id']]
        else:
            row_message_ids_map[row['Linked_Message_ID']].append(row['_id'])

    new_row_id_list = []
    new_other_rows_ids_map = {}
    if insert_row_dict:
        insert_thread_rows = [{'Linked_Message_ID': row, 'Last time': insert_row_dict[row][0], 'Subject': insert_row_dict[row][1]} for row in insert_row_dict]
        # subject and 'Last time' insert threads table
        seatable.batch_append_rows(settings.LINK_TABLE_NAME, insert_thread_rows)

        # get new threads table row_id_list and other_rows_ids_map
        date_param = "'Last time' like %s%%" % send_time
        new_thread_rows = seatable.filter(settings.LINK_TABLE_NAME, date_param, view_name=settings.LINK_TABLE_VIEW)
        for row in new_thread_rows:
            new_row_id_list.append(row['_id'])
            new_other_rows_ids_map[row['_id']] = row_message_ids_map[row['Linked_Message_ID']]

    row_id_list = new_row_id_list + row_id_list
    other_rows_ids_map.update(new_other_rows_ids_map)
    link_id = seatable.get_column_link_id('Threads', 'Link', view_name=None)

    seatable.batch_update_links(link_id, table_id, other_table_id, row_id_list, other_rows_ids_map)
    seatable.batch_update_rows(settings.LINK_TABLE_NAME, threads_need_update_date_row_list)


def get_emails(send_date):
    imap = ImapMail(settings.EMAIL_SERVER, settings.EMAIL_USER, settings.EMAIL_PASSWORD)
    imap.client()
    imap.login()
    email_list = imap.get_email_list(send_date)
    imap.close()
    return email_list


def get_link_info(email_dict):
    linked_dict = {}
    has_linked_set = set()
    for r_mail in email_dict:
        for f_mail in email_dict:
            if r_mail == f_mail:
                continue
            if email_dict[r_mail] == f_mail:
                if linked_dict.get(r_mail):
                    is_linked = False
                    for i in linked_dict:
                        if f_mail in linked_dict[i]:
                            linked_dict[i] += linked_dict[r_mail]
                            linked_dict.pop(r_mail)
                            is_linked = True
                            break
                    if not is_linked:
                        linked_dict[r_mail].insert(0, f_mail)
                        linked_dict[f_mail] = linked_dict[r_mail]
                        linked_dict.pop(r_mail)
                    has_linked_set.add(f_mail)
                else:
                    if linked_dict.get(f_mail):
                        linked_dict[f_mail].append(r_mail)
                    else:
                        is_linked = False
                        for i in linked_dict:
                            if f_mail in linked_dict[i]:
                                linked_dict[i].append(r_mail)
                                is_linked = True
                                break
                        if not is_linked:
                            linked_dict[f_mail] = [f_mail, r_mail]
                    has_linked_set.add(f_mail)
                    has_linked_set.add(r_mail)
                break
    for mail in email_dict:
        if mail not in has_linked_set:
            linked_dict[mail] = [mail]
    return linked_dict


def main():
    args = parser.parse_args()
    send_date = args.send_date
    emails = get_emails(send_date)
    sync_email(emails)
    update_links(send_date)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--send-date', required=True, type=str, help='email send date')
    main()
