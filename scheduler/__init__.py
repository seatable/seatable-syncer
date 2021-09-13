from apscheduler.events import EVENT_JOB_EXECUTED
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.sync_app import db
from models.email_sync_models import EmailSyncJobs
from email_sync.email_syncer import sync


class ScheduelrJobsManager:
    """
    Encapsulated scheduler for add/update/remove jobs
    """

    def __init__(self):
        self.email_sync_scheduler = BackgroundScheduler()

    def _load_email_sync_jobs(self):
        jobs = db.query.all()
        for job in jobs:
            pass

    def load_jobs(self):
        pass


scheduler_jobs_manager = ScheduelrJobsManager()
scheduler_jobs_manager.load_jobs()
