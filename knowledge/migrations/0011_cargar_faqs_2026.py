"""Carga inicial de las FAQs institucionales 2026 desde el fixture JSON.

El fixture (`knowledge/fixtures/faqs_2026.json`) es un volcado UTF-16 con pks
fijos que no se puede cargar directo con `loaddata`: la codificacion no es
UTF-8, el campo `image` ya fue eliminado (migracion 0007) y los intents
referenciados no vienen incluidos. Esta migracion lo normaliza:

- Categorias por `name` (no por pk, para no pisar las existentes).
- Intents por pk solo si ya existen; si no, se dejan en NULL.
- FAQs por `question` con `update_or_create` (idempotente).

Corre sola con `python manage.py migrate` en el arranque del contenedor (ver
`entrypoint.sh`), una unica vez, sin shell en Render.
"""
import json
from pathlib import Path

from django.db import migrations
from django.utils.text import slugify


FIXTURE = Path(__file__).resolve().parent.parent / "fixtures" / "faqs_2026.json"


def cargar_faqs_2026(apps, schema_editor):
    if not FIXTURE.exists():
        print(f"   (se omite la carga de FAQs 2026: no existe {FIXTURE})")
        return

    Category = apps.get_model("knowledge", "Category")
    Intent = apps.get_model("knowledge", "Intent")
    FAQ = apps.get_model("knowledge", "FAQ")

    datos = json.loads(FIXTURE.read_text(encoding="utf-16"))

    categorias = {}
    for item in datos:
        if item["model"] != "knowledge.category":
            continue
        campos = item["fields"]
        categoria, creada = Category.objects.get_or_create(
            name=campos["name"],
            defaults={
                "description": campos.get("description", ""),
                "is_active": campos.get("is_active", True),
                "slug": slugify(campos["name"]),
            },
        )
        # Los modelos historicos no tienen el save() del modelo real, asi que el
        # slug no se autogenera: se cubre aqui solo si falta.
        if not creada and not categoria.slug:
            categoria.slug = slugify(campos["name"])
            categoria.save()
        categorias[item["pk"]] = categoria

    creadas = actualizadas = omitidas = 0
    for item in datos:
        if item["model"] != "knowledge.faq":
            continue
        campos = item["fields"]
        categoria = categorias.get(campos["category"])
        if categoria is None:
            omitidas += 1
            print(
                f"   (se omite la FAQ {campos['question']!r}: "
                f"la categoria {campos['category']!r} no existe en el fixture)"
            )
            continue

        intent_pk = campos.get("intent")
        intent = Intent.objects.filter(pk=intent_pk).first() if intent_pk else None

        _, creada = FAQ.objects.update_or_create(
            question=campos["question"],
            defaults={
                "answer": campos["answer"],
                "category": categoria,
                "intent": intent,
                "is_active": campos.get("is_active", True),
                "order": campos.get("order", 0),
                "valid_from": campos.get("valid_from"),
                "valid_until": campos.get("valid_until"),
            },
        )
        if creada:
            creadas += 1
        else:
            actualizadas += 1

    print(
        f"   FAQs 2026: {creadas} creadas, {actualizadas} actualizadas, "
        f"{omitidas} omitidas"
    )


class Migration(migrations.Migration):

    dependencies = [
        ("knowledge", "0010_chatconversation_advisor_document_number"),
    ]

    operations = [
        migrations.RunPython(cargar_faqs_2026, migrations.RunPython.noop),
    ]
