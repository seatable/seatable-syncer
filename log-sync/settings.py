# SeaTable
server_url = ''
api_token = ''
table_name = ''

# Redis
redis_host = ''
redis_db = 0
redis_port = 6379
redis_password = None

filebeat_key = 'seatable-error-logs'

try:
    from log_syncer_settings import *
except:
    pass
