import json

from channels.auth import login
from django.conf import settings
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST

from .adapters.meta_adapter import MetaAdapter
from .models import MessageTemplate
from .services.test_send_registry import record_test_send


@login_required
def campaigns(request):
    context = {
        "active_nav": "campaigns",
        "nav_section": "campaigns",
    }
    return render(request, "communications/campanas.html", context)


@login_required
def campaign_new(request):
    return render(
        request,
        "communications/campaign_new.html",
        {"nav_section": "campaigns", "active_nav": "campaigns"},
    )


@login_required
def campaign_detail(request):
    return render(
        request,
        "communications/campaign_detail.html",
        {"nav_section": "campaigns", "active_nav": "campaigns"},
    )

@login_required
def templates(request):
    return render(request, "communications/templates.html")


@login_required
def segments(request):
    return render(
        request,
        "communications/segments.html",
        {"nav_section": "segments", "active_nav": "campaigns"},
    )


@login_required
def interactions(request):
    return render(
        request,
        "communications/interactions.html",
        {"nav_section": "interactions", "active_nav": "campaigns"},
    )


@require_POST
@login_required
@user_passes_test(lambda user: user.is_active and user.is_staff)
def test_send(request):
    if request.content_type != "application/json":
        return JsonResponse(
            {"success": False, "message": "La solicitud debe enviarse como JSON."},
            status=400,
        )

    try:
        payload = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse(
            {"success": False, "message": "El cuerpo JSON no es válido."},
            status=400,
        )

    if not isinstance(payload, dict):
        return JsonResponse(
            {"success": False, "message": "La solicitud debe ser un objeto JSON."},
            status=400,
        )

    template_id = payload.get("template")
    params = payload.get("params", {})
    if (
        isinstance(template_id, bool)
        or not isinstance(template_id, int)
        or template_id < 1
    ):
        return JsonResponse(
            {"success": False, "message": "Debes indicar un ID de plantilla válido."},
            status=400,
        )
    if not isinstance(params, dict):
        return JsonResponse(
            {"success": False, "message": "Los parámetros deben ser un objeto JSON."},
            status=400,
        )

    test_recipient = settings.WHATSAPP_TEST_RECIPIENT
    if not test_recipient:
        return JsonResponse(
            {
                "success": False,
                "message": "No está configurado el destinatario de pruebas de WhatsApp.",
            },
            status=503,
        )

    template = MessageTemplate.objects.filter(pk=template_id).first()
    if template is None:
        return JsonResponse(
            {"success": False, "message": "La plantilla indicada no existe."},
            status=404,
        )
    if template.status != MessageTemplate.Status.APPROVED:
        return JsonResponse(
            {
                "success": False,
                "message": "La plantilla debe estar aprobada por Meta para enviar una prueba.",
            },
            status=400,
        )

    result = MetaAdapter().send_template_message(test_recipient, template, params)
    if not result.success:
        return JsonResponse(
            {
                "success": False,
                "message": result.error or "Meta no pudo enviar el mensaje de prueba.",
            },
            status=502,
        )

    if result.provider_message_id:
        record_test_send(
            test_recipient,
            result.provider_message_id,
            "test_template",
            f"{template.meta_template_name} {params}",
        )

    return JsonResponse(
        {
            "success": True,
            "message": "Mensaje de prueba enviado correctamente.",
            "provider_message_id": result.provider_message_id,
        }
    )
