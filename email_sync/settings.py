# seatable
TEMPLATE_BASE_API_TOKEN = ''
DTABLE_WEB_SERVICE_URL = ''
EMAIL_TABLE_NAME = ''
LINK_TABLE_NAME = ''
LANG = ''

# email
EMAIL_SERVER = ''
EMAIL_USER = ''
EMAIL_PASSWORD = ''

import os
import sys

if os.path.isfile(os.path.join(os.path.dirname(__file__), 'email_syncer_settings.py')):
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'email_syncer_settings.py'))
    try:
        from email_syncer_settings import *
    except:
        pass

