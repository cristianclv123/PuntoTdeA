from django.db import migrations

CHANNELS = [
    ("whatsapp", "WhatsApp"),
    ("facebook", "Facebook"),
    ("instagram", "Instagram"),
    ("web", "Web"),
]

DEPARTMENTS = [
    ("registro_academico", "Registro académico"),
    ("admisiones", "Admisiones"),
    ("bienestar", "Bienestar"),
    ("financiera", "Financiera"),
    ("biblioteca", "Biblioteca"),
    ("graduados", "Graduados"),
    ("tic", "TIC"),
    ("secretaria_general", "Secretaría general"),
]

TEMPLATES = [
    (
        "Saludo inicial",
        "Hola, gracias por contactar a Punto TdeA. ¿En qué podemos ayudarte hoy?",
    ),
    (
        "Solicitud de datos",
        "Para continuar con tu solicitud, por favor confirma tu nombre completo, número de documento y programa académico.",
    ),
    (
        "Cierre de caso",
        "Hemos gestionado tu solicitud. Si necesitas algo más, vuelve a escribirnos. ¡Que tengas un buen día!",
    ),
    (
        "Derivación a dependencia",
        "Tu caso será escalado a la dependencia correspondiente. Te confirmaremos cuando tengamos una respuesta.",
    ),
]


def seed(apps, schema_editor):
    Channel = apps.get_model("cases", "Channel")
    Department = apps.get_model("cases", "Department")
    ReplyTemplate = apps.get_model("cases", "ReplyTemplate")
    for code, name in CHANNELS:
        Channel.objects.update_or_create(code=code, defaults={"name": name, "is_active": True})
    for code, name in DEPARTMENTS:
        Department.objects.update_or_create(code=code, defaults={"name": name, "is_active": True})
    for title, body in TEMPLATES:
        ReplyTemplate.objects.update_or_create(
            title=title,
            defaults={"body": body, "is_active": True},
        )


def unseed(apps, schema_editor):
    Channel = apps.get_model("cases", "Channel")
    Department = apps.get_model("cases", "Department")
    ReplyTemplate = apps.get_model("cases", "ReplyTemplate")
    Channel.objects.filter(code__in=[c for c, _ in CHANNELS]).delete()
    Department.objects.filter(code__in=[c for c, _ in DEPARTMENTS]).delete()
    ReplyTemplate.objects.filter(title__in=[t for t, _ in TEMPLATES]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("cases", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
