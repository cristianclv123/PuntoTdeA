import json
from io import BytesIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from openpyxl import Workbook

from communications.adapters.base import SendResult
from communications.models import (
    AudienceSegment,
    BroadcastRecipient,
    Campaign,
    Contact,
)
from communications.services import campaign_service, meta_templates


class CampaignPersonalizationTests(TestCase):
    template_snapshot = {
        "name": "recordatorio",
        "language": "es_CO",
        "category": "UTILITY",
        "body_text": "Hola {{1}}, fecha {{2}}.",
        "header_type": "none",
        "header_text": "",
        "buttons": [],
    }

    meta_template = {
        "meta_id": "meta-template-id",
        "name": "recordatorio",
        "status": "APPROVED",
        "category": "utility",
        "language": "es_CO",
        "body_text": "Hola {{1}}, fecha {{2}}.",
        "header_type": "none",
        "header_text": "",
        "buttons": [],
        "is_sample": False,
    }

    def setUp(self):
        user = get_user_model().objects.create_user(
            username="personalizacion",
            password="test-password",
        )
        self.client.force_login(user)
        self.segment = AudienceSegment.objects.create(name="Aspirantes")
        self.contact = Contact.objects.create(
            full_name="Ana Pérez",
            document_number="1001",
            phone="+573001112233",
            whatsapp_opt_in=Contact.OptInStatus.SUSCRITO,
        )
        self.other_contact = Contact.objects.create(
            full_name="Luis Gómez",
            document_number="1002",
            phone="+573004445566",
            whatsapp_opt_in=Contact.OptInStatus.SUSCRITO,
        )
        self.segment.contacts.add(self.contact, self.other_contact)
        self.meta_template_lookup_patch = patch(
            "communications.services.meta_templates.get_template",
            return_value=meta_templates.TemplateResult(
                ok=True,
                meta_id=self.meta_template["meta_id"],
                meta_status=self.meta_template["status"],
                template=self.meta_template.copy(),
            ),
        )
        self.meta_lookup = self.meta_template_lookup_patch.start()
        self.addCleanup(self.meta_template_lookup_patch.stop)

    @staticmethod
    def _excel(rows):
        workbook = Workbook()
        sheet = workbook.active
        sheet.append(["Documento", "Nombre", "Variable 1", "Variable 2"])
        for row in rows:
            sheet.append(row)
        content = BytesIO()
        workbook.save(content)
        return SimpleUploadedFile(
            "personalizacion.xlsx",
            content.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    def _inspect(self, rows):
        return self.client.post(
            "/campanas/api/campaigns/personalization/inspect/",
            {"file": self._excel(rows)},
        )

    def _validate(self, rows, **overrides):
        payload = {
            "file": self._excel(rows),
            "segment": str(self.segment.pk),
            "template": "meta-template-id",
            "template_name": "recordatorio",
            "template_language": "es_CO",
            "template_snapshot": json.dumps(self.template_snapshot),
            "default_params": "{}",
            "document_column": "0",
            "variable_mappings": json.dumps(
                {
                    "1": {"source": "column", "column": 2},
                    "2": {"source": "fixed", "value": "2026-11-01"},
                }
            ),
        }
        payload.update(overrides)
        return self.client.post(
            "/campanas/api/campaigns/personalization/validate/",
            payload,
        )

    def _create_campaign(self, report, *, confirm_partial=False, **overrides):
        payload = {
            "name": "Recordatorio Excel",
            "template": "meta-template-id",
            "template_name": "recordatorio",
            "template_language": "es_CO",
            "template_snapshot": self.template_snapshot,
            "segment": self.segment.pk,
            "default_params": {},
            "personalization_validation_id": report["validation_id"],
            "confirm_partial": confirm_partial,
        }
        payload.update(overrides)
        return self.client.post(
            "/campanas/api/campaigns/",
            data=json.dumps(payload),
            content_type="application/json",
        )

    def test_normal_campaign_creation_verifies_approved_template(self):
        response = self.client.post(
            "/campanas/api/campaigns/",
            data=json.dumps(
                {
                    "name": "Campaña normal",
                    "template": "meta-template-id",
                    "template_name": "recordatorio",
                    "template_language": "es_CO",
                    "template_snapshot": self.template_snapshot,
                    "segment": self.segment.pk,
                    "default_params": {},
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201, response.content)
        campaign = Campaign.objects.get(pk=response.json()["id"])
        self.assertEqual(campaign.template_snapshot["body_text"], self.meta_template["body_text"])
        self.meta_lookup.assert_called_once_with("meta-template-id")

    def test_normal_campaign_rejects_unavailable_meta_without_creating_campaign(self):
        self.meta_lookup.return_value = meta_templates.TemplateResult(
            ok=False, message="Meta no está disponible."
        )

        response = self.client.post(
            "/campanas/api/campaigns/",
            data=json.dumps(
                {
                    "name": "Campaña sin Meta",
                    "template": "meta-template-id",
                    "template_name": "recordatorio",
                    "template_language": "es_CO",
                    "template_snapshot": self.template_snapshot,
                    "segment": self.segment.pk,
                    "default_params": {},
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("Meta no está disponible", str(response.json()))
        self.assertEqual(Campaign.objects.count(), 0)

    def test_normal_campaign_rejects_client_modified_template_fields(self):
        payload = {
            "name": "Campaña manipulada",
            "template": "meta-template-id",
            "template_name": "recordatorio",
            "template_language": "es_CO",
            "template_snapshot": self.template_snapshot,
            "segment": self.segment.pk,
            "default_params": {},
        }
        altered_snapshots = [
            {**self.template_snapshot, "body_text": "Contenido manipulado"},
            {**self.template_snapshot, "name": "nombre_manipulado"},
            {**self.template_snapshot, "language": "en_US"},
        ]

        for overrides in (
            {"template_name": "nombre_manipulado"},
            {"template_language": "en_US"},
            {"template_snapshot": altered_snapshots[0]},
            {"template_snapshot": altered_snapshots[1]},
            {"template_snapshot": altered_snapshots[2]},
        ):
            with self.subTest(overrides=overrides):
                response = self.client.post(
                    "/campanas/api/campaigns/",
                    data=json.dumps({**payload, **overrides}),
                    content_type="application/json",
                )

                self.assertEqual(response.status_code, 400)
                self.assertEqual(Campaign.objects.count(), 0)

    def test_inspection_returns_excel_columns(self):
        response = self._inspect([["1001", "Ana", "Hola", ""]])

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["columns"],
            [
                {"index": 0, "label": "Documento"},
                {"index": 1, "label": "Nombre"},
                {"index": 2, "label": "Variable 1"},
                {"index": 3, "label": "Variable 2"},
            ],
        )

    def test_valid_document_creates_recipient_with_personalized_params(self):
        response = self._validate([["1001", "Ana", "Bienvenida", ""]])

        self.assertEqual(response.status_code, 201, response.content)
        report = response.json()
        self.assertEqual(report["valid_count"], 1)
        self.assertEqual(report["rejected_count"], 0)
        self.assertEqual(report["valid_rows"][0]["message"], "Hola Bienvenida, fecha 2026-11-01.")

        created = self._create_campaign(report)

        self.assertEqual(created.status_code, 201, created.content)
        campaign = Campaign.objects.get(pk=created.json()["id"])
        recipient = campaign.recipients.get()
        self.assertEqual(recipient.contact, self.contact)
        self.assertEqual(recipient.params, {"1": "Bienvenida", "2": "2026-11-01"})
        self.contact.refresh_from_db()
        self.assertEqual(self.contact.attributes, {})
        self.assertEqual(campaign.personalization.authorized_contact_ids, [str(self.contact.pk)])

    def test_personalization_rejects_sample_template(self):
        sample = {
            **self.meta_template,
            "name": "hello_world",
            "language": "en_US",
            "is_sample": True,
        }
        self.meta_lookup.return_value = meta_templates.TemplateResult(
            ok=True,
            meta_id="meta-template-id",
            meta_status="APPROVED",
            template=sample,
        )

        response = self._validate([["1001", "Ana", "Bienvenida", ""]])

        self.assertEqual(response.status_code, 400)
        self.assertIn("muestra", str(response.json()))
        self.assertEqual(Campaign.objects.count(), 0)

    def test_personalization_rejects_pending_or_rejected_meta_template(self):
        for status_value in ("PENDING", "REJECTED"):
            with self.subTest(status=status_value):
                self.meta_lookup.return_value = meta_templates.TemplateResult(
                    ok=True,
                    meta_id="meta-template-id",
                    meta_status=status_value,
                    template={**self.meta_template, "status": status_value},
                )

                response = self._validate([["1001", "Ana", "Bienvenida", ""]])

                self.assertEqual(response.status_code, 400)
                self.assertEqual(Campaign.objects.count(), 0)

    def test_personalization_rejects_missing_or_unavailable_meta_template(self):
        for result in (
            meta_templates.TemplateResult(
                ok=False, message="Meta no devolvió la plantilla."
            ),
            meta_templates.TemplateResult(
                ok=True,
                meta_id="different-meta-id",
                template={**self.meta_template, "meta_id": "different-meta-id"},
            ),
        ):
            with self.subTest(result=result):
                self.meta_lookup.return_value = result
                response = self._validate([["1001", "Ana", "Bienvenida", ""]])

                self.assertEqual(response.status_code, 400)
                self.assertEqual(Campaign.objects.count(), 0)

    def test_personalization_rejects_client_modified_template_identity_and_content(self):
        altered_snapshot = {**self.template_snapshot, "body_text": "Mensaje manipulado"}
        for overrides in (
            {"template_name": "nombre_manipulado"},
            {"template_language": "en_US"},
            {"template_snapshot": json.dumps(altered_snapshot)},
        ):
            with self.subTest(overrides=overrides):
                response = self._validate(
                    [["1001", "Ana", "Bienvenida", ""]],
                    **overrides,
                )

                self.assertEqual(response.status_code, 400)
                self.assertEqual(Campaign.objects.count(), 0)

    def test_creation_rejects_a_different_template_than_personalization_validation(self):
        report = self._validate([["1001", "Ana", "Bienvenida", ""]]).json()
        different_template = {
            **self.meta_template,
            "meta_id": "another-meta-id",
            "name": "otro_recordatorio",
            "body_text": "Otro texto {{1}}.",
        }
        self.meta_lookup.return_value = meta_templates.TemplateResult(
            ok=True,
            meta_id="another-meta-id",
            meta_status="APPROVED",
            template=different_template,
        )
        different_snapshot = {
            "name": "otro_recordatorio",
            "language": "es_CO",
            "category": "utility",
            "body_text": "Otro texto {{1}}.",
            "header_type": "none",
            "header_text": "",
            "buttons": [],
        }

        response = self._create_campaign(
            report,
            template="another-meta-id",
            template_name="otro_recordatorio",
            template_snapshot=different_snapshot,
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("cambió después de validar", str(response.json()))
        self.assertEqual(Campaign.objects.count(), 0)

    def test_rejects_unknown_duplicate_missing_document_and_missing_variables(self):
        response = self._validate(
            [
                ["1001", "Ana", "Uno", ""],
                ["1001", "Ana", "Dos", ""],
                ["9999", "Desconocido", "Texto", ""],
                ["1002", "Luis", "", ""],
                ["", "Sin documento", "Texto", ""],
            ]
        )

        self.assertEqual(response.status_code, 201, response.content)
        report = response.json()
        self.assertEqual(report["valid_count"], 0)
        self.assertEqual(report["rejected_count"], 5)
        reasons = [row["reason"] for row in report["rejected_rows"]]
        self.assertTrue(any("duplicado" in reason for reason in reasons))
        self.assertTrue(any("No existe un contacto" in reason for reason in reasons))
        self.assertTrue(any("documento obligatorio" in reason for reason in reasons))
        self.assertTrue(any("variable {{1}}" in reason for reason in reasons))

    def test_rejects_contacts_with_missing_required_fields(self):
        self.other_contact.phone = ""
        self.other_contact.save(update_fields=["phone"])

        response = self._validate([["1002", "Luis", "Texto", ""]])

        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.json()["valid_count"], 0)
        self.assertIn("no tiene teléfono", response.json()["rejected_rows"][0]["reason"])

    def test_partial_campaign_requires_backend_confirmation(self):
        report = self._validate(
            [
                ["1001", "Ana", "Bienvenida", ""],
                ["9999", "Desconocido", "Texto", ""],
            ]
        ).json()

        rejected = self._create_campaign(report, confirm_partial=False)
        self.assertEqual(rejected.status_code, 400)
        self.assertEqual(Campaign.objects.count(), 0)

        confirmed = self._create_campaign(report, confirm_partial=True)
        self.assertEqual(confirmed.status_code, 201, confirmed.content)
        campaign = Campaign.objects.get(pk=confirmed.json()["id"])
        self.assertEqual(list(campaign.recipients.values_list("contact_id", flat=True)), [self.contact.pk])

    def test_partial_confirmation_boolean_without_validation_is_rejected(self):
        response = self.client.post(
            "/campanas/api/campaigns/",
            data=json.dumps(
                {
                    "name": "Sin validación",
                    "template": "meta-template-id",
                    "template_name": "recordatorio",
                    "template_language": "es_CO",
                    "template_snapshot": self.template_snapshot,
                    "segment": self.segment.pk,
                    "default_params": {},
                    "confirm_partial": True,
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(Campaign.objects.count(), 0)

    def test_confirmed_partial_campaign_sends_only_valid_rows(self):
        report = self._validate(
            [
                ["1001", "Ana", "Bienvenida", ""],
                ["9999", "Desconocido", "Texto", ""],
            ]
        ).json()
        response = self._create_campaign(report, confirm_partial=True)
        campaign_id = response.json()["id"]

        with patch.object(
            campaign_service.DEFAULT_ADAPTER,
            "send_template_message",
            return_value=SendResult(success=True, provider_message_id="mock-id"),
        ) as send:
            result = self.client.post(
                f"/campanas/api/campaigns/{campaign_id}/send/",
                data="{}",
                content_type="application/json",
            )

        self.assertEqual(result.status_code, 200, result.content)
        send.assert_called_once()
        self.assertEqual(send.call_args.kwargs["to"], self.contact.phone)
        self.assertEqual(send.call_args.kwargs["params"], {"1": "Bienvenida", "2": "2026-11-01"})
        self.assertEqual(
            list(Campaign.objects.get(pk=campaign_id).recipients.values_list("contact_id", flat=True)),
            [self.contact.pk],
        )

    def test_direct_send_rejects_recipients_outside_validation(self):
        report = self._validate(
            [
                ["1001", "Ana", "Bienvenida", ""],
                ["9999", "Desconocido", "Texto", ""],
            ]
        ).json()
        response = self._create_campaign(report, confirm_partial=True)
        campaign = Campaign.objects.get(pk=response.json()["id"])
        BroadcastRecipient.objects.create(
            campaign=campaign,
            contact=self.other_contact,
            phone_snapshot=self.other_contact.phone,
            params={"1": "intruso", "2": "2026-11-01"},
        )

        with patch.object(
            campaign_service.DEFAULT_ADAPTER,
            "send_template_message",
            return_value=SendResult(success=True, provider_message_id="mock-id"),
        ) as send:
            result = self.client.post(
                f"/campanas/api/campaigns/{campaign.pk}/send/",
                data="{}",
                content_type="application/json",
            )

        self.assertEqual(result.status_code, 400)
        self.assertIn("no coinciden", result.json()["detail"])
        send.assert_not_called()
        campaign.refresh_from_db()
        self.assertEqual(campaign.status, Campaign.Status.DRAFT)

    def test_direct_send_rejects_modified_personalized_parameters(self):
        report = self._validate([["1001", "Ana", "Bienvenida", ""]]).json()
        response = self._create_campaign(report)
        campaign = Campaign.objects.get(pk=response.json()["id"])
        recipient = campaign.recipients.get()
        recipient.params = {"1": "alterado", "2": "2026-11-01"}
        recipient.save(update_fields=["params"])

        with patch.object(
            campaign_service.DEFAULT_ADAPTER,
            "send_template_message",
            return_value=SendResult(success=True, provider_message_id="mock-id"),
        ) as send:
            result = self.client.post(
                f"/campanas/api/campaigns/{campaign.pk}/send/",
                data="{}",
                content_type="application/json",
            )

        self.assertEqual(result.status_code, 400)
        self.assertIn("parámetros", result.json()["detail"])
        send.assert_not_called()
        campaign.refresh_from_db()
        self.assertEqual(campaign.status, Campaign.Status.DRAFT)

    def test_send_preflights_all_variables_before_any_adapter_call(self):
        campaign = Campaign.objects.create(
            name="Plantilla incompleta",
            template_name="recordatorio",
            template_snapshot={"body_text": "Hola {{1}} y {{2}}"},
            segment=self.segment,
            default_params={"1": "Ana", "2": "fecha"},
        )
        BroadcastRecipient.objects.create(
            campaign=campaign,
            contact=self.contact,
            phone_snapshot=self.contact.phone,
            params={"1": "Ana", "2": "fecha"},
        )
        BroadcastRecipient.objects.create(
            campaign=campaign,
            contact=self.other_contact,
            phone_snapshot=self.other_contact.phone,
            params={"1": "Luis"},
        )

        with patch.object(
            campaign_service.DEFAULT_ADAPTER,
            "send_template_message",
            return_value=SendResult(success=True, provider_message_id="mock-id"),
        ) as send:
            with self.assertRaises(campaign_service.CampaignSendError):
                campaign_service.send_campaign(campaign)

        send.assert_not_called()
        campaign.refresh_from_db()
        self.assertEqual(campaign.status, Campaign.Status.DRAFT)

    def test_resolve_recipients_preserves_existing_custom_parameters(self):
        campaign = Campaign.objects.create(
            name="Con valores por destinatario",
            template_name="recordatorio",
            template_snapshot={"body_text": "Hola {{1}}"},
            segment=self.segment,
            default_params={"1": "general"},
        )
        recipient = BroadcastRecipient.objects.create(
            campaign=campaign,
            contact=self.contact,
            phone_snapshot=self.contact.phone,
            params={"1": "valor personalizado"},
        )

        recipients = campaign_service.resolve_recipients(campaign)

        recipient.refresh_from_db()
        self.assertEqual(recipient.params, {"1": "valor personalizado"})
        self.assertEqual(len(recipients), 2)
