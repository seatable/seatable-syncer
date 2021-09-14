# log-sync

## Dependence

### SeaTable

Create a table in SeaTable, then add the following columns in the table

* Service, type `text` or `single-select`
* Time, type `datetime`
* Log, type `long-text`

### Filebeat

How to install Filebeat: <https://www.elastic.co/guide/en/beats/filebeat/7.14/setup-repositories.html#_apt>

### Python

```shell
pip3 install -r requirements.txt
```

## Config

### Filebeat

```shell
vim /etc/filebeat/filebeat.yml
```

content

```text
Reference the sample file filebeat.yml
```

Start Filebeat

```shell
service filebeat restart
```

### log_syncer_settings.py

```shell
vim log_syncer_settings.py
```

content

```python
# SeaTable
server_url = 'SeaTable server_url'
api_token = 'SeaTable api_token'
table_name = 'table name'

# Redis
redis_host = 'redis host'
redis_db = 0
redis_port = 6379
redis_password = None
```

### Run log sync

```shell
python3 log_syncer.py
```
