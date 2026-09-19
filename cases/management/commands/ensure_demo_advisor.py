from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Crea un asesor demo solo en DEBUG (username=asesor / password por env DEMO_ADVISOR_PASSWORD)."

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("Solo disponible con DJANGO_DEBUG=true")

        User = get_user_model()
        username = "asesor"
        email = "asesor@tdea.edu.co"
        password = getattr(settings, "DEMO_ADVISOR_PASSWORD", None) or "asesor123"
        user, created = User.objects.get_or_create(
            username=username,
            defaults={
                "email": email,
                "first_name": "Asesor",
                "last_name": "Demo",
                "is_staff": True,
            },
        )
        user.set_password(password)
        user.email = email
        user.is_active = True
        user.save()
        action = "creado" if created else "actualizado"
        self.stdout.write(self.style.SUCCESS(f"Usuario demo {action}: {username}"))
