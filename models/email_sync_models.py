from app import db
from utils.constants import EMAIL_SYNC_JOB_PREFIX


class EmailSyncJobs(db.Model):
    __tablename__ = 'email_sync_jobs'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(255), nullable=False)
    dtable_uuid = db.Column(db.String(32), nullable=False, index=True)
    api_token = db.Column(db.String(50), nullable=False)
    cron_expr = db.Column(db.String(50), nullable=False)
    imap_server = db.Column(db.String(255), nullable=False)
    email_user = db.Column(db.String(255), nullable=False)
    email_password = db.Column(db.String(255), nullable=False)
    email_table_name = db.Column(db.String(255), nullable=False)
    link_table_name = db.Column(db.String(255), nullable=False)
    last_trigger_time = db.Column(db.DateTime, nullable=True)
    is_valid = db.Column(db.Boolean, default=True, index=True)

    __table_args__ = (
        db.UniqueConstraint('dtable_uuid', 'email_table_name', 'link_table_name'),
    )

    @property
    def job_id(self):
        return f'{EMAIL_SYNC_JOB_PREFIX}{self.id}'

    def __repr__(self) -> str:
        return '<EmailSyncJobs id=%s dtable_uuid=%s>' % (self.id, self.dtable_uuid)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'dtable_uuid': self.dtable_uuid,
            'api_token': self.api_token,
            'cron_expr': self.cron_expr,
            'imap_server': self.imap_server,
            'email_user': self.email_user,
            'email_password': self.email_password,
            'email_table_name': self.email_table_name,
            'link_table_name': self.link_table_name,
            'last_trigger_time': str(self.last_trigger_time.isoformat()) if self.last_trigger_time else None,
            'is_valid': self.is_valid
        }
