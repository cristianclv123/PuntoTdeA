import json
from unittest.mock import Mock, patch

from django.test import TestCase, override_settings
from django.urls import reverse

from ..models import ChatConversation
from .whatsapp import handle_message


class WhatsAppFlowTests(TestCase):
    def test_whatsapp_messages_follow_the_chatbot_states(self):
        self.assertIn('ayudarte', handle_message('573001112233', 'Hola')[0])
        response = handle_message('573001112233', 'Necesito información de matrícula')[0]
        self.assertTrue(response)
        conversation = getattr(ChatConversation, '_default_manager').get(  # pyright: ignore[reportPrivateUsage]
            external_user_id='573001112233'
        )
        self.assertEqual(conversation.flow_state, 'waiting_confirmation')
        self.assertIn('nueva pregunta', handle_message('573001112233', 'sí')[0])
        conversation.refresh_from_db()
        self.assertEqual(conversation.flow_state, 'help_options')

    def test_advisor_is_only_available_after_confirmation(self):
        handle_message('573001112234', 'Hola')
        self.assertNotIn('asesor', handle_message('573001112234', 'Quiero un asesor')[0].lower())
        self.assertIn('¿te puedo ayudar', handle_message('573001112234', 'Quiero un asesor')[0])
        self.assertIn('nueva pregunta', handle_message('573001112234', 'sí')[0])
        self.assertIn('solicitud', handle_message('573001112234', 'asesor')[0].lower())

    @override_settings(META_VERIFY_TOKEN='test-token')
    def test_webhook_verification(self):
        response = self.client.get(
            reverse('knowledge:whatsapp-webhook'),
            {'hub.mode': 'subscribe', 'hub.verify_token': 'test-token', 'hub.challenge': 'abc123'},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), 'abc123')

    @override_settings(META_ACCESS_TOKEN='token', WHATSAPP_PHONE_NUMBER_ID='phone-id')
    def test_webhook_processes_and_sends_message(self):
        payload = {
            'entry': [{'changes': [{'value': {'messages': [{
                'from': '573001112233', 'type': 'text', 'text': {'body': 'Hola'},
            }]}}]}],
        }
        response_mock = Mock(status_code=200)
        response_mock.raise_for_status.return_value = None
        with patch('knowledge.chatbot.whatsapp.requests.post', return_value=response_mock) as send:
            response = self.client.post(
                reverse('knowledge:whatsapp-webhook'),
                data=json.dumps(payload),
                content_type='application/json',
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['processed'], 1)
        send.assert_called_once()