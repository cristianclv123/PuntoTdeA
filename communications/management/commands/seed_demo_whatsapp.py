"""Pobla la base de datos con datos de demostración para probar la integración.

No envía nada a Meta: solo crea contactos, segmentos, plantillas y campañas con
estados y `wamid` sintéticos, que es lo que permite ejercitar el flujo de
estados de entrega desde la página de prueba.

Es idempotente: se puede ejecutar varias veces sin duplicar nada.
"""

from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from communications.models import (
    AudienceSegment,
    BroadcastRecipient,
    Campaign,
    Contact,
    ContactEvent,
    MessageTemplate,
    SegmentMembership,
)

# Marca los contactos sembrados para poder limpiarlos después.
SEED_SOURCE = 'demo_whatsapp'
SEED_MARKER = {'seed': True}

CONTACTS = [
    {
        'document_number': '1000000001',
        'full_name': 'Ana María Restrepo Soto',
        'phone': '+573001112201',
        'email': 'ana.restrepo@correo.eafit.edu.co',
        'academic_program': 'Ingeniería en Sistemas',
        'semester': '6',
        'role': Contact.Role.ESTUDIANTE,
        'whatsapp_opt_in': Contact.OptInStatus.SUSCRITO,
    },
    {
        'document_number': '1000000002',
        'full_name': 'Brandon Ospina Herrera',
        'phone': '+573001112202',
        'email': 'brandon.ospina@correo.eafit.edu.co',
        'academic_program': 'Administración de Negocios',
        'semester': '4',
        'role': Contact.Role.ESTUDIANTE,
        'whatsapp_opt_in': Contact.OptInStatus.SUSCRITO,
    },
    {
        'document_number': '1000000003',
        'full_name': 'Camila Andrea Tuberkero',
        'phone': '+573001112203',
        'email': 'camila.tuberkero@correo.eafit.edu.co',
        'academic_program': 'Contaduría Pública',
        'semester': '8',
        'role': Contact.Role.ESTUDIANTE,
        'whatsapp_opt_in': Contact.OptInStatus.SUSCRITO,
    },
    {
        'document_number': '1000000004',
        'full_name': 'Diego Fernando Hoyos',
        'phone': '+573001112204',
        'email': 'diego.hoyos@correo.eafit.edu.co',
        'academic_program': 'Ingeniería Civil',
        'semester': '10',
        'role': Contact.Role.EGRESADO,
        'whatsapp_opt_in': Contact.OptInStatus.SUSCRITO,
    },
    {
        'document_number': '1000000005',
        'full_name': 'Juliana Cepeda Álvarez',
        'phone': '+573001112205',
        'email': 'juliana.cepeda@correo.eafit.edu.co',
        'academic_program': 'Diseño Gráfico',
        'semester': '3',
        'role': Contact.Role.ESTUDIANTE,
        'whatsapp_opt_in': Contact.OptInStatus.SUSCRITO,
    },
    {
        'document_number': '1000000006',
        'full_name': 'Sebastián Díaz Correa',
        'phone': '+573001112206',
        'email': 'sebastian.diaz@correo.eafit.edu.co',
        'academic_program': 'Ingeniería en Sistemas',
        'semester': '2',
        'role': Contact.Role.ASPIRANTE,
        # Given de baja: el envío lo excluye automáticamente.
        'whatsapp_opt_in': Contact.OptInStatus.BAJA,
    },
    {
        'document_number': '1000000007',
        'full_name': 'Valentina Ruiz Ríos',
        'phone': '+573001112207',
        'email': 'valentina.ruiz@correo.eafit.edu.co',
        'academic_program': 'Psicología',
        'semester': '5',
        'role': Contact.Role.ESTUDIANTE,
        'whatsapp_opt_in': Contact.OptInStatus.SUSCRITO,
    },
    {
        'document_number': '1000000008',
        'full_name': 'Andrés Felipe Villa',
        'phone': '+573001112208',
        'email': 'andres.villa@correo.eafit.edu.co',
        'academic_program': 'Medicina',
        'semester': '1',
        'role': Contact.Role.ASPIRANTE,
        'whatsapp_opt_in': Contact.OptInStatus.NO_CONTACTADO,
    },
]

TEMPLATES = [
    {
        'name': 'Recordatorio de matrícula',
        'meta_template_name': 'recordatorio_matricula_2026',
        'category': MessageTemplate.Category.UTILITY,
        'body_text': (
            'Hola {{1}}, tu matrícula para {{2}} sigue pendiente. '
            'Ingresa al portal del estudiante antes de la fecha límite.'
        ),
        'status': MessageTemplate.Status.APPROVED,
        'variable_types': {'1': 'text', '2': 'text'},
    },
    {
        'name': 'Borrador de bienvenida',
        'meta_template_name': 'bienvenida_nuevos_2026',
        'category': MessageTemplate.Category.MARKETING,
        'body_text': '¡Bienvenido/a a Punto TdeA, {{1}}!',
        # En borrador: el envío real la rechaza a propósito.
        'status': MessageTemplate.Status.DRAFT,
        'variable_types': {'1': 'text'},
    },
]

SEGMENTS = [
    {
        'name': 'Demo: creados 2026-1',
        'description': 'Segmento de demostración con todos los contactos sembrados.',
        'all_contacts': True,
    },
    {
        'name': 'Demo: solo matriculados',
        'description': 'Excluye al contacto que dio de baja, para probar el filtro.',
        'opted_in_only': True,
    },
]

CAMPAIGN_SENT = 'Demo: recordatorio de matrícula (enviada)'

# Estado por destinatario. Los `wamid` son sintéticos: sirven para ejercitar el
# webhook de estados, no provienen de Meta.
RECIPIENT_STATES = [
    {'document_number': '1000000001', 'status': BroadcastRecipient.Status.READ, 'wamid': 'wamid.SEED0001'},
    {'document_number': '1000000002', 'status': BroadcastRecipient.Status.DELIVERED, 'wamid': 'wamid.SEED0002'},
    {'document_number': '1000000003', 'status': BroadcastRecipient.Status.SENT, 'wamid': 'wamid.SEED0003'},
    {'document_number': '1000000004', 'status': BroadcastRecipient.Status.FAILED, 'wamid': 'wamid.SEED0004'},
    {'document_number': '1000000005', 'status': BroadcastRecipient.Status.QUEUED, 'wamid': ''},
    # El que dio de baja: ya marcado como excluido por el envío.
    {'document_number': '1000000006', 'status': BroadcastRecipient.Status.OPTED_OUT, 'wamid': ''},
    {'document_number': '1000000007', 'status': BroadcastRecipient.Status.DELIVERED, 'wamid': 'wamid.SEED0007'},
    {'document_number': '1000000008', 'status': BroadcastRecipient.Status.PENDING, 'wamid': ''},
]

# Orden de los estados en el tiempo, para que las marcas de fecha tengan sentido.
STATE_OFFSET_HOURS = {
    BroadcastRecipient.Status.QUEUED: 48,
    BroadcastRecipient.Status.SENT: 47,
    BroadcastRecipient.Status.DELIVERED: 46,
    BroadcastRecipient.Status.READ: 12,
    BroadcastRecipient.Status.FAILED: 46,
    BroadcastRecipient.Status.OPTED_OUT: 47,
    BroadcastRecipient.Status.PENDING: None,
}


def _stamp(hours_ago):
    if hours_ago is None:
        return None
    return timezone.now() - timedelta(hours=hours_ago)


class Command(BaseCommand):
    help = (
        'Carga datos de demostración para probar la integración de WhatsApp. '
        'Idempotente: se puede repetir sin duplicar. Usa --limpiar para borrar '
        'lo previamente sembrado.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Permite ejecutarlo aunque DEBUG esté apagado.',
        )
        parser.add_argument(
            '--limpiar',
            action='store_true',
            help='Borra los datos de demostración anteriores en lugar de crearlos.',
        )

    def handle(self, *args, **options):
        if not settings.DEBUG and not options['force']:
            raise SystemExit(
                'seed_demo_whatsapp crea datos ficticios y está pensado solo para '
                'desarrollo. DEBUG está apagado; si de verdad quieres continuar, '
                'pásale --force.'
            )

        if options['limpiar']:
            self._limpiar()
            return

        with transaction.atomic():
            contacts = self._crear_contactos()
            self._crear_segmentos(contacts)
            self._crear_plantillas()
            self._crear_campanas(contacts)

        self.stdout.write(self.style.SUCCESS('Datos de demostración cargados.'))
        self.stdout.write(
            f'  Campaña enviada:   {CAMPAIGN_SENT} '
            f'({Campaign.objects.filter(name=CAMPAIGN_SENT).first().total_recipients} destinatarios)'
        )
        self.stdout.write(
            '  Los wamid son sintéticos (wamid.SEED0002, wamid.SEED0007):'
        )
        self.stdout.write('  no provienen de Meta, solo ejercitan la lógica de estados.')
        self.stdout.write(
            '  Para probar el envío real, usa la campaña en borrador, que solo'
        )
        self.stdout.write('  tiene destinatarios pendientes, o la plantilla aprobada.')

    # --- pasos ---

    def _crear_contactos(self) -> dict:
        contacts = {}
        for item in CONTACTS:
            contact, _ = Contact.objects.update_or_create(
                document_number=item['document_number'],
                defaults={**item, 'source': SEED_SOURCE},
            )
            contacts[item['document_number']] = contact
        return contacts

    def _crear_segmentos(self, contacts: dict) -> None:
        for item in SEGMENTS:
            segment, _ = AudienceSegment.objects.update_or_create(
                name=item['name'],
                defaults={
                    'description': item['description'],
                    'source_type': AudienceSegment.SourceType.MANUAL,
                },
            )
            if item.get('all_contacts'):
                selected = contacts.values()
            else:
                selected = [
                    c for c in contacts.values()
                    if c.whatsapp_opt_in != Contact.OptInStatus.BAJA
                ]
            # Reemplaza la membresía para que el segmento refleje el estado actual.
            SegmentMembership.objects.filter(segment=segment).delete()
            SegmentMembership.objects.bulk_create(
                SegmentMembership(segment=segment, contact=contact)
                for contact in selected
            )

    def _crear_plantillas(self) -> None:
        for item in TEMPLATES:
            MessageTemplate.objects.update_or_create(
                meta_template_name=item['meta_template_name'],
                defaults={
                    'name': item['name'],
                    'category': item['category'],
                    'body_text': item['body_text'],
                    'status': item['status'],
                    'header_type': MessageTemplate.HeaderType.NONE,
                    'language': 'es_CO',
                },
            )

    def _crear_campanas(self, contacts: dict) -> None:
        template = MessageTemplate.objects.get(
            meta_template_name='recordatorio_matricula_2026'
        )
        segment = AudienceSegment.objects.get(name=SEGMENTS[0]['name'])
        draft_template = MessageTemplate.objects.get(
            meta_template_name='bienvenida_nuevos_2026'
        )
        opted_in_segment = AudienceSegment.objects.get(name=SEGMENTS[1]['name'])

        sent, _ = Campaign.objects.update_or_create(
            name=CAMPAIGN_SENT,
            defaults={
                'template': template,
                'segment': segment,
                'status': Campaign.Status.SENT,
                'default_params': {
                    '1': 'contact.full_name',
                    '2': '2026-1',
                },
                'created_by': SEED_SOURCE,
                'sent_at': _stamp(48),
            },
        )

        ContactEvent.objects.filter(
            campaign=sent, payload=SEED_MARKER
        ).delete()

        for item in RECIPIENT_STATES:
            contact = contacts[item['document_number']]
            status = item['status']
            offset = STATE_OFFSET_HOURS.get(status)
            recipient, created = BroadcastRecipient.objects.update_or_create(
                campaign=sent,
                contact=contact,
                defaults={
                    'phone_snapshot': contact.phone,
                    'params': {'1': contact.full_name, '2': '2026-1'},
                    'status': status,
                    'provider': 'meta' if item['wamid'] else '',
                    'provider_message_id': item['wamid'],
                    'error_message': (
                        'Número no entregado (131026 Message undeliverable)'
                        if status == BroadcastRecipient.Status.FAILED else ''
                    ),
                    'queued_at': _stamp(offset),
                    'sent_at': _stamp(offset) if status != BroadcastRecipient.Status.PENDING else None,
                    'delivered_at': _stamp(
                        (offset - 1) if status in {
                            BroadcastRecipient.Status.DELIVERED,
                            BroadcastRecipient.Status.READ,
                        } else None
                    ),
                    'read_at': _stamp(offset) if status == BroadcastRecipient.Status.READ else None,
                },
            )
            if created or not recipient.events.exists():
                self._sembrar_eventos(recipient, status)

        # Campaña en borrador: todos los destinatarios quedan pendientes, que es
        # exactamente lo que necesita el envío real para probarse con credenciales.
        Campaign.objects.update_or_create(
            name='Demo: bienvenida a admitidos (borrador)',
            defaults={
                'template': draft_template,
                'segment': opted_in_segment,
                'status': Campaign.Status.DRAFT,
                'default_params': {'1': 'contact.full_name'},
                'created_by': SEED_SOURCE,
            },
        )

    def _sembrar_eventos(self, recipient: BroadcastRecipient, status: str) -> None:
        """Línea de tiempo del contacto, coherente con el estado del destinatario."""
        chain = {
            BroadcastRecipient.Status.SENT: [ContactEvent.EventType.MESSAGE_SENT],
            BroadcastRecipient.Status.DELIVERED: [
                ContactEvent.EventType.MESSAGE_SENT,
                ContactEvent.EventType.MESSAGE_DELIVERED,
            ],
            BroadcastRecipient.Status.READ: [
                ContactEvent.EventType.MESSAGE_SENT,
                ContactEvent.EventType.MESSAGE_DELIVERED,
                ContactEvent.EventType.MESSAGE_READ,
            ],
            BroadcastRecipient.Status.FAILED: [
                ContactEvent.EventType.MESSAGE_SENT,
                ContactEvent.EventType.MESSAGE_FAILED,
            ],
        }
        for event_type in chain.get(status, []):
            ContactEvent.objects.create(
                contact=recipient.contact,
                event_type=event_type,
                campaign=recipient.campaign,
                broadcast_recipient=recipient,
                payload={**SEED_MARKER, 'status': recipient.status},
            )

    def _limpiar(self) -> None:
        campaigns = Campaign.objects.filter(name__startswith='Demo:')
        names = list(campaigns.values_list('name', flat=True))
        campaigns.delete()
        AudienceSegment.objects.filter(name__startswith='Demo:').delete()
        demo_template_names = [
            t['meta_template_name'] for t in TEMPLATES
        ]

        # Solo eliminar plantillas del seed que no estén siendo utilizadas
        # por campañas que no sean de demostración.
        for template in MessageTemplate.objects.filter(
            meta_template_name__in=demo_template_names
        ):
            used_by_real_campaign = Campaign.objects.filter(
                template=template
            ).exclude(name__startswith='Demo:').exists()

            if not used_by_real_campaign:
                template.delete()
        ContactEvent.objects.filter(payload=SEED_MARKER).delete()
        # Cuenta antes de borrar: delete() devuelve un total que incluye los
        # borrados en cascada y daría un número que no corresponde a contactos.
        to_remove = Contact.objects.filter(source=SEED_SOURCE)
        removed_contacts = to_remove.count()
        to_remove.delete()

        self.stdout.write(self.style.SUCCESS('Datos de demostración borrados.'))
        for name in names:
            self.stdout.write(f'  campaña: {name}')
        self.stdout.write(f'  contactos: {removed_contacts}')
        self.stdout.write(
            '  Los contactos que tuvieras antes de sembrar no se borran: solo los'
        )
        self.stdout.write('  marcados como origen demo_whatsapp.')
