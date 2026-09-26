"""Importación masiva de FAQs y artículos desde Excel (.xlsx).

Mismo patrón que communications/services/segmentation_service.py: alias de
columnas insensibles a mayúsculas/acentos, resultado con conteo de
creados/actualizados/omitidos y errores aislados por fila.
"""
from dataclasses import dataclass, field

import openpyxl
from django.utils.text import slugify

from ..models import Category, FAQ, KnowledgeArticle

FAQ_COLUMN_ALIASES = {
    "question": ["pregunta", "question"],
    "answer": ["respuesta", "answer"],
    "category": ["categoria", "categoría", "category"],
    "is_active": ["activo", "active"],
}
FAQ_REQUIRED_FIELDS = ["question", "answer", "category"]

ARTICLE_COLUMN_ALIASES = {
    "title": ["titulo", "título", "title"],
    "content": ["contenido", "content"],
    "category": ["categoria", "categoría", "category"],
    "summary": ["resumen", "summary"],
    "tags": ["etiquetas", "tags"],
    "status": ["estado", "status"],
}
ARTICLE_REQUIRED_FIELDS = ["title", "content", "category"]


@dataclass
class ImportResult:
    created: int = 0
    updated: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)


def _normalize_header(header) -> str:
    return str(header or "").strip().lower()


def _map_columns(header_row, aliases: dict[str, list[str]]) -> dict[str, int]:
    normalized = [_normalize_header(h) for h in header_row]
    mapping = {}
    for field_name, names in aliases.items():
        for idx, header in enumerate(normalized):
            if header in names:
                mapping[field_name] = idx
                break
    return mapping


def _get(row, column_map: dict[str, int], field_name: str):
    idx = column_map.get(field_name)
    if idx is None or idx >= len(row):
        return None
    return row[idx]


def _get_category(name: str) -> Category:
    name = (name or "").strip()
    category, _ = Category.objects.get_or_create(
        name=name,
        defaults={"description": f"Creada automáticamente al importar contenido ({name})."},
    )
    return category


def _read_rows(file_obj):
    workbook = openpyxl.load_workbook(file_obj, read_only=True, data_only=True)
    sheet = workbook.active
    return sheet.iter_rows(values_only=True)


def import_faqs_from_excel(file_obj) -> ImportResult:
    result = ImportResult()
    rows = _read_rows(file_obj)

    try:
        header_row = next(rows)
    except StopIteration:
        result.errors.append("El archivo está vacío.")
        return result

    column_map = _map_columns(header_row, FAQ_COLUMN_ALIASES)
    missing = [f for f in FAQ_REQUIRED_FIELDS if f not in column_map]
    if missing:
        result.errors.append(
            f"Faltan columnas obligatorias: {', '.join(missing)}. "
            f"Encabezados encontrados: {list(header_row)}"
        )
        return result

    for row_number, row in enumerate(rows, start=2):
        try:
            question = str(_get(row, column_map, "question") or "").strip()
            answer = str(_get(row, column_map, "answer") or "").strip()
            category_name = str(_get(row, column_map, "category") or "").strip()
            if not question or not answer or not category_name:
                result.skipped += 1
                result.errors.append(f"Fila {row_number}: pregunta, respuesta y categoría son obligatorias.")
                continue

            is_active_raw = _get(row, column_map, "is_active")
            is_active = True
            if is_active_raw is not None:
                is_active = str(is_active_raw).strip().lower() in {"1", "true", "si", "sí", "activo"}

            category = _get_category(category_name)
            _, created = FAQ.objects.update_or_create(
                question=question,
                defaults={"answer": answer, "category": category, "is_active": is_active},
            )
            if created:
                result.created += 1
            else:
                result.updated += 1
        except Exception as exc:  # una fila corrupta no debe tumbar toda la carga
            result.skipped += 1
            result.errors.append(f"Fila {row_number}: {exc}")

    return result


def import_articles_from_excel(file_obj) -> ImportResult:
    result = ImportResult()
    rows = _read_rows(file_obj)

    try:
        header_row = next(rows)
    except StopIteration:
        result.errors.append("El archivo está vacío.")
        return result

    column_map = _map_columns(header_row, ARTICLE_COLUMN_ALIASES)
    missing = [f for f in ARTICLE_REQUIRED_FIELDS if f not in column_map]
    if missing:
        result.errors.append(
            f"Faltan columnas obligatorias: {', '.join(missing)}. "
            f"Encabezados encontrados: {list(header_row)}"
        )
        return result

    valid_statuses = {choice for choice, _ in KnowledgeArticle.STATUS_CHOICES}

    for row_number, row in enumerate(rows, start=2):
        try:
            title = str(_get(row, column_map, "title") or "").strip()
            content = str(_get(row, column_map, "content") or "").strip()
            category_name = str(_get(row, column_map, "category") or "").strip()
            if not title or not content or not category_name:
                result.skipped += 1
                result.errors.append(f"Fila {row_number}: título, contenido y categoría son obligatorios.")
                continue

            summary = str(_get(row, column_map, "summary") or "").strip()
            tags_raw = str(_get(row, column_map, "tags") or "").strip()
            tags = [t.strip() for t in tags_raw.split(",") if t.strip()] if tags_raw else []
            status = str(_get(row, column_map, "status") or "").strip().lower() or "published"
            if status not in valid_statuses:
                status = "published"

            category = _get_category(category_name)
            _, created = KnowledgeArticle.objects.update_or_create(
                slug=slugify(title),
                defaults={
                    "title": title,
                    "summary": summary,
                    "content": content,
                    "category": category,
                    "tags": tags,
                    "status": status,
                    "published": status == "published",
                },
            )
            if created:
                result.created += 1
            else:
                result.updated += 1
        except Exception as exc:
            result.skipped += 1
            result.errors.append(f"Fila {row_number}: {exc}")

    return result
