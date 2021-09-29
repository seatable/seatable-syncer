# SeaTable
server_url = 'https://dev.seatable.cn/'
api_token = '3ad73fb127395cf29acc1854669296497b78c3a8'
table_name = 'Table1'

# Redis
redis_host = '39.106.191.165'
redis_db = 0
redis_port = 6379
redis_password = None

filebeat_key = 'seatable-error-logs'

try:
    from log_syncer_settings import *
except:
    pass
