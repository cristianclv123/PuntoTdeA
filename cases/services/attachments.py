"""Validación y helpers de adjuntos del chat."""

from pathlib import Path

from django.core.exceptions import ValidationError

# Límite por archivo (25 MB)
MAX_ATTACHMENT_BYTES = 25 * 1024 * 1024

ALLOWED_EXTENSIONS = {
    "image": {".jpg", ".jpeg", ".png", ".gif", ".webp"},
    "video": {".mp4", ".webm", ".mov", ".m4v"},
    "office": {
        ".pdf",
        ".doc",
        ".docx",
        ".xls",
        ".xlsx",
        ".ppt",
        ".pptx",
        ".odt",
        ".ods",
        ".odp",
        ".rtf",
        ".csv",
    },
}

ACCEPT_ATTR = ",".join(
    sorted({ext for group in ALLOWED_EXTENSIONS.values() for ext in group})
)


def detect_kind(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    for kind, exts in ALLOWED_EXTENSIONS.items():
        if ext in exts:
            return kind
    raise ValidationError(
        "Solo se permiten imágenes, videos u archivos de ofimática "
        "(PDF, Word, Excel, PowerPoint, OpenDocument, RTF, CSV)."
    )


def validate_uploaded_file(uploaded) -> str:
    if not uploaded:
        raise ValidationError("Archivo vacío.")
    if uploaded.size > MAX_ATTACHMENT_BYTES:
        raise ValidationError("El archivo supera el límite de 25 MB.")
    return detect_kind(uploaded.name)
