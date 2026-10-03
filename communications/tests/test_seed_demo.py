from io import StringIO

from django.core.management import call_command
from django.test import TestCase, override_settings

from communications.models import (
    AudienceSegment,
    BroadcastRecipient,
    Campaign,
    Contact,
    ContactEvent,
    MessageTemplate,
)


@override_settings(DEBUG=True)
class SeedDemoCommandTests(TestCase):
    """El runner de tests pone DEBUG=False, así que el entorno de desarrollo
    se declara explícitamente para ejercitar la ruta normal del comando."""
    def _run(self, *args, **kwargs):
        out = StringIO()
        call_command('seed_demo_whatsapp', *args, stdout=out, stderr=StringIO(), **kwargs)
        return out.getvalue()

    def test_creates_a_coherent_scenario(self):
        self._run()

        contacts = Contact.objects.filter(source='demo_whatsapp')
        self.assertEqual(contacts.count(), 8)
        self.assertEqual(AudienceSegment.objects.filter(name__startswith='Demo:').count(), 2)

        campaign = Campaign.objects.get(name__startswith='Demo: recordatorio')
        self.assertEqual(campaign.status, Campaign.Status.SENT)
        self.assertEqual(campaign.total_recipients, 8)
        self.assertEqual(campaign.read_count, 1)
        self.assertEqual(campaign.failed_count, 1)

        statuses = set(
            campaign.recipients.values_list('status', flat=True)
        )
        # Cubre un estado por cada rama que el webhook puede tocar.
        for expected in (
            BroadcastRecipient.Status.PENDING,
            BroadcastRecipient.Status.SENT,
            BroadcastRecipient.Status.DELIVERED,
            BroadcastRecipient.Status.READ,
            BroadcastRecipient.Status.FAILED,
            BroadcastRecipient.Status.OPTED_OUT,
        ):
            self.assertIn(expected, statuses)

    def test_synthesized_wamids_are_unique_and_marked_as_meta(self):
        self._run()

        wamids = list(
            BroadcastRecipient.objects.exclude(provider_message_id='').values_list(
                'provider_message_id', flat=True
            )
        )
        self.assertEqual(len(wamids), len(set(wamids)))
        # El prefijo los delata como sintéticos: nadie los confunde con Meta.
        self.assertTrue(all(w.startswith('wamid.SEED') for w in wamids))
        self.assertEqual(
            set(
                BroadcastRecipient.objects.exclude(provider_message_id='').values_list(
                    'provider', flat=True
                )
            ),
            {'meta'},
        )

    def test_running_twice_does_not_duplicate(self):
        self._run()
        before = {
            'contacts': Contact.objects.filter(source='demo_whatsapp').count(),
            'recipients': BroadcastRecipient.objects.count(),
            'events': ContactEvent.objects.filter(payload__seed=True).count(),
        }

        self._run()

        self.assertEqual(Contact.objects.filter(source='demo_whatsapp').count(), before['contacts'])
        self.assertEqual(BroadcastRecipient.objects.count(), before['recipients'])
        self.assertEqual(
            ContactEvent.objects.filter(payload__seed=True).count(), before['events']
        )

    def test_draft_campaign_leaves_recipients_pending_for_a_real_send(self):
        self._run()

        draft = Campaign.objects.get(name__startswith='Demo: bienvenida')
        self.assertEqual(draft.status, Campaign.Status.DRAFT)
        # El envío solo procesa los pendientes: es lo que habilita la prueba real.
        self.assertEqual(
            draft.segment.contacts.filter(whatsapp_opt_in=Contact.OptInStatus.BAJA).count(),
            0,
        )
        self.assertEqual(
            draft.template.status, MessageTemplate.Status.DRAFT
        )

    def test_limpiar_removes_only_seeded_data(self):
        self._run()
        propio = Contact.objects.create(
            full_name='Contacto Real', document_number='9999999999', phone='+573009999999'
        )

        self._run('--limpiar')

        self.assertFalse(Contact.objects.filter(source='demo_whatsapp').exists())
        self.assertFalse(Campaign.objects.filter(name__startswith='Demo:').exists())
        self.assertFalse(AudienceSegment.objects.filter(name__startswith='Demo:').exists())
        self.assertFalse(ContactEvent.objects.filter(payload__seed=True).exists())
        # El contacto que no es de la semilla sobrevive.
        self.assertTrue(Contact.objects.filter(pk=propio.pk).exists())

    def test_limpiar_reports_the_real_contact_count(self):
        """delete() incluye los cascadas: el número debe ser el de contactos."""
        self._run()
        out = self._run('--limpiar')
        self.assertIn('contactos: 8', out)


@override_settings(DEBUG=False)
class SeedDemoGuardTests(TestCase):
    """Sin la guarda, una semilla de datos ficticios en producción crearía
    campañas con aspecto real. Verifica que se opone."""

    def test_refuses_to_run_with_debug_disabled(self):
        from io import StringIO

        with self.assertRaises(SystemExit) as ctx:
            call_command(
                'seed_demo_whatsapp', stdout=StringIO(), stderr=StringIO()
            )
        self.assertIn('--force', str(ctx.exception))
        self.assertFalse(Contact.objects.filter(source='demo_whatsapp').exists())

    def test_force_allows_running_with_debug_disabled(self):
        from io import StringIO

        call_command('seed_demo_whatsapp', '--force', stdout=StringIO(), stderr=StringIO())
        self.assertEqual(Contact.objects.filter(source='demo_whatsapp').count(), 8)
