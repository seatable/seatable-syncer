import argparse
import json
import re
from email.utils import parseaddr

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
    def get_reference(msg):
        value = msg.get('References', '')
        reference_list = re.split('[(\n )(\r\n)(,)]+', value.lower())
        reference_list = list(filter(lambda x: x != '', reference_list))
        return json.dumps(reference_list)

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
        self.server.select_folder('INBOX', readonly=True)
        r_result = self.server.search(['ON', send_date])
        f_result = self.server.search(['ON', before_send_date])
        result = f_result + r_result
        total_email_list = []
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

            references = self.get_reference(msg)
            email_dict['To'] = to_address.rstrip(',')
            email_dict['References'] = references
            email_dict['UID'] = str(mail)
            email_dict['Message_ID'] = message_id.strip().lower()
            email_dict['cc'] = cc_address.rstrip(',')
            email_dict['Content'] = content
            email_dict['Date'] = datetime.strftime(send_time, '%Y-%m-%d %H:%M:%S')
            total_email_list.append(email_dict)
        return total_email_list

    def close(self):
        self.server.logout()


def sync_email(email_list):
    try:
        seatable = SeaTableAPI(settings.TEMPLATE_BASE_API_TOKEN, settings.DTABLE_WEB_SERVICE_URL)
        seatable.auth()

        thread_rows = seatable.list_rows(settings.LINK_TABLE_NAME, view_name=settings.LINK_TABLE_VIEW)
        thread_linked_messge_references_dict1 = {row['Linked_message_id']: [json.loads(row['References']), row['_id']] for row in thread_rows}
        thread_linked_messge_references_dict = {row['Linked_message_id']: json.loads(row['References']) for row in thread_rows}
        email_linked_message_references_dict = {email['Message_ID']: json.loads(email['References']) for email in email_list}
        thread_linked_messge_references_dict.update(email_linked_message_references_dict)
        linked_dict, all_references_linked_dict = get_link_info(thread_linked_messge_references_dict)

        thread_message_subject_dict = {row['Linked_message_id']: row['Subject'] for row in thread_rows}
        email_message_subject_dict = {email['Message_ID']: email['Subject'] for email in email_list}
        email_message_subject_dict.update(thread_message_subject_dict)
        for email in email_list:
            for link_message_id in linked_dict:
                if email['Message_ID'] in linked_dict[link_message_id]:
                    email['Linked_message_id'] = link_message_id
        seatable.batch_append_rows(settings.EMAIL_TABLE_NAME, email_list)

        need_update_insert_thread_info = []
        need_del_row_list = []
        update_message_dict = {}
        not_need_insert_list = []
        need_update_reference_list = []
        if thread_linked_messge_references_dict1:
            for linked_message_id in thread_linked_messge_references_dict1:
                if linked_message_id not in linked_dict:
                    for linked_message in linked_dict:
                        if linked_message_id in linked_dict[linked_message]:
                            update_message_dict[linked_message_id] = linked_message
                else:
                    if len(thread_linked_messge_references_dict1[linked_message_id][0]) != len(all_references_linked_dict[linked_message_id]):
                        row_id = thread_linked_messge_references_dict1[linked_message_id][1]
                        references = all_references_linked_dict[linked_message_id]
                        need_update_reference_list.append({'row_id': row_id, 'row': {'References': json.dumps(references)}})

                    not_need_insert_list.append(linked_message_id)

            if update_message_dict:
                for update_message in update_message_dict:
                    conditions = 'Linked_message_id=%s' % update_message
                    update_data = {'Linked_message_id': update_message_dict[update_message]}
                    seatable.filter(settings.EMAIL_TABLE_NAME, conditions, view_name=settings.EMAIL_TABLE_VIEW).update(update_data)

                    for insert_row_info in thread_rows:
                        if update_message == insert_row_info['Linked_message_id']:
                            insert_data = {
                                'Linked_message_id': update_message_dict[update_message],
                                'Subject': email_message_subject_dict[update_message_dict[update_message]],
                                'Link': insert_row_info['Link'],
                                'Last time': insert_row_info['Last time'],
                                'References': json.dumps(all_references_linked_dict[update_message_dict[update_message]])
                            }
                            need_update_insert_thread_info.append(insert_data)
                            need_del_row_list.append(insert_row_info['_id'])
        update_message_list = [update_message_dict[message_id] for message_id in update_message_dict]
        threads_insert_date_list = []
        for linked_message_id in linked_dict:
            if linked_message_id not in update_message_list and linked_message_id not in not_need_insert_list:
                data_dict = {
                    'Linked_message_id': linked_message_id,
                    'References': json.dumps(all_references_linked_dict[linked_message_id]),
                    'Subject': email_message_subject_dict[linked_message_id]
                }
                threads_insert_date_list.append(data_dict)

        if need_update_insert_thread_info:
            seatable.batch_delete_rows(settings.LINK_TABLE_NAME, need_del_row_list)
            threads_insert_date_list += need_update_insert_thread_info
        seatable.batch_append_rows(settings.LINK_TABLE_NAME, threads_insert_date_list)
        if need_update_reference_list:
            seatable.batch_update_rows(settings.LINK_TABLE_NAME, rows_data=need_update_reference_list)
    except Exception as e:
        logger.error(f'seatable error: {e}')


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
            if thread_row['Linked_message_id'] == email_row['Linked_message_id']:
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
    row_subject_ids_map = {}
    for row in need_insert_rows:
        if insert_row_dict.get(row['Linked_message_id']) and insert_row_dict[row['Linked_message_id']] < row['Date']:
            insert_row_dict[row['Linked_message_id']] = row['Date']
        if not insert_row_dict.get(row['Linked_message_id']):
            insert_row_dict[row['Linked_message_id']] = row['Date']

        # get row_subject_ids_map for update links
        if not row_subject_ids_map.get(row['Linked_message_id'], []):
            row_subject_ids_map[row['Linked_message_id']] = [row['_id']]
        else:
            row_subject_ids_map[row['Linked_message_id']].append(row['_id'])

    new_row_id_list = []
    new_other_rows_ids_map = {}
    if insert_row_dict:
        insert_thread_rows = [{'Linked_message_id': row, 'Last time': insert_row_dict[row]} for row in insert_row_dict]
        # subject and 'Last time' insert threads table
        seatable.batch_append_rows(settings.LINK_TABLE_NAME, insert_thread_rows)

        # get new threads table row_id_list and other_rows_ids_map
        date_param = "'Last time' like %s%%" % send_time
        new_thread_rows = seatable.filter(settings.LINK_TABLE_NAME, date_param, view_name=settings.LINK_TABLE_VIEW)
        for row in new_thread_rows:
            new_row_id_list.append(row['_id'])
            new_other_rows_ids_map[row['_id']] = row_subject_ids_map[row['Linked_message_id']]

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


def get_link_info(message_id_reference_dict):
    linked_dict = {}
    has_compared = []
    num = 0
    total_link = len(message_id_reference_dict)
    has_linked_set = set()
    for message in message_id_reference_dict:
        num += 1
        if num == total_link and message in has_linked_set:
            continue
        has_compared.append(message)
        references = message_id_reference_dict[message]
        if not references:
            is_in_linked_dict = False
            if message not in linked_dict:
                for i in linked_dict:
                    if message in linked_dict[i]:
                        is_in_linked_dict = True
                        break
            if not is_in_linked_dict:
                linked_dict[message] = [message]
                has_linked_set.add(message)
            continue
        else:
            is_message_linked = False
            if linked_dict.get(message, []):
                is_message_linked = True
            is_in_lined_dict_list = []
            for ref_message in references:
                for i in linked_dict:
                    if ref_message in linked_dict[i]:
                        linked_dict[i].append(message)
                        is_message_linked = True
                        is_in_lined_dict_list.append(i)
                        has_linked_set.add(message)
                        has_linked_set.add(i)
                for i in message_id_reference_dict:
                    if i in has_compared:
                        continue
                    if message in message_id_reference_dict[i]:
                        if linked_dict.get(message):
                            if linked_dict.get(i):
                                linked_dict[message] += linked_dict[i]
                            else:
                                linked_dict[message].append(i)
                        else:
                            if linked_dict.get(i):
                                linked_dict[i].append(message)
                            else:
                                linked_dict[message] = [message, i]
                        is_message_linked = True

                    if ref_message == i:
                        if linked_dict.get(message):
                            linked_dict[message].append(i)
                            has_linked_set.add(i)
                        else:
                            is_message_linked = True
                            if linked_dict.get(i):
                                linked_dict[i].append(message)
                                is_in_lined_dict_list.append(i)
                            else:
                                linked_dict[message] = [message, i]
                                is_in_lined_dict_list.append(message)
                                has_linked_set.add(i)

                    if ref_message in message_id_reference_dict[i]:
                        if linked_dict.get(message):
                            if linked_dict.get(i):
                                # is_in_lined_dict_list.append(i)
                                linked_dict[message] += linked_dict[i]
                            else:
                                if i not in linked_dict[message]:
                                    linked_dict[message].append(i)
                                    has_linked_set.add(i)
                        else:
                            is_not_in = True
                            for m in linked_dict:
                                if message in linked_dict[m]:
                                    linked_dict[m].append(i)
                                    linked_dict[m].append(message)
                                    is_not_in = False
                                    has_linked_set.add(message)
                                    has_linked_set.add(i)
                                    break
                            if is_not_in:
                                if linked_dict.get(i):
                                    is_in_lined_dict_list.append(i)
                                    linked_dict[i].append(message)
                                    has_linked_set.add(message)
                                else:
                                    is_in_lined_dict_list.append(message)
                                    linked_dict[message] = [message, i]
                                    has_linked_set.add(message)
                                    has_linked_set.add(i)
                        is_message_linked = True
                        break

            is_in_lined_dict_list = list(set(is_in_lined_dict_list))
            if len(is_in_lined_dict_list) > 1:  # merge if length > 2
                for i in range(len(is_in_lined_dict_list)):
                    if i == 0:
                        continue
                    linked_dict[is_in_lined_dict_list[0]] = linked_dict[is_in_lined_dict_list[0]] + linked_dict[
                        is_in_lined_dict_list[i]]
                    linked_dict.pop(is_in_lined_dict_list[i])
                linked_dict[is_in_lined_dict_list[0]] = list(set(linked_dict[is_in_lined_dict_list[0]]))

            if not is_message_linked:
                linked_dict[message] = [message]

    # get all references
    all_references_linked_dict = {}
    for link in linked_dict:
        references = [link]
        for message_id in linked_dict[link]:
            references += (message_id_reference_dict[message_id] + [message_id])
        all_references_linked_dict[link] = list(set(references))
    return linked_dict, all_references_linked_dict


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
