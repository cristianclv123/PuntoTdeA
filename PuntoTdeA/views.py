from django.contrib.auth import authenticate, get_user_model, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Count, Q
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from cases.models import Conversation
from communications.services import dashboard_service

User = get_user_model()


def home(request):
    """Landing pública alineada al estilo de la app."""
    qs = Conversation.objects.filter(channel__code="whatsapp")
    today = timezone.localdate()
    open_cases = qs.exclude(status=Conversation.Status.CERRADO).count()
    closed_today = qs.filter(
        status=Conversation.Status.CERRADO,
        closed_at__date=today,
    ).count()
    if closed_today == 0:
        closed_today = qs.filter(
            status=Conversation.Status.CERRADO,
            updated_at__date=today,
        ).count()
    return render(
        request,
        "index.html",
        {
            "stats": {
                "open_cases": open_cases,
                "closed_today": closed_today,
            },
        },
    )


def _resolve_user(identifier: str):
    identifier = (identifier or "").strip()
    if not identifier:
        return None
    return (
        User.objects.filter(Q(username__iexact=identifier) | Q(email__iexact=identifier))
        .filter(is_active=True)
        .first()
    )


@require_http_methods(["GET", "POST"])
def login_view(request):
    if request.user.is_authenticated:
        return redirect("dashboard")

    error = ""
    identifier = ""
    if request.method == "POST":
        identifier = (request.POST.get("username") or "").strip()
        password = request.POST.get("password") or ""
        remember = bool(request.POST.get("remember"))
        user_obj = _resolve_user(identifier)
        user = None
        if user_obj is not None:
            user = authenticate(request, username=user_obj.username, password=password)
        if user is None:
            error = "Credenciales inválidas. Verifica usuario/correo y contraseña."
        else:
            login(request, user)
            if remember:
                request.session.set_expiry(60 * 60 * 24 * 14)
            else:
                request.session.set_expiry(0)
            next_url = request.GET.get("next") or request.POST.get("next") or ""
            if next_url.startswith("/") and not next_url.startswith("//"):
                return redirect(next_url)
            return redirect("dashboard")

    return render(
        request,
        "login.html",
        {
            "error": error,
            "username": identifier,
            "next": request.GET.get("next", ""),
        },
    )


@require_http_methods(["POST", "GET"])
def logout_view(request):
    logout(request)
    return redirect("login")


def _whatsapp_conversations():
    return Conversation.objects.filter(channel__code="whatsapp")


def _dashboard_case_metrics():
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


def _dashboard_advisor_workload():
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
def dashboard(request):
    context = {
        "active_nav": "dashboard",
        "metric_cards": _dashboard_case_metrics(),
        "workload_rows": _dashboard_advisor_workload(),
        "campaign_metrics": dashboard_service.campaign_kpis(),
        "recent_campaigns": dashboard_service.recent_campaigns(),
        "campaign_activity": dashboard_service.recent_activity(),
    }
    return render(request, "dashboard.html", context)


def _profile_initials(user) -> str:
    first = (user.first_name or "").strip()
    last = (user.last_name or "").strip()
    if first or last:
        return f"{first[:1]}{last[:1]}".upper() or user.username[:2].upper()
    return (user.username or "?")[:2].upper()


@login_required
@require_http_methods(["GET", "POST"])
def profile_view(request):
    user = request.user
    error = ""
    password_error = ""

    if request.method == "POST":
        action = (request.POST.get("action") or "profile").strip()
        if action == "password":
            current = request.POST.get("current_password") or ""
            new_password = request.POST.get("new_password") or ""
            confirm = request.POST.get("confirm_password") or ""
            if not user.check_password(current):
                password_error = "La contraseña actual no es correcta."
            elif len(new_password) < 8:
                password_error = "La nueva contraseña debe tener al menos 8 caracteres."
            elif new_password != confirm:
                password_error = "La confirmación no coincide con la nueva contraseña."
            else:
                user.set_password(new_password)
                user.save(update_fields=["password"])
                update_session_auth_hash(request, user)
                messages.success(request, "Contraseña actualizada.")
                return redirect("profile")
        else:
            first_name = (request.POST.get("first_name") or "").strip()[:150]
            last_name = (request.POST.get("last_name") or "").strip()[:150]
            email = (request.POST.get("email") or "").strip()[:254]
            if email and User.objects.filter(email__iexact=email).exclude(pk=user.pk).exists():
                error = "Ese correo ya está en uso por otro usuario."
            else:
                user.first_name = first_name
                user.last_name = last_name
                user.email = email
                user.save(update_fields=["first_name", "last_name", "email"])
                messages.success(request, "Perfil actualizado.")
                return redirect("profile")

    assigned_open = Conversation.objects.filter(
        assigned_to=user,
        channel__code="whatsapp",
    ).exclude(status=Conversation.Status.CERRADO).count()
    assigned_total = Conversation.objects.filter(
        assigned_to=user,
        channel__code="whatsapp",
    ).count()

    return render(
        request,
        "profile.html",
        {
            "active_nav": "profile",
            "profile_user": user,
            "initials": _profile_initials(user),
            "error": error,
            "password_error": password_error,
            "stats": {
                "assigned_open": assigned_open,
                "assigned_total": assigned_total,
            },
        },
    )
