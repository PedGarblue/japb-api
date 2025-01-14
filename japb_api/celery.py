
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
    'update_currency_historial': {
        'task': 'japb_api.currencies.tasks.update_currency_historial',
        # 9:30 VET (13:30 UTC) and 13:30 VET (17:30 UTC)
        'schedule': crontab(minute=30, hour='13,17'),
    },
}
