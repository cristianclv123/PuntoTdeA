"""Traducción de los errores de Meta a un mensaje que diga qué hacer.

Meta responde con un código y un texto en inglés que no siempre orienta. Estos
mensajes se muestran en la página de prueba, donde la persona está
diagnosticando: el valor está en decir cuál es el siguiente paso, no en repetir
el texto de Meta.

Códigos tomados de la documentación oficial de Cloud API (sección
"Support > Error codes"). El texto de Meta se conserva aparte y se muestra
junto a la explicación, para poder contrastar.
"""

from __future__ import annotations

import re


#: ``código: (qué pasó, qué hacer)``. Solo los que se pueden dar al enviar;
#: los de autenticación y los de plantillas incompletas se repiten sin
#: explicación porque el mensaje de Meta ya es inequívoco en esos casos.
SEND_ERRORS: dict[int, tuple[str, str]] = {
    131047: (
        "Pasaron más de 24 horas desde que ese número te escribió.",
        "Meta solo entrega texto libre dentro de la ventana de servicio de 24 h, "
        "y esa ventana solo la abre el usuario cuando escribe primero. Pedile "
        "que te escriba, o usá una plantilla aprobada.",
    ),
    131026: (
        "Meta no pudo entregar el mensaje.",
        "Ese número no tiene WhatsApp, no aceptó los Términos y Condiciones, o "
        "tiene una versión antigua de la app. Pedile que confirme que puede "
        "escribirle al número de negocio.",
    ),
    131050: (
        "Ese destinatario pidió no recibir mensajes de marketing.",
        "Meta lo bloquea a nivel de negocio. No reintentes y dejá de enviarle "
        "plantillas de categoría marketing.",
    ),
    131049: (
        "Meta decidió no entregar este mensaje.",
        "Suele ser un límite de frecuencia por usuario. Esperá al menos 24 h "
        "antes de reenviar la plantilla.",
    ),
    131048: (
        "Ese número tiene restringido cuántos mensajes puede recibir.",
        "Suele indicar bloqueos o reportes de spam previos. Revisá la calidad "
        "del número en WhatsApp Manager.",
    ),
    130429: (
        "Se alcanzó el límite de mensajes de la API de Meta.",
        "Esperá unos minutos y reintentá, o bajá la frecuencia de envío.",
    ),
    132001: (
        "Meta no conoce esa plantilla en ese idioma.",
        "El nombre tiene que coincidir exactamente con una plantilla aprobada "
        "en tu cuenta de Meta. Revisá también el idioma, por ejemplo es_CO.",
    ),
    132000: (
        "La cantidad de parámetros no coincide con la plantilla.",
        "Revisá cuántos marcadores {{1}}, {{2}}... tiene el cuerpo de la "
        "plantilla en Meta.",
    ),
}


def _code(error: str) -> int | None:
    match = re.search(r"#(\d+)", error or "")
    return int(match.group(1)) if match else None


def explain(error: str) -> str:
    """Vuelve accionable el texto de error que devuelve Meta.

    Si el código no está en la tabla se devuelve el texto de Meta tal cual:
    es preferible mostrar la respuesta cruda de la API a inventar una
    explicación que puede ser falsa.
    """
    raw = (error or "").strip()
    code = _code(raw)
    if code is not None and code in SEND_ERRORS:
        what, how = SEND_ERRORS[code]
        return f"{what} {how} (Meta respondió: {raw})"
    return raw or "Meta no aceptó el mensaje y no dio detalle."
