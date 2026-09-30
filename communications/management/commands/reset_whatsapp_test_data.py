"""Deja la consola de pruebas de WhatsApp en cero para empezar a medir de verdad.

La página de /whatsapp-prueba/ muestra lo que Meta realmente reporta: los
envíos que hacés, los estados que vuelven por webhook y las conversaciones del
bot. Con datos de demostración mezclados es imposible distinguir un problema
real de uno sembrado, así que este comando borra todo lo que no es producción:

  - los eventos del webhook (entradas, estados y los registros de los envíos
    de prueba, que se guardan en la misma tabla);
  - las campañas, segmentos, destinatarios y contactos que creó el comando
    seed_demo_whatsapp;
  - las conversaciones del chatbot que llegaron por WhatsApp.

NO toca las plantillas de mensajes, porque hacen falta para probar el envío
con plantilla, ni los contactos reales, ni los usuarios.

Por defecto es un ensayo (dry-run): solo informa lo que borraría. Para borrar
de verdad hace falta --ejecutar.

Ejemplos:
  python manage.py reset_whatsapp_test_data
  python manage.py reset_whatsapp_test_data --ejecutar
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q

from communications.management.commands.seed_demo_whatsapp import (
    SEED_MARKER,
    SEED_SOURCE,
)
from communications.models import (
    AudienceSegment,
    BroadcastRecipient,
    Campaign,
    Contact,
    ContactEvent,
    WhatsAppWebhookEvent,
)
from knowledge.models import ChatConversation

# `created_by` y el prefijo de nombre son las dos marcas que deja el seed. Se
# acepta cualquiera de las dos para no arrastrar una campaña real que happen de
# llamarse "Demo: ...".
DEMO_NAME_PREFIX = "Demo:"


class Command(BaseCommand):
    help = (
        "Borra los datos de demo y de observabilidad de WhatsApp: eventos del "
        "webhook, campañas sembradas y conversaciones del bot. Las plantillas "
        "y los contactos reales se conservan."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--ejecutar",
            action="store_true",
            help="Borra de verdad. Sin este flag el comando solo informa (dry-run).",
        )

    def handle(self, *args, **options):
        ejecutar = options["ejecutar"]

        campanas = Campaign.objects.filter(
            Q(name__startswith=DEMO_NAME_PREFIX) | Q(created_by=SEED_SOURCE)
        )
        segmentos = AudienceSegment.objects.filter(name__startswith=DEMO_NAME_PREFIX)
        contactos_demo = Contact.objects.filter(source=SEED_SOURCE)
        eventos_demo = ContactEvent.objects.filter(payload=SEED_MARKER)

        # Un contacto de la semilla no se borra si una campaña real lo tiene
        # como destinatario: `BroadcastRecipient.contact` es CASCADE, así que
        # borrarlo se llevaría por delante un envío que sí importa.
        con_envio_real = BroadcastRecipient.objects.exclude(
            campaign__in=campanas
        ).values_list("contact_id", flat=True)
        contactos_a_borrar = contactos_demo.exclude(id__in=con_envio_real)
        contactos_protegidos = contactos_demo.filter(id__in=con_envio_real)

        conversaciones = ChatConversation.objects.filter(channel="whatsapp")
        eventos = WhatsAppWebhookEvent.objects.all()

        self.stdout.write(self.style.MIGRATE_HEADING("Reinicio de la consola de pruebas"))
        self._linea("eventos del webhook (entradas, estados y envíos de prueba)", eventos.count())
        self._linea("conversaciones del bot por WhatsApp", conversaciones.count())
        self._linea("campañas de demostración", campanas.count())
        self._linea("destinatarios de esas campañas", BroadcastRecipient.objects.filter(campaign__in=campanas).count())
        self._linea("segmentos de demostración", segmentos.count())
        self._linea("contactos de demostración", contactos_demo.count())
        self._linea("eventos de contacto de demostración", eventos_demo.count())

        if contactos_protegidos.exists():
            self.stdout.write(
                self.style.WARNING(
                    f"  OJO: {contactos_protegidos.count()} contacto(s) de la semilla "
                    "aparecen en una campaña que no es de demostración. Se conservan."
                )
            )

        total = (
            eventos.count()
            + conversaciones.count()
            + campanas.count()
            + segmentos.count()
            + contactos_a_borrar.count()
            + eventos_demo.count()
        )
        if not total:
            self.stdout.write(self.style.SUCCESS("  No hay nada que borrar."))
            return

        self.stdout.write("")
        self.stdout.write("  Se conservan: plantillas de mensajes, contactos reales y usuarios.")

        if not ejecutar:
            self.stdout.write(
                self.style.WARNING("  Modo ensayo: no se borró nada. Usa --ejecutar para borrar.")
            )
            return

        with transaction.atomic():
            # El orden importa: `Campaign.segment` y `Campaign.template` son
            # PROTECT, así que las campañas tienen que caer antes que los segmentos.
            campanas_nombres = list(campanas.values_list("name", flat=True))
            campanas.delete()
            segmentos.delete()
            eventos_demo.delete()
            contactos_a_borrar.delete()
            conversaciones.delete()
            eventos.delete()

        self.stdout.write(self.style.SUCCESS("  Consola de pruebas reiniciada."))
        for name in campanas_nombres:
            self.stdout.write(f"  campaña borrada: {name}")
        self.stdout.write("  Quedan las plantillas aprobadas para probar el envío con plantilla.")

    def _linea(self, etiqueta, cantidad):
        self.stdout.write(f"  {etiqueta:<54}{cantidad}")
