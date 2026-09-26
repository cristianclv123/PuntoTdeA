from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.shortcuts import render
from django.utils import timezone

from cases.models import Conversation
from communications.services import dashboard_service


def _whatsapp_conversations():
    return Conversation.objects.filter(channel__code="whatsapp")


def _case_metrics():
    qs = _whatsapp_conversations()
    open_qs = qs.exclude(status=Conversation.Status.CERRADO)
    today = timezone.localdate()

    pendientes = open_qs.filter(status=Conversation.Status.PENDIENTE).count()
    escalados = open_qs.filter(status=Conversation.Status.ESCALADO).count()
    sin_asesor = open_qs.filter(assigned_to__isnull=True).count()
    abiertos = open_qs.count()
    cerrados_hoy = qs.filter(
        status=Conversation.Status.CERRADO,
        closed_at__date=today,
    ).count()
    # Fallback si closed_at aún no está poblado en casos viejos
    if cerrados_hoy == 0:
        cerrados_hoy = qs.filter(
            status=Conversation.Status.CERRADO,
            updated_at__date=today,
        ).count()

    return [
        {
            "label": "Casos abiertos",
            "value": str(abiertos),
            "sub": "WhatsApp en cola",
            "icon": "message-circle",
            "bg": "var(--blue-soft)",
            "fg": "var(--blue)",
        },
        {
            "label": "Pendientes",
            "value": str(pendientes),
            "sub": "requieren atención",
            "icon": "inbox",
            "bg": "var(--warning-bg)",
            "fg": "var(--warning-text)",
        },
        {
            "label": "Sin asesor",
            "value": str(sin_asesor),
            "sub": "esperando asignación",
            "icon": "user-round",
            "bg": "var(--info-bg)",
            "fg": "var(--info-text)",
        },
        {
            "label": "Escalados",
            "value": str(escalados),
            "sub": "a dependencias",
            "icon": "arrow-up-right",
            "bg": "var(--danger-bg)",
            "fg": "var(--danger-text)",
        },
        {
            "label": "Cerrados hoy",
            "value": str(cerrados_hoy),
            "sub": "resueltos en el día",
            "icon": "circle-check",
            "bg": "var(--success-bg)",
            "fg": "var(--success-text)",
        },
    ]


def _advisor_workload():
    today = timezone.localdate()
    open_qs = _whatsapp_conversations().exclude(status=Conversation.Status.CERRADO)

    by_advisor = (
        open_qs.filter(assigned_to__isnull=False)
        .values("assigned_to_id", "assigned_to__first_name", "assigned_to__last_name", "assigned_to__username")
        .annotate(
            assigned=Count("id"),
            pending=Count("id", filter=Q(status=Conversation.Status.PENDIENTE)),
            escalated=Count("id", filter=Q(status=Conversation.Status.ESCALADO)),
        )
        .order_by("-assigned")
    )

    closed_today = {
        row["closed_by_id"]: row["total"]
        for row in _whatsapp_conversations()
        .filter(status=Conversation.Status.CERRADO, closed_at__date=today)
        .values("closed_by_id")
        .annotate(total=Count("id"))
        if row["closed_by_id"]
    }

    rows = []
    for row in by_advisor:
        first = (row["assigned_to__first_name"] or "").strip()
        last = (row["assigned_to__last_name"] or "").strip()
        username = row["assigned_to__username"] or ""
        name = f"{first} {last}".strip() or username
        initials = (
            f"{first[:1]}{last[:1]}".upper()
            if first or last
            else (username[:2] or "?").upper()
        )
        advisor_id = row["assigned_to_id"]
        rows.append(
            {
                "initials": initials,
                "name": name,
                "assigned": row["assigned"],
                "pending": row["pending"],
                "escalated": row["escalated"],
                "closed_today": closed_today.get(advisor_id, 0),
            }
        )

    unassigned = open_qs.filter(assigned_to__isnull=True).count()
    if unassigned:
        rows.append(
            {
                "initials": "—",
                "name": "Sin asignar",
                "assigned": unassigned,
                "pending": open_qs.filter(
                    assigned_to__isnull=True, status=Conversation.Status.PENDIENTE
                ).count(),
                "escalated": open_qs.filter(
                    assigned_to__isnull=True, status=Conversation.Status.ESCALADO
                ).count(),
                "closed_today": 0,
            }
        )

    return rows


@login_required
def index(request):
    context = {
        "active_nav": "dashboard",
        "metric_cards": _case_metrics(),
        "workload_rows": _advisor_workload(),
        "campaign_metrics": dashboard_service.campaign_kpis(),
        "recent_campaigns": dashboard_service.recent_campaigns(),
        "campaign_activity": dashboard_service.recent_activity(),
    }
    return render(request, "dashboard/index.html", context)
