# Interfaz común ChannelAdapter
"""Interfaz común que deben implementar los adaptadores de canal.

Cualquier proveedor de envío (mock, Twilio, Meta Cloud API directo) se
conecta implementando esta misma interfaz. La lógica de negocio en
`services/campaign_service.py` solo depende de `ChannelAdapter`, nunca de
un proveedor concreto — así el proveedor final (Twilio vs Meta) se decide
sin tocar el resto del código.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class SendResult:
    """Resultado normalizado de un intento de envío, sin importar el proveedor."""

    success: bool
    provider_message_id: str = ""
    error: str = ""


class ChannelAdapter(ABC):
    """Contrato que debe cumplir cualquier adaptador de canal de mensajería."""

    #: Identificador corto del proveedor, ej. "mock", "twilio", "meta".
    provider_name: str = "base"

    @abstractmethod
    def send_template_message(self, to: str, template, params: dict) -> SendResult:
        """Envía un mensaje de plantilla aprobada a un número de WhatsApp.

        Args:
            to: número de teléfono en formato E.164 (ej. +573001234567).
            template: instancia de communications.models.MessageTemplate.
            params: dict con los valores para {{1}}, {{2}}, ... de la plantilla.

        Returns:
            SendResult con el resultado normalizado del intento de envío.
        """
        raise NotImplementedError