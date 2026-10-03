"""Diagnostico de la configuracion de Meta Marketing API para anuncios.

Es de solo lectura: valida el token, la cuenta de anuncios, la Pagina y el
portafolio de negocio. No crea ni modifica nada.

Ejemplos:
  python manage.py check_meta_ads
"""

from datetime import datetime, timezone as dt_timezone

from django.core.management.base import BaseCommand

from communications.services import ads_service


def _human_date(timestamp) -> str:
    try:
        value = int(timestamp)
    except (TypeError, ValueError):
        return str(timestamp or "-")
    if not value:
        return "-"
    return datetime.fromtimestamp(value, tz=dt_timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


class Command(BaseCommand):
    help = (
        "Muestra el estado de la cuenta de anuncios, la Pagina y el negocio "
        "para los anuncios en WhatsApp Status."
    )

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING("Meta Marketing API (WhatsApp Status)"))

        errors = ads_service.configuration_errors()
        if errors:
            self.stdout.write(self.style.ERROR("  Falta configurar: " + ", ".join(errors)))
            return
        self.stdout.write("  configuracion de anuncios   OK")

        # Token.
        token_ok = False
        result = ads_service.debug_token()
        if result.ok:
            data = result.data.get("token", {})
            token_ok = bool(data.get("is_valid"))
            scopes = ", ".join(data.get("scopes", []) or []) or "(sin scopes)"
            style = self.style.SUCCESS if token_ok else self.style.ERROR
            self.stdout.write(style(f"  token valido                {token_ok}"))
            self.stdout.write(f"  expira                      {_human_date(data.get('expires_at'))}")
            self.stdout.write(f"  scopes                      {scopes}")
            if "ads_management" not in (data.get("scopes") or []):
                self.stdout.write(self.style.WARNING(
                    "  Aviso: el token no tiene 'ads_management'."
                ))
        else:
            self.stdout.write(self.style.ERROR(f"  token                       {result.error}"))

        # Cuenta de anuncios.
        result = ads_service.get_ad_account()
        if result.ok:
            account = result.data.get("account", {})
            self.stdout.write(
                f"  cuenta de anuncios          {account.get('name')} "
                f"[{account.get('id')}] -> {account.get('account_status_label')}"
            )
            self.stdout.write(
                f"  moneda / zona               {account.get('currency')} / {account.get('timezone_name')}"
            )
            if account.get("account_status") != 1:
                self.stdout.write(self.style.ERROR(
                    "  La cuenta de anuncios no esta activa: no habra entrega."
                ))
        else:
            self.stdout.write(self.style.ERROR(f"  cuenta                      {result.error}"))

        # Pagina.
        result = ads_service.get_page()
        if result.ok:
            page = result.data.get("page", {})
            self.stdout.write(f"  Pagina                      {page.get('name')} [{page.get('id')}]")
        else:
            self.stdout.write(self.style.ERROR(f"  Pagina                      {result.error}"))

        # Negocio.
        result = ads_service.get_business()
        if result.ok:
            business = result.data.get("business", {})
            verification = business.get("verification_status", "-")
            style = self.style.SUCCESS if verification == "verified" else self.style.WARNING
            self.stdout.write(style(
                f"  negocio                     {business.get('name')} -> {verification}"
            ))
        else:
            self.stdout.write(f"  negocio                     {result.error}")

        # Numero de WhatsApp configurado para el anuncio.
        phone = ads_service.whatsapp_phone()
        self.stdout.write(f"  numero WhatsApp (anuncio)   {('+' + phone) if phone else '-'}")

        self.stdout.write("")
        self.stdout.write(self.style.WARNING("Pasos manuales que la API no cubre:"))
        self.stdout.write("  - La Pagina debe estar vinculada a la cuenta de WhatsApp.")
        self.stdout.write("  - El negocio debe estar verificado para usar el numero de Cloud API.")
        self.stdout.write("  - Debe existir un metodo de pago en la cuenta de anuncios.")
