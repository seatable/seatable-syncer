import logging

from apscheduler.events import EVENT_JOB_EXECUTED
# from apscheduler.schedulers.gevent import GeventScheduler
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from flask import current_app as app

from app import db, app
from config import Config
from models.email_sync_models import EmailSyncJobs
from scheduler.job_funcs import email_sync_job_func
from utils.constants import EMAIL_SYNC_JOB_PREFIX

logger = logging.getLogger(__name__)


class ScheduelrJobsManager:
    """
    Encapsulated scheduler for add/update/remove jobs
    """

    def __init__(self):
        # self.email_sync_scheduler = GeventScheduler()
        self.email_sync_scheduler = BackgroundScheduler()
        self.email_sync_scheduler.add_listener(self.update_last_trigger_time, mask=EVENT_JOB_EXECUTED)
        # TODO: set invalid when func invalid

    def get_jobs(self):
        jobs = {
            'email_sync_jobs': []
        }
        email_sync_jobs = self.email_sync_scheduler.get_jobs()
        for job in email_sync_jobs:
            jobs['email_sync_jobs'].append({
                'id': job.id,
                'args': job.args,
                'next_run_time': str(job.next_run_time),
                'trigger': str(job.trigger)
            })

        return jobs

    def add_email_sync_job(self, db_job):
        trigger = CronTrigger.from_crontab(db_job.cron_expr)
        return self.email_sync_scheduler.add_job(
            email_sync_job_func,
            trigger=trigger,
            args=(
                db_job.api_token,
                Config.DTABLE_WEB_SERVICE_URL,
                db_job.email_table_name,
                db_job.link_table_name,
                db_job.imap_server,
                db_job.email_user,
                db_job.email_password
            ),
            id=db_job.job_id
        )

    def update_email_sync_job(self, db_job):
        self.remove_job(db_job.job_id)
        self.add_email_sync_job(db_job)

    def remove_job(self, job_id, prefix=None):
        job_id = job_id if not prefix else f'{prefix}{job_id}'
        if self.email_sync_scheduler.get_job(job_id):
            self.email_sync_scheduler.remove_job(job_id)

    def update_last_trigger_time(self, event):
        """
        a callback for email_sync_scheduler job-executed event
        """
        with app.app_context():
            job_id = event.job_id
            scheduled_run_time = event.scheduled_run_time
            try:
                if job_id.startswith(EMAIL_SYNC_JOB_PREFIX):
                    db_job_id = job_id[len(EMAIL_SYNC_JOB_PREFIX):]
                    EmailSyncJobs.query.filter(EmailSyncJobs.id == db_job_id).update({'last_trigger_time': scheduled_run_time})
                    db.session.commit()
            except Exception as e:
                logger.error('update job: %s last_trigger_time error: %s, scheduled_run_time: %s', job_id, e, scheduled_run_time)

    def _load_email_sync_jobs(self):
        db_jobs = EmailSyncJobs.query.filter(EmailSyncJobs.is_valid == True)
        for db_job in db_jobs:
            job = self.add_email_sync_job(db_job)
            logger.info('job: %s loaded', job)

    def load_jobs(self):
        self._load_email_sync_jobs()

    def start(self):
        self.email_sync_scheduler.start()


scheduler_jobs_manager = ScheduelrJobsManager()
scheduler_jobs_manager.load_jobs()
scheduler_jobs_manager.start()
