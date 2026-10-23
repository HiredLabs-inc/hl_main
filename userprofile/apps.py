from django.apps import AppConfig


class UserprofileConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'userprofile'

    def ready(self):
        from pipeline import services

        from . import bootcamp

        if bootcamp.status_rule not in services.STATUS_RULES:
            services.STATUS_RULES.append(bootcamp.status_rule)
