"""Procesa periódicamente las campañas programadas que ya vencieron."""

import logging
import time

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from communications.models import Campaign
from communications.services import campaign_service

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Procesa campañas programadas cuya fecha de envío ya venció."

    def add_arguments(self, parser):
        parser.add_argument(
            "--interval",
            type=int,
            default=30,
            help="Segundos entre consultas (predeterminado: 30).",
        )
        parser.add_argument(
            "--once",
            action="store_true",
            help="Procesa las campañas vencidas una vez y termina.",
        )

    def handle(self, *args, **options):
        interval = options["interval"]
        if interval < 1:
            raise CommandError("--interval debe ser un entero mayor que cero.")

        while True:
            processed = self.process_due_campaigns()
            self.stdout.write(f"Campañas programadas procesadas: {processed}.")
            if options["once"]:
                return
            time.sleep(interval)

    def process_due_campaigns(self):
        campaign_ids = list(
            Campaign.objects.filter(
                status=Campaign.Status.SCHEDULED,
                scheduled_at__lte=timezone.now(),
            )
            .order_by("scheduled_at", "pk")
            .values_list("pk", flat=True)
        )

        processed = 0
        for campaign_id in campaign_ids:
            try:
                campaign_service.send_campaign(Campaign(pk=campaign_id))
            except Exception:
                logger.exception(
                    "No se pudo procesar la campaña programada %s.", campaign_id
                )
                if self._mark_failed_if_still_scheduled(campaign_id):
                    self.stderr.write(
                        self.style.ERROR(
                            f"La campaña {campaign_id} falló y quedó marcada como fallida."
                        )
                    )
                else:
                    self.stderr.write(
                        self.style.WARNING(
                            f"La campaña {campaign_id} cambió de estado; no se modificó."
                        )
                    )
            else:
                processed += 1

        return processed

    @staticmethod
    def _mark_failed_if_still_scheduled(campaign_id):
        now = timezone.now()
        return Campaign.objects.filter(
            pk=campaign_id,
            status=Campaign.Status.SCHEDULED,
            scheduled_at__lte=now,
        ).update(
            status=Campaign.Status.FAILED,
            updated_at=now,
        ) == 1
