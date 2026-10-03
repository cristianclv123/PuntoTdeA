"""Crea un anuncio en WhatsApp Status (historias) via Meta Marketing API.

Todo se crea en PAUSED por defecto para probar sin gastar. Con `--activar` el
anuncio se publica (ACTIVE). La audiencia puede salir de un segmento de
campanas (`--segmento`) o ser una audiencia personalizada ya existente
(`--audiencia-id`). Por defecto se limita a la lista; `--publico-amplio` deja
que Meta amplie la entrega mas alla de la lista.

Ejemplos:
  python manage.py create_whatsapp_status_ad --texto "Matriculas abiertas" \
      --nombre "Aviso matricula" --imagen media/avisos/matricula.jpg
  python manage.py create_whatsapp_status_ad --texto "Hola" --segmento 3 \
      --plan --pais CO --presupuesto 2000000
"""

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from communications.models import AudienceSegment
from communications.services import ads_service


class Command(BaseCommand):
    help = (
        "Crea campana, ad set, creativo y anuncio de WhatsApp Status. "
        "Por defecto queda PAUSED."
    )

    def add_arguments(self, parser):
        parser.add_argument("--texto", required=True, help="Texto principal del aviso.")
        parser.add_argument("--nombre", default="", help="Nombre comun de los objetos en Meta.")
        parser.add_argument("--titulo", default="", help="Titulo corto del anuncio (opcional).")
        parser.add_argument("--imagen", default="", help="Ruta local de la imagen del aviso.")
        parser.add_argument(
            "--presupuesto", type=int, default=2000000,
            help="Presupuesto diario en la unidad menor de la moneda (default: 2000000).",
        )
        parser.add_argument(
            "--pais", action="append", default=None,
            help="Pais ISO para geo (repetible). Default: CO.",
        )
        parser.add_argument(
            "--segmento", type=int, default=None,
            help="Id de AudienceSegment para construir la audiencia personalizada.",
        )
        parser.add_argument(
            "--audiencia-id", default="",
            help="Id de una audiencia personalizada ya existente en Meta.",
        )
        parser.add_argument(
            "--publico-amplio", action="store_true",
            help="Permite que Meta amplie la entrega mas alla de la lista.",
        )
        parser.add_argument("--instagram-actor-id", default="", help="Cuenta de Instagram para el creativo.")
        parser.add_argument("--campaign-id", default="", help="Reutiliza una campana existente.")
        parser.add_argument("--ad-set-id", default="", help="Reutiliza un ad set existente.")
        parser.add_argument(
            "--activar", action="store_true",
            help="Publica el anuncio (ACTIVE). Sin este flag queda PAUSED.",
        )
        parser.add_argument(
            "--plan", action="store_true", dest="plan",
            help="Muestra solo el plan sin llamar a Meta (dry-run).",
        )

    def handle(self, *args, **options):
        status = "ACTIVE" if options["activar"] else "PAUSED"
        name = options["nombre"].strip() or f"Aviso Status {timezone.localtime():%Y-%m-%d %H:%M}"
        message = options["texto"].strip()
        if not message:
            raise CommandError("--texto no puede estar vacio.")

        countries = options["pais"] or None
        image = options["imagen"].strip()
        advantage = bool(options["publico_amplio"])

        self.stdout.write(self.style.MIGRATE_HEADING("Anuncio en WhatsApp Status"))
        self.stdout.write(f"  nombre                      {name}")
        self.stdout.write(f"  estado                      {status}")
        self.stdout.write(f"  presupuesto diario          {options['presupuesto']}")
        self.stdout.write(f"  imagen                      {image or '(sin imagen)'}")
        self.stdout.write(f"  paises                      {', '.join(countries or ads_service.DEFAULT_COUNTRIES)}")
        self.stdout.write(f"  entrega                     {'lista + publico amplio' if advantage else 'solo lista'}")

        # Audiencia: reutilizar una existente o construirla desde un segmento.
        audience_id = options["audiencia_id"].strip()
        if options["segmento"] and not audience_id:
            try:
                segment = AudienceSegment.objects.get(pk=options["segmento"])
            except AudienceSegment.DoesNotExist:
                raise CommandError(f"No existe el segmento {options['segmento']}.")
            phones = ads_service.phones_from_segment(segment)
            self.stdout.write(f"  segmento                    {segment.name} ({len(phones)} telefonos suscritos)")
            if not phones and not advantage:
                raise CommandError("El segmento no tiene contactos suscritos.")
            if options["plan"]:
                audience_id = "(nueva audiencia)"
            else:
                created = ads_service.create_custom_audience(f"{name} - {segment.name}")
                if not created.ok:
                    raise CommandError(created.error or created.summary)
                audience_id = created.object_id
                self.stdout.write(f"  audiencia creada            {audience_id}")
                uploaded = ads_service.add_phones_to_audience(audience_id, phones)
                if not uploaded.ok:
                    raise CommandError(uploaded.error or uploaded.summary)
                self.stdout.write(f"  telefonos cargados          {uploaded.data.get('added')}")
        elif audience_id:
            self.stdout.write(f"  audiencia reutilizada       {audience_id}")

        custom_audiences = [audience_id] if audience_id and audience_id != "(nueva audiencia)" else []

        if options["plan"]:
            self.stdout.write(self.style.WARNING("  Modo plan: no se llamo a Meta."))
            return

        result = ads_service.create_status_ad(
            name=name,
            message=message,
            daily_budget=options["presupuesto"],
            image=image or None,
            title=options["titulo"].strip(),
            countries=countries,
            custom_audiences=custom_audiences,
            advantage_audience=advantage,
            status=status,
            campaign_id=options["campaign_id"].strip(),
            ad_set_id=options["ad_set_id"].strip(),
            instagram_actor_id=options["instagram_actor_id"].strip(),
        )

        if not result.ok:
            if result.data:
                self.stdout.write(self.style.WARNING("  Objetos ya creados:"))
                for key, value in result.data.items():
                    self.stdout.write(f"    {key}: {value}")
            raise CommandError(result.error or result.summary)

        self.stdout.write(self.style.SUCCESS(f"  {result.summary}"))
        for key, value in result.data.items():
            self.stdout.write(f"    {key}: {value}")
        if status == "PAUSED":
            self.stdout.write(self.style.WARNING(
                "  El anuncio esta PAUSED: activalo desde Ads Manager para que entregue."
            ))
