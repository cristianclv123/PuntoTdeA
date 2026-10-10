import json
import hashlib
import hmac
from datetime import timedelta
from unittest.mock import Mock, patch

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from cases.models import Conversation as CaseConversation, Message as CaseMessage
from communications.models import Contact
from ..models import ChatConversation
from .whatsapp import close_inactive_whatsapp_conversations, handle_message


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
    def test_low_confidence_keeps_whatsapp_conversation_active(self):
        handle_message('573001112235', 'Hola')

        responses = handle_message('573001112235', 'Pregunta sin respuesta')

        conversation = _manager(ChatConversation).get(external_user_id='573001112235')
        self.assertEqual(len(responses), 1)
        self.assertIn('un asesor te dará respuesta', responses[0].lower())
        self.assertIn('horario de atención', responses[0])
        self.assertIn('otras preguntas', responses[0])
        self.assertEqual(conversation.flow_state, 'help_options')
        self.assertEqual(conversation.status, ChatConversation.STATUS_ACTIVE)
        self.assertIsNone(conversation.case_conversation)
        self.assertTrue(conversation.messages[-1]['awaiting_advisor'])
        self.assertFalse(_manager(CaseConversation).filter(
            channel__code='whatsapp',
            external_thread_id='573001112235',
        ).exists())
        next_responses = handle_message('573001112235', 'Otra pregunta que tampoco entiende')
        conversation.refresh_from_db()
        self.assertEqual(len(next_responses), 1)
        self.assertEqual(conversation.last_question, 'Otra pregunta que tampoco entiende')
        self.assertEqual(conversation.status, ChatConversation.STATUS_ACTIVE)
        self.assertEqual(conversation.flow_state, 'help_options')

    def test_new_message_after_ended_conversation_creates_new_chat(self):
        previous = _manager(ChatConversation).create(
            channel='whatsapp',
            external_user_id='573001112240',
            status=ChatConversation.STATUS_ENDED,
            flow_state='ended',
            messages=[{'author': 'bot', 'content': 'Conversación finalizada.'}],
        )

        response = handle_message('573001112240', 'Hola de nuevo')

        conversations = _manager(ChatConversation).filter(
            channel='whatsapp',
            external_user_id='573001112240',
        ).order_by('-created_at')
        self.assertEqual(conversations.count(), 2)
        new_conversation = conversations.first()
        self.assertNotEqual(new_conversation.pk, previous.pk)
        self.assertEqual(new_conversation.status, ChatConversation.STATUS_ACTIVE)
        self.assertEqual(new_conversation.flow_state, 'waiting_question')
        self.assertIn('ayudarte', response[0])

    def test_new_message_after_advisor_closes_case_creates_new_chat(self):
        handle_message('573001112241', 'Hola')
        handle_message('573001112241', 'Quiero un asesor')
        handle_message('573001112241', 'Necesito revisar mi solicitud')
        previous = _manager(ChatConversation).get(
            channel='whatsapp',
            external_user_id='573001112241',
        )
        previous_case = previous.case_conversation
        previous_case.status = CaseConversation.Status.CERRADO
        previous_case.save(update_fields=['status'])

        response = handle_message('573001112241', 'Tengo otra pregunta')

        previous.refresh_from_db()
        conversations = _manager(ChatConversation).filter(
            channel='whatsapp',
            external_user_id='573001112241',
        ).order_by('-created_at')
        self.assertEqual(conversations.count(), 2)
        self.assertEqual(previous.status, ChatConversation.STATUS_ENDED)
        self.assertEqual(previous.flow_state, 'ended')
        self.assertNotEqual(conversations.first().pk, previous.pk)
        self.assertEqual(conversations.first().status, ChatConversation.STATUS_ACTIVE)
        self.assertIn('ayudarte', response[0])

    def test_open_advisor_case_does_not_create_new_chat(self):
        handle_message('573001112242', 'Hola')
        handle_message('573001112242', 'Quiero un asesor')
        handle_message('573001112242', 'Necesito revisar mi solicitud')

        response = handle_message('573001112242', '¿Ya revisaron mi solicitud?')

        self.assertEqual(
            _manager(ChatConversation).filter(
                channel='whatsapp',
                external_user_id='573001112242',
            ).count(),
            1,
        )
        self.assertIn('cerrada', response[0])

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


class WhatsAppInactivityTests(TestCase):
    @patch('knowledge.chatbot.whatsapp.send_text', return_value=True)
    def test_closes_and_notifies_inactive_whatsapp_conversation(self, send_text):
        conversation = _manager(ChatConversation).create(
            channel='whatsapp',
            external_user_id='573001112236',
            status=ChatConversation.STATUS_ACTIVE,
            flow_state='waiting_question',
            messages=[{'author': 'bot', 'content': '¿En qué puedo ayudarte?'}],
        )
        current_time = timezone.now()
        _manager(ChatConversation).filter(pk=conversation.pk).update(
            updated_at=current_time - timedelta(minutes=5)
        )

        closed_count = close_inactive_whatsapp_conversations(current_time)

        conversation.refresh_from_db()
        self.assertEqual(closed_count, 1)
        self.assertEqual(conversation.status, ChatConversation.STATUS_ENDED)
        self.assertEqual(conversation.flow_state, 'ended')
        self.assertIn('inactividad', conversation.messages[-1]['content'])
        send_text.assert_called_once_with(
            '573001112236',
            conversation.messages[-1]['content'],
        )

        response = handle_message('573001112236', 'Quiero hacer otra consulta')
        conversations = _manager(ChatConversation).filter(
            channel='whatsapp',
            external_user_id='573001112236',
        ).order_by('-created_at')
        self.assertEqual(conversations.count(), 2)
        self.assertNotEqual(conversations.first().pk, conversation.pk)
        self.assertEqual(conversations.first().status, ChatConversation.STATUS_ACTIVE)
        self.assertIn('ayudarte', response[0])

    @patch('knowledge.chatbot.whatsapp.send_text', return_value=True)
    def test_keeps_recent_whatsapp_conversation_active(self, send_text):
        conversation = _manager(ChatConversation).create(
            channel='whatsapp',
            external_user_id='573001112237',
            status=ChatConversation.STATUS_ACTIVE,
            messages=[{'author': 'bot', 'content': '¿En qué puedo ayudarte?'}],
        )

        closed_count = close_inactive_whatsapp_conversations()

        conversation.refresh_from_db()
        self.assertEqual(closed_count, 0)
        self.assertEqual(conversation.status, ChatConversation.STATUS_ACTIVE)
        send_text.assert_not_called()

    @patch('knowledge.chatbot.whatsapp.send_text', return_value=True)
    def test_does_not_close_when_last_message_was_sent_by_user(self, send_text):
        conversation = _manager(ChatConversation).create(
            channel='whatsapp',
            external_user_id='573001112238',
            status=ChatConversation.STATUS_ACTIVE,
            messages=[
                {'author': 'bot', 'content': '¿En qué puedo ayudarte?'},
                {'author': 'user', 'content': 'Mi última pregunta'},
            ],
        )
        _manager(ChatConversation).filter(pk=conversation.pk).update(
            updated_at=timezone.now() - timedelta(minutes=5)
        )

        closed_count = close_inactive_whatsapp_conversations()

        conversation.refresh_from_db()
        self.assertEqual(closed_count, 0)
        self.assertEqual(conversation.status, ChatConversation.STATUS_ACTIVE)
        send_text.assert_not_called()

    @patch('knowledge.chatbot.whatsapp.send_text', return_value=True)
    def test_does_not_close_while_waiting_for_advisor_answer(self, send_text):
        conversation = _manager(ChatConversation).create(
            channel='whatsapp',
            external_user_id='573001112239',
            status=ChatConversation.STATUS_ACTIVE,
            flow_state='help_options',
            messages=[
                {
                    'author': 'bot',
                    'content': 'Un asesor responderá tu duda.',
                    'awaiting_advisor': True,
                },
                {'author': 'user', 'content': 'Otra duda'},
                {'author': 'bot', 'content': 'Esta otra respuesta sí está disponible.'},
            ],
        )
        _manager(ChatConversation).filter(pk=conversation.pk).update(
            updated_at=timezone.now() - timedelta(minutes=5)
        )

        closed_count = close_inactive_whatsapp_conversations()

        conversation.refresh_from_db()
        self.assertEqual(closed_count, 0)
        self.assertEqual(conversation.status, ChatConversation.STATUS_ACTIVE)
        send_text.assert_not_called()
