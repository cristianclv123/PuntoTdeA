"""TEMPORAL: recrea el espejo local de la plantilla real de Meta.

La plantilla existe en Meta (APROBADA) pero la consola de pruebas solo la ofrece
si hay una fila local `approved` que la refleje. Este comando la vuelve a crear
en cualquier base de datos, sin arrastrar toda la BD.

Se puede borrar cuando ya no se necesite. Es idempotente.
"""

from django.core.management.base import BaseCommand

from communications.models import MessageTemplate

TEMPLATES = [
    {
        "meta_template_name": "3p_direct_integration_test_template",
        "name": "3p Integration Test",
        "language": "en_US",
        "category": MessageTemplate.Category.UTILITY,
        "body_text": (
            "Welcome! This is a test message from the WhatsApp Business Platform. "
            "You have successfully configured your WhatsApp Business account and "
            "completed onboarding. You can now start sending messages to your "
            "customers."
        ),
        "header_type": MessageTemplate.HeaderType.NONE,
        "status": MessageTemplate.Status.APPROVED,
    },
]


class Command(BaseCommand):
    help = (
        "TEMPORAL: crea el espejo local de la plantilla real de Meta para la "
        "consola de pruebas. Idempotente."
    )

    def handle(self, *args, **options):
        for item in TEMPLATES:
            name = item["meta_template_name"]
            defaults = {key: value for key, value in item.items() if key != "meta_template_name"}
            template, created = MessageTemplate.objects.update_or_create(
                meta_template_name=name, defaults=defaults
            )
            action = "creada" if created else "actualizada"
            self.stdout.write(
                self.style.SUCCESS(
                    f"  {action}: {template.meta_template_name} "
                    f"({template.language}, {template.status})"
                )
            )
