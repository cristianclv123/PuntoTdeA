import json
import hashlib
import hmac
from datetime import timedelta
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from cases.models import Conversation as CaseConversation, Message as CaseMessage
from communications.models import Contact
from ..models import Category, ChatConversation, FAQ
from .case_status import get_case_status
from .inactivity import (
    INACTIVITY_CLOSED_MESSAGE,
    INACTIVITY_WARNING_MESSAGE,
    close_if_inactive,
    warn_if_inactive,
)
from .whatsapp import (
    CHAT_ADVISOR,
    CHAT_FINISH,
    CHAT_MORE,
    CONFIRMATION_BUTTONS,
    HELP_BUTTONS,
    LOW_CONFIDENCE_BUTTONS,
    handle_message,
    process_inactivity,
    process_webhook,
)


def _manager(model):
    return getattr(model, '_default_manager')


def _text(reply):
    """Extrae el texto de un mensaje que puede ser string o dict con 'text'."""
    return reply if isinstance(reply, str) else reply.get('text', '')


class WhatsAppFlowTests(TestCase):
    @patch('knowledge.chatbot.case_status.requests.get')
    def test_case_status_uses_session_cookie_and_remote_ticket_id(self, get):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {'id': 42, 'status': 'cerrado'}
        get.return_value = response

        with patch.dict(
            'os.environ',
            {
                'CASES_API_BASE_URL': 'https://puntotdea-qmcv.onrender.com/',
                'CASES_API_SESSION_ID': 'test-session-id',
            },
        ):
            status = get_case_status(42)

        self.assertEqual(status, 'cerrado')
        get.assert_called_once_with(
            'https://puntotdea-qmcv.onrender.com/api/cases/tickets/42/',
            headers={'Cookie': 'sessionid=test-session-id'},
            timeout=10,
        )

    def test_knowledge_ticket_status_endpoint_proxies_associated_case(self):
        handle_message('573001112249', 'Hola')
        handle_message('573001112249', 'Quiero un asesor')
        handle_message('573001112249', 'Necesito ayuda con matrícula')
        conversation = _manager(ChatConversation).get(
            channel='whatsapp',
            external_user_id='573001112249',
        )
        conversation.case_conversation.status = CaseConversation.Status.CERRADO
        conversation.case_conversation.save(update_fields=['status'])
        user = get_user_model().objects.create_user(
            username='knowledge-ticket-status-test',
            password='test-password',
        )
        knowledge_content_type = ContentType.objects.get(
            app_label='knowledge',
            model='knowledgearticle',
        )
        permission = Permission.objects.get(
            content_type=knowledge_content_type,
            codename='access_knowledge',
        )
        user.user_permissions.add(permission)
        client = APIClient()
        client.force_authenticate(user=user)

        with patch(
            'knowledge.api.viewsets.get_case_status',
            return_value=CaseConversation.Status.PENDIENTE,
        ) as get_status:
            response = client.get(
                f'/api/knowledge/conversations/{conversation.pk}/ticket-status/'
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['conversation_id'], conversation.pk)
        self.assertEqual(response.data['ticket_id'], conversation.case_conversation_id)
        self.assertEqual(response.data['status'], CaseConversation.Status.PENDIENTE)
        get_status.assert_called_once_with(conversation.case_conversation_id)
        conversation.case_conversation.refresh_from_db()
        self.assertEqual(
            conversation.case_conversation.status,
            CaseConversation.Status.CERRADO,
        )

    def test_knowledge_ticket_status_endpoint_requires_authentication(self):
        conversation = _manager(ChatConversation).create(
            channel='whatsapp',
            external_user_id='573001112250',
        )

        response = APIClient().get(
            f'/api/knowledge/conversations/{conversation.pk}/ticket-status/'
        )

        self.assertEqual(response.status_code, 403)

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
        response = handle_message('573001112233', 'Necesito información de matrícula')
        self.assertTrue(response[0])
        conversation = getattr(ChatConversation, '_default_manager').get(  # pyright: ignore[reportPrivateUsage]
            external_user_id='573001112233'
        )
        self.assertEqual(conversation.flow_state, 'waiting_confirmation')
        text0 = response[0]['text'] if isinstance(response[0], dict) else response[0]
        text1 = response[1]['text'] if isinstance(response[1], dict) else response[1]
        self.assertIn('La respuesta de prueba', text0)
        self.assertIn('otra duda', text1)
        self.assertIn('asesor', text1)
        continuation = handle_message('573001112233', 'sí')[0]
        continuation_text = continuation if isinstance(continuation, str) else continuation['text']
        self.assertIn('otra pregunta', continuation_text)
        self.assertIn('hablar con un asesor', continuation_text)
        conversation.refresh_from_db()
        self.assertEqual(conversation.flow_state, 'help_options')
        self.assertIn('contactaremos', handle_message('573001112233', 'Quiero un asesor')[0])

    @patch(
        'knowledge.chatbot.workflow.generate_response',
        new=Mock(return_value={
            'answer': 'La información que solicitas es esta.',
            'confidence': 0.9,
            'needs_human_attention': False,
            'sources': [],
        }),
    )
    def test_user_can_close_chat_after_answering_doubt(self):
        handle_message('573001112245', 'Hola')

        response = handle_message('573001112245', '¿Cuándo son las matrículas?')

        self.assertIn('La información que solicitas es esta.', _text(response[0]))
        self.assertIn('¿Tienes otra duda', _text(response[1]))
        close_response = handle_message('573001112245', 'no')
        conversation = _manager(ChatConversation).get(
            channel='whatsapp',
            external_user_id='573001112245',
        )
        self.assertIn('finalizado', _text(close_response[0]))
        self.assertEqual(conversation.status, ChatConversation.STATUS_ENDED)
        self.assertEqual(conversation.flow_state, 'ended')

        restart_response = handle_message('573001112245', 'Necesito otra consulta')
        conversations = _manager(ChatConversation).filter(
            channel='whatsapp',
            external_user_id='573001112245',
        ).order_by('-created_at')
        self.assertEqual(conversations.count(), 2)
        self.assertNotEqual(conversations.first().pk, conversation.pk)
        self.assertEqual(conversations.first().status, ChatConversation.STATUS_ACTIVE)
        self.assertIn('ayudarte', _text(restart_response[0]))
        self.assertEqual(len(restart_response), 1)
        self.assertEqual(conversations.first().flow_state, 'waiting_question')

        next_response = handle_message('573001112245', '¿Cuándo son las matrículas?')
        self.assertIn('La información que solicitas es esta.', _text(next_response[0]))
        self.assertIn('¿Tienes otra duda', _text(next_response[1]))

    def test_user_can_request_advisor_and_get_a_case_ticket(self):
        handle_message('573001112234', 'Hola')
        advisor_prompt = handle_message('573001112234', 'Quiero un asesor')[0]
        self.assertIn('contactaremos', advisor_prompt)
        self.assertIn('documento de identidad', advisor_prompt)
        responses = handle_message('573001112234', 'Necesito ayuda con mi matrícula')
        conversation = _manager(ChatConversation).get(external_user_id='573001112234')
        case_conversation = _manager(CaseConversation).get(
            channel__code='whatsapp',
            external_thread_id='573001112234',
        )
        self.assertIn(case_conversation.ticket_number, _text(responses[1]))
        self.assertEqual(conversation.case_conversation, case_conversation)
        self.assertEqual(conversation.status, ChatConversation.STATUS_ACTIVE)
        self.assertEqual(conversation.flow_state, 'help_options')
        self.assertTrue(conversation.messages[-1]['awaiting_advisor'])
        case_message = _manager(CaseMessage).get(conversation=case_conversation)
        self.assertEqual(case_message.body, 'Necesito ayuda con mi matrícula')
        self.assertIsNone(case_conversation.assigned_to_id)

    def test_ticket_confirmation_includes_business_hours_when_closed(self):
        handle_message('573001112251', 'Hola')
        handle_message('573001112251', 'Quiero un asesor')

        with patch(
            'knowledge.chatbot.whatsapp.get_business_schedule'
        ) as get_schedule:
            get_schedule.return_value.is_open.return_value = False
            responses = handle_message(
                '573001112251',
                'Necesito ayuda con mi matrícula',
            )

        confirmation = _text(responses[-1])
        self.assertIn('lunes a viernes', confirmation)
        self.assertIn('8:00 a. m. a 5:00 p. m.', confirmation)
        self.assertIn('atendida dentro de ese horario', confirmation)

    def test_pending_whatsapp_message_appends_to_case_ticket(self):
        handle_message('573001112236', 'Hola')
        handle_message('573001112236', 'Quiero un asesor')
        handle_message('573001112236', 'Necesito ayuda con mi matrícula')
        chat = _manager(ChatConversation).get(external_user_id='573001112236')
        chat.status = ChatConversation.STATUS_PENDING
        chat.flow_state = 'pending'
        chat.save(update_fields=['status', 'flow_state'])

        replies = handle_message('573001112236', 'Sigo esperando, es urgente')
        self.assertEqual(replies, [])
        case_conversation = _manager(CaseConversation).get(
            channel__code='whatsapp',
            external_thread_id='573001112236',
        )
        bodies = list(
            _manager(CaseMessage).filter(conversation=case_conversation).values_list(
                'body', flat=True
            )
        )
        self.assertIn('Necesito ayuda con mi matrícula', bodies)
        self.assertIn('Sigo esperando, es urgente', bodies)
        self.assertIsNone(case_conversation.assigned_to_id)
        chat.refresh_from_db()
        self.assertEqual(chat.flow_state, 'pending')

    def test_pending_message_is_forwarded_to_open_advisor_case(self):
        handle_message('573001112243', 'Hola')
        handle_message('573001112243', 'Quiero un asesor')
        handle_message('573001112243', 'Necesito revisar mi solicitud')

        conversation = _manager(ChatConversation).get(
            channel='whatsapp',
            external_user_id='573001112243',
        )
        conversation.status = ChatConversation.STATUS_PENDING
        conversation.flow_state = 'pending'
        conversation.save(update_fields=['status', 'flow_state'])

        response = handle_message(
            '573001112243',
            '¿Dónde consulto el calendario académico?',
            'wamid.pending.1',
        )

        conversation.refresh_from_db()
        self.assertEqual(conversation.status, ChatConversation.STATUS_PENDING)
        self.assertEqual(conversation.flow_state, 'pending')
        self.assertEqual(response, [])
        self.assertEqual(
            _manager(CaseConversation).filter(
                channel__code='whatsapp',
                external_thread_id='573001112243',
            ).count(),
            1,
        )
        forwarded_message = _manager(CaseMessage).get(
            conversation=conversation.case_conversation,
            external_id='wamid.pending.1',
        )
        self.assertEqual(
            forwarded_message.body,
            '¿Dónde consulto el calendario académico?',
        )

    @patch(
        'knowledge.chatbot.workflow.generate_response',
        new=Mock(return_value={
            'answer': 'No encontré información suficiente.',
            'confidence': 0.0,
            'needs_human_attention': True,
            'sources': [],
        }),
    )
    def test_low_confidence_waits_for_advisor_confirmation_before_creating_case(self):
        handle_message('573001112235', 'Hola')

        responses = handle_message(
            '573001112235',
            'Pregunta sin respuesta',
            'wamid.low-confidence.1',
        )

        conversation = _manager(ChatConversation).get(external_user_id='573001112235')
        self.assertEqual(len(responses), 1)
        self.assertIn('No encontré una respuesta confiable', _text(responses[0]))
        self.assertIn('¿deseas comunicarte con un asesor?', _text(responses[0]).lower())
        self.assertEqual(responses[0]['buttons'], LOW_CONFIDENCE_BUTTONS)
        self.assertEqual(conversation.flow_state, 'waiting_low_confidence_choice')
        self.assertEqual(conversation.status, ChatConversation.STATUS_ACTIVE)
        self.assertIsNone(conversation.case_conversation)
        self.assertNotIn('awaiting_advisor', conversation.messages[-1])
        self.assertEqual(
            _manager(CaseConversation).filter(channel__code='whatsapp').count(),
            0,
        )

        ticket_response = handle_message('573001112235', 'Sí')
        conversation.refresh_from_db()
        self.assertIn('He creado el ticket', _text(ticket_response[0]))
        self.assertEqual(conversation.flow_state, 'help_options')
        self.assertIsNotNone(conversation.case_conversation)
        self.assertTrue(conversation.messages[-1]['awaiting_advisor'])
        case_message = _manager(CaseMessage).get(
            conversation=conversation.case_conversation,
        )
        self.assertEqual(case_message.body, 'Pregunta sin respuesta')

    def test_low_confidence_no_choice_returns_to_question_entry(self):
        handle_message('573001112250', 'Hola')
        with patch(
            'knowledge.chatbot.workflow.generate_response',
            side_effect=[
                {
                    'answer': 'No encontré información suficiente.',
                    'confidence': 0.0,
                    'needs_human_attention': True,
                    'sources': [],
                },
                {
                    'answer': 'Encontré la respuesta a tu nueva pregunta.',
                    'confidence': 0.9,
                    'needs_human_attention': False,
                    'sources': [],
                },
            ],
        ) as generate_response:
            first_response = handle_message('573001112250', 'Primera pregunta sin respuesta')
            no_response = handle_message('573001112250', 'no')
            responses = handle_message('573001112250', '¿Cuál es el horario de atención?')

        conversation = _manager(ChatConversation).get(external_user_id='573001112250')
        self.assertEqual(generate_response.call_count, 2)
        self.assertEqual(len(first_response), 1)
        self.assertIn('¿Deseas comunicarte con un asesor?', _text(first_response[0]))
        self.assertEqual(
            no_response,
            ['De acuerdo. Escribe tu nueva pregunta y la buscaré en la base de conocimiento.'],
        )
        self.assertEqual(conversation.last_question, '¿Cuál es el horario de atención?')
        self.assertEqual(conversation.flow_state, 'waiting_confirmation')
        self.assertIsNone(conversation.case_conversation)
        self.assertIn('Encontré la respuesta a tu nueva pregunta.', _text(responses[0]))

    def test_low_confidence_allows_retrying_with_a_new_question(self):
        handle_message('573001112249', 'Hola')
        with patch(
            'knowledge.chatbot.workflow.generate_response',
            side_effect=[
                {
                    'answer': 'No encontré información suficiente.',
                    'confidence': 0.0,
                    'needs_human_attention': True,
                    'sources': [],
                },
                {
                    'answer': 'Encontré la respuesta a tu nueva pregunta.',
                    'confidence': 0.9,
                    'needs_human_attention': False,
                    'sources': [],
                },
            ],
        ) as generate_response:
            handle_message('573001112249', 'Pregunta sin respuesta')
            responses = handle_message('573001112249', '¿Cuál es el horario de atención?')

        conversation = _manager(ChatConversation).get(external_user_id='573001112249')
        self.assertEqual(generate_response.call_count, 2)
        self.assertEqual(conversation.last_question, '¿Cuál es el horario de atención?')
        self.assertEqual(conversation.flow_state, 'waiting_confirmation')
        self.assertIn('Encontré la respuesta a tu nueva pregunta.', _text(responses[0]))
        self.assertIsNone(conversation.case_conversation)

    def test_new_message_after_ended_conversation_creates_new_chat(self):
        previous = _manager(ChatConversation).create(
            channel='whatsapp',
            external_user_id='573001112240',
            status=ChatConversation.STATUS_ENDED,
            flow_state='ended',
            messages=[{'author': 'bot', 'content': 'Conversación finalizada.'}],
        )

        with patch(
            'knowledge.chatbot.workflow.generate_response',
            return_value={
                'answer': 'Respuesta del nuevo chat.',
                'confidence': 0.9,
                'needs_human_attention': False,
                'sources': [],
            },
        ) as generate_response:
            response = handle_message('573001112240', 'Hola de nuevo')
            generate_response.assert_not_called()

        user_conversations = _manager(ChatConversation).filter(
            channel='whatsapp',
            external_user_id='573001112240',
        )
        conversations = user_conversations.filter(
            status=ChatConversation.STATUS_ACTIVE,
        ).order_by('-updated_at', '-created_at')
        self.assertEqual(user_conversations.count(), 2)
        new_conversation = conversations.first()
        self.assertNotEqual(new_conversation.pk, previous.pk)
        self.assertEqual(new_conversation.status, ChatConversation.STATUS_ACTIVE)
        self.assertEqual(new_conversation.flow_state, 'waiting_question')
        self.assertIn('ayudarte', _text(response[0]))
        self.assertEqual(len(response), 1)
        self.assertFalse(
            _manager(CaseConversation).filter(
                channel__code='whatsapp',
                external_thread_id='573001112240',
            ).exists()
        )

        with patch(
            'knowledge.chatbot.workflow.generate_response',
            return_value={
                'answer': 'La conversación nueva sigue activa.',
                'confidence': 0.9,
                'needs_human_attention': False,
                'sources': [],
            },
        ):
            next_response = handle_message('573001112240', 'Otra pregunta')

        new_conversation.refresh_from_db()
        self.assertEqual(new_conversation.last_question, 'Otra pregunta')
        self.assertEqual(new_conversation.flow_state, 'waiting_confirmation')
        self.assertEqual(
            _manager(ChatConversation).filter(
                channel='whatsapp',
                external_user_id='573001112240',
            ).count(),
            2,
        )
        self.assertIn('La conversación nueva sigue activa.', _text(next_response[0]))
        self.assertIn('¿Tienes otra duda', _text(next_response[1]))

    def test_inconsistent_ended_flow_starts_a_new_chat_instead_of_staying_closed(self):
        previous = _manager(ChatConversation).create(
            channel='whatsapp',
            external_user_id='573001112246',
            status=ChatConversation.STATUS_ACTIVE,
            flow_state='ended',
            messages=[{'author': 'bot', 'content': 'Conversación finalizada.'}],
        )

        with patch(
            'knowledge.chatbot.workflow.generate_response',
            return_value={
                'answer': 'La conversación nueva está activa.',
                'confidence': 0.9,
                'needs_human_attention': False,
                'sources': [],
            },
        ):
            response = handle_message('573001112246', 'Tengo otra pregunta')
            next_response = handle_message('573001112246', 'Otra pregunta')

        previous.refresh_from_db()
        conversations = _manager(ChatConversation).filter(
            channel='whatsapp',
            external_user_id='573001112246',
        ).order_by('-created_at')
        self.assertEqual(conversations.count(), 2)
        self.assertEqual(previous.status, ChatConversation.STATUS_ENDED)
        self.assertEqual(len(response), 1)
        self.assertIn('ayudarte', _text(response[0]))
        self.assertIn('La conversación nueva está activa.', _text(next_response[0]))
        self.assertIn('¿Tienes otra duda', _text(next_response[1]))
        self.assertNotIn('Esta conversación ya está cerrada', ' '.join(response))

    def test_whatsapp_webhook_sends_answer_and_follow_up_separately(self):
        sender = '573001112247'
        _manager(ChatConversation).create(
            channel='whatsapp',
            external_user_id=sender,
            status=ChatConversation.STATUS_ACTIVE,
            flow_state='waiting_question',
            messages=[{'author': 'bot', 'content': '¿En qué puedo ayudarte?'}],
        )
        payload = {
            'entry': [{
                'changes': [{
                    'value': {
                        'messages': [{
                            'from': sender,
                            'type': 'text',
                            'text': {'body': '¿Cuándo son las matrículas?'},
                        }],
                    },
                }],
            }],
        }

        with (
            patch(
                'knowledge.chatbot.workflow.generate_response',
                return_value={
                    'answer': 'Las matrículas son en enero.',
                    'confidence': 0.9,
                    'needs_human_attention': False,
                    'sources': [],
                },
            ),
            patch('knowledge.chatbot.whatsapp.send_text') as send_text,
            patch('knowledge.chatbot.whatsapp.send_interactive_buttons') as send_buttons,
        ):
            send_buttons.return_value = Mock(success=True)
            processed = process_webhook(payload)

        self.assertEqual(processed, 1)
        send_text.assert_called_once_with(sender, 'Las matrículas son en enero.')
        self.assertEqual(send_buttons.call_count, 1)
        args, kwargs = send_buttons.call_args
        self.assertEqual(args[0], sender)
        self.assertIn('¿Tienes otra duda', args[1])
        self.assertEqual(args[2], CONFIRMATION_BUTTONS)

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

        with patch(
            'knowledge.chatbot.workflow.generate_response',
            return_value={
                'answer': 'Respuesta en la nueva conversación.',
                'confidence': 0.9,
                'needs_human_attention': False,
                'sources': [],
            },
        ), patch(
            'knowledge.chatbot.whatsapp.get_case_status',
            return_value=CaseConversation.Status.CERRADO,
        ):
            response = handle_message('573001112241', 'Tengo otra pregunta')

        previous.refresh_from_db()
        conversations = _manager(ChatConversation).filter(
            channel='whatsapp',
            external_user_id='573001112241',
        ).order_by('-updated_at', '-created_at')
        self.assertEqual(conversations.count(), 2)
        self.assertEqual(previous.status, ChatConversation.STATUS_ENDED)
        self.assertEqual(previous.flow_state, 'ended')
        self.assertNotEqual(conversations.first().pk, previous.pk)
        self.assertEqual(conversations.first().status, ChatConversation.STATUS_ACTIVE)
        self.assertIn('ayudarte', _text(response[0]))
        self.assertEqual(len(response), 1)
        self.assertEqual(conversations.first().flow_state, 'waiting_question')

        handle_message('573001112241', 'Quiero un asesor')
        ticket_responses = handle_message('573001112241', 'Necesito una nueva revisión')
        new_case = _manager(CaseConversation).get(
            channel__code='whatsapp',
            external_thread_id=f'573001112241:chat-{conversations.first().pk}',
        )
        self.assertNotEqual(new_case.pk, previous_case.pk)
        self.assertEqual(new_case.status, CaseConversation.Status.PENDIENTE)
        self.assertIn(new_case.ticket_number, _text(ticket_responses[1]))
        self.assertEqual(
            _manager(CaseConversation).filter(channel__code='whatsapp').count(),
            2,
        )

    def test_remote_open_case_forwards_message_without_bot_reply(self):
        handle_message('573001112248', 'Hola')
        handle_message('573001112248', 'Quiero un asesor')
        handle_message('573001112248', 'Necesito revisar mi solicitud')
        conversation = _manager(ChatConversation).get(
            channel='whatsapp',
            external_user_id='573001112248',
        )
        conversation.case_conversation.status = CaseConversation.Status.CERRADO
        conversation.case_conversation.save(update_fields=['status'])

        with (
            patch(
                'knowledge.chatbot.whatsapp.get_case_status',
                return_value=CaseConversation.Status.PENDIENTE,
            ),
            patch('knowledge.chatbot.workflow.generate_response') as generate_response,
        ):
            response = handle_message('573001112248', '¿Dónde consulto el calendario?')

        conversation.refresh_from_db()
        conversation.case_conversation.refresh_from_db()
        self.assertEqual(conversation.status, ChatConversation.STATUS_ACTIVE)
        self.assertEqual(conversation.flow_state, 'help_options')
        self.assertEqual(response, [])
        self.assertTrue(
            _manager(CaseMessage).filter(
                conversation=conversation.case_conversation,
                direction=CaseMessage.Direction.INBOUND,
                body='¿Dónde consulto el calendario?',
            ).exists()
        )
        generate_response.assert_not_called()

    def test_open_advisor_case_forwards_every_message_without_bot_reply(self):
        handle_message('573001112242', 'Hola')
        handle_message('573001112242', 'Quiero un asesor')
        handle_message('573001112242', 'Necesito revisar mi solicitud')

        first_response = handle_message(
            '573001112242',
            '¿Ya revisaron mi solicitud?',
            'wamid.case-follow-up.1',
        )
        second_response = handle_message(
            '573001112242',
            'Adjunto más información sobre mi solicitud.',
            'wamid.case-follow-up.2',
        )

        conversation = _manager(ChatConversation).get(
            channel='whatsapp',
            external_user_id='573001112242',
        )
        self.assertEqual(
            _manager(ChatConversation).filter(
                channel='whatsapp',
                external_user_id='573001112242',
            ).count(),
            1,
        )
        case_messages = _manager(CaseMessage).filter(
            conversation=conversation.case_conversation,
            direction=CaseMessage.Direction.INBOUND,
        )
        self.assertEqual(conversation.status, ChatConversation.STATUS_ACTIVE)
        self.assertEqual(conversation.flow_state, 'help_options')
        self.assertEqual(first_response, [])
        self.assertEqual(second_response, [])
        self.assertTrue(case_messages.filter(body='¿Ya revisaron mi solicitud?').exists())
        self.assertTrue(
            case_messages.filter(body='Adjunto más información sobre mi solicitud.').exists()
        )

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

    @patch('knowledge.chatbot.whatsapp.send_interactive_buttons')
    @patch('knowledge.chatbot.whatsapp.send_text', return_value=True)
    @patch('knowledge.chatbot.whatsapp.send_uploaded_image_message')
    @patch('knowledge.chatbot.whatsapp.upload_whatsapp_media')
    def test_webhook_sends_the_image_attached_to_the_answer(
        self,
        upload_whatsapp_media,
        send_image_message,
        send_text,
        send_buttons,
    ):
        send_buttons.return_value = Mock(success=True)
        sender = '573001112233'
        question = '¿Cómo consulto el calendario?'
        faq = FAQ(
            question=question,
            answer='Consulta el calendario.',
            category=_manager(Category).create(name='Calendario'),
        )
        faq.set_image(SimpleUploadedFile(
            'calendario.png',
            b'faq-image-content',
            content_type='image/png',
        ))
        faq.save()
        handle_message(sender, 'Hola')
        upload_whatsapp_media.return_value = Mock(
            success=True,
            provider_message_id='media-faq-image',
        )
        send_image_message.return_value = Mock(success=True, error='')
        payload = {
            'entry': [{'changes': [{'value': {'messages': [{
                'id': 'wamid.inbound.image-test',
                'from': sender,
                'type': 'text',
                'text': {'body': question},
            }]}}]}],
        }

        with patch(
            'knowledge.chatbot.workflow.generate_response',
            return_value={
                'answer': faq.answer,
                'confidence': 0.95,
                'needs_human_attention': False,
                'sources': [],
                'image_url': reverse('knowledge:faq-image', kwargs={'pk': faq.pk}),
                'image_source_id': faq.pk,
            },
        ):
            self.assertEqual(process_webhook(payload), 1)

        upload_whatsapp_media.assert_called_once_with(
            b'faq-image-content',
            filename='calendario.png',
            content_type='image/png',
        )
        send_image_message.assert_called_once_with(
            sender,
            'media-faq-image',
            caption=faq.answer,
        )
        send_text.assert_not_called()
        self.assertEqual(send_buttons.call_count, 1)
        args, _ = send_buttons.call_args
        self.assertEqual(args[0], sender)
        self.assertIn('¿Tienes otra duda', args[1])
        self.assertEqual(args[2], CONFIRMATION_BUTTONS)


class WhatsAppInactivityTests(TestCase):
    def _conversation(
        self,
        sender,
        *,
        minutes_ago=0,
        flow_state='waiting_question',
        messages=None,
        **kwargs,
    ):
        return _manager(ChatConversation).create(
            channel='whatsapp',
            external_user_id=sender,
            status=ChatConversation.STATUS_ACTIVE,
            flow_state=flow_state,
            messages=messages or [{'author': 'bot', 'content': '¿En qué puedo ayudarte?'}],
            last_user_activity_at=timezone.now() - timedelta(minutes=minutes_ago),
            **kwargs,
        )

    @patch('knowledge.chatbot.whatsapp.send_text', return_value=True)
    def test_sends_only_one_warning_after_five_minutes(self, send_text):
        conversation = self._conversation('573001112244', minutes_ago=5)
        current_time = timezone.now()

        summary = process_inactivity(current_time)

        conversation.refresh_from_db()
        self.assertEqual(summary, {'warned': 1, 'closed': 0})
        self.assertEqual(conversation.status, ChatConversation.STATUS_ACTIVE)
        self.assertIsNotNone(conversation.inactivity_warned_at)
        self.assertEqual(
            conversation.messages[-1]['content'],
            INACTIVITY_WARNING_MESSAGE,
        )
        send_text.assert_called_once_with(
            '573001112244',
            INACTIVITY_WARNING_MESSAGE,
        )

        second = process_inactivity(current_time)
        self.assertEqual(second, {'warned': 0, 'closed': 0})
        self.assertEqual(send_text.call_count, 1)

    @patch('knowledge.chatbot.whatsapp.send_text', return_value=True)
    def test_closes_only_after_the_two_minute_grace(self, send_text):
        conversation = self._conversation('573001112245', minutes_ago=5)
        current_time = timezone.now()

        self.assertEqual(process_inactivity(current_time)['warned'], 1)

        one_minute_later = current_time + timedelta(minutes=1)
        self.assertEqual(process_inactivity(one_minute_later)['closed'], 0)
        conversation.refresh_from_db()
        self.assertEqual(conversation.status, ChatConversation.STATUS_ACTIVE)

        after_grace = current_time + timedelta(minutes=2, seconds=1)
        summary = process_inactivity(after_grace)
        conversation.refresh_from_db()
        self.assertEqual(summary['closed'], 1)
        self.assertEqual(conversation.status, ChatConversation.STATUS_ENDED)
        self.assertEqual(conversation.flow_state, 'ended')
        self.assertEqual(
            conversation.messages[-1]['content'],
            INACTIVITY_CLOSED_MESSAGE,
        )
        send_text.assert_any_call('573001112245', INACTIVITY_CLOSED_MESSAGE)

        again = process_inactivity(after_grace + timedelta(minutes=5))
        self.assertEqual(again['closed'], 0)

    @patch(
        'knowledge.chatbot.workflow.generate_response',
        new=Mock(return_value={
            'answer': 'Respuesta después del aviso.',
            'confidence': 0.9,
            'needs_human_attention': False,
            'sources': [],
        }),
    )
    def test_user_reply_after_warning_cancels_pending_close(self):
        conversation = self._conversation('573001112246', minutes_ago=6)
        warned_at = timezone.now() - timedelta(minutes=1)
        _manager(ChatConversation).filter(pk=conversation.pk).update(
            inactivity_warned_at=warned_at,
        )
        conversation.refresh_from_db()

        responses = handle_message('573001112246', 'Quiero continuar')

        conversation.refresh_from_db()
        self.assertEqual(
            _manager(ChatConversation).filter(
                channel='whatsapp',
                external_user_id='573001112246',
            ).count(),
            1,
        )
        self.assertEqual(conversation.status, ChatConversation.STATUS_ACTIVE)
        self.assertIsNone(conversation.inactivity_warned_at)
        self.assertEqual(conversation.flow_state, 'waiting_confirmation')
        self.assertIn('Respuesta después del aviso.', _text(responses[0]))

        # Ya no queda un cierre pendiente: el aviso anterior se descartó.
        summary = process_inactivity(timezone.now() + timedelta(minutes=3))
        self.assertEqual(summary['closed'], 0)

    @patch(
        'knowledge.chatbot.workflow.generate_response',
        new=Mock(return_value={
            'answer': 'Respuesta en el chat reiniciado.',
            'confidence': 0.9,
            'needs_human_attention': False,
            'sources': [],
        }),
    )
    def test_message_after_seven_minutes_starts_and_uses_new_chat(self):
        previous = self._conversation('573001112247', minutes_ago=8)

        responses = handle_message('573001112247', 'Necesito ayuda con mi matrícula')

        previous.refresh_from_db()
        conversations = _manager(ChatConversation).filter(
            channel='whatsapp',
            external_user_id='573001112247',
            status=ChatConversation.STATUS_ACTIVE,
        ).order_by('-updated_at', '-created_at')
        new_conversation = conversations.first()
        self.assertEqual(
            _manager(ChatConversation).filter(
                channel='whatsapp',
                external_user_id='573001112247',
            ).count(),
            2,
        )
        self.assertEqual(previous.status, ChatConversation.STATUS_ENDED)
        self.assertEqual(
            previous.messages[-1]['content'],
            INACTIVITY_CLOSED_MESSAGE,
        )
        self.assertNotEqual(new_conversation.pk, previous.pk)
        self.assertEqual(new_conversation.last_question, '')
        self.assertEqual(new_conversation.status, ChatConversation.STATUS_ACTIVE)
        self.assertIn('inactividad', _text(responses[0]))
        self.assertIn('ayudarte', _text(responses[1]))
        self.assertEqual(len(responses), 2)
        self.assertEqual(new_conversation.flow_state, 'waiting_question')

        question_response = handle_message(
            '573001112247',
            'Necesito ayuda con mi matrícula',
        )
        new_conversation.refresh_from_db()
        self.assertEqual(new_conversation.last_question, 'Necesito ayuda con mi matrícula')
        self.assertIn('Respuesta en el chat reiniciado.', _text(question_response[0]))

    @patch('knowledge.chatbot.whatsapp.send_text', return_value=True)
    def test_recent_conversation_is_not_touched(self, send_text):
        conversation = self._conversation('573001112248', minutes_ago=1)

        summary = process_inactivity()

        conversation.refresh_from_db()
        self.assertEqual(summary, {'warned': 0, 'closed': 0})
        self.assertEqual(conversation.status, ChatConversation.STATUS_ACTIVE)
        self.assertIsNone(conversation.inactivity_warned_at)
        send_text.assert_not_called()

    @patch('knowledge.chatbot.whatsapp.send_text', return_value=True)
    def test_does_not_warn_while_waiting_for_advisor_answer(self, send_text):
        conversation = self._conversation(
            '573001112249',
            minutes_ago=8,
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

        summary = process_inactivity()

        conversation.refresh_from_db()
        self.assertEqual(summary, {'warned': 0, 'closed': 0})
        self.assertEqual(conversation.status, ChatConversation.STATUS_ACTIVE)
        send_text.assert_not_called()

    def test_warning_claim_is_idempotent(self):
        conversation = self._conversation('573001112250', minutes_ago=6)
        current_time = timezone.now()

        first = warn_if_inactive(conversation, current_time)
        second = warn_if_inactive(conversation, current_time)

        self.assertIsNotNone(first)
        self.assertIsNone(second)
        conversation.refresh_from_db()
        warnings = [
            message for message in conversation.messages
            if message.get('inactivity_warning')
        ]
        self.assertEqual(len(warnings), 1)

    def test_close_claim_is_idempotent(self):
        conversation = self._conversation('573001112251', minutes_ago=8)
        _manager(ChatConversation).filter(pk=conversation.pk).update(
            inactivity_warned_at=timezone.now() - timedelta(minutes=3),
        )
        conversation.refresh_from_db()
        current_time = timezone.now()

        first = close_if_inactive(conversation, current_time)
        second = close_if_inactive(conversation, current_time)

        self.assertIsNotNone(first)
        self.assertIsNone(second)
        conversation.refresh_from_db()
        closures = [
            message for message in conversation.messages
            if message.get('inactivity_closed')
        ]
        self.assertEqual(len(closures), 1)

    @patch('knowledge.chatbot.whatsapp.send_text', return_value=False)
    def test_failed_warning_is_released_for_retry(self, send_text):
        conversation = self._conversation('573001112252', minutes_ago=6)

        summary = process_inactivity()

        conversation.refresh_from_db()
        self.assertEqual(summary, {'warned': 0, 'closed': 0})
        self.assertIsNone(conversation.inactivity_warned_at)
        send_text.assert_called_once()


class WhatsAppInteractiveChoiceTests(TestCase):
    def _conversation(self, sender, *, flow_state, messages=None):
        return _manager(ChatConversation).create(
            channel='whatsapp',
            external_user_id=sender,
            status=ChatConversation.STATUS_ACTIVE,
            flow_state=flow_state,
            messages=messages or [{'author': 'bot', 'content': '¿En qué puedo ayudarte?'}],
            last_user_activity_at=timezone.now(),
        )

    def _interactive_payload(self, sender, message_id, interactive_type, choice_id, title):
        return {
            'entry': [{'changes': [{'value': {'messages': [{
                'id': message_id,
                'from': sender,
                'type': 'interactive',
                'interactive': {
                    'type': interactive_type,
                    interactive_type: {'id': choice_id, 'title': title},
                },
            }]}}]}],
        }

    @patch('knowledge.chatbot.whatsapp.send_text', return_value=True)
    def test_button_reply_finishes_the_conversation(self, send_text):
        sender = '573001112260'
        conversation = self._conversation(
            sender,
            flow_state='waiting_confirmation',
            messages=[
                {'author': 'bot', 'content': '¿Tienes otra duda?'},
                {'author': 'user', 'content': 'No'},
            ],
        )
        payload = self._interactive_payload(
            sender,
            'wamid.interactive.finish',
            'button_reply',
            CHAT_FINISH,
            'Finalizar',
        )

        processed = process_webhook(payload)

        conversation.refresh_from_db()
        self.assertEqual(processed, 1)
        self.assertEqual(conversation.status, ChatConversation.STATUS_ENDED)
        self.assertEqual(conversation.flow_state, 'ended')
        send_text.assert_called_once()
        self.assertIn('finalizado', send_text.call_args.args[1])

    @patch('knowledge.chatbot.whatsapp.send_text', return_value=True)
    def test_list_reply_requests_an_advisor(self, send_text):
        sender = '573001112261'
        conversation = self._conversation(
            sender,
            flow_state='waiting_confirmation',
            messages=[{'author': 'bot', 'content': '¿Tienes otra duda?'}],
        )
        payload = self._interactive_payload(
            sender,
            'wamid.interactive.advisor',
            'list_reply',
            CHAT_ADVISOR,
            'Hablar con asesor',
        )

        process_webhook(payload)

        conversation.refresh_from_db()
        self.assertEqual(conversation.flow_state, 'waiting_advisor_question')
        self.assertIn('asesor', send_text.call_args.args[1])

    @patch('knowledge.chatbot.whatsapp.send_text', return_value=True)
    def test_out_of_context_choice_does_not_advance_the_flow(self, send_text):
        sender = '573001112262'
        conversation = self._conversation(sender, flow_state='waiting_question')
        payload = self._interactive_payload(
            sender,
            'wamid.interactive.stale',
            'button_reply',
            CHAT_FINISH,
            'Finalizar',
        )

        process_webhook(payload)

        conversation.refresh_from_db()
        self.assertEqual(conversation.status, ChatConversation.STATUS_ACTIVE)
        self.assertEqual(conversation.flow_state, 'waiting_question')
        self.assertIn('Escribe tu pregunta', send_text.call_args.args[1])

    def test_numeric_alias_finishes_when_interactive_is_unavailable(self):
        sender = '573001112266'
        conversation = self._conversation(
            sender,
            flow_state='waiting_confirmation',
            messages=[{'author': 'bot', 'content': '¿Tienes otra duda?'}],
        )

        replies = handle_message(sender, '3')

        conversation.refresh_from_db()
        self.assertEqual(conversation.status, ChatConversation.STATUS_ENDED)
        self.assertIn('finalizado', _text(replies[0]))

    @patch(
        'knowledge.chatbot.workflow.generate_response',
        new=Mock(return_value={
            'answer': 'Respuesta de prueba.',
            'confidence': 0.9,
            'needs_human_attention': False,
            'sources': [],
        }),
    )
    def test_answer_offers_confirmation_buttons(self):
        sender = '573001112263'
        handle_message(sender, 'Hola')

        replies = handle_message(sender, '¿Cuándo son las matrículas?')

        self.assertEqual(replies[0]['text'], 'Respuesta de prueba.')
        self.assertEqual(replies[1]['buttons'], CONFIRMATION_BUTTONS)

    @patch(
        'knowledge.chatbot.workflow.generate_response',
        new=Mock(return_value={
            'answer': 'No encontré información.',
            'confidence': 0.0,
            'needs_human_attention': True,
            'sources': [],
        }),
    )
    def test_low_confidence_offers_advisor_buttons(self):
        sender = '573001112264'
        handle_message(sender, 'Hola')

        replies = handle_message(sender, 'Tema muy específico')

        self.assertEqual(replies[0]['buttons'], LOW_CONFIDENCE_BUTTONS)
        self.assertIn('asesor', replies[0]['text'])

    @patch(
        'knowledge.chatbot.workflow.generate_response',
        new=Mock(return_value={
            'answer': 'Respuesta de prueba.',
            'confidence': 0.9,
            'needs_human_attention': False,
            'sources': [],
        }),
    )
    def test_more_question_button_opens_help_options(self):
        sender = '573001112265'
        handle_message(sender, 'Hola')
        handle_message(sender, '¿Cuándo son las matrículas?')

        replies = handle_message(sender, 'Otra consulta', interactive_id=CHAT_MORE)

        conversation = _manager(ChatConversation).get(external_user_id=sender)
        self.assertEqual(conversation.flow_state, 'help_options')
        self.assertEqual(replies[0]['buttons'], HELP_BUTTONS)
        self.assertIn('otra pregunta', replies[0]['text'])
