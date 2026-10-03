import json
import hashlib
import hmac
from unittest.mock import Mock, patch

from django.test import TestCase, override_settings
from django.urls import reverse

from cases.models import Conversation as CaseConversation, Message as CaseMessage
from communications.models import Contact
from ..models import ChatConversation
from .whatsapp import handle_message


def _manager(model):
    return getattr(model, '_default_manager')


class WhatsAppFlowTests(TestCase):
    def test_whatsapp_conversation_links_matching_communications_contact(self):
        contact = _manager(Contact).create(
            full_name='Estudiante de prueba',
            document_number='1234567890',
            phone='+573001112233',
        )

        handle_message('573001112233', 'Hola')

        conversation = getattr(ChatConversation, '_default_manager').get(
            channel='whatsapp',
            external_user_id='573001112233',
        )
        self.assertEqual(conversation.contact, contact)

    @patch(
        'knowledge.chatbot.workflow.generate_response',
        new=Mock(return_value={
            'answer': 'La respuesta de prueba está disponible.',
            'confidence': 0.9,
            'needs_human_attention': False,
            'sources': [],
        }),
    )
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

    def test_user_can_request_advisor_and_get_a_case_ticket(self):
        handle_message('573001112234', 'Hola')
        self.assertIn('transferiremos', handle_message('573001112234', 'Quiero un asesor')[0])
        responses = handle_message('573001112234', 'Necesito ayuda con mi matrícula')
        conversation = _manager(ChatConversation).get(external_user_id='573001112234')
        case_conversation = _manager(CaseConversation).get(
            channel__code='whatsapp',
            external_thread_id='573001112234',
        )
        self.assertIn(case_conversation.ticket_number, responses[1])
        self.assertEqual(conversation.case_conversation, case_conversation)
        self.assertEqual(conversation.status, ChatConversation.STATUS_PENDING)
        case_message = _manager(CaseMessage).get(conversation=case_conversation)
        self.assertEqual(case_message.body, 'Necesito ayuda con mi matrícula')

    @patch(
        'knowledge.chatbot.workflow.generate_response',
        new=Mock(return_value={
            'answer': 'No encontré información suficiente.',
            'confidence': 0.0,
            'needs_human_attention': True,
            'sources': [],
        }),
    )
    def test_low_confidence_answer_creates_case_ticket(self):
        handle_message('573001112235', 'Hola')

        responses = handle_message('573001112235', 'Pregunta sin respuesta')

        conversation = _manager(ChatConversation).get(external_user_id='573001112235')
        case_conversation = _manager(CaseConversation).get(
            channel__code='whatsapp',
            external_thread_id='573001112235',
        )
        self.assertIn(case_conversation.ticket_number, responses[1])
        self.assertEqual(conversation.case_conversation, case_conversation)
        self.assertEqual(conversation.flow_state, 'pending')
        case_message = _manager(CaseMessage).get(conversation=case_conversation)
        self.assertEqual(case_message.body, 'Pregunta sin respuesta')

    @override_settings(META_VERIFY_TOKEN='test-token')
    def test_webhook_verification(self):
        response = self.client.get(
            reverse('knowledge:whatsapp-webhook'),
            {'hub.mode': 'subscribe', 'hub.verify_token': 'test-token', 'hub.challenge': 'abc123'},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), 'abc123')

    @override_settings(
        META_ACCESS_TOKEN='token',
        WHATSAPP_PHONE_NUMBER_ID='phone-id',
        META_APP_SECRET='app-secret',
    )
    def test_webhook_processes_and_sends_message(self):
        payload = {
            'entry': [{'changes': [{'value': {'messages': [{
                'id': 'wamid.inbound.knowledge-test',
                'from': '573001112233', 'type': 'text', 'text': {'body': 'Hola'},
            }]}}]}],
        }
        response_mock = Mock(status_code=200)
        response_mock.raise_for_status.return_value = None
        response_mock.json.return_value = {'messages': [{'id': 'wamid.outbound.knowledge-test'}]}
        body = json.dumps(payload).encode()
        signature = hmac.new(b'app-secret', body, hashlib.sha256).hexdigest()
        with patch('communications.adapters.meta_adapter.requests.post', return_value=response_mock) as send:
            response = self.client.post(
                reverse('knowledge:whatsapp-webhook'),
                data=body,
                content_type='application/json',
                HTTP_X_HUB_SIGNATURE_256=f'sha256={signature}',
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['processed'], 1)
        send.assert_called_once()
