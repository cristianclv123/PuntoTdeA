"""Adaptador simulado: no llama a ningún proveedor real.

Permite que campañas, colas y estados funcionen de punta a punta sin
credenciales de Twilio ni de Meta. Se reemplaza por TwilioAdapter o
MetaAdapter (mismo contrato ChannelAdapter) cuando el proveedor esté decidido.
"""

import random
import uuid

from .base import ChannelAdapter, SendResult


class MockAdapter(ChannelAdapter):
    provider_name = "mock"

    def __init__(self, failure_rate: float = 0.0):
        """failure_rate: fracción (0-1) de envíos que se simulan fallidos,
        útil para probar el manejo de errores sin depender de un proveedor real."""
        self.failure_rate = failure_rate

    def send_template_message(self, to: str, template, params: dict) -> SendResult:
        if not to:
            return SendResult(success=False, error="Número de teléfono vacío")

        if random.random() < self.failure_rate:
            return SendResult(success=False, error="Fallo simulado (mock)")

        fake_id = f"mock-{uuid.uuid4().hex[:12]}"
        return SendResult(success=True, provider_message_id=fake_id)