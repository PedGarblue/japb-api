from django.apps import AppConfig

class ReportsConfig(AppConfig):
    name = 'japb_api.reports'

    def ready(self):
        pass
        # Import signals here to ensure they are registered when the app is ready
