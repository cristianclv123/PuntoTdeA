import json

from django.contrib.auth.decorators import login_required
from django.core.exceptions import ObjectDoesNotExist
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt

from communications.webhooks.meta_webhook import whatsapp_webhook as meta_whatsapp_webhook
from .chatbot import workflow as chatbot_workflow
from .models import Category, ChatConversation, FAQ, KnowledgeArticle


def _manager(model):
    return getattr(model, '_default_manager')


@login_required
def index(request):
    articles = _manager(KnowledgeArticle).filter(published=True, status='published')[:10]
    faqs = _manager(FAQ).filter(is_active=True)[:5]
    return render(
        request,
        'knowledge/index.html',
        {'articles': articles, 'faqs': faqs, 'active_nav': 'knowledge'},
    )


@login_required
def faq_list(request):
    return index(request)


@login_required
def manage(request):
    """Gestión de preguntas y artículos: la tabla se carga y muta por JS
    contra /api/knowledge/ (ver knowledge/static/knowledge/js/manage.js)."""
    return render(
        request,
        'knowledge/manage.html',
        {'active_nav': 'knowledge-manage', 'categories': _manager(Category).filter(is_active=True).order_by('name')},
    )


@csrf_exempt
def chatbot(request):
    """HTTP adapter for the chatbot workflow; state is persisted by conversation UUID."""
    if request.method == 'GET':
        conversation = _manager(ChatConversation).create()
        request.session['chatbot_conversation_id'] = str(conversation.pk)
        greeting = chatbot_workflow.ChatbotWorkflow(conversation).start()
        if request.headers.get('Accept') == 'application/json':
            return JsonResponse(greeting)
        return render(request, 'knowledge/chatbot.html', {'greeting': greeting})

    try:
        payload = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'error': 'El cuerpo de la solicitud debe ser JSON válido.'}, status=400)

    conversation_id = request.session.get('chatbot_conversation_id') or payload.get('conversation_id')
    if not conversation_id:
        return JsonResponse({'error': 'Inicia una conversación antes de enviar mensajes.'}, status=400)
    try:
        conversation = _manager(ChatConversation).get(pk=conversation_id)
    except (ObjectDoesNotExist, ValueError):
        return JsonResponse({'error': 'La conversación no existe.'}, status=404)

    workflow = chatbot_workflow.ChatbotWorkflow(conversation)
    action = payload.get('action', 'question')
    if action == 'question':
        result = workflow.submit_question(payload.get('question', ''))
    elif action == 'confirm':
        if conversation.flow_state != 'waiting_confirmation':
            return JsonResponse({'error': 'Primero debes enviar una pregunta.'}, status=400)
        result = workflow.confirm_more_help(bool(payload.get('needs_more_help')))
    elif action == 'escalate':
        if conversation.flow_state != 'help_options':
            return JsonResponse({'error': 'Primero debes recibir una respuesta y confirmar que necesitas más ayuda.'}, status=400)
        result = workflow.escalate(payload.get('reason', ''))
    elif action == 'advisor_question':
        result = workflow.submit_advisor_question(payload.get('question', ''))
    else:
        return JsonResponse({'error': 'Acción de chatbot no soportada.'}, status=400)
    return JsonResponse(result)


def whatsapp_webhook(request):
    """Alias temporal del webhook central para no romper URLs ya publicadas."""
    return meta_whatsapp_webhook(request)
