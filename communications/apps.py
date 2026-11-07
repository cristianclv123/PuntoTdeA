"""Configuracion de la app communications.

Incluye el scheduler incrustado de campañas programadas. En Render free no hay
workers ni Cron Jobs, asi que puede correr dentro del propio proceso web
(Daphne) como un hilo demonio. El flag se desactiva por defecto y no arranca en
tests ni comandos de gestion.
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

# Intervalo del ciclo en segundos. Debe coincidir con el comando
# run_scheduled_campaigns --interval 30.
CAMPAIGN_SCHEDULER_INTERVAL = 30.0


def _should_start_campaign_scheduler() -> bool:
    """True si el scheduler de campañas debe arrancar en este proceso."""
    if not settings.ENABLE_CAMPAIGN_SCHEDULER:
        return False
    if len(sys.argv) > 1 and sys.argv[1] in COMMANDS_WITHOUT_SCHEDULER:
        return False
    return True


def run_campaign_scheduler(
    interval: float = CAMPAIGN_SCHEDULER_INTERVAL,
    max_iterations: int | None = None,
) -> None:
    """Ejecuta ``process_due_campaigns`` en un ciclo infinito.

    ``max_iterations`` existe para pruebas. En produccion el hilo corre hasta
    que el proceso termina.
    """
    iterations = 0
    while max_iterations is None or iterations < max_iterations:
        try:
            # Se importa dentro del hilo para no cargar comandos antes de tiempo.
            # Si la importacion falla, se reintenta en la siguiente pasada.
            from communications.management.commands.run_scheduled_campaigns import (
                Command,
            )

            Command().process_due_campaigns()
        except Exception:
            logger.exception('Error en el scheduler de campañas.')
        iterations += 1
        if max_iterations is None or iterations < max_iterations:
            time.sleep(interval)


class CommunicationsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'communications'

    def ready(self):
        if not _should_start_campaign_scheduler():
            return

        thread = threading.Thread(
            target=run_campaign_scheduler,
            name='campaign-scheduler',
            daemon=True,
        )
        thread.start()
        logger.info('Scheduler de campañas incrustado activado.')
