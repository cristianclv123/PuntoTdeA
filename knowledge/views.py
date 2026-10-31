import json

from django.core.exceptions import ObjectDoesNotExist
from django.db import models
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from PuntoTdeA.access import module_access_required
from communications.webhooks.meta_webhook import whatsapp_webhook as meta_whatsapp_webhook
from .chatbot import workflow as chatbot_workflow
from .models import Category, ChatConversation, FAQ, KnowledgeArticle
from .api.permissions import KNOWLEDGE_PERMISSION


def _manager(model):
    return getattr(model, '_default_manager')


@module_access_required(KNOWLEDGE_PERMISSION, module_name="Knowledge")
def index(request):
    articles = _manager(KnowledgeArticle).filter(published=True, status='published')[:10]
    faqs = _manager(FAQ).filter(is_active=True)[:5]
    return render(
        request,
        'knowledge/index.html',
        {'articles': articles, 'faqs': faqs, 'active_nav': 'knowledge'},
    )


@module_access_required(KNOWLEDGE_PERMISSION, module_name="Knowledge")
def faq_list(request):
    return index(request)


@module_access_required(KNOWLEDGE_PERMISSION, module_name="Knowledge")
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
        return render(request, 'knowledge/chatbot.html', {'greeting': greeting})

    try:
        payload = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'error': 'El cuerpo de la solicitud debe ser JSON válido.'}, status=400)

    conversation_id = request.session.get('chatbot_conversation_id')
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


def faq_image(request, pk):
    """Sirve imágenes activas de FAQ, que el chatbot puede mostrar públicamente."""
    now = timezone.now()
    faqs = FAQ.objects.filter(pk=pk, is_active=True).filter(
        models.Q(valid_from__isnull=True) | models.Q(valid_from__lte=now),
    ).filter(
        models.Q(valid_until__isnull=True) | models.Q(valid_until__gte=now),
    )
    faq = get_object_or_404(faqs)
    data = faq.get_image_bytes()
    if not data:
        return HttpResponse(status=404)
    response = HttpResponse(
        data, content_type=faq.image_content_type or 'application/octet-stream'
    )
    response['Cache-Control'] = 'public, max-age=86400'
    if faq.image_name:
        response['Content-Disposition'] = f'inline; filename="{faq.image_name}"'
    return response
