
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

@app.on_after_configure.connect
def setup_periodic_tasks(sender: Celery, **kwargs):
    sender.add_periodic_task(10.0, debug_task.s(), name='add every 10')

@app.task()
def debug_task():
    print(f'Request: CRONTAB')
