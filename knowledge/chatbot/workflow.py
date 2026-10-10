"""Orquestación del diagrama de estados del chatbot."""

from datetime import datetime
from typing import Any

from django.utils import timezone

from ..models import ChatConversation
from .responder import Responder, generate_response
from .schedule import BusinessSchedule, get_business_schedule
from .validation import validate_question


class ChatbotWorkflow:
    def __init__(
        self,
        conversation: ChatConversation,
        responder: Responder | None = None,
        schedule: BusinessSchedule | None = None,
    ):
        self.conversation = conversation
        self.responder = responder
        self.schedule = schedule or get_business_schedule()

    def start(self) -> dict[str, Any]:
        message = 'Hola, soy el asistente de Punto TdeA. ¿En qué puedo ayudarte?'
        self.conversation.flow_state = 'waiting_question'
        self._add_message('bot', message)
        self._save()
        return self._result('waiting_question', message)

    def submit_question(self, question: str) -> dict[str, Any]:
        valid, error = validate_question(question)
        if not valid:
            self._add_message('bot', error)
            self._save()
            return self._result('waiting_question', error, valid=False)

        question = question.strip()
        self.conversation.last_question = question
        self._add_message('user', question)
        response = generate_response(question, self.responder) if self.responder else generate_response(question)
        answer = response.get('answer', 'No pude generar una respuesta.')
        needs_human_attention = response.get('needs_human_attention', False)
        if needs_human_attention:
            answer = (
                f'{answer}\n\nUn asesor te dará respuesta en cuanto esté disponible, '
                'dentro del horario de atención. Mientras tanto, puedes hacerme otras '
                'preguntas o escribir "asesor" para solicitar atención humana.'
            )
            state = 'help_options'
        else:
            state = 'waiting_confirmation'
        self.conversation.flow_state = state
        self._add_message('bot', answer, awaiting_advisor=needs_human_attention)
        self._save()
        result = self._result(state, answer, valid=True)
        result.update(response)
        result['message'] = answer
        result['state'] = state
        return result

    def confirm_more_help(self, needs_more_help: bool) -> dict[str, Any]:
        if needs_more_help:
            message = 'Claro. ¿Qué deseas hacer? Puedes ingresar una nueva pregunta o solicitar hablar con un asesor.'
            state = 'help_options'
        else:
            message = 'Gracias por comunicarte con nosotros. Hemos finalizado el chat.'
            self.conversation.status = ChatConversation.STATUS_ENDED
            state = 'ended'
        self.conversation.flow_state = state
        self._add_message('bot', message)
        self._save()
        return self._result(state, message)

    def close_for_inactivity(self) -> dict[str, Any]:
        message = (
            'La conversación se cerró por inactividad después de 5 minutos. '
            'Cuando quieras, puedes escribirnos de nuevo.'
        )
        self.conversation.status = ChatConversation.STATUS_ENDED
        self.conversation.flow_state = 'ended'
        self._add_message('bot', message)
        self._save()
        return self._result('ended', message, inactivity=True)

    def escalate(self, reason: str = '') -> dict[str, Any]:
        message = 'Para ayudarte mejor, transferiremos esta conversación a un asesor. ¿Qué solicitud deseas enviarle?'
        self.conversation.escalation_reason = reason.strip()
        self.conversation.flow_state = 'waiting_advisor_question'
        self._add_message('bot', message)
        self._save()
        return self._result('waiting_advisor_question', message)

    def submit_advisor_question(self, question: str, current_time: datetime | None = None) -> dict[str, Any]:
        valid, error = validate_question(question)
        if not valid:
            return self._result('waiting_advisor_question', error, valid=False)

        question = question.strip()
        is_open = self.schedule.is_open(current_time)
        self.conversation.advisor_question = question
        self.conversation.status = ChatConversation.STATUS_PENDING
        self.conversation.flow_state = 'pending'
        self.conversation.escalated_at = current_time or timezone.now()
        message = (
            'Hemos recibido tu solicitud. Un asesor estará disponible para atenderte pronto.'
            if is_open else
            'Hemos recibido tu solicitud. Actualmente estamos fuera del horario de atención. '
            'Tu mensaje queda pendiente y será atendido dentro del horario establecido.'
        )
        self._add_message('user', question)
        self._add_message('bot', message)
        self._save()
        return self._result('pending', message, valid=True, within_business_hours=is_open)

    def _add_message(self, author: str, content: str, *, awaiting_advisor: bool = False) -> None:
        message = {
            'author': author,
            'content': content,
            'created_at': timezone.now().isoformat(),
        }
        if awaiting_advisor:
            message['awaiting_advisor'] = True
        self.conversation.messages.append(message)

    def _save(self) -> None:
        self.conversation.save(update_fields=[
            'status', 'messages', 'escalation_reason', 'advisor_question', 'escalated_at',
            'case_conversation', 'flow_state', 'last_question', 'updated_at',
        ])

    def _result(self, state: str, message: str, **extra: Any) -> dict[str, Any]:
        return {'conversation_id': str(self.conversation.pk), 'state': state, 'message': message, **extra}