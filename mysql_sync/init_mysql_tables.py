import json
import os
import sys
import pymysql

from seatable_api import SeaTableAPI
from seatable_api.constants import ColumnTypes
import settings


def init_select_option(field_info, seatable, base_table_name):
    """
    init multiple select and single select
    :param field_info:
    :param seatable:
    :param base_table_name:
    :return:
    """
    for field in field_info:
        field_type = field['Type'].split('(')[0].upper()
        col = field['Field']

        if field_type in ['SET', 'ENUM']:
            option_list = field['Type'].split('(')[1].split(')')[0].split(',')
            options = [{'name': option.strip("'"), "color": "#f9f9f9", "textColor": "#ff8000"}
                       for option in option_list]
            seatable.add_column_options(base_table_name, col, options)


def mysql_type_to_seatable_type(field_type):
    with open(os.path.join(os.path.dirname(__file__), 'mysql_to_dtable.json'), 'r') as f:
        mysql_to_dtable_dict = json.load(f)
    f_type = mysql_to_dtable_dict.get(field_type)
    if f_type == 'text':
        return ColumnTypes.TEXT
    elif f_type == 'number':
        return ColumnTypes.NUMBER
    elif f_type == 'long-text':
        return ColumnTypes.LONG_TEXT
    elif f_type == 'checkbox':
        return ColumnTypes.CHECKBOX
    elif f_type == 'date':
        return ColumnTypes.DATE
    elif f_type == 'single-select':
        return ColumnTypes.SINGLE_SELECT
    elif f_type == 'multiple-select':
        return ColumnTypes.MULTIPLE_SELECT
    elif f_type == 'file':
        return ColumnTypes.FILE


def get_mysql_field_info(mysql_table_name, cursor):
    sql = "DESC " + mysql_table_name
    cursor.execute(sql)
    return cursor.fetchall()


def main():
    try:
        conn = pymysql.connect(user=settings.MYSQL_USER, password=settings.MYSQL_PASSWORD,
                               database=settings.DB_NAME, host=settings.MYSQL_HOST, charset=settings.CHARSET)
        cursor = conn.cursor(cursor=pymysql.cursors.DictCursor)
    except Exception as e:
        print('database connected error: ', e, file=sys.stderr)
        exit(-1)

    try:
        seatable = SeaTableAPI(settings.BASE_API_TOKEN, settings.DTABLE_WEB_SERVICE_URL)
        seatable.auth()
    except Exception as e:
        print('init seatable api error: ', e, file=sys.stderr)
        exit(-1)

    try:
        # get columns
        field_info = get_mysql_field_info(settings.MYSQL_TABLE_NAME, cursor)
        columns = [{
            'column_name': field['Field'],
            'type': mysql_type_to_seatable_type(field['Type'].split('(')[0].upper())
        } for field in field_info]

        # create table and columns
        base_table_name = settings.BASE_TABLE_NAME
        seatable.add_table(base_table_name, lang=settings.LANG)
        for index, col in enumerate(columns):
            col_name, col_type = col.get('column_name'), col.get('type')
            if index == 0:
                seatable.rename_column(base_table_name, '0000', col_name)
                if col_type != ColumnTypes.TEXT:
                    seatable.modify_column_type(base_table_name, '0000', col_type)
                continue

            seatable.insert_column(base_table_name, col_name, ColumnTypes(col_type), column_data=col.get('data'))
            print(f'table {base_table_name}, insert column {col_name} type {col_type}')

        init_select_option(field_info, seatable, base_table_name)

    except Exception as e:
        print('create tables error: ', e, file=sys.stderr)
        exit(-1)
    finally:
        conn.close()
        cursor.close()

    print('Successfully init base tables!')
    print('mysql table:')
    print('<' * 30)
    columns = seatable.list_columns(base_table_name)
    for col in columns:
        print(f"{col['name']:20}\t{ColumnTypes(col['type'])}")
    print('>' * 30)
    print()


if __name__ == '__main__':
    main()
