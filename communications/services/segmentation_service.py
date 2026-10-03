# Resolución de audiencias contra Backend CRUD
"""Resolución de audiencias a partir de archivos .xlsx exportados de Campus."""

import re
from dataclasses import dataclass, field

import openpyxl

from ..models import AudienceSegment, Contact, ContactEvent, SegmentMembership
from .logging_service import log_event

EXCEL_COLUMNS = {
    "document_number": "documento identidad",
    "full_name": "nombre",
    "phone": "celular",
    "email": "email",
}

REQUIRED_FIELDS = ["document_number", "full_name", "phone"]


@dataclass
class ImportResult:
    created: int = 0
    updated: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)


def _normalize_header(header: str) -> str:
    return " ".join(str(header or "").split()).casefold()


def _map_columns(header_row) -> dict[str, int]:
    """Devuelve {campo_interno: índice_columna} según los encabezados del Excel."""
    normalized = [_normalize_header(h) for h in header_row]
    mapping = {}
    for field_name, official_header in EXCEL_COLUMNS.items():
        for idx, header in enumerate(normalized):
            if header == official_header:
                mapping[field_name] = idx
                break
    return mapping


def _normalize_phone(raw: str) -> str:
    """Normaliza a E.164 asumiendo Colombia (+57) cuando no hay indicativo."""
    digits = re.sub(r"[^\d+]", "", str(raw or ""))
    if not digits:
        return ""
    if digits.startswith("+"):
        return digits
    if digits.startswith("57") and len(digits) > 10:
        return f"+{digits}"
    return f"+57{digits}"


def import_segment_from_excel(
    file_obj,
    segment_name: str,
    description: str = "",
) -> tuple[AudienceSegment, ImportResult]:
    """Lee un .xlsx, crea/actualiza los Contact y arma un AudienceSegment.

    Args:
        file_obj: archivo .xlsx (ruta o file-like object, ej. request.FILES['file']).
        segment_name: nombre del segmento a crear.
        description: descripción opcional del segmento.

    Returns:
        (AudienceSegment creado, ImportResult con el resumen de la carga)
    """
    result = ImportResult()
    workbook = openpyxl.load_workbook(file_obj, read_only=True, data_only=True)
    sheet = workbook.active

    rows = sheet.iter_rows(values_only=True)
    try:
        header_row = next(rows)
    except StopIteration:
        result.errors.append("El archivo está vacío.")
        segment = AudienceSegment.objects.create(
            name=segment_name, description=description, source_type=AudienceSegment.SourceType.EXCEL_IMPORT
        )
        return segment, result

    column_map = _map_columns(header_row)
    missing = [f for f in REQUIRED_FIELDS if f not in column_map]
    if missing:
        result.errors.append(
            f"Faltan columnas obligatorias en el Excel: {', '.join(missing)}. "
            f"Encabezados encontrados: {list(header_row)}"
        )
        segment = AudienceSegment.objects.create(
            name=segment_name, description=description, source_type=AudienceSegment.SourceType.EXCEL_IMPORT
        )
        return segment, result

    segment = AudienceSegment.objects.create(
        name=segment_name,
        description=description,
        source_type=AudienceSegment.SourceType.EXCEL_IMPORT,
    )

    for row_number, row in enumerate(rows, start=2):
        try:
            contact = _upsert_contact_from_row(row, column_map, result)
        except Exception as exc:  # fila corrupta no debe tumbar toda la carga
            result.skipped += 1
            result.errors.append(f"Fila {row_number}: {exc}")
            continue

        if contact is None:
            continue

        SegmentMembership.objects.get_or_create(segment=segment, contact=contact)
        log_event(
            contact,
            ContactEvent.EventType.SEGMENT_ADDED,
            payload={"segment": segment.name, "source": "excel_import"},
        )

    return segment, result


def _upsert_contact_from_row(row, column_map: dict[str, int], result: ImportResult):
    def get(field_name):
        idx = column_map.get(field_name)
        return row[idx] if idx is not None and idx < len(row) else None

    document_number = str(get("document_number") or "").strip()
    full_name = str(get("full_name") or "").strip()
    phone = _normalize_phone(get("phone"))
    email = str(get("email") or "").strip()
    if not document_number or not full_name or not phone:
        result.skipped += 1
        result.errors.append(
            f"Fila descartada por datos obligatorios incompletos (doc='{document_number}', "
            f"nombre='{full_name}', tel='{phone}')."
        )
        return None

    contact, created = Contact.objects.get_or_create(
        document_number=document_number,
        defaults={
            "full_name": full_name,
            "phone": phone,
            "email": email,
            "source": "excel_campus",
            # Dato oficial de Campus: se asume consentido salvo que ya
            # se haya dado de baja explícitamente (ver update más abajo).
            "whatsapp_opt_in": Contact.OptInStatus.SUSCRITO,
        },
    )

    if created:
        result.created += 1
        return contact

    # Contacto ya existía: actualizamos datos, pero NUNCA revertimos una baja.
    contact.full_name = full_name or contact.full_name
    contact.phone = phone or contact.phone
    contact.email = email or contact.email
    if contact.whatsapp_opt_in != Contact.OptInStatus.BAJA:
        contact.whatsapp_opt_in = Contact.OptInStatus.SUSCRITO
    contact.save()
    result.updated += 1
    return contact