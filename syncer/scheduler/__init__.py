import json
import logging

import pytz
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR
# from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.schedulers.gevent import GeventScheduler
from apscheduler.triggers.cron import CronTrigger
from flask import current_app as app

from app import db, app
from config import Config
from models.sync_models import SyncJobs
from scheduler.job_funcs import email_sync_job_func
from utils.constants import JOB_TYPE_EMAIL_SYNC, SYNC_JOB_PREFIX
from utils.exceptions import SchedulerJobInvalidException

logger = logging.getLogger(__name__)
class SchedulerJobsManager:
    """
    Encapsulated scheduler for add/update/remove jobs
    """

    def __init__(self):
        self.scheduler = GeventScheduler()
        self.scheduler.add_listener(self.update_last_trigger_time, mask=(EVENT_JOB_EXECUTED | EVENT_JOB_ERROR))
        self.scheduler.add_listener(self.invalidate_job, mask=EVENT_JOB_ERROR)

    def update_last_trigger_time(self, event):
        """
        a callback for scheduler job-executed / job-error events to udpate last_trigger_time
        """
        with app.app_context():
            job_id = event.job_id
            scheduled_run_time = event.scheduled_run_time  # an instantance of datetime
            db_job_id = job_id[len(SYNC_JOB_PREFIX):]
            try:
                SyncJobs.query.filter(SyncJobs.id == db_job_id).update({
                    'last_trigger_time': scheduled_run_time.astimezone(pytz.timezone('UTC'))
                })
                db.session.commit()
            except Exception as e:
                logger.error('update job: %s last_trigger_time: %s', job_id, scheduled_run_time)

    def invalidate_job(self, event):
        job_id = event.job_id
        scheduled_run_time = event.scheduled_run_time
        if not isinstance(event.exception, SchedulerJobInvalidException):
            logger.error('job: %s execute error: %s run time at: %s', job_id, event.exception, scheduled_run_time)
            return
        db_job_id = job_id[len(SYNC_JOB_PREFIX):]
        with app.app_context():
            try:
                SyncJobs.query.filter(SyncJobs.id == db_job_id).update({'is_valid': False})
                db.session.commit()
            except Exception as e:
                logger.error('invalidate job: %s error: %s, scheduled_run_time: %s', job_id, e, scheduled_run_time)

    def add_job(self, db_job):
        logger.info('add job: %s to scheduler...', db_job)
        trigger = CronTrigger(**json.loads(db_job.trigger_detail))
        if db_job.job_type == JOB_TYPE_EMAIL_SYNC:
            detail = json.loads(db_job.detail)
            self.scheduler.add_job(
                email_sync_job_func,
                trigger=trigger,
                args=(
                    db_job.api_token,
                    Config.DTABLE_WEB_SERVICE_URL,
                    detail
                ),
                id=db_job.job_id
            )

    def remove_job(self, job_id):
        self.scheduler.remove_job(job_id)

    def update_job(self, db_job):
        self.remove_job(db_job.job_id)
        self.add_job(db_job)

    def load_jobs(self):
        with app.app_context():
            db_jobs = SyncJobs.query.filter(SyncJobs.is_valid == True).all()
            for db_job in db_jobs:
                try:
                    self.add_job(db_job)
                except Exception as e:
                    logger.error('add job: %s error: %s', db_job, e)

    def start(self):
        self.scheduler.start()


scheduler_jobs_manager = SchedulerJobsManager()
