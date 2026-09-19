from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from cases.models import Conversation

METRIC_CARDS = [
    {"label": "Casos pendientes", "value": "34", "sub": "requieren atención", "icon": "inbox", "bg": "var(--warning-bg)", "fg": "var(--warning-text)"},
    {"label": "Casos escalados", "value": "7", "sub": "a otras dependencias", "icon": "arrow-up-right", "bg": "var(--danger-bg)", "fg": "var(--danger-text)"},
    {"label": "Cerrados hoy", "value": "52", "sub": "resueltos en el día", "icon": "circle-check", "bg": "var(--success-bg)", "fg": "var(--success-text)"},
    {"label": "Tiempo prom. respuesta", "value": "6m 40s", "sub": "últimas 24 horas", "icon": "clock-4", "bg": "var(--blue-soft)", "fg": "var(--blue)"},
]

CHANNEL_BARS = [
    {"label": "WhatsApp", "value": 58, "icon": "message-circle", "color": "var(--green)"},
    {"label": "Facebook", "value": 34, "icon": "facebook", "color": "var(--facebook)"},
    {"label": "Instagram", "value": 22, "icon": "instagram", "color": "var(--instagram)"},
    {"label": "Web", "value": 14, "icon": "globe", "color": "var(--web)"},
]

ADVISOR_LOAD = [
    {"name": "Laura Gómez", "value": 42},
    {"name": "Karen Ruiz", "value": 36},
    {"name": "Julián Torres", "value": 29},
    {"name": "Sin asignar", "value": 15},
]

WORKLOAD_ROWS = [
    {"initials": "LG", "name": "Laura Gómez", "assigned": 42, "pending": 9, "closed_today": 14, "state": "Disponible", "state_class": "pill-success"},
    {"initials": "KR", "name": "Karen Ruiz", "assigned": 36, "pending": 12, "closed_today": 10, "state": "En llamada", "state_class": "pill-info"},
    {"initials": "JT", "name": "Julián Torres", "assigned": 29, "pending": 4, "closed_today": 18, "state": "Disponible", "state_class": "pill-success"},
    {"initials": "CO", "name": "Camila Ortiz", "assigned": 24, "pending": 7, "closed_today": 11, "state": "Ausente", "state_class": "pill-neutral"},
]

User = get_user_model()


def home(request):
    """Vista principal (Landing Page) para el proyecto Punto TdeA."""
    return render(request, "index.html")


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


@login_required
def dashboard(request):
    max_channel_value = max(bar["value"] for bar in CHANNEL_BARS)
    channel_bars = [
        {**bar, "height_pct": round(bar["value"] / max_channel_value * 100)}
        for bar in CHANNEL_BARS
    ]
    max_advisor_value = max(row["value"] for row in ADVISOR_LOAD)
    advisor_load = [
        {**row, "width_pct": round(row["value"] / max_advisor_value * 100)}
        for row in ADVISOR_LOAD
    ]
    context = {
        "active_nav": "dashboard",
        "metric_cards": METRIC_CARDS,
        "channel_bars": channel_bars,
        "advisor_load": advisor_load,
        "workload_rows": WORKLOAD_ROWS,
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
    ).exclude(status__in=["cerrado", "completado"]).count()
    assigned_total = Conversation.objects.filter(assigned_to=user).count()

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
