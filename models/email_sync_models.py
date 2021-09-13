from app.sync_app import db


class EmailSyncJobs(db.Model):
    __tablename__ = 'email_sync_jobs'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    dtable_uuid = db.Column(db.String(32), nullable=False, index=True)
    api_token = db.Column(db.String(50), nullable=False)
    cron_expr = db.Column(db.String(50), nullable=False)
    imap_server = db.Column(db.String(255), nullable=False)
    email_user = db.Column(db.String(255), nullable=False)
    email_password = db.Column(db.String(255), nullable=False)
    email_table_name = db.Column(db.String(255), nullable=False)
    link_table_name = db.Column(db.String(255), nullable=False)
    last_trigger_time = db.Column(db.Datetime, nullable=True)
    is_valid = db.Column(db.Boolean, default=True, index=True)

    __table_args__ = (
        db.UniqueConstraint('dtable_uuid', 'email_table_name', 'link_table_name'),
    )
