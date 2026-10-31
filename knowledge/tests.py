import os
import shutil
import tempfile
from datetime import datetime, time, timezone as datetime_timezone

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from .chatbot.schedule import BusinessSchedule
from .chatbot.workflow import ChatbotWorkflow
from .models import Category, ChatConversation, FAQ, KnowledgeArticle
from .services.rag_service import answer_query, search_knowledge


def _manager(model):
    return getattr(model, 'objects')


class KnowledgeRagTests(TestCase):
    def setUp(self):
        category = _manager(Category).create(name='Matrículas')
        _manager(KnowledgeArticle).create(
            title='Matrícula 2026',
            summary='Información sobre las matrículas de 2026.',
            content='Consulta las fechas y requisitos de matrícula.',
            category=category,
            status='published',
            published=True,
        )
        _manager(KnowledgeArticle).create(
            title='Pago de matrícula en línea',
            summary='Puedes pagar la matrícula por los canales virtuales habilitados.',
            content='Consulta el botón de pagos institucional y descarga el comprobante.',
            category=category,
            tags=['pagar', 'pago', 'canales virtuales'],
            status='published',
            published=True,
        )

    def test_plural_query_matches_singular_answer(self):
        self.assertGreater(answer_query('matriculas 2026')['confidence'], 0.0)

    def test_keywords_match_a_differently_worded_question(self):
        results = search_knowledge('¿Cómo puedo pagar la matrícula?', limit=1)
        self.assertEqual(results[0]['title'], 'Pago de matrícula en línea')
        self.assertIn('canales virtuales', answer_query('¿Cómo puedo pagar la matrícula?')['answer'])

    def test_faq_image_is_returned_and_publicly_served(self):
        faq = FAQ(
            question='¿Cómo consultar el calendario académico de Punto TdeA?',
            answer='Consulta el calendario académico en esta imagen.',
            category=_manager(Category).get(name='Matrículas'),
        )
        faq.set_image(SimpleUploadedFile(
            'calendario.png',
            b'faq-image-content',
            content_type='image/png',
        ))
        faq.save()

        result = answer_query('¿Cómo consultar el calendario académico de Punto TdeA?')

        image_url = reverse('knowledge:faq-image', kwargs={'pk': faq.pk})
        self.assertEqual(result['image_url'], image_url)
        self.assertEqual(result['image_source_id'], faq.pk)
        response = self.client.get(image_url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b'faq-image-content')


class ChatbotWorkflowTests(TestCase):
    def setUp(self):
        self.conversation = _manager(ChatConversation).create()
        self.workflow = ChatbotWorkflow(
            self.conversation,
            responder=lambda question: {
                'answer': f'Respuesta para: {question}',
                'confidence': 1.0,
                'needs_human_attention': False,
                'sources': [],
            },
            schedule=BusinessSchedule(
                weekdays=frozenset({0, 1, 2, 3, 4}),
                opening_time=time(8),
                closing_time=time(17),
            ),
        )

    def test_valid_question_can_end_chat(self):
        self.assertEqual(self.workflow.start()['state'], 'waiting_question')
        response = self.workflow.submit_question('¿Cuándo son las matrículas?')
        self.assertEqual(response['state'], 'waiting_confirmation')
        self.assertEqual(self.workflow.confirm_more_help(False)['state'], 'ended')
        self.assertEqual(self.conversation.refresh_from_db(), None)
        self.assertEqual(self.conversation.status, ChatConversation.STATUS_ENDED)

    def test_invalid_question_is_rejected_until_valid(self):
        invalid = self.workflow.submit_question('??')
        self.assertFalse(invalid['valid'])
        self.assertEqual(invalid['state'], 'waiting_question')
        self.assertTrue(self.workflow.submit_question('Necesito ayuda').get('valid'))

    def test_question_without_confident_answer_keeps_chat_active(self):
        self.workflow.responder = lambda question: {
            'answer': 'No encontré información suficiente.',
            'confidence': 0.0,
            'needs_human_attention': True,
            'sources': [],
        }

        response = self.workflow.submit_question('Pregunta sin respuesta')

        self.assertEqual(response['state'], 'waiting_confirmation')
        self.assertIn('un asesor te dará respuesta', response['message'].lower())
        self.assertIn('horario de atención', response['message'])
        self.assertIn('otra duda', response['message'])
        self.assertEqual(self.conversation.status, ChatConversation.STATUS_ACTIVE)
        self.assertEqual(self.conversation.flow_state, 'waiting_confirmation')

    def test_user_can_request_more_help(self):
        self.workflow.submit_question('¿Dónde consulto mi horario?')
        self.assertEqual(self.workflow.confirm_more_help(True)['state'], 'help_options')

    def test_advisor_request_during_business_hours_is_pending(self):
        self.workflow.submit_question('No puedo resolver mi caso')
        self.workflow.escalate('La respuesta requiere revisión humana')
        result = self.workflow.submit_advisor_question(
            'Necesito que revisen mi caso', datetime(2026, 9, 18, 15, 0, tzinfo=datetime_timezone.utc)
        )
        self.assertTrue(result['within_business_hours'])
        self.assertEqual(self.conversation.status, ChatConversation.STATUS_PENDING)
        self.assertEqual(self.conversation.advisor_question, 'Necesito que revisen mi caso')

    def test_advisor_request_outside_business_hours_is_pending(self):
        self.workflow.escalate('No hay respuesta disponible')
        result = self.workflow.submit_advisor_question(
            'Quiero hablar con un asesor', datetime(2026, 9, 19, 20, 0, tzinfo=datetime_timezone.utc)
        )
        self.assertFalse(result['within_business_hours'])
        self.assertIn('fuera del horario', result['message'])


def _faq_image(name='faq.png'):
    return SimpleUploadedFile(name, b'fake-faq-image-bytes', content_type='image/png')


def _faq_with_image(**kwargs):
    category = Category.objects.create(name='Matrículas')
    faq = FAQ(category=category, **kwargs)
    faq.set_image(_faq_image())
    faq.save()
    return faq


class FAQImageTests(TestCase):
    def setUp(self):
        self._media = tempfile.mkdtemp()
        self._override = override_settings(MEDIA_ROOT=self._media)
        self._override.enable()
        self.addCleanup(self._override.disable)
        self.addCleanup(shutil.rmtree, self._media, True)
        self.user = get_user_model().objects.create_superuser(username='tester', password='clave-segura')
        knowledge_content_type = ContentType.objects.get(
            app_label='knowledge',
            model='knowledgearticle',
        )
        permission = Permission.objects.get(
            content_type=knowledge_content_type,
            codename='access_knowledge',
        )
        self.user.user_permissions.add(permission)
        self.api = APIClient()

    def test_faq_stores_image_bytes_in_database_not_media(self):
        faq = _faq_with_image(question='¿Qué es?', answer='Es algo.')
        faq.refresh_from_db()
        self.assertEqual(bytes(faq.image_data), b'fake-faq-image-bytes')
        self.assertEqual(faq.image_name, 'faq.png')
        self.assertEqual(faq.image_content_type, 'image/png')
        self.assertTrue(faq.has_image)
        self.assertEqual(os.listdir(self._media), [])

    def test_image_endpoint_serves_stored_bytes(self):
        faq = _faq_with_image(question='¿Qué es?', answer='Es algo.')
        self.client.force_login(self.user)
        response = self.client.get(reverse('knowledge:faq-image', args=[faq.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'image/png')
        self.assertEqual(response.content, b'fake-faq-image-bytes')

    def test_image_endpoint_returns_404_without_image(self):
        category = Category.objects.create(name='General')
        faq = FAQ.objects.create(question='Sin imagen', answer='Sin imagen.', category=category)
        self.client.force_login(self.user)
        response = self.client.get(reverse('knowledge:faq-image', args=[faq.pk]))
        self.assertEqual(response.status_code, 404)

    def test_api_stores_image_bytes_with_multipart(self):
        self.api.force_login(self.user)
        category = Category.objects.create(name='Pagos')
        response = self.api.post(
            reverse('faq-list'),
            {
                'question': '¿Cómo pago?',
                'answer': 'Por la plataforma.',
                'category': str(category.id),
                'is_active': 'true',
                'image': _faq_image('pago.png'),
            },
            format='multipart',
        )
        self.assertEqual(response.status_code, 201)
        faq = FAQ.objects.get()
        self.assertEqual(bytes(faq.image_data), b'fake-faq-image-bytes')
        self.assertEqual(faq.image_name, 'pago.png')
        self.assertEqual(faq.image_content_type, 'image/png')
        self.assertTrue(response.json()['image_url'])

    def test_api_update_replaces_image(self):
        self.api.force_login(self.user)
        faq = _faq_with_image(question='¿Qué es?', answer='Es algo.')
        response = self.api.patch(
            reverse('faq-detail', args=[faq.pk]),
            {'image': _faq_image('nueva.png')},
            format='multipart',
        )
        self.assertEqual(response.status_code, 200)
        faq.refresh_from_db()
        self.assertEqual(faq.image_name, 'nueva.png')

    def test_admin_form_stores_image_bytes(self):
        self.client.force_login(self.user)
        category = Category.objects.create(name='Admin')
        response = self.client.post(
            reverse('admin:knowledge_faq_add'),
            {
                'question': 'Desde admin',
                'answer': 'Respuesta',
                'category': str(category.id),
                'is_active': 'on',
                'order': '0',
                'image_upload': _faq_image('admin.png'),
            },
        )
        self.assertEqual(response.status_code, 302)
        faq = FAQ.objects.get()
        self.assertEqual(bytes(faq.image_data), b'fake-faq-image-bytes')
        self.assertEqual(faq.image_name, 'admin.png')

    def test_manage_page_renders_with_image_field(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('knowledge:manage'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="faq_image"')
