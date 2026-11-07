"""Corrige el mojibake del fixture de FAQs 2026 cargado por 0011.

El fixture original tenia el texto UTF-8 interpretado como CP850 (¿ -> ┬┐,
á -> ├í, é -> ├®, etc.). La migracion 0011 lo cargo tal cual; esta lo
corrige en los datos existentes. El fixture ya viaja corregido, asi que en
una BD fresca el 0011 carga el texto bien y esta migracion no hace nada.

Corre sola con `python manage.py migrate` en el arranque del contenedor.
"""
import json
from pathlib import Path

from django.db import migrations
from django.utils.text import slugify


FIXTURE = Path(__file__).resolve().parent.parent / "fixtures" / "faqs_2026.json"


def _es_mojibake(texto: str) -> bool:
    """True si el texto tiene caracteres de dibujo de CP850 (el mojibake)."""
    return any(0x2500 <= ord(c) <= 0x257F for c in texto)


def _arreglar(texto):
    """Revierte el mojibake CP850 -> UTF-8. Si no parece mojibake, no toca."""
    if not texto or not _es_mojibake(texto):
        return texto
    try:
        return texto.encode("cp850").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return texto


def _mojibake(texto):
    """Reproduce el mojibake del fixture a partir del texto corregido."""
    if not texto:
        return texto
    try:
        return texto.encode("utf-8").decode("cp850")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return texto


def corregir_mojibake(apps, schema_editor):
    Category = apps.get_model("knowledge", "Category")
    FAQ = apps.get_model("knowledge", "FAQ")

    if not FIXTURE.exists():
        print(f"   (se omite la correccion de mojibake: no existe {FIXTURE})")
        return

    datos = json.loads(FIXTURE.read_text(encoding="utf-16"))

    categorias_por_pk = {}
    for item in datos:
        if item["model"] != "knowledge.category":
            continue
        campos = item["fields"]
        nombre_fix = _arreglar(campos["name"])
        nombre_mojibake = _mojibake(nombre_fix)

        cat = Category.objects.filter(name=nombre_mojibake).first()
        if cat is None:
            # BD fresca: el 0011 ya cargo el texto corregido.
            cat = Category.objects.filter(name=nombre_fix).first()
            if cat is not None:
                categorias_por_pk[item["pk"]] = cat
            continue

        existente = Category.objects.filter(name=nombre_fix).exclude(pk=cat.pk).first()
        if existente is not None:
            # Ya existe la categoria correcta: mover las FAQs y borrar el duplicado.
            FAQ.objects.filter(category=cat).update(category=existente)
            cat.delete()
            categorias_por_pk[item["pk"]] = existente
            continue

        cat.name = nombre_fix
        cat.description = _arreglar(cat.description)
        slug = slugify(nombre_fix)
        if Category.objects.filter(slug=slug).exclude(pk=cat.pk).exists():
            slug = f"{slug}-{cat.pk}"
        cat.slug = slug
        cat.save()
        categorias_por_pk[item["pk"]] = cat

    for item in datos:
        if item["model"] != "knowledge.faq":
            continue
        campos = item["fields"]
        pregunta_fix = _arreglar(campos["question"])
        pregunta_mojibake = _mojibake(pregunta_fix)

        faq = FAQ.objects.filter(question=pregunta_mojibake).first()
        if faq is None:
            continue

        faq.question = pregunta_fix
        # Solo corrije la respuesta si sigue con mojibake (no pisa ediciones).
        if _es_mojibake(faq.answer):
            faq.answer = _arreglar(faq.answer)
        categoria = categorias_por_pk.get(campos["category"])
        if categoria is not None:
            faq.category = categoria
        faq.save()

    print("   (mojibake de FAQs 2026 corregido)")


class Migration(migrations.Migration):

    dependencies = [
        ("knowledge", "0011_cargar_faqs_2026"),
    ]

    operations = [
        migrations.RunPython(corregir_mojibake, migrations.RunPython.noop),
    ]
