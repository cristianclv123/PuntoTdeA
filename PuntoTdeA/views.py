from django.contrib.auth import authenticate, get_user_model, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from cases.models import Conversation

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
        return redirect("dashboard:index")

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
            return redirect("dashboard:index")

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
