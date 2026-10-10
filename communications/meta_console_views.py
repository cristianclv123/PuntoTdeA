"""Consola de verificación de la integración con Meta WhatsApp Cloud API.

Reúne el estado de la configuración, el envío de mensajes reales y lo que Meta
reporta de vuelta por webhook. Es una herramienta interna: no forma parte de la
experiencia de los equipos de campañas ni de conocimiento.
"""

from __future__ import annotations

import re
from collections import OrderedDict
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.http import HttpRequest, JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from communications.adapters.meta_adapter import MetaAdapter, send_text_message
from communications.adapters.meta_adapter import _normalize_phone
from communications.models import (
    BroadcastRecipient,
    MessageTemplate,
    WhatsAppWebhookEvent,
)
from communications.services import meta_config, meta_diagnostics, meta_errors
from communications.services.test_send_registry import (
    TEST_SEND_KEY_PREFIX,
    record_test_send,
)


def _staff_required(view):
    return user_passes_test(
        lambda user: user.is_active and user.is_staff,
        login_url="login",
    )(view)


@_staff_required
def config(request: HttpRequest):
    """Estado de la configuración y los pasos para aplicarla. Solo lectura."""
    return render(
        request,
        "communications/whatsapp_config.html",
        {
            "config": meta_config.capability_status(),
            "callback_path": meta_config.WEBHOOK_PATH,
            "active_nav": "whatsapp-config",
        },
    )


SERVICE_WINDOW = timedelta(hours=24)

def service_window(phone: str) -> dict | None:
    """Estado de la ventana de servicio al cliente de 24 horas.

    Meta solo entrega texto libre dentro de una ventana que abre el usuario
    cuando escribe primero. Fuera de ella, el envío falla con 131047. La
    última hora se guarda en el payload del evento entrante, así que esto solo
    puede afirmar la ventana para números que ya escribieron alguna vez.
    """
    normalized = _normalize_phone(phone)
    if not normalized:
        return None
    last_inbound = (
        WhatsAppWebhookEvent.objects.filter(
            event_type=WhatsAppWebhookEvent.Type.INBOUND,
            **{"payload__from": normalized},
        )
        .order_by("-created_at")
        .first()
    )
    if last_inbound is None:
        return {"known": False, "open": False}

    expires_at = last_inbound.created_at + SERVICE_WINDOW
    remaining = expires_at - timezone.now()
    return {
        "known": True,
        "open": remaining > timedelta(0),
        "last_inbound": last_inbound.created_at,
        "expires_at": expires_at,
        "remaining": max(remaining, timedelta(0)),
    }


def status_threads(limit: int = 8, per_thread: int = 6) -> list[dict]:
    """Agrupa los estados por `wamid` para leerlos como una línea de tiempo.

    La tabla plana de eventos obliga a reconstruir a mano qué pasó con cada
    mensaje. Acá cada `wamid` es una fila con sus estados en orden.
    """
    events = list(
        WhatsAppWebhookEvent.objects.filter(
            event_type=WhatsAppWebhookEvent.Type.STATUS
        ).order_by("-created_at")[: limit * per_thread]
    )
    threads: OrderedDict[str, dict] = OrderedDict()
    for event in events:
        thread = threads.setdefault(
            event.provider_message_id,
            {"wamid": event.provider_message_id, "steps": []},
        )
        if len(thread["steps"]) < per_thread:
            thread["steps"].append(event)
    return list(threads.values())[:limit]


def approved_templates() -> list[dict]:
    """Plantillas usables para envío real, con los índices de sus parámetros.

    Los índices se extraen del cuerpo porque el formulario tiene que ofrecer un
    campo por marcador y `param_count` solo da la cantidad, no cuáles.
    """
    result = []
    for template in MessageTemplate.objects.filter(
        status=MessageTemplate.Status.APPROVED
    ):
        indexes = sorted(
            {int(i) for i in re.findall(r"\{\{(\d+)\}\}", template.body_text or "")}
        )
        result.append(
            {
                "obj": template,
                "indexes": indexes,
                "needs_header": template.header_type != template.HeaderType.NONE,
                "body": (template.body_text or "").replace("\n", " ")[:160],
            }
        )
    return result


def recent_chats(limit: int = 5) -> list[dict]:
    """Últimas conversaciones del bot originadas por WhatsApp.

    Import local: `knowledge` ya importa `communications` en su módulo de
    WhatsApp, así que importarlo arriba cerraría el ciclo al cargar URLs.
    """
    from knowledge.models import ChatConversation

    chats = []
    for conversation in ChatConversation.objects.filter(channel="whatsapp").order_by(
        "-updated_at"
    )[:limit]:
        history = conversation.messages or []
        chats.append(
            {
                "conversation": conversation,
                "last_user": next(
                    (m for m in reversed(history) if m.get("author") == "user"), None
                ),
                "last_bot": next(
                    (m for m in reversed(history) if m.get("author") == "bot"), None
                ),
                "turns": len(history),
            }
        )
    return chats


@_staff_required
def index(request: HttpRequest):
    """Estado de configuración, envío de prueba y estados reales de Meta."""
    context = {
        "config": meta_config.capability_status(),
        "callback_path": meta_config.WEBHOOK_PATH,
        "recent_events": WhatsAppWebhookEvent.objects.all()[:20],
        "event_count": WhatsAppWebhookEvent.objects.count(),
        "threads": status_threads(),
        "test_sends": WhatsAppWebhookEvent.objects.filter(
            event_key__startswith=TEST_SEND_KEY_PREFIX
        ).order_by("-created_at")[:10],
        "recent_recipients": (
            BroadcastRecipient.objects.exclude(provider_message_id="")
            .select_related("campaign", "contact")
            .order_by("-id")[:10]
        ),
        "templates": approved_templates(),
        "chats": recent_chats(),
        "active_nav": "whatsapp-test",
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

    window = service_window(phone)
    result = send_text_message(phone, text)
    if result.success:
        record_test_send(phone, result.provider_message_id, "test_text", text[:200])
        messages.success(
            request,
            f"Meta aceptó el mensaje. wamid: {result.provider_message_id}. "
            "Quedó registrado: los estados que Meta reporte se van a ver en la "
            "tabla de estados de más abajo. Ojo: que Meta lo acepte no garantiza "
            "que lo entregue; si el número no tiene WhatsApp, el fallo aparece "
            "después como estado «failed».",
        )
        if window and window.get("known") and not window.get("open"):
            messages.warning(
                request,
                "La ventana de servicio de ese número estaba vencida: el envío "
                "puede ser rechazado con el error 131047.",
            )
    else:
        messages.error(request, meta_errors.explain(result.error))
    return redirect("meta-whatsapp-test")


@_staff_required
@require_POST
def send_test_template(request: HttpRequest):
    """Envía una plantilla aprobada al número indicado.

    Es la única vía que funciona fuera de la ventana de servicio de 24 horas,
    porque Meta solo permite texto libre cuando el usuario ya escribió primero.
    """
    phone = (request.POST.get("phone") or "").strip()
    template = MessageTemplate.objects.filter(
        pk=request.POST.get("template"),
        status=MessageTemplate.Status.APPROVED,
    ).first()

    if not phone or template is None:
        messages.error(
            request, "Completa el teléfono y elegí una plantilla aprobada."
        )
        return redirect("meta-whatsapp-test")

    # Los campos del formulario se llaman param_1, param_2... según los
    # marcadores del cuerpo, así que se recogen por patrón.
    params: dict[str, str] = {}
    for key, value in request.POST.items():
        match = re.match(r"^param_(\d+)$", key)
        if match and (value or "").strip():
            params[match.group(1)] = value.strip()

    result = MetaAdapter().send_template_message(phone, template, params)
    if result.success:
        record_test_send(
            phone,
            result.provider_message_id,
            "test_template",
            f"{template.meta_template_name} {params}",
        )
        messages.success(
            request,
            f"Meta aceptó la plantilla «{template.meta_template_name}». "
            f"wamid: {result.provider_message_id}. Quedó registrada para seguir "
            "sus estados.",
        )
    else:
        messages.error(request, meta_errors.explain(result.error))
    return redirect("meta-whatsapp-test")


@_staff_required
def window_status(request: HttpRequest) -> JsonResponse:
    """Ventana de servicio de 24 h para un número, sin recargar la página.

    Evita mandar a ciegas un texto libre que Meta va a rechazar con 131047: la
    persona escribe el teléfono y le dice al toque si la ventana está abierta.
    """
    window = service_window(request.GET.get("phone", ""))
    if window is None or not window["known"]:
        return JsonResponse(
            {
                "known": False,
                "open": False,
                "detail": "Ese número todavía no te escribió: Meta solo entrega "
                "texto libre dentro de la ventana de 24 h que abre el usuario.",
            }
        )
    if window["open"]:
        hours = int(window["remaining"].total_seconds() // 3600)
        minutes = int((window["remaining"].total_seconds() % 3600) // 60)
        return JsonResponse(
            {
                "known": True,
                "open": True,
                "detail": f"Ventana abierta. Le quedan {hours} h {minutes} min. "
                "Este texto libre debería llegar.",
            }
        )
    return JsonResponse(
        {
            "known": True,
            "open": False,
            "last_inbound": window["last_inbound"].isoformat(),
            "detail": "La ventana venció. Meta va a rechazar el texto libre con "
            "el error 131047: usá una plantilla.",
        }
    )


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
