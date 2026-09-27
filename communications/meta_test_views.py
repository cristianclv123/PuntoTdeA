"""Página de prueba de la integración con Meta WhatsApp Cloud API.

Es una herramienta de verificación interna: no forma parte de la experiencia de
los equipos de campañas ni de conocimiento y se accede únicamente por URL,
sin enlace en la navegación principal.
"""

from __future__ import annotations

import hashlib
import hmac
import json

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.http import HttpRequest, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from communications.adapters.meta_adapter import send_text_message
from communications.models import BroadcastRecipient, WhatsAppWebhookEvent
from communications.services import meta_config, meta_diagnostics


def _staff_required(view):
    return user_passes_test(
        lambda user: user.is_active and user.is_staff,
        login_url="login",
    )(view)


@_staff_required
def index(request: HttpRequest):
    """Estado de configuración, envío de prueba y simulador de webhook."""
    context = {
        "config": meta_config.capability_status(),
        "callback_path": meta_config.WEBHOOK_PATH,
        "recent_events": WhatsAppWebhookEvent.objects.all()[:20],
        "event_count": WhatsAppWebhookEvent.objects.count(),
        "recent_recipients": (
            BroadcastRecipient.objects.exclude(provider_message_id="")
            .select_related("campaign", "contact")
            .order_by("-id")[:10]
        ),
        "simulator_enabled": settings.ALLOW_WEBHOOK_SIMULATOR,
    }
    return render(request, "communications/whatsapp_test.html", context)


@_staff_required
@require_POST
def send_test_message(request: HttpRequest):
    """Envía un mensaje de texto real al número indicado."""
    phone = (request.POST.get("phone") or "").strip()
    text = (request.POST.get("text") or "").strip()

    if not phone or not text:
        messages.error(request, "Completa el teléfono y el mensaje.")
        return redirect("meta-whatsapp-test")

    result = send_text_message(phone, text)
    if result.success:
        messages.success(
            request,
            f"Meta aceptó el mensaje. wamid: {result.provider_message_id}",
        )
    else:
        messages.error(request, f"No se pudo enviar: {result.error}")
    return redirect("meta-whatsapp-test")


def _simulated_payload(scenario: str, reference: str) -> dict:
    """Payload con la misma forma que envía Meta."""
    now = int(timezone.now().timestamp())
    # Usa el Phone Number ID real: si no coincide, el webhook descarta el evento
    # por Proveniente de un número no configurado.
    metadata: dict[str, str] = {"display_phone_number": "15550000000"}
    phone_number_id = str(settings.WHATSAPP_PHONE_NUMBER_ID or "").strip()
    if phone_number_id:
        metadata["phone_number_id"] = phone_number_id
    if scenario == "inbound":
        return {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "id": "SIMULATED_WABA_ID",
                    "changes": [
                        {
                            "field": "messages",
                            "value": {
                                "messaging_product": "whatsapp",
                                "metadata": metadata,
                                "messages": [
                                    {
                                        "id": f"wamid.simulated.inbound.{now}",
                                        "from": "573001112233",
                                        "timestamp": str(now),
                                        "type": "text",
                                        "text": {"body": "Hola, necesito información de matrículas"},
                                    }
                                ],
                            },
                        }
                    ],
                }
            ],
        }

    status = "failed" if scenario == "failed" else "delivered"
    value = {
        "id": reference or "wamid.NO_ENCONTRADO",
        "status": status,
        "timestamp": str(now),
        "recipient_id": "573001112233",
        "conversation": {"id": f"conversation.simulated.{now}", "origin": {"type": "marketing"}},
        "pricing": {"billable": True, "pricing_model": "CBP"},
    }
    if status == "failed":
        value["errors"] = [
            {"code": 131026, "title": "Message undeliverable", "message": "Número no entregado"}
        ]
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "SIMULATED_WABA_ID",
                "changes": [
                    {"field": "messages", "value": {"messaging_product": "whatsapp", "metadata": metadata, "statuses": [value]}}
                ],
            }
        ],
    }


@_staff_required
@require_POST
def simulate_webhook(request: HttpRequest):
    """Firma un payload con el App Secret y lo envía al webhook real."""
    scenario = (request.POST.get("scenario") or "inbound").strip()
    reference = (request.POST.get("reference") or "").strip()

    if not settings.ALLOW_WEBHOOK_SIMULATOR:
        messages.error(
            request,
            "El simulador está desactivado porque DEBUG está apagado. "
            "Un payload firmado con el App Secret es indistinguible de uno real de "
            "Meta, así que solo debe habilitarse en entornos de prueba.",
        )
        return redirect("meta-whatsapp-test")

    if not meta_config.can_receive_webhooks():
        messages.error(
            request,
            "No se puede simular: falta META_APP_SECRET. Sin ese secreto el webhook "
            "rechaza toda petición porque no se puede validar la firma.",
        )
        return redirect("meta-whatsapp-test")

    payload = _simulated_payload(scenario, reference)
    body = json.dumps(payload).encode()
    signature = _sign(body)
    response_data = _post_to_webhook(body, signature)
    result = response_data.get("result")
    status_code = response_data.get("status_code")

    if result is not None and status_code == 200:
        processed = result.get("processed", 0)
        duplicates = result.get("duplicates", 0)
        unmatched = result.get("unmatched", 0)
        detail = f"procesados={processed} duplicados={duplicates} sin_match={unmatched}"
        if scenario == "inbound":
            messages.success(request, f"Webhook aceptó el mensaje del bot. {detail}")
        elif unmatched:
            messages.warning(
                request,
                "El estado se recibió pero ningún destinatario tiene ese wamid. " + detail,
            )
        else:
            messages.success(request, f"Webhook aplicó el estado '{scenario}'. {detail}")
    else:
        messages.error(
            request,
            f"El webhook respondió {status_code}: {result or response_data.get('error')}",
        )
    return redirect("meta-whatsapp-test")


def _sign(body: bytes) -> str:
    digest = hmac.new(
        str(settings.META_APP_SECRET or "").encode(), body, hashlib.sha256
    ).hexdigest()
    return f"sha256={digest}"


def _post_to_webhook(body: bytes, signature: str) -> dict:
    """Reenvía el payload al endpoint usando el cliente interno de Django.

    Se usa el cliente de Django y no `requests` para no depender de que el
    servidor esté escuchando en `localhost:8000` desde dentro del contenedor.
    `raise_request_exception=False` evita que un fallo del webhook reviente la
    página de prueba con un 500 en lugar de reportar el error.
    """
    from django.test import Client  # import local: no se carga en el arranque

    client = Client(raise_request_exception=False)
    response = client.post(
        reverse("meta-whatsapp-webhook"),
        data=body,
        content_type="application/json",
        HTTP_X_HUB_SIGNATURE_256=signature,
    )
    try:
        result = response.json()
    except (TypeError, ValueError):
        result = response.content[:200].decode(errors="replace")
    return {"status_code": response.status_code, "result": result}


@_staff_required
@require_POST
def validate_credentials(request: HttpRequest):
    """Ejecuta las consultas reales a Graph API bajo demanda."""
    if not meta_config.is_fully_configured():
        messages.error(
            request,
            "Faltan META_ACCESS_TOKEN o WHATSAPP_PHONE_NUMBER_ID para validar.",
        )
        return redirect("meta-whatsapp-test")

    for label, result in meta_diagnostics.run_all():
        if result.ok:
            messages.success(request, f"{label}: {result.summary}")
        else:
            messages.error(request, f"{label}: {result.summary} {result.error}".strip())
    return redirect("meta-whatsapp-test")


@_staff_required
def health(request: HttpRequest) -> JsonResponse:
    """Resumen de configuración en formato JSON, para chequeos automatizados."""
    config = meta_config.capability_status()
    return JsonResponse(
        {
            "configured": meta_config.is_fully_configured(),
            "can_receive_webhooks": config["can_receive"],
            "can_verify_subscription": config["can_verify"],
            "missing": config["missing"],
            "webhook_path": config["webhook_path"],
            "events_recorded": WhatsAppWebhookEvent.objects.count(),
        }
    )
