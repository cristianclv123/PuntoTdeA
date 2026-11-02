"""Avisa y cierra las conversaciones de WhatsApp inactivas.

Sin ``--interval`` ejecuta una sola pasada, que es lo que espera un cron
tradicional. Con ``--interval`` se queda como proceso persistente y repite el
ciclo cada N segundos; ese es el modo que usa el servicio ``inactivity`` de
``docker-compose.yml`` (o systemd/supervisor en un servidor propio).
"""

import time

from django.core.management.base import BaseCommand, CommandError

from knowledge.chatbot.whatsapp import process_inactivity


class Command(BaseCommand):
    help = (
        'Avisa a las conversaciones de WhatsApp inactivas durante 5 minutos y '
        'las cierra 2 minutos después si el usuario no responde.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--interval',
            type=int,
            default=None,
            help=(
                'Repite el ciclo cada N segundos en vez de ejecutar una sola '
                'pasada. Pensado para un servicio persistente.'
            ),
        )
        parser.add_argument(
            '--once',
            action='store_true',
            help='Ejecuta una sola pasada aunque se haya indicado --interval.',
        )

    def handle(self, *args, **options):
        interval = options['interval']
        if interval is not None and interval < 1:
            raise CommandError('--interval debe ser un entero mayor que cero.')

        once = options['once'] or interval is None

        try:
            while True:
                summary = process_inactivity()
                self.stdout.write(
                    f'Avisos de inactividad enviados: {summary["warned"]}'
                )
                self.stdout.write(
                    f'Conversaciones cerradas por inactividad: {summary["closed"]}'
                )
                if once:
                    return
                time.sleep(interval)
        except KeyboardInterrupt:
            self.stdout.write('Servicio de inactividad detenido.')
