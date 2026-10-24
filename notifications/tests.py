import hashlib
import hmac
import json

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from cases.models import Message
from cases.services.ingestion import InboundPayload, ingest_inbound_message
from notifications.models import Notification
from notifications.services import notify

User = get_user_model()


class NotificationServiceTests(TestCase):
    def test_notify_persists_event(self):
        item = notify(
            module=Notification.Module.CASES,
            event="chat.new",
            title="Llegó un nuevo chat",
            body="Camila espera un asesor.",
            url="/bandeja/1/",
        )
        self.assertEqual(Notification.objects.count(), 1)
        self.assertEqual(item.title, "Llegó un nuevo chat")

    def test_first_inbound_is_new_chat_then_reply(self):
        first, _, _ = ingest_inbound_message(
            InboundPayload(
                channel_code="whatsapp",
                external_thread_id="573009990011",
                body="Hola, necesito un certificado",
                external_message_id="wamid.n1",
                contact_full_name="Camila Restrepo",
                contact_document_number="DOC-NOTIF-1",
                contact_email="camila.n@tdea.edu.co",
                contact_phone="573009990011",
            )
        )
        self.assertTrue(
            Notification.objects.filter(event="chat.new", url=f"/bandeja/{first.id}/").exists()
        )
        ingest_inbound_message(
            InboundPayload(
                channel_code="whatsapp",
                external_thread_id="573009990011",
                body="Sigo en espera",
                external_message_id="wamid.n2",
                contact_full_name="Camila Restrepo",
                contact_document_number="DOC-NOTIF-1",
                contact_email="camila.n@tdea.edu.co",
                contact_phone="573009990011",
            )
        )
        self.assertTrue(Notification.objects.filter(event="chat.reply").exists())
        self.assertEqual(
            Message.objects.filter(conversation=first, direction=Message.Direction.INBOUND).count(),
            2,
        )


class NotificationApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="asesor", password="secret123")
        self.client = Client()

    def test_list_requires_login(self):
        res = self.client.get(reverse("notifications:list"))
        self.assertEqual(res.status_code, 302)

    def test_list_and_mark_read(self):
        item = notify(
            module=Notification.Module.CASES,
            event="chat.new",
            title="Llegó un nuevo chat",
        )
        self.client.login(username="asesor", password="secret123")
        listed = self.client.get(reverse("notifications:list"))
        self.assertEqual(listed.status_code, 200)
        payload = listed.json()
        self.assertEqual(payload["unread"], 1)
        self.assertEqual(payload["results"][0]["title"], "Llegó un nuevo chat")
        marked = self.client.post(reverse("notifications:mark-read", args=[item.id]))
        self.assertEqual(marked.json()["unread"], 0)


@override_settings(
    META_ACCESS_TOKEN="token",
    META_APP_SECRET="app-secret",
    META_VERIFY_TOKEN="verify",
    WHATSAPP_PHONE_NUMBER_ID="123",
)
class TemplateApprovalNotificationTests(TestCase):
    def test_meta_template_approved_notifies(self):
        payload = {
            "entry": [
                {
                    "changes": [
                        {
                            "field": "message_template_status_update",
                            "value": {
                                "event": "APPROVED",
                                "message_template_name": "recordatorio_tdea",
                                "message_template_language": "es_CO",
                            },
                        }
                    ]
                }
            ]
        }
        body = json.dumps(payload).encode()
        signature = hmac.new(b"app-secret", body, hashlib.sha256).hexdigest()
        res = self.client.post(
            reverse("meta-whatsapp-webhook"),
            data=body,
            content_type="application/json",
            HTTP_X_HUB_SIGNATURE_256=f"sha256={signature}",
        )
        self.assertEqual(res.status_code, 200)
        notice = Notification.objects.get(event="template.approved")
        self.assertEqual(notice.title, "Se aprobó una plantilla en Meta")
        self.assertEqual(notice.body, "recordatorio_tdea")
