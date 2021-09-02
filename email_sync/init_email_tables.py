import json
import os
import sys

from seatable_api import SeaTableAPI
from seatable_api.constants import ColumnTypes

from settings import TEMPLATE_BASE_API_TOKEN, DTABLE_WEB_SERVICE_URL, LANG, \
    EMAIL_TABLE_NAME, LINK_TABLE_NAME


with open(os.path.join(os.path.dirname(__file__), 'tables.json'), 'r') as f:
    tables_dict = json.load(f)


def main(api_token,
         dtable_web_service_url, 
         email_table_name,
         link_table_name,
         lang):
    try:
        seatable = SeaTableAPI(api_token, dtable_web_service_url)
        seatable.auth()
    except Exception as e:
        print('init seatable api error: ', e, file=sys.stderr)
        exit(-1)

    try:
        # create emails table and columns
        email_table = seatable.add_table(email_table_name, lang=lang)
        columns = tables_dict.get('email_table', [])
        for index, col in enumerate(columns):
            if index == 0:
                seatable.rename_column(email_table_name, '0000', col.get('column_name'))
                continue
            col_name, col_type = col.get('column_name'), col.get('type')
            # column_data = json.dumps(col['data']) if col.get('data') else None
            seatable.insert_column(email_table_name, col_name, ColumnTypes(col_type), column_data=col.get('data'))
            print(f'table {email_table_name}, insert column {col_name} type {col_type}')

        # create links table and columns
        link_table = seatable.add_table(link_table_name, lang=lang)
        columns = tables_dict.get('link_table', [])
        for index, col in enumerate(columns):
            if index == 0:
                seatable.rename_column(link_table_name, '0000', col.get('column_name'))
                continue
            col_name, col_type = col.get('column_name'), col.get('type')
            # column_data = json.dumps(col['data']) if col.get('data') else None
            seatable.insert_column(link_table_name, col_name, ColumnTypes(col_type), column_data=col.get('data'))
            print(f'table {link_table_name}, insert column {col_name} type {col_type}')

        # add link columns between email/table tables
        seatable.insert_column(link_table_name, 'Emails', ColumnTypes.LINK, column_data={
            'table': link_table_name,
            'other_table': email_table_name
        })
        seatable.rename_column(email_table_name, link_table_name, 'Threads')
    except Exception as e:
        print('create tables error: ', e, file=sys.stderr)
        exit(-1)

    print('Successfully init email tables!')
    print('email table:')
    print('<' * 30)
    columns = seatable.list_columns(email_table_name)
    for col in columns:
        print(f"{col['name']:20}\t{ColumnTypes(col['type'])}")
    print('>' * 30)
    print()
    print('link table:')
    print('>' * 30)
    columns = seatable.list_columns(email_table_name)
    for col in columns:
        print(f"{col['name']:20}\t{ColumnTypes(col['type'])}")
    print('<' * 30)


if __name__ == '__main__':
    main(TEMPLATE_BASE_API_TOKEN, DTABLE_WEB_SERVICE_URL, EMAIL_TABLE_NAME, LINK_TABLE_NAME, LANG)
