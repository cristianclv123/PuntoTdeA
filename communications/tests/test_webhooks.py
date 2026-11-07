"""Pruebas unitarias de ``communications/webhooks/meta_webhook.py``.

Cubren la verificación de suscripción, la firma HMAC, el registro idempotente
de eventos y el procesamiento de estados, mensajes entrantes y estados de
plantilla. No se llama a la Graph API: el chatbot, el envío de respuestas y
las notificaciones se mockean.
"""

import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone as datetime_timezone
from unittest.mock import patch

from django.db import IntegrityError
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from communications.models import (
    AudienceSegment,
    BroadcastRecipient,
    Campaign,
    Contact,
    ContactEvent,
    WhatsAppWebhookEvent,
)
from communications.webhooks import meta_webhook


META_APP_SECRET = "meta-app-secret"
META_VERIFY_TOKEN = "meta-verify-token"
PHONE_NUMBER_ID = "123456789"

_contact_seq = [0]


def sign_body(body: bytes, secret: str = META_APP_SECRET) -> str:
    digest = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def make_contact(phone="+573001112233", document=None):
    _contact_seq[0] += 1
    return Contact.objects.create(
        full_name=f"Contacto Webhook {_contact_seq[0]}",
        document_number=document or f"WHAPP-{_contact_seq[0]}",
        phone=phone,
        whatsapp_opt_in=Contact.OptInStatus.SUSCRITO,
    )


def make_recipient(
    contact=None,
    *,
    status=BroadcastRecipient.Status.PENDING,
    provider_message_id="wamid.campaign.1",
    error_message="",
    phone="+573001112233",
):
    contact = contact or make_contact(phone=phone)
    segment = AudienceSegment.objects.create(name="Segmento webhook")
    campaign = Campaign.objects.create(
        name="Campaña webhook",
        template_meta_id="",
        template_name="plantilla_webhook",
        template_language="es_CO",
        template_snapshot={"body_text": "Hola", "header_type": "none"},
        segment=segment,
    )
    return BroadcastRecipient.objects.create(
        campaign=campaign,
        contact=contact,
        phone_snapshot=phone,
        status=status,
        provider="meta",
        provider_message_id=provider_message_id,
        error_message=error_message,
    )


@override_settings(
    META_VERIFY_TOKEN=META_VERIFY_TOKEN,
    META_APP_SECRET=META_APP_SECRET,
    WHATSAPP_PHONE_NUMBER_ID=PHONE_NUMBER_ID,
)
class MetaWebhookTestCase(TestCase):
    """Base con secretos falsos y helpers para firmar y publicar."""

    def sign(self, body: bytes) -> str:
        return sign_body(body)

    def post_signed(self, payload, *, raw=None):
        body = raw if raw is not None else json.dumps(payload).encode()
        return self.client.post(
            reverse("meta-whatsapp-webhook"),
            data=body,
            content_type="application/json",
            HTTP_X_HUB_SIGNATURE_256=self.sign(body),
        )


class VerifySubscriptionTests(MetaWebhookTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_token_correcto_devuelve_el_challenge(self):
        request = self.factory.get(
            "/api/whatsapp/webhook/",
            {
                "hub.mode": "subscribe",
                "hub.verify_token": META_VERIFY_TOKEN,
                "hub.challenge": "challenge-123",
            },
        )

        response = meta_webhook._verify_subscription(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "challenge-123")
        self.assertEqual(response["Content-Type"], "text/plain")

    def test_token_incorrecto_devuelve_403(self):
        request = self.factory.get(
            "/api/whatsapp/webhook/",
            {
                "hub.mode": "subscribe",
                "hub.verify_token": "token-equivocado",
                "hub.challenge": "challenge-123",
            },
        )

        response = meta_webhook._verify_subscription(request)

        self.assertEqual(response.status_code, 403)

    def test_hub_mode_invalido_devuelve_403(self):
        request = self.factory.get(
            "/api/whatsapp/webhook/",
            {
                "hub.mode": "denied",
                "hub.verify_token": META_VERIFY_TOKEN,
                "hub.challenge": "challenge-123",
            },
        )

        response = meta_webhook._verify_subscription(request)

        self.assertEqual(response.status_code, 403)

    @override_settings(META_VERIFY_TOKEN="")
    def test_sin_secreto_configurado_devuelve_403(self):
        request = self.factory.get(
            "/api/whatsapp/webhook/",
            {
                "hub.mode": "subscribe",
                "hub.verify_token": "",
                "hub.challenge": "challenge-123",
            },
        )

        response = meta_webhook._verify_subscription(request)

        self.assertEqual(response.status_code, 403)


class SignatureTests(MetaWebhookTestCase):
    def test_firma_correcta(self):
        body = b'{"entry": []}'

        self.assertTrue(meta_webhook._signature_is_valid(body, sign_body(body)))

    def test_firma_incorrecta(self):
        body = b'{"entry": []}'

        self.assertFalse(meta_webhook._signature_is_valid(body, "sha256=" + "0" * 64))

    def test_header_sin_prefijo_sha256(self):
        self.assertFalse(meta_webhook._signature_is_valid(b"{}", "deadbeef"))

    def test_header_ausente(self):
        self.assertFalse(meta_webhook._signature_is_valid(b"{}", None))

    @override_settings(META_APP_SECRET="")
    def test_secreto_vacio(self):
        body = b"{}"

        self.assertFalse(meta_webhook._signature_is_valid(body, sign_body(body)))


class EventTests(MetaWebhookTestCase):
    def test_crea_evento_con_defaults(self):
        event, should_process = meta_webhook._event(
            "status:wamid.1:sent",
            "wamid.1",
            WhatsAppWebhookEvent.Type.STATUS,
            "sent",
            {"a": 1},
        )

        self.assertTrue(should_process)
        self.assertEqual(event.event_key, "status:wamid.1:sent")
        self.assertEqual(event.provider_message_id, "wamid.1")
        self.assertEqual(event.event_type, WhatsAppWebhookEvent.Type.STATUS)
        self.assertEqual(event.status, "sent")
        self.assertEqual(event.payload, {"a": 1})
        self.assertIsNone(event.processed_at)

    def test_evento_sin_payload_no_incluye_la_clave(self):
        event, _ = meta_webhook._event(
            "inbound:wamid.2", "wamid.2", WhatsAppWebhookEvent.Type.INBOUND
        )

        self.assertEqual(event.payload, {})

    def test_segunda_llamada_procesado_devuelve_duplicate(self):
        WhatsAppWebhookEvent.objects.create(
            event_key="status:wamid.3:read",
            provider_message_id="wamid.3",
            event_type=WhatsAppWebhookEvent.Type.STATUS,
            status="read",
            processed_at=timezone.now(),
        )

        _, should_process = meta_webhook._event(
            "status:wamid.3:read",
            "wamid.3",
            WhatsAppWebhookEvent.Type.STATUS,
            "read",
        )

        self.assertFalse(should_process)

    def test_registro_existente_sin_procesar_se_vuelve_a_procesar(self):
        WhatsAppWebhookEvent.objects.create(
            event_key="inbound:wamid.4",
            provider_message_id="wamid.4",
            event_type=WhatsAppWebhookEvent.Type.INBOUND,
        )

        event, should_process = meta_webhook._event(
            "inbound:wamid.4", "wamid.4", WhatsAppWebhookEvent.Type.INBOUND
        )

        self.assertTrue(should_process)
        self.assertEqual(event.event_key, "inbound:wamid.4")

    def test_integrity_error_recupera_el_evento_existente(self):
        event = WhatsAppWebhookEvent.objects.create(
            event_key="inbound:wamid.5",
            provider_message_id="wamid.5",
            event_type=WhatsAppWebhookEvent.Type.INBOUND,
        )

        with patch.object(
            WhatsAppWebhookEvent.objects, "get_or_create", side_effect=IntegrityError
        ):
            with patch.object(
                WhatsAppWebhookEvent.objects, "get", return_value=event
            ) as get:
                result, should_process = meta_webhook._event(
                    "inbound:wamid.5", "wamid.5", WhatsAppWebhookEvent.Type.INBOUND
                )

        self.assertEqual(result, event)
        self.assertTrue(should_process)
        get.assert_called_once_with(event_key="inbound:wamid.5")

    def test_finish_event_marca_processed_y_guarda_payload(self):
        event = WhatsAppWebhookEvent.objects.create(
            event_key="status:wamid.6:failed",
            provider_message_id="wamid.6",
            event_type=WhatsAppWebhookEvent.Type.STATUS,
            status="failed",
        )
        event.payload = {"unmatched": True}

        with patch.object(event, "save") as save:
            meta_webhook._finish_event(event)

        self.assertIsNotNone(event.processed_at)
        save.assert_called_once_with(update_fields=["processed_at", "payload"])


class CompactHelpersTests(MetaWebhookTestCase):
    def test_compact_status_guarda_pricing_y_errors(self):
        payload = {
            "timestamp": "1760000000",
            "recipient_id": "573001112233",
            "pricing": {
                "billable": True,
                "pricing_model": "CBP",
                "type": "business",
                "category": "marketing",
                "extra": "no",
            },
            "errors": [
                {
                    "code": 131047,
                    "title": "Reenganche no permitido",
                    "message": "No se pudo entregar",
                    "extra": "no",
                },
                "entrada no dict",
            ],
            "conversation": {"id": "conv-1", "origin": "service"},
        }

        compact = meta_webhook._compact_status(payload)

        self.assertEqual(
            compact["pricing"],
            {
                "billable": True,
                "pricing_model": "CBP",
                "type": "business",
                "category": "marketing",
            },
        )
        self.assertEqual(
            compact["errors"],
            [
                {
                    "code": 131047,
                    "title": "Reenganche no permitido",
                    "message": "No se pudo entregar",
                }
            ],
        )
        self.assertEqual(compact["conversation_id"], "conv-1")
        self.assertEqual(compact["timestamp"], "1760000000")
        self.assertEqual(compact["recipient_id"], "573001112233")

    def test_compact_status_sin_pricing_errores_ni_conversacion(self):
        compact = meta_webhook._compact_status(
            {"timestamp": "1760000000", "recipient_id": "573001112233"}
        )

        self.assertEqual(
            compact, {"timestamp": "1760000000", "recipient_id": "573001112233"}
        )

    def test_compact_inbound_texto_se_trunca_a_500(self):
        message = {
            "from": "573001112233",
            "type": "text",
            "text": {"body": "a" * 600},
            "timestamp": "1760000000",
        }

        compact = meta_webhook._compact_inbound(message)

        self.assertEqual(len(compact["text"]), 500)
        self.assertEqual(compact["from"], "573001112233")
        self.assertEqual(compact["type"], "text")
        self.assertNotIn("interactive", compact)

    def test_compact_inbound_interactive_recorta_id_y_title(self):
        message = {
            "from": "573001112233",
            "type": "interactive",
            "interactive": {
                "type": "button_reply",
                "button_reply": {"id": "b" * 300, "title": "t" * 250},
            },
            "timestamp": "1760000000",
        }

        compact = meta_webhook._compact_inbound(message)

        self.assertEqual(compact["interactive"]["type"], "button_reply")
        self.assertEqual(len(compact["interactive"]["id"]), 256)
        self.assertEqual(len(compact["interactive"]["title"]), 200)

    def test_timestamp_valido(self):
        result = meta_webhook._timestamp("1760000000")

        expected = datetime.fromtimestamp(1760000000, tz=datetime_timezone.utc)
        self.assertEqual(result, expected)

    def test_timestamp_invalido_devuelve_now(self):
        for value in ("no-es-numero", "", None, []):
            result = meta_webhook._timestamp(value)
            self.assertIsNotNone(result.tzinfo)
            self.assertLess(abs((timezone.now() - result).total_seconds()), 5)

    def test_error_message_une_titulos_mensajes_y_codigos(self):
        payload = {
            "errors": [
                {"title": "Fallo A", "message": "detalle"},
                {"message": "Fallo B"},
                {"code": 131047},
                "no dict",
                {"title": "", "message": "", "code": ""},
            ]
        }

        self.assertEqual(
            meta_webhook._error_message(payload), "Fallo A; Fallo B; 131047"
        )

    def test_error_message_sin_errores_usa_fallback(self):
        self.assertEqual(
            meta_webhook._error_message({}), "Meta reportó un fallo de entrega."
        )
        self.assertEqual(
            meta_webhook._error_message({"errors": []}),
            "Meta reportó un fallo de entrega.",
        )


class ProcessStatusTests(MetaWebhookTestCase):
    def setUp(self):
        self.recipient = make_recipient(status=BroadcastRecipient.Status.PENDING)

    def _status_payload(self, status, message_id="wamid.campaign.1", **extra):
        payload = {"id": message_id, "status": status}
        payload.update(extra)
        return payload

    @patch("communications.webhooks.meta_webhook.log_event")
    def test_sent_marca_enviado_y_fecha(self, log_event):
        result = meta_webhook._process_status(
            self._status_payload("sent", timestamp="1760000000")
        )

        self.assertEqual(result, "processed")
        self.recipient.refresh_from_db()
        self.assertEqual(self.recipient.status, BroadcastRecipient.Status.SENT)
        self.assertIsNotNone(self.recipient.sent_at)
        self.assertIsNone(self.recipient.delivered_at)
        log_event.assert_called_once()
        args, kwargs = log_event.call_args
        self.assertEqual(args[1], ContactEvent.EventType.MESSAGE_SENT)
        self.assertEqual(kwargs["broadcast_recipient"], self.recipient)

    @patch("communications.webhooks.meta_webhook.log_event")
    def test_delivered_marca_entregado(self, log_event):
        self.recipient.status = BroadcastRecipient.Status.SENT
        self.recipient.save(update_fields=["status"])

        result = meta_webhook._process_status(
            self._status_payload("delivered", timestamp="1760000001")
        )

        self.assertEqual(result, "processed")
        self.recipient.refresh_from_db()
        self.assertEqual(self.recipient.status, BroadcastRecipient.Status.DELIVERED)
        self.assertIsNotNone(self.recipient.delivered_at)
        args, _ = log_event.call_args
        self.assertEqual(args[1], ContactEvent.EventType.MESSAGE_DELIVERED)

    @patch("communications.webhooks.meta_webhook.log_event")
    def test_read_marca_leido(self, log_event):
        self.recipient.status = BroadcastRecipient.Status.DELIVERED
        self.recipient.save(update_fields=["status"])

        result = meta_webhook._process_status(
            self._status_payload("read", timestamp="1760000002")
        )

        self.assertEqual(result, "processed")
        self.recipient.refresh_from_db()
        self.assertEqual(self.recipient.status, BroadcastRecipient.Status.READ)
        self.assertIsNotNone(self.recipient.read_at)
        args, _ = log_event.call_args
        self.assertEqual(args[1], ContactEvent.EventType.MESSAGE_READ)

    @patch("communications.webhooks.meta_webhook.log_event")
    def test_failed_marca_fallido_con_error(self, log_event):
        result = meta_webhook._process_status(
            self._status_payload(
                "failed",
                errors=[{"code": 131047, "title": "Reenganche", "message": "No se pudo"}],
            )
        )

        self.assertEqual(result, "processed")
        self.recipient.refresh_from_db()
        self.assertEqual(self.recipient.status, BroadcastRecipient.Status.FAILED)
        self.assertEqual(self.recipient.error_message, "Reenganche")
        args, kwargs = log_event.call_args
        self.assertEqual(args[1], ContactEvent.EventType.MESSAGE_FAILED)
        self.assertEqual(kwargs["payload"]["error"], "Reenganche")

    def test_duplicado_no_vuelve_a_procesar(self):
        payload = self._status_payload("sent")

        self.assertEqual(meta_webhook._process_status(payload), "processed")
        self.assertEqual(meta_webhook._process_status(payload), "duplicate")
        self.assertEqual(WhatsAppWebhookEvent.objects.count(), 1)

    def test_unmatched_conserva_el_motivo(self):
        result = meta_webhook._process_status(
            self._status_payload(
                "failed",
                message_id="wamid.suelto",
                errors=[{"title": "Sin destino"}],
            )
        )

        self.assertEqual(result, "unmatched")
        event = WhatsAppWebhookEvent.objects.get(event_key="status:wamid.suelto:failed")
        self.assertTrue(event.payload["unmatched"])
        self.assertIsNotNone(event.processed_at)
        self.assertEqual(ContactEvent.objects.count(), 0)

    def test_read_no_revierte_con_delivered(self):
        self.recipient.status = BroadcastRecipient.Status.READ
        self.recipient.read_at = timezone.now()
        self.recipient.save(update_fields=["status", "read_at"])

        result = meta_webhook._process_status(self._status_payload("delivered"))

        self.assertEqual(result, "processed")
        self.recipient.refresh_from_db()
        self.assertEqual(self.recipient.status, BroadcastRecipient.Status.READ)
        self.assertIsNone(self.recipient.delivered_at)

    def test_failed_despues_de_read_no_revierte(self):
        self.recipient.status = BroadcastRecipient.Status.READ
        self.recipient.save(update_fields=["status"])

        with patch("communications.webhooks.meta_webhook.log_event") as log_event:
            result = meta_webhook._process_status(
                self._status_payload("failed", errors=[{"title": "tarde"}])
            )

        self.assertEqual(result, "processed")
        self.recipient.refresh_from_db()
        self.assertEqual(self.recipient.status, BroadcastRecipient.Status.READ)
        self.assertEqual(self.recipient.error_message, "")
        log_event.assert_not_called()

    def test_sent_no_sobrescribe_sent_at(self):
        original = timezone.now() - timedelta(days=1)
        self.recipient.sent_at = original
        self.recipient.save(update_fields=["sent_at"])

        meta_webhook._process_status(self._status_payload("sent"))

        self.recipient.refresh_from_db()
        self.assertEqual(self.recipient.sent_at, original)

    def test_estatus_invalido_o_id_vacio_se_ignora(self):
        self.assertEqual(
            meta_webhook._process_status({"id": "", "status": "sent"}), "ignored"
        )
        self.assertEqual(
            meta_webhook._process_status({"id": "wamid.x", "status": "raro"}), "ignored"
        )
        self.assertEqual(WhatsAppWebhookEvent.objects.count(), 0)


class ProcessInboundTests(MetaWebhookTestCase):
    def setUp(self):
        self.message = {
            "id": "wamid.inbound.1",
            "from": "573001112233",
            "type": "text",
            "text": {"body": "Hola"},
        }

    @patch("communications.webhooks.meta_webhook.chatbot_whatsapp.send_replies")
    @patch(
        "communications.webhooks.meta_webhook.chatbot_whatsapp.handle_message",
        return_value=["Respuesta"],
    )
    def test_texto_se_envia_al_chatbot(self, handle_message, send_replies):
        result = meta_webhook._process_inbound(dict(self.message), PHONE_NUMBER_ID)

        self.assertEqual(result, "processed")
        handle_message.assert_called_once_with(
            "573001112233",
            "Hola",
            external_message_id="wamid.inbound.1",
            interactive_id="",
        )
        send_replies.assert_called_once_with("573001112233", "Hola", ["Respuesta"])
        event = WhatsAppWebhookEvent.objects.get(event_key="inbound:wamid.inbound.1")
        self.assertIsNotNone(event.processed_at)

    @patch("communications.webhooks.meta_webhook.chatbot_whatsapp.send_replies")
    @patch(
        "communications.webhooks.meta_webhook.chatbot_whatsapp.handle_message",
        return_value=["Respuesta"],
    )
    def test_duplicado_no_llama_al_chatbot(self, handle_message, send_replies):
        meta_webhook._process_inbound(dict(self.message), PHONE_NUMBER_ID)

        result = meta_webhook._process_inbound(dict(self.message), PHONE_NUMBER_ID)

        self.assertEqual(result, "duplicate")
        handle_message.assert_called_once()

    def test_phone_number_id_no_configurado_se_ignora(self):
        result = meta_webhook._process_inbound(dict(self.message), "999999")

        self.assertEqual(result, "ignored")
        event = WhatsAppWebhookEvent.objects.get(event_key="inbound:wamid.inbound.1")
        self.assertIsNotNone(event.processed_at)

    @override_settings(WHATSAPP_PHONE_NUMBER_ID="")
    @patch("communications.webhooks.meta_webhook.chatbot_whatsapp.send_replies")
    @patch(
        "communications.webhooks.meta_webhook.chatbot_whatsapp.handle_message",
        return_value=["Respuesta"],
    )
    def test_sin_phone_id_configurado_acepta_cualquiera(
        self, handle_message, send_replies
    ):
        result = meta_webhook._process_inbound(dict(self.message), "999999")

        self.assertEqual(result, "processed")
        handle_message.assert_called_once()

    def test_interactivo_no_soportado_se_ignora(self):
        message = {
            "id": "wamid.inbound.2",
            "from": "573001112233",
            "type": "interactive",
            "interactive": {"type": "nfm_reply", "nfm_reply": {"id": "x"}},
        }

        result = meta_webhook._process_inbound(message, PHONE_NUMBER_ID)

        self.assertEqual(result, "ignored")

    def test_tipo_no_textual_se_ignora(self):
        message = {
            "id": "wamid.inbound.3",
            "from": "573001112233",
            "type": "image",
            "image": {"id": "media-1"},
        }

        result = meta_webhook._process_inbound(message, PHONE_NUMBER_ID)

        self.assertEqual(result, "ignored")

    def test_texto_vacio_se_ignora(self):
        message = {
            "id": "wamid.inbound.4",
            "from": "573001112233",
            "type": "text",
            "text": {"body": "   "},
        }

        result = meta_webhook._process_inbound(message, PHONE_NUMBER_ID)

        self.assertEqual(result, "ignored")

    def test_interactivo_sin_id_ni_title_se_ignora(self):
        message = {
            "id": "wamid.inbound.5",
            "from": "573001112233",
            "type": "interactive",
            "interactive": {"type": "button_reply", "button_reply": {}},
        }

        result = meta_webhook._process_inbound(message, PHONE_NUMBER_ID)

        self.assertEqual(result, "ignored")

    def test_sin_id_o_remitente_se_ignora(self):
        self.assertEqual(
            meta_webhook._process_inbound(
                {"from": "573001112233", "type": "text", "text": {"body": "Hola"}},
                PHONE_NUMBER_ID,
            ),
            "ignored",
        )
        self.assertEqual(
            meta_webhook._process_inbound(
                {"id": "wamid.inbound.7", "type": "text", "text": {"body": "Hola"}},
                PHONE_NUMBER_ID,
            ),
            "ignored",
        )

    @patch(
        "communications.webhooks.meta_webhook.chatbot_whatsapp.handle_message",
        side_effect=RuntimeError("boom"),
    )
    def test_excepcion_del_chatbot_se_propaga_y_no_marca_el_evento(
        self, handle_message
    ):
        with self.assertRaises(RuntimeError):
            meta_webhook._process_inbound(dict(self.message), PHONE_NUMBER_ID)

        event = WhatsAppWebhookEvent.objects.get(event_key="inbound:wamid.inbound.1")
        self.assertIsNone(event.processed_at)

    @patch("communications.webhooks.meta_webhook.chatbot_whatsapp.send_replies")
    @patch(
        "communications.webhooks.meta_webhook.chatbot_whatsapp.handle_message",
        return_value=["Respuesta"],
    )
    def test_interactivo_button_reply(self, handle_message, send_replies):
        message = {
            "id": "wamid.inbound.6",
            "from": "573001112233",
            "type": "interactive",
            "interactive": {
                "type": "button_reply",
                "button_reply": {"id": "chat_finish", "title": "Finalizar"},
            },
        }

        result = meta_webhook._process_inbound(message, PHONE_NUMBER_ID)

        self.assertEqual(result, "processed")
        handle_message.assert_called_once_with(
            "573001112233",
            "Finalizar",
            external_message_id="wamid.inbound.6",
            interactive_id="chat_finish",
        )


class ProcessTemplateStatusTests(MetaWebhookTestCase):
    @patch("notifications.events.notify_template_status")
    def test_status_update_notifica(self, notify):
        field = "message_template_status_update"
        value = {
            "message_template_name": "matricula_2026",
            "event": "approved",
            "message_template_language": "es_CO",
        }

        result = meta_webhook._process_template_status(field, value)

        self.assertEqual(result, "processed")
        notify.assert_called_once_with("matricula_2026", "APPROVED")
        event = WhatsAppWebhookEvent.objects.get(
            event_key=(
                "template:message_template_status_update:"
                "matricula_2026:es_CO:APPROVED"
            )
        )
        self.assertEqual(event.status, "approved")
        self.assertIsNotNone(event.processed_at)

    @patch("notifications.events.notify_template_status")
    def test_duplicado_no_notifica_dos_veces(self, notify):
        field = "message_template_status_update"
        value = {"message_template_name": "matricula_2026", "event": "approved"}

        self.assertEqual(
            meta_webhook._process_template_status(field, value), "processed"
        )
        self.assertEqual(
            meta_webhook._process_template_status(field, value), "duplicate"
        )
        notify.assert_called_once()

    @patch("notifications.events.notify_template_status")
    def test_calidad_update_usa_new_quality_score(self, notify):
        field = "message_template_quality_update"
        value = {"name": "matricula_2026", "new_quality_score": "high"}

        result = meta_webhook._process_template_status(field, value)

        self.assertEqual(result, "processed")
        notify.assert_called_once_with("matricula_2026", "HIGH")

    @patch("notifications.events.notify_template_status")
    def test_sin_nombre_usa_valor_por_defecto(self, notify):
        field = "message_template_status_update"
        value = {"event": "paused"}

        result = meta_webhook._process_template_status(field, value)

        self.assertEqual(result, "processed")
        notify.assert_called_once_with("Plantilla de WhatsApp", "PAUSED")

    def test_sin_nombre_ni_evento_se_ignora(self):
        self.assertEqual(
            meta_webhook._process_template_status("", {}), "ignored"
        )


class ProcessPayloadTests(MetaWebhookTestCase):
    def setUp(self):
        make_recipient(
            status=BroadcastRecipient.Status.SENT,
            provider_message_id="wamid.p.2",
        )

    @patch("notifications.events.notify_template_status")
    @patch("communications.webhooks.meta_webhook.chatbot_whatsapp.send_replies")
    @patch(
        "communications.webhooks.meta_webhook.chatbot_whatsapp.handle_message",
        return_value=["Respuesta"],
    )
    def test_procesa_mensajes_estados_y_plantillas(
        self, handle_message, send_replies, notify
    ):
        payload = {
            "entry": [
                {
                    "changes": [
                        {
                            "field": "message_template_status_update",
                            "value": {
                                "message_template_name": "matricula",
                                "event": "approved",
                            },
                        },
                        {
                            "value": {
                                "metadata": {"phone_number_id": PHONE_NUMBER_ID},
                                "messages": [
                                    {
                                        "id": "wamid.p.1",
                                        "from": "573001112233",
                                        "type": "text",
                                        "text": {"body": "Hola"},
                                    }
                                ],
                                "statuses": [
                                    {
                                        "id": "wamid.p.2",
                                        "status": "delivered",
                                        "timestamp": "1760000000",
                                    }
                                ],
                            }
                        },
                    ]
                }
            ]
        }

        summary = meta_webhook._process_payload(payload)

        self.assertEqual(summary["processed"], 3)
        self.assertEqual(summary["duplicates"], 0)
        handle_message.assert_called_once()
        notify.assert_called_once_with("matricula", "APPROVED")

    @patch("communications.webhooks.meta_webhook.chatbot_whatsapp.send_replies")
    @patch(
        "communications.webhooks.meta_webhook.chatbot_whatsapp.handle_message",
        return_value=["Respuesta"],
    )
    def test_duplicados_se_cuentan(self, handle_message, send_replies):
        payload = {
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "metadata": {"phone_number_id": PHONE_NUMBER_ID},
                                "messages": [
                                    {
                                        "id": "wamid.p.3",
                                        "from": "573001112233",
                                        "type": "text",
                                        "text": {"body": "Hola"},
                                    }
                                ],
                            }
                        }
                    ]
                }
            ]
        }

        self.assertEqual(meta_webhook._process_payload(payload)["processed"], 1)

        summary = meta_webhook._process_payload(payload)

        self.assertEqual(summary["duplicates"], 1)
        self.assertEqual(summary["processed"], 0)
        handle_message.assert_called_once()

    @patch("communications.webhooks.meta_webhook.chatbot_whatsapp.send_replies")
    @patch(
        "communications.webhooks.meta_webhook.chatbot_whatsapp.handle_message",
        return_value=["Respuesta"],
    )
    def test_entrada_vacia_no_procesa_nada(self, handle_message, send_replies):
        summary = meta_webhook._process_payload({"entry": []})

        self.assertEqual(
            summary,
            {"processed": 0, "duplicates": 0, "ignored": 0, "unmatched": 0},
        )
        handle_message.assert_not_called()


class WebhookViewTests(MetaWebhookTestCase):
    def test_metodo_no_permitido_devuelve_405(self):
        response = self.client.put(reverse("meta-whatsapp-webhook"))

        self.assertEqual(response.status_code, 405)

    def test_get_con_token_invalido_devuelve_403(self):
        response = self.client.get(
            reverse("meta-whatsapp-webhook"),
            {
                "hub.mode": "subscribe",
                "hub.verify_token": "malo",
                "hub.challenge": "challenge-123",
            },
        )

        self.assertEqual(response.status_code, 403)

    def test_json_invalido_devuelve_400(self):
        body = b"{no es json"

        response = self.client.post(
            reverse("meta-whatsapp-webhook"),
            data=body,
            content_type="application/json",
            HTTP_X_HUB_SIGNATURE_256=sign_body(body),
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("JSON", response.json()["error"])

    def test_json_no_dict_devuelve_400(self):
        body = json.dumps(["no", "es", "dict"]).encode()

        response = self.client.post(
            reverse("meta-whatsapp-webhook"),
            data=body,
            content_type="application/json",
            HTTP_X_HUB_SIGNATURE_256=sign_body(body),
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("objeto", response.json()["error"])

    @patch("communications.webhooks.meta_webhook._process_payload")
    def test_excepcion_interna_devuelve_500(self, process_payload):
        process_payload.side_effect = RuntimeError("boom")

        response = self.post_signed({"entry": []})

        self.assertEqual(response.status_code, 500)
        self.assertIn("procesar", response.json()["error"])

    @patch(
        "communications.webhooks.meta_webhook.chatbot_whatsapp.handle_message",
        side_effect=RuntimeError("boom"),
    )
    def test_excepcion_del_chatbot_devuelve_500(self, handle_message):
        payload = {
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "metadata": {"phone_number_id": PHONE_NUMBER_ID},
                                "messages": [
                                    {
                                        "id": "wamid.http.error",
                                        "from": "573001112233",
                                        "type": "text",
                                        "text": {"body": "Hola"},
                                    }
                                ],
                            }
                        }
                    ]
                }
            ]
        }

        response = self.post_signed(payload)

        self.assertEqual(response.status_code, 500)

    @patch("communications.webhooks.meta_webhook.chatbot_whatsapp.send_replies")
    @patch(
        "communications.webhooks.meta_webhook.chatbot_whatsapp.handle_message",
        return_value=["Respuesta"],
    )
    def test_post_firmado_procesa_y_responde_ok(self, handle_message, send_replies):
        payload = {
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "metadata": {"phone_number_id": PHONE_NUMBER_ID},
                                "messages": [
                                    {
                                        "id": "wamid.http.1",
                                        "from": "573001112233",
                                        "type": "text",
                                        "text": {"body": "Hola"},
                                    }
                                ],
                            }
                        }
                    ]
                }
            ]
        }

        response = self.post_signed(payload)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["ok"], True)
        self.assertEqual(response.json()["processed"], 1)
        handle_message.assert_called_once()

    @patch("notifications.events.notify_template_status")
    def test_post_firmado_de_template_status(self, notify):
        payload = {
            "entry": [
                {
                    "changes": [
                        {
                            "field": "message_template_status_update",
                            "value": {
                                "message_template_name": "matricula_2026",
                                "event": "approved",
                                "message_template_language": "es_CO",
                            },
                        }
                    ]
                }
            ]
        }

        response = self.post_signed(payload)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["processed"], 1)
        notify.assert_called_once_with("matricula_2026", "APPROVED")
