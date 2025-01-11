
from __future__ import absolute_import, unicode_literals
import os
import configurations
from celery import Celery
from celery.schedules import crontab

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'japb_api.config')
os.environ.setdefault('DJANGO_CONFIGURATION', 'Local')

configurations.setup()

app = Celery('japb_api')

app.config_from_object('django.conf:settings', namespace='CELERY')

# # Auto-discover tasks from installed apps.
app.autodiscover_tasks()

app.conf.beat_schedule = {
    'update_user_reports': {
        'task': 'japb_api.reports.tasks.update_user_reports',
        'schedule': crontab(minute=0, hour=0),
    },
    'debug_task': {
        'task': 'japb_api.celery.debug_task',
        'schedule': 30.0,
    },
}


@app.task()
def debug_task():
    print(f'Request: CRONTAB')
