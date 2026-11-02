"""Configuracion de la app knowledge.

Aqui vive el scheduler incrustado de inactividad. En Render free no hay
workers ni Cron Jobs, asi que el ciclo 5 + 2 minutos puede correr dentro del
propio proceso web (Daphne) como un hilo demonio. El flag se desactiva por
defecto y localmente sigue usandose el servicio `inactivity` de
`docker-compose.yml`.
"""

import logging
import sys
import threading
import time

from django.apps import AppConfig
from django.conf import settings

logger = logging.getLogger(__name__)

# Comandos en los que no debe arrancar el scheduler: tests, migraciones y
# comandos de gestion que no son el servidor real.
COMMANDS_WITHOUT_SCHEDULER = {
    'test',
    'migrate',
    'makemigrations',
    'collectstatic',
    'check',
    'shell',
    'createsuperuser',
    'run_scheduled_campaigns',
    'close_inactive_chats',
}

# Intervalo del ciclo en segundos. Debe coincidir con la documentacion y el
# comando close_inactive_chats --interval 60.
INACTIVITY_SCHEDULER_INTERVAL = 60.0


def _should_start_scheduler() -> bool:
    """True si el scheduler incrustado debe arrancar en este proceso."""
    if not settings.ENABLE_INACTIVITY_SCHEDULER:
        return False
    if len(sys.argv) > 1 and sys.argv[1] in COMMANDS_WITHOUT_SCHEDULER:
        return False
    return True


def run_inactivity_scheduler(
    interval: float = INACTIVITY_SCHEDULER_INTERVAL,
    max_iterations: int | None = None,
) -> None:
    """Ejecuta ``process_inactivity`` en un ciclo infinito.

    ``max_iterations`` existe para pruebas. En produccion el hilo corre hasta
    que el proceso termina.
    """
    iterations = 0
    while max_iterations is None or iterations < max_iterations:
        try:
            # Se importa dentro del hilo para no tocar el registro de apps antes
            # de tiempo y para que el scheduler no cargue el modulo en cada
            # comando. Si la importacion falla, se reintenta en la siguiente
            # pasada en vez de morir.
            from knowledge.chatbot.whatsapp import process_inactivity

            process_inactivity()
        except Exception:
            # Un error transitorio (base de datos cayendo, Meta sin responder)
            # no debe tumbar el servidor web. Se registra y se reintenta en la
            # siguiente pasada.
            logger.exception('Error en el scheduler de inactividad.')
        iterations += 1
        if max_iterations is None or iterations < max_iterations:
            time.sleep(interval)


class KnowledgeConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'knowledge'

    def ready(self):
        from . import signals as _signals  # noqa: F401

        if not _should_start_scheduler():
            return

        thread = threading.Thread(
            target=run_inactivity_scheduler,
            name='inactivity-scheduler',
            daemon=True,
        )
        thread.start()
        logger.info('Scheduler de inactividad incrustado activado.')
