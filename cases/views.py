from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db.models import Prefetch
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from cases.constants import channel_ui
from cases.models import CaseComment, Conversation, Department, Message, ReplyTemplate
from cases.services.attachments import ACCEPT_ATTR
from cases.services.ingestion import create_outbound_message

User = get_user_model()


def _serialize_conversation(conversation: Conversation) -> dict:
    contact = conversation.contact
    last = conversation.messages.order_by("-sent_at", "-id").first()
    advisor = "Sin asignar"
    if conversation.assigned_to:
        advisor = (
            conversation.assigned_to.get_full_name()
            or conversation.assigned_to.username
        )
    data = {
        "id": conversation.id,
        "ticket_number": conversation.ticket_number or f"TDEA-{conversation.id:06d}",
        "name": contact.full_name,
        "initials": contact.initials,
        "role": contact.academic_program,
        "last_message": last.body if last else "",
        "theme": conversation.theme or "General",
        "department_name": conversation.department.name if conversation.department else "Sin dependencia",
        "priority": conversation.priority,
        "priority_label": conversation.get_priority_display(),
        "time": conversation.last_message_at.strftime("%H:%M"),
        "advisor": advisor,
        "status": conversation.status,
        "status_label": conversation.get_status_display(),
        "contact": contact,
        "opened_at": conversation.created_at,
        "assigned_to_id": conversation.assigned_to_id,
        "department_id": conversation.department_id,
        "escalated_to_id": conversation.escalated_to_id,
        "escalated_to_name": conversation.escalated_to.name if conversation.escalated_to else "",
    }
    data.update(channel_ui(conversation.channel.code))
    return data


def _advisors_queryset():
    return User.objects.filter(is_active=True).order_by("first_name", "username")


def bandeja(request):
    qs = (
        Conversation.objects.select_related(
            "channel",
            "contact",
            "assigned_to",
            "department",
            "escalated_to",
        )
        .prefetch_related(
            Prefetch(
                "messages",
                queryset=Message.objects.order_by("-sent_at", "-id"),
            )
        )
        .all()
    )

    status_filter = request.GET.get("status")
    channel_filter = request.GET.get("channel")
    assigned = request.GET.get("assigned_to")
    priority_filter = request.GET.get("priority")
    department_filter = request.GET.get("department")

    if status_filter:
        qs = qs.filter(status=status_filter)
    if channel_filter:
        qs = qs.filter(channel__code=channel_filter)
    if assigned == "none":
        qs = qs.filter(assigned_to__isnull=True)
    elif assigned:
        qs = qs.filter(assigned_to_id=assigned)
    if priority_filter:
        qs = qs.filter(priority=priority_filter)
    if department_filter:
        qs = qs.filter(department_id=department_filter)

    conversations = [_serialize_conversation(c) for c in qs]
    context = {
        "active_nav": "bandeja",
        "conversations": conversations,
        "result_count": len(conversations),
        "departments": Department.objects.filter(is_active=True),
        "filters": {
            "status": status_filter or "",
            "channel": channel_filter or "",
            "assigned_to": assigned or "",
            "priority": priority_filter or "",
            "department": department_filter or "",
        },
    }
    return render(request, "cases/bandeja.html", context)


def _handle_update_case(request, conversation: Conversation):
    status = (request.POST.get("status") or "").strip()
    priority = (request.POST.get("priority") or "").strip()
    department_id = request.POST.get("department") or ""
    escalated_to_id = request.POST.get("escalated_to") or ""
    assigned_to_id = request.POST.get("assigned_to") or ""

    valid_statuses = {c.value for c in Conversation.Status}
    valid_priorities = {c.value for c in Conversation.Priority}

    if status not in valid_statuses:
        messages.error(request, "Estado inválido.")
        return False
    if priority not in valid_priorities:
        messages.error(request, "Prioridad inválida.")
        return False

    if status == Conversation.Status.ESCALADO and not escalated_to_id:
        messages.error(request, "Si el caso está escalado, debes indicar a qué dependencia.")
        return False

    conversation.status = status
    conversation.priority = priority
    conversation.department_id = int(department_id) if department_id.isdigit() else None
    conversation.escalated_to_id = (
        int(escalated_to_id) if escalated_to_id.isdigit() else None
    )
    if status != Conversation.Status.ESCALADO:
        conversation.escalated_to = None
    conversation.assigned_to_id = int(assigned_to_id) if assigned_to_id.isdigit() else None
    conversation.save()
    messages.success(request, "Caso actualizado.")
    return True


def _handle_add_comment(request, conversation: Conversation):
    body = (request.POST.get("comment_body") or "").strip()
    if not body:
        messages.error(request, "El comentario no puede estar vacío.")
        return False
    CaseComment.objects.create(
        conversation=conversation,
        author=request.user if request.user.is_authenticated else None,
        body=body,
    )
    messages.success(request, "Comentario agregado.")
    return True


def _handle_create_template(request):
    title = (request.POST.get("template_title") or "").strip()
    body = (request.POST.get("template_body") or "").strip()
    if not title or not body:
        messages.error(request, "Título y cuerpo son obligatorios para la plantilla.")
        return False
    ReplyTemplate.objects.create(
        title=title,
        body=body,
        created_by=request.user if request.user.is_authenticated else None,
    )
    messages.success(request, "Plantilla creada.")
    return True


def _handle_reply(request, conversation: Conversation):
    body = (request.POST.get("body") or "").strip()
    files = request.FILES.getlist("attachments")
    try:
        create_outbound_message(
            conversation,
            body,
            user=request.user if request.user.is_authenticated else None,
            uploaded_files=files,
        )
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages) if hasattr(exc, "messages") else str(exc))
        return False
    messages.success(request, "Mensaje enviado.")
    return True


@require_http_methods(["GET", "POST"])
def caso_detail(request, case_id):
    conversation = get_object_or_404(
        Conversation.objects.select_related(
            "channel",
            "contact",
            "assigned_to",
            "department",
            "escalated_to",
        ),
        pk=case_id,
    )

    if request.method == "POST":
        action = (request.POST.get("action") or "reply").strip()
        if action == "update_case":
            _handle_update_case(request, conversation)
        elif action == "add_comment":
            _handle_add_comment(request, conversation)
        elif action == "create_template":
            _handle_create_template(request)
        else:
            _handle_reply(request, conversation)
        return redirect("cases:detail", case_id=conversation.id)

    message_qs = conversation.messages.prefetch_related("attachments").order_by("sent_at", "id")
    comments = conversation.comments.select_related("author").all()
    serialized = _serialize_conversation(conversation)
    context = {
        "active_nav": "bandeja",
        "conversation": serialized,
        "conversation_obj": conversation,
        "messages": [
            {
                "text": m.body,
                "time": m.sent_at.strftime("%H:%M"),
                "from_agent": m.direction == Message.Direction.OUTBOUND,
                "id": m.id,
                "attachments": list(m.attachments.all()),
            }
            for m in message_qs
        ],
        "comments": comments,
        "contact": conversation.contact,
        "departments": Department.objects.filter(is_active=True),
        "advisors": _advisors_queryset(),
        "status_choices": Conversation.Status.choices,
        "priority_choices": Conversation.Priority.choices,
        "reply_templates": ReplyTemplate.objects.filter(is_active=True),
        "attachment_accept": ACCEPT_ATTR,
    }
    return render(request, "cases/caso_detail.html", context)
