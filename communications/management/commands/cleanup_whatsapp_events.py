"""Limpia eventos antiguos del webhook de WhatsApp para controlar el crecimiento.

Meta notifica un estado (sent/delivered/read) por cada mensaje de campaña:
con miles de destinatarios, la tabla de eventos crece rápido. Este comando
borra los eventos de estado antiguos y conserva los que sirven para
diagnóstico: los `failed` (errores de entrega) y todos los `inbound`
(conversaciones del bot).

Por defecto es un ensayo (dry-run): solo informa lo que borraría. Para borrar
de verdad hace falta `--ejecutar`.

Ejemplos:
  python manage.py cleanup_whatsapp_events
  python manage.py cleanup_whatsapp_events --days 7 --ejecutar
"""

from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from communications.models import WhatsAppWebhookEvent


class Command(BaseCommand):
    help = (
        "Borra eventos de estado del webhook más antiguos que --days, "
        "conservando los 'failed' y los mensajes entrantes."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=30,
            help="Edad mínima en días para borrar un evento (default: 30).",
        )
        parser.add_argument(
            "--ejecutar",
            action="store_true",
            help="Borra de verdad. Sin este flag el comando solo informa (dry-run).",
        )

    def handle(self, *args, **options):
        days = options["days"]
        if days < 1:
            raise CommandError("--days debe ser al menos 1.")

        cutoff = timezone.now() - timedelta(days=days)
        total = WhatsAppWebhookEvent.objects.count()

        # Candidatos: estados de envío procesados (sent/delivered/read u otros)
        # anteriores al corte. Se excluye 'failed' porque conserva el motivo del
        # error; los 'inbound' (mensajes del bot) quedan fuera por constructor.
        candidates = (
            WhatsAppWebhookEvent.objects.filter(
                created_at__lt=cutoff,
                event_type=WhatsAppWebhookEvent.Type.STATUS,
            )
            .exclude(status="failed")
            .order_by()
        )
        candidates_count = candidates.count()

        self.stdout.write(self.style.MIGRATE_HEADING("Eventos del webhook de WhatsApp"))
        self.stdout.write(f"  total de eventos              {total}")
        self.stdout.write(f"  umbral de antigüedad          > {days} días (corte: {cutoff:%Y-%m-%d %H:%M})")
        self.stdout.write(f"  candidatos a borrar           {candidates_count}")
        self.stdout.write(f"  se conservarían               {total - candidates_count}")
        self.stdout.write(
            "  (failed, inbound y eventos más recientes que el corte)"
        )

        if not candidates_count:
            self.stdout.write(self.style.SUCCESS("  Nada que borrar."))
            return

        if not options["ejecutar"]:
            self.stdout.write(
                self.style.WARNING(
                    "  Modo ensayo: no se borró nada. Usa --ejecutar para borrar."
                )
            )
            return

        deleted, _ = candidates.delete()
        self.stdout.write(
            self.style.SUCCESS(f"  Borrados {deleted} eventos de estado antiguos.")
        )