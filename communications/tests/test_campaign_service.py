from types import SimpleNamespace

from django.test import SimpleTestCase

from communications.services.campaign_service import _template_ref


class CampaignTemplateSnapshotTests(SimpleTestCase):
    def test_template_ref_includes_static_text_header_from_snapshot(self):
        campaign = SimpleNamespace(
            template_name="recordatorio",
            template_language="es_CO",
            template_snapshot={
                "body_text": "Hola {{1}} y {{2}}",
                "header_type": "text",
                "header_text": "Aviso importante",
                "header_media_url": "",
                "buttons": [{"text": "Ver", "url": "https://example.com"}],
            },
        )

        template = _template_ref(campaign)

        self.assertEqual(template.name, "recordatorio")
        self.assertEqual(template.language, "es_CO")
        self.assertEqual(template.body_text, "Hola {{1}} y {{2}}")
        self.assertEqual(template.header_type, "text")
        self.assertEqual(template.header_text, "Aviso importante")
        self.assertEqual(template.header_media_url, "")

    def test_legacy_snapshot_without_header_text_remains_compatible(self):
        campaign = SimpleNamespace(
            template_name="recordatorio",
            template_language="",
            template_snapshot={
                "body_text": "Hola {{1}}",
                "header_type": "none",
                "header_media_url": "",
            },
        )

        template = _template_ref(campaign)

        self.assertEqual(template.header_type, "none")
        self.assertEqual(template.header_text, "")
        self.assertEqual(template.language, "es_CO")