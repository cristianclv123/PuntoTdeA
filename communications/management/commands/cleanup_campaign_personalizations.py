"""Elimina validaciones Excel vencidas que no se asociaron a una campaña."""

from django.core.management.base import BaseCommand
from django.utils import timezone

from communications.models import CampaignPersonalization


class Command(BaseCommand):
    help = "Elimina validaciones Excel vencidas y aún no consumidas."

    def add_arguments(self, parser):
        parser.add_argument(
            "--ejecutar",
            action="store_true",
            help="Borra de verdad. Sin este flag el comando solo informa (dry-run).",
        )

    def handle(self, *args, **options):
        candidates = CampaignPersonalization.objects.filter(
            campaign__isnull=True,
            expires_at__lte=timezone.now(),
        )
        count = candidates.count()
        self.stdout.write(f"Validaciones Excel vencidas sin consumir: {count}")

        if not count:
            self.stdout.write(self.style.SUCCESS("Nada que borrar."))
            return

        if not options["ejecutar"]:
            self.stdout.write(
                self.style.WARNING(
                    "Modo ensayo: no se borró nada. Usa --ejecutar para borrar."
                )
            )
            return

        deleted, _ = candidates.delete()
        self.stdout.write(self.style.SUCCESS(f"Borradas {deleted} validaciones vencidas."))
