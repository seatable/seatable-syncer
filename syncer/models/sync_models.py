import json

from app import db
from utils import utc_datetime_to_isoformat_timestr
from utils.constants import SYNC_JOB_PREFIX


class SyncJobs(db.Model):
    __tablename__ = 'sync_jobs'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(255), nullable=False)
    dtable_uuid = db.Column(db.String(32), nullable=False, index=True)
    api_token = db.Column(db.String(500), nullable=False)
    trigger_detail = db.Column(db.String(255), nullable=False)
    job_type = db.Column(db.String(50), nullable=False, index=True)
    detail = db.Column(db.TEXT, nullable=False)
    last_trigger_time = db.Column(db.DateTime, nullable=True)
    is_valid = db.Column(db.Boolean, default=True, index=True)

    @property
    def job_id(self):
        return f'{SYNC_JOB_PREFIX}{self.id}'

    def __repr__(self) -> str:
        return '<SyncJobs id=%s dtable_uuid=%s job_type=%s>' % (self.id, self.dtable_uuid, self.job_type)

    def to_dict(self):
        trigger_detail = json.loads(self.trigger_detail)
        hour, minute = trigger_detail.get('hour'), trigger_detail.get('minute')
        if hour.isalnum() and minute.isalnum():
            trigger_detail['trigger_type'] = 'daily'
        else:
            trigger_detail['trigger_type'] = 'hoursly'
        return {
            'id': self.id,
            'name': self.name,
            'dtable_uuid': self.dtable_uuid,
            'api_token': self.api_token,
            'trigger_detail': trigger_detail,
            'job_type': self.job_type,
            'detail': json.loads(self.detail),
            'last_trigger_time': utc_datetime_to_isoformat_timestr(self.last_trigger_time),
            'is_valid': 1 if self.is_valid else 0
        }
