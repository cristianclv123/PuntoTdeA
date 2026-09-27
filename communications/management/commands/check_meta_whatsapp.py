"""Diagnóstico de la configuración de Meta WhatsApp Cloud API."""

from django.conf import settings
from django.core.management.base import BaseCommand

from communications.services import meta_config, meta_diagnostics


class Command(BaseCommand):
    help = (
        "Muestra el estado de la configuración de Meta WhatsApp Cloud API. "
        "Con --validate consulta Graph API para confirmar token y número."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--validate",
            action="store_true",
            help="Consulta Graph API para validar el token y el número emisor.",
        )
        parser.add_argument(
            "--callback-url",
            default="",
            help="Callback público de Meta, por ejemplo https://dominio/api/whatsapp/webhook/.",
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING("Meta WhatsApp Cloud API"))
        for line, _ok, _detail in meta_config.readiness_lines():
            self.stdout.write(f"  {line}")

        self.stdout.write("")
        self.stdout.write(f"  Callback configurado  {meta_config.WEBHOOK_PATH}")
        self.stdout.write(f"  DEBUG                  {settings.DEBUG}")
        self.stdout.write(f"  Simulador webhooks     {settings.ALLOW_WEBHOOK_SIMULATOR}")

        failures: list[str] = []
        config = meta_config.capability_status()
        missing = config["missing"]
        optional_missing = config["optional_missing"]
        if missing:
            self.stdout.write("")
            self.stdout.write(
                self.style.WARNING(
                    "Faltan valores en el entorno: " + ", ".join(missing) + "."
                )
            )
            self.stdout.write(
                self.style.WARNING(
                    "Defínelos en .env (ver .env.example) y recrea el servicio web."
                )
            )
            failures.append("configuración incompleta")
        else:
            self.stdout.write("")
            self.stdout.write(self.style.SUCCESS("Configuración completa."))
        if optional_missing:
            self.stdout.write(
                "Opcionales sin definir (no bloquean la integración): "
                + ", ".join(optional_missing)
            )

        if options["validate"]:
            self.stdout.write("")
            self.stdout.write(self.style.MIGRATE_HEADING("Validación contra Graph API"))
            for label, result in meta_diagnostics.run_all():
                style = self.style.SUCCESS if result.ok else self.style.ERROR
                self.stdout.write(f"  {style(label + ': ' + result.summary)}")
                for key, value in result.details.items():
                    if key == "scopes" and isinstance(value, list) and len(value) > 12:
                        value = value[:12] + ["..."]
                    self.stdout.write(f"      {key}: {value}")
                if result.error:
                    self.stdout.write(self.style.ERROR(f"      {result.error}"))
                if not result.ok:
                    failures.append(label)

        if options["callback_url"]:
            self.stdout.write("")
            self.stdout.write(self.style.MIGRATE_HEADING("Callback público"))
            result = meta_diagnostics.webhook_reachable(options["callback_url"])
            style = self.style.SUCCESS if result.ok else self.style.ERROR
            self.stdout.write(f"  {style(options['callback_url'] + ' → ' + result.summary)}")
            if result.error:
                self.stdout.write(self.style.ERROR(f"      {result.error}"))
            if not result.ok:
                failures.append("callback público")

        # Salida distinta de cero para poder encadenarlo en un monitor.
        if failures:
            self.stderr.write(
                self.style.ERROR("Diagnóstico fallido: " + "; ".join(failures))
            )
            raise SystemExit(1)
