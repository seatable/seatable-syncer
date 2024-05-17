from uuid import UUID

from settings import api_token, server_url, table_name

import requests
from seatable_api import Base
from seatable_api.constants import ColumnTypes


base = Base(api_token, server_url)
base.auth()

dtable_server_url = base.dtable_server_url.strip('/')

url = f'{dtable_server_url}/api/v1/dtables/{str(UUID(base.dtable_uuid))}/tables/'

body = {
    'table_name': table_name,
    'columns': [
        {'column_name': 'org_id', 'column_type': ColumnTypes.NUMBER.value},
        {'column_name': 'dataset_id', 'column_type': ColumnTypes.NUMBER.value},
        {'column_name': 'src_dtable_uuid', 'column_type': ColumnTypes.TEXT.value},
        {'column_name': 'src_table_id', 'column_type': ColumnTypes.TEXT.value},
        {'column_name': 'src_view_id', 'column_type': ColumnTypes.TEXT.value},
        {'column_name': 'dst_dtable_uuid', 'column_type': ColumnTypes.TEXT.value},
        {'column_name': 'dst_table_id', 'column_type': ColumnTypes.TEXT.value},
        {'column_name': 'import_or_sync', 'column_type': ColumnTypes.TEXT.value},
        {'column_name': 'operator', 'column_type': ColumnTypes.TEXT.value},
        {'column_name': 'started_at', 'column_type': ColumnTypes.DATE.value},
        {'column_name': 'finished_at', 'column_type': ColumnTypes.DATE.value},
        {'column_name': 'to_be_appended_rows_count', 'column_type': ColumnTypes.NUMBER.value},
        {'column_name': 'to_be_updated_rows_count', 'column_type': ColumnTypes.NUMBER.value},
        {'column_name': 'to_be_deleted_rows_count', 'column_type': ColumnTypes.NUMBER.value},
        {'column_name': 'appended_rows_count', 'column_type': ColumnTypes.NUMBER.value},
        {'column_name': 'updated_rows_count', 'column_type': ColumnTypes.NUMBER.value},
        {'column_name': 'deleted_rows_count', 'column_type': ColumnTypes.NUMBER.value},
        {'column_name': 'columns_count', 'column_type': ColumnTypes.NUMBER.value},
        {'column_name': 'link_formula_columns_count', 'column_type': ColumnTypes.NUMBER.value},
        {'column_name': 'is_success', 'column_type': ColumnTypes.CHECKBOX.value},
        {'column_name': 'error', 'column_type': ColumnTypes.LONG_TEXT.value}
    ]
}

response = requests.post(url, json=body, headers=base.headers)
table_data = response.json()

print('create table: %s success' % table_data.get('name'))
