from django.apps import AppConfig


class KnowledgeConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'PuntoTdeA.knowledge'

    def ready(self):
        from . import signals as _signals  # noqa: F401

