"""Consulta el estado de tickets en el servicio remoto de cases."""

import os
from typing import Any

import requests

from cases.models import Conversation


DEFAULT_CASES_API_BASE_URL = 'https://puntotdea-qmcv.onrender.com'
CASES_API_TIMEOUT = 10


class CaseStatusAPIError(RuntimeError):
    """Error consultando el estado de un ticket en el API de cases."""


def get_case_status(ticket_id: int) -> str:
    base_url = os.environ.get(
        'CASES_API_BASE_URL',
        DEFAULT_CASES_API_BASE_URL,
    ).strip().rstrip('/')
    session_id = os.environ.get('CASES_API_SESSION_ID', '').strip()
    if not base_url:
        raise CaseStatusAPIError('CASES_API_BASE_URL no está configurada.')
    if not session_id:
        raise CaseStatusAPIError('CASES_API_SESSION_ID no está configurada.')
    if ticket_id <= 0:
        raise CaseStatusAPIError('El identificador del ticket debe ser positivo.')

    try:
        response = requests.get(
            f'{base_url}/api/cases/tickets/{ticket_id}/',
            headers={'Cookie': f'sessionid={session_id}'},
            timeout=CASES_API_TIMEOUT,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise CaseStatusAPIError(
            f'No se pudo consultar el ticket {ticket_id} en el API de cases.'
        ) from exc

    try:
        payload: Any = response.json()
    except ValueError as exc:
        raise CaseStatusAPIError(
            f'El API de cases devolvió una respuesta inválida para el ticket {ticket_id}.'
        ) from exc

    if not isinstance(payload, dict):
        raise CaseStatusAPIError(
            f'El API de cases devolvió un formato inesperado para el ticket {ticket_id}.'
        )
    status = payload.get('status')
    if not isinstance(status, str) or not status.strip():
        raise CaseStatusAPIError(
            f'La respuesta del API no contiene el estado del ticket {ticket_id}.'
        )
    normalized_status = status.strip()
    if normalized_status not in Conversation.Status.values:
        raise CaseStatusAPIError(
            f'El API devolvió un estado desconocido para el ticket {ticket_id}.'
        )
    return normalized_status
