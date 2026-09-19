from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db.models import OuterRef, Prefetch, Subquery
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods, require_POST

from cases.constants import channel_ui, status_tag_class
from cases.models import CaseComment, Conversation, Department, Message, ReplyTemplate
from cases.services.assignment import ClaimError, advisor_can_reply, claim_conversation
from cases.services.attachments import ACCEPT_ATTR
from cases.services.case_events import advisor_label, mark_claimed, mark_closed
from cases.services.ingestion import create_outbound_message
from cases.services.realtime import broadcast_conversation_update

User = get_user_model()


def _whatsapp_channel_qs():
    return Conversation.objects.filter(channel__code="whatsapp")


def _whatsapp_base_qs():
    """Cola activa de WhatsApp: excluye casos cerrados."""
    return _whatsapp_channel_qs().exclude(status=Conversation.Status.CERRADO)


def _whatsapp_closed_qs():
    return _whatsapp_channel_qs().filter(status=Conversation.Status.CERRADO)


def _unanswered_q():
    """Último mensaje del contacto (inbound): espera respuesta del asesor."""
    last_direction = (
        Message.objects.filter(conversation_id=OuterRef("pk"))
        .exclude(direction=Message.Direction.SYSTEM)
        .order_by("-sent_at", "-id")
        .values("direction")[:1]
    )
    return {"_last_direction": Subquery(last_direction)}


def _filter_query_for_tab(active_tab: str) -> str:
    if active_tab == "mine":
        return "assigned_to=me"
    if active_tab == "unanswered":
        return "unanswered=1"
    if active_tab == "unassigned":
        return "unassigned=1"
    if active_tab == "closed":
        return "closed=1"
    return ""


def _redirect_with_filters(request, view_name, **kwargs):
    url = reverse(view_name, kwargs=kwargs)
    qs = request.GET.urlencode()
    if qs:
        return redirect(f"{url}?{qs}")
    return redirect(url)


def _serialize_conversation(conversation: Conversation) -> dict:
    contact = conversation.contact
    last = (
        conversation.messages.exclude(direction=Message.Direction.SYSTEM)
        .order_by("-sent_at", "-id")
        .first()
    )
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
        "phone": contact.phone,
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
        "status_badge": (
            "Esperando asesor"
            if (
                conversation.assigned_to_id is None
                and conversation.status != Conversation.Status.CERRADO
            )
            else conversation.get_status_display()
        ),
        "status_tag_class": status_tag_class(
            status=conversation.status,
            unassigned=(
                conversation.assigned_to_id is None
                and conversation.status != Conversation.Status.CERRADO
            ),
        ),
        "contact": contact,
        "opened_at": conversation.created_at,
        "claimed_at": conversation.claimed_at,
        "claimed_by_name": (
            advisor_label(conversation.claimed_by) if conversation.claimed_by_id else ""
        ),
        "closed_at": conversation.closed_at,
        "closed_by_name": (
            advisor_label(conversation.closed_by) if conversation.closed_by_id else ""
        ),
        "assigned_to_id": conversation.assigned_to_id,
        "department_id": conversation.department_id,
        "escalated_to_id": conversation.escalated_to_id,
        "escalated_to_name": conversation.escalated_to.name if conversation.escalated_to else "",
        "unassigned": conversation.assigned_to_id is None,
    }
    data.update(channel_ui(conversation.channel.code))
    return data


def _advisors_queryset():
    return User.objects.filter(is_active=True).order_by("first_name", "username")


def _bandeja_list_context(request, selected_id=None):
    status_filter = request.GET.get("status")
    assigned = request.GET.get("assigned_to")
    unanswered = request.GET.get("unanswered")
    unassigned = request.GET.get("unassigned") or request.GET.get("queue")
    closed = request.GET.get("closed")
    priority_filter = request.GET.get("priority")
    department_filter = request.GET.get("department")

    active_tab = "all"
    if closed == "1" or status_filter == Conversation.Status.CERRADO:
        qs = _whatsapp_closed_qs()
        active_tab = "closed"
    elif assigned == "me":
        qs = _whatsapp_base_qs().filter(assigned_to=request.user)
        active_tab = "mine"
    elif unanswered == "1":
        qs = _whatsapp_base_qs().annotate(**_unanswered_q()).filter(
            _last_direction=Message.Direction.INBOUND
        )
        active_tab = "unanswered"
    elif unassigned == "1" or assigned == "none":
        qs = _whatsapp_base_qs().filter(assigned_to__isnull=True)
        active_tab = "unassigned"
    else:
        qs = _whatsapp_base_qs()

    qs = (
        qs.select_related(
            "channel",
            "contact",
            "assigned_to",
            "department",
            "escalated_to",
            "claimed_by",
            "closed_by",
        )
        .prefetch_related(
            Prefetch(
                "messages",
                queryset=Message.objects.order_by("-sent_at", "-id"),
            )
        )
        .order_by("-last_message_at", "-id")
    )

    if status_filter and active_tab != "closed":
        qs = qs.filter(status=status_filter)
    if priority_filter:
        qs = qs.filter(priority=priority_filter)
    if department_filter:
        qs = qs.filter(department_id=department_filter)

    conversations = [_serialize_conversation(c) for c in qs]

    # Si estás viendo un caso cerrado fuera de la pestaña Cerrados, mantenlo visible.
    if (
        selected_id
        and active_tab != "closed"
        and not any(c["id"] == selected_id for c in conversations)
    ):
        selected = (
            _whatsapp_closed_qs()
            .filter(pk=selected_id)
            .select_related(
                "channel",
                "contact",
                "assigned_to",
                "department",
                "escalated_to",
                "claimed_by",
                "closed_by",
            )
            .first()
        )
        if selected:
            conversations.insert(0, _serialize_conversation(selected))

    base = _whatsapp_base_qs()
    mine_count = base.filter(assigned_to=request.user).count()
    unassigned_count = base.filter(assigned_to__isnull=True).count()
    unanswered_count = (
        base.annotate(**_unanswered_q())
        .filter(_last_direction=Message.Direction.INBOUND)
        .count()
    )
    closed_count = _whatsapp_closed_qs().count()
    filter_query = _filter_query_for_tab(active_tab)

    return {
        "active_nav": "bandeja",
        "conversations": conversations,
        "result_count": len(conversations),
        "mine_count": mine_count,
        "unanswered_count": unanswered_count,
        "unassigned_count": unassigned_count,
        "closed_count": closed_count,
        "active_tab": active_tab,
        "selected_id": selected_id,
        "filter_query": filter_query,
        "departments": Department.objects.filter(is_active=True),
        "filters": {
            "status": status_filter or "",
            "channel": "whatsapp",
            "assigned_to": "me" if active_tab == "mine" else "",
            "unanswered": "1" if active_tab == "unanswered" else "",
            "unassigned": "1" if active_tab == "unassigned" else "",
            "closed": "1" if active_tab == "closed" else "",
            "priority": priority_filter or "",
            "department": department_filter or "",
        },
    }


@login_required
def bandeja(request):
    context = _bandeja_list_context(request)
    return render(request, "cases/bandeja.html", context)


@login_required
@require_POST
def claim_case(request, case_id):
    try:
        conversation = claim_conversation(case_id, request.user)
    except ClaimError as exc:
        messages.error(request, exc.message)
        if exc.code == "not_found":
            return _redirect_with_filters(request, "cases:bandeja")
        return _redirect_with_filters(request, "cases:detail", case_id=case_id)
    messages.success(request, "Chat tomado. Ya puedes responder.")
    return _redirect_with_filters(request, "cases:detail", case_id=conversation.id)


def _handle_update_case(request, conversation: Conversation):
    status = (request.POST.get("status") or "").strip()
    priority = (request.POST.get("priority") or "").strip()
    department_id = request.POST.get("department") or ""
    escalated_to_id = request.POST.get("escalated_to") or ""
    assigned_to_id = request.POST.get("assigned_to") or ""

    valid_statuses = {c.value for c in Conversation.Status if c.value != Conversation.Status.CERRADO}
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

    was_unassigned = conversation.assigned_to_id is None
    conversation.status = status
    conversation.priority = priority
    conversation.department_id = int(department_id) if department_id.isdigit() else None
    conversation.escalated_to_id = (
        int(escalated_to_id) if escalated_to_id.isdigit() else None
    )
    if status != Conversation.Status.ESCALADO:
        conversation.escalated_to = None
    if conversation.assigned_to_id in (None, request.user.id) or request.user.is_staff:
        conversation.assigned_to_id = (
            int(assigned_to_id) if assigned_to_id.isdigit() else conversation.assigned_to_id
        )
    conversation.save()

    if conversation.assigned_to_id and (was_unassigned or not conversation.claimed_at):
        assignee = conversation.assigned_to or request.user
        mark_claimed(conversation, assignee, assign=False)

    messages.success(request, "Gestión del caso guardada.")
    return True


def _case_is_managed(conversation: Conversation, request) -> list[str]:
    """Requisitos para poder cerrar: asesor asignado y dependencia de clasificación."""
    errors = []
    assigned_to_id = request.POST.get("assigned_to") or ""
    department_id = request.POST.get("department") or ""
    effective_assigned = (
        int(assigned_to_id)
        if assigned_to_id.isdigit()
        else conversation.assigned_to_id
    )
    effective_department = (
        int(department_id)
        if department_id.isdigit()
        else conversation.department_id
    )
    if not effective_assigned:
        errors.append("Debes asignar un asesor antes de cerrar el caso.")
    if not effective_department:
        errors.append("Debes indicar la dependencia (clasificación) antes de cerrar.")
    return errors


def _handle_close_case(request, conversation: Conversation):
    errors = _case_is_managed(conversation, request)
    if errors:
        for err in errors:
            messages.error(request, err)
        return False

    priority = (request.POST.get("priority") or "").strip()
    department_id = request.POST.get("department") or ""
    assigned_to_id = request.POST.get("assigned_to") or ""
    valid_priorities = {c.value for c in Conversation.Priority}
    if priority and priority not in valid_priorities:
        messages.error(request, "Prioridad inválida.")
        return False

    if conversation.assigned_to_id in (None, request.user.id) or request.user.is_staff:
        if assigned_to_id.isdigit():
            conversation.assigned_to_id = int(assigned_to_id)
    if not conversation.assigned_to_id:
        conversation.assigned_to = request.user

    if not conversation.claimed_at:
        mark_claimed(conversation, conversation.assigned_to or request.user, assign=False)

    conversation.department_id = int(department_id) if department_id.isdigit() else conversation.department_id
    if priority:
        conversation.priority = priority
    conversation.status = Conversation.Status.CERRADO
    conversation.escalated_to = None
    conversation.save()
    mark_closed(conversation, request.user)
    broadcast_conversation_update(conversation)
    messages.success(request, "Caso cerrado correctamente.")
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
    if not advisor_can_reply(conversation, request.user):
        messages.error(request, "Debes tomar el chat antes de responder.")
        return False
    body = (request.POST.get("body") or "").strip()
    files = request.FILES.getlist("attachments")
    try:
        create_outbound_message(
            conversation,
            body,
            user=request.user,
            uploaded_files=files,
        )
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages) if hasattr(exc, "messages") else str(exc))
        return False
    messages.success(request, "Mensaje enviado.")
    return True


@login_required
@require_http_methods(["GET", "POST"])
def caso_detail(request, case_id):
    conversation = get_object_or_404(
        Conversation.objects.select_related(
            "channel",
            "contact",
            "assigned_to",
            "department",
            "escalated_to",
            "claimed_by",
            "closed_by",
        ),
        pk=case_id,
    )

    if request.method == "POST":
        action = (request.POST.get("action") or "reply").strip()
        is_closed = conversation.status == Conversation.Status.CERRADO

        if is_closed and action != "close_case":
            messages.error(request, "Este caso está cerrado. Solo puedes consultarlo.")
            return _redirect_with_filters(request, "cases:detail", case_id=conversation.id)

        if action == "claim":
            try:
                claim_conversation(conversation.id, request.user)
                messages.success(request, "Chat tomado. Ya puedes responder.")
            except ClaimError as exc:
                messages.error(request, exc.message)
        elif action == "update_case":
            _handle_update_case(request, conversation)
        elif action == "close_case":
            if is_closed:
                messages.info(request, "El caso ya estaba cerrado.")
            else:
                _handle_close_case(request, conversation)
        elif action == "add_comment":
            _handle_add_comment(request, conversation)
        elif action == "create_template":
            _handle_create_template(request)
        else:
            _handle_reply(request, conversation)
        return _redirect_with_filters(request, "cases:detail", case_id=conversation.id)

    conversation.refresh_from_db()
    message_qs = conversation.messages.prefetch_related("attachments").order_by("sent_at", "id")
    comments = conversation.comments.select_related("author").all()
    serialized = _serialize_conversation(conversation)
    can_reply = advisor_can_reply(conversation, request.user)
    is_owner = conversation.assigned_to_id == request.user.id
    context = _bandeja_list_context(request, selected_id=conversation.id)
    context.update(
        {
            "conversation": serialized,
            "conversation_obj": conversation,
            "chat_messages": [
                {
                    "text": m.body,
                    "time": m.sent_at.strftime("%H:%M"),
                    "from_agent": m.direction == Message.Direction.OUTBOUND,
                    "is_system": m.direction == Message.Direction.SYSTEM,
                    "id": m.id,
                    "attachments": list(m.attachments.all()),
                }
                for m in message_qs
            ],
            "comments": comments,
            "contact": conversation.contact,
            "advisors": _advisors_queryset(),
            "status_choices": (
                list(Conversation.Status.choices)
                if conversation.status == Conversation.Status.CERRADO
                else [
                    c
                    for c in Conversation.Status.choices
                    if c[0] != Conversation.Status.CERRADO
                ]
            ),
            "case_is_closed": conversation.status == Conversation.Status.CERRADO,
            "priority_choices": Conversation.Priority.choices,
            "reply_templates": ReplyTemplate.objects.filter(is_active=True),
            "attachment_accept": ACCEPT_ATTR,
            "can_reply": can_reply,
            "is_owner": is_owner,
            "needs_claim": (
                conversation.assigned_to_id is None
                and conversation.status != Conversation.Status.CERRADO
            ),
            "assigned_to_other": bool(
                conversation.assigned_to_id
                and conversation.assigned_to_id != request.user.id
                and conversation.status != Conversation.Status.CERRADO
            ),
        }
    )
    return render(request, "cases/caso_detail.html", context)
