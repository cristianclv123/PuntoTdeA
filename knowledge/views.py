<<<<<<< Updated upstream
from django.shortcuts import render

# Create your views here.
from django.http import HttpResponse
=======
import json

from django.core.exceptions import ObjectDoesNotExist
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt

from .chatbot import workflow as chatbot_workflow
from .chatbot.whatsapp import parse_json, process_webhook, validate_signature, verify_webhook
from .models import ChatConversation
from .models import FAQ, KnowledgeArticle
from .services.indexing_service import index_academic_calendar
from .services.rag_service import answer_query, search_knowledge

>>>>>>> Stashed changes

def _manager(model):
    return getattr(model, '_default_manager')


def index(request):
<<<<<<< Updated upstream
    return HttpResponse("<h1>Módulo de Conocimiento</h1><p>En construcción</p>")
=======
    articles = _manager(KnowledgeArticle).filter(published=True, status='published')[:10]
    faqs = _manager(FAQ).filter(is_active=True)[:5]
    return render(request, 'knowledge/index.html', {'articles': articles, 'faqs': faqs})


def faq_list(request):
    return index(request)


def search(request):
    query = request.GET.get('q', '').strip()
    results = search_knowledge(query) if query else []
    return JsonResponse({'results': results, 'query': query})


def ask(request):
    query = request.GET.get('q', '').strip()
    response = answer_query(query)
    return JsonResponse(response)


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


@csrf_exempt
def whatsapp_webhook(request):
    if request.method == 'GET':
        challenge = verify_webhook(
            request.GET.get('hub.mode', ''),
            request.GET.get('hub.verify_token', ''),
            request.GET.get('hub.challenge', ''),
        )
        if challenge is None:
            return HttpResponseForbidden('Verification failed')
        return HttpResponse(challenge, content_type='text/plain')
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido.'}, status=405)
    if not validate_signature(request.body, request.META.get('HTTP_X_HUB_SIGNATURE_256')):
        return HttpResponseForbidden('Invalid signature')
    try:
        payload = parse_json(request.body)
    except (UnicodeDecodeError, ValueError):
        return JsonResponse({'error': 'El cuerpo debe ser JSON válido.'}, status=400)
    return JsonResponse({'ok': True, 'processed': process_webhook(payload)})


def reindex_academic_calendar(_request):
    payload = index_academic_calendar()
    return JsonResponse({'status': 'ok', 'payload': payload})
>>>>>>> Stashed changes
