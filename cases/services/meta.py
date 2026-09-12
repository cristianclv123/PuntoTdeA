import hashlib
import hmac
import json
from typing import Any

from django.conf import settings

from cases.models import Channel
from cases.services.ingestion import InboundPayload


def verify_meta_token(mode: str, token: str, challenge: str) -> str | None:
    if mode == "subscribe" and token == settings.META_VERIFY_TOKEN:
        return challenge
    return None


def validate_meta_signature(raw_body: bytes, signature_header: str | None) -> bool:
    secret = settings.META_APP_SECRET
    if not secret:
        # Local/dev without secret: accept payloads (simulator / unsigned).
        return True
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    expected = signature_header.split("=", 1)[1]
    digest = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(digest, expected)


def _channel_from_object(object_name: str) -> str:
    mapping = {
        "whatsapp_business_account": Channel.Code.WHATSAPP,
        "page": Channel.Code.FACEBOOK,
        "instagram": Channel.Code.INSTAGRAM,
    }
    return mapping.get(object_name, Channel.Code.WHATSAPP)


def parse_meta_webhook(payload: dict[str, Any]) -> list[InboundPayload]:
    """Normalize Meta Cloud API webhook entries into inbound payloads."""
    results: list[InboundPayload] = []
    object_name = payload.get("object", "")
    channel_code = _channel_from_object(object_name)

    for entry in payload.get("entry", []):
        # WhatsApp Cloud API
        for change in entry.get("changes", []):
            value = change.get("value", {})
            contacts = value.get("contacts") or []
            contact_name = ""
            contact_wa_id = ""
            if contacts:
                contact_name = (contacts[0].get("profile") or {}).get("name", "")
                contact_wa_id = contacts[0].get("wa_id", "")
            for msg in value.get("messages") or []:
                body = ""
                if msg.get("type") == "text":
                    body = (msg.get("text") or {}).get("body", "")
                elif msg.get("type"):
                    body = f"[{msg.get('type')} message]"
                sender = msg.get("from") or contact_wa_id
                results.append(
                    InboundPayload(
                        channel_code=Channel.Code.WHATSAPP,
                        external_thread_id=sender,
                        body=body or "(mensaje vacío)",
                        external_message_id=msg.get("id", ""),
                        contact_full_name=contact_name or sender,
                        contact_phone=sender,
                        contact_document_number=f"WA-{sender}",
                        contact_email=f"{sender}@whatsapp.local",
                    )
                )

        # Messenger / Instagram messaging
        for messaging in entry.get("messaging", []):
            message = messaging.get("message") or {}
            if message.get("is_echo"):
                continue
            sender_id = (messaging.get("sender") or {}).get("id", "")
            text = message.get("text") or "[mensaje no textual]"
            results.append(
                InboundPayload(
                    channel_code=channel_code if channel_code != Channel.Code.WHATSAPP else Channel.Code.FACEBOOK,
                    external_thread_id=sender_id,
                    body=text,
                    external_message_id=message.get("mid", ""),
                    contact_full_name=sender_id or "Usuario Meta",
                    contact_phone=sender_id or "0000000000",
                    contact_document_number=f"META-{sender_id}",
                    contact_email=f"{sender_id}@meta.local",
                )
            )

    return results


def dump_payload(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False)
