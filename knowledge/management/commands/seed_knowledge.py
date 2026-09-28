from django.core.management.base import BaseCommand

from knowledge.models import Category, FAQ, Intent, KnowledgeArticle


CATEGORIES = {
    'Inscripciones': 'Admisiones e inscripción de estudiantes.',
    'Matrícula': 'Fechas, pagos y requisitos de matrícula.',
    'Calendario académico': 'Fechas importantes del periodo académico.',
    'Trámites': 'Solicitudes y certificados académicos.',
    'Programas': 'Información de programas y sedes.',
    'Atención': 'Canales y horarios de atención.',
}

INTENTS = {
    'consultar_matricula': 'Preguntas sobre fechas, requisitos y pagos de matrícula.',
    'consultar_inscripciones': 'Preguntas sobre inscripción y admisión.',
    'consultar_calendario': 'Preguntas sobre fechas del calendario académico.',
    'consultar_tramites': 'Preguntas sobre certificados y solicitudes.',
    'contactar_asesor': 'Solicitudes que requieren atención humana.',
}

FAQS = [
    {
        'question': '¿Cuándo se realiza la matrícula?',
        'answer': 'La matrícula se realiza dentro de las fechas publicadas en el calendario académico institucional. Revisa el calendario de tu programa antes de pagar.',
        'category': 'Matrícula',
        'intent': 'consultar_matricula',
        'tags': ['matrícula', 'fecha', 'periodo', 'semestre'],
    },
    {
        'question': '¿Cómo puedo pagar la matrícula?',
        'answer': 'Puedes pagar la matrícula mediante los canales virtuales habilitados por la institución. Conserva el comprobante de pago para futuras consultas.',
        'category': 'Matrícula',
        'intent': 'consultar_matricula',
        'tags': ['pagar', 'pago', 'matrícula', 'comprobante'],
    },
    {
        'question': '¿Dónde consulto el calendario académico?',
        'answer': 'El calendario académico se consulta en los canales oficiales de Punto TdeA y contiene las fechas de inscripción, matrícula, clases y evaluaciones.',
        'category': 'Calendario académico',
        'intent': 'consultar_calendario',
        'tags': ['calendario', 'fechas', 'clases', 'evaluaciones'],
    },
    {
        'question': '¿Cómo solicito un certificado de notas?',
        'answer': 'Solicita el certificado de notas mediante el canal institucional de trámites académicos. Ten a mano tu documento y programa académico.',
        'category': 'Trámites',
        'intent': 'consultar_tramites',
        'tags': ['certificado', 'notas', 'solicitud', 'trámite'],
    },
    {
        'question': '¿Cómo hablo con un asesor?',
        'answer': 'Puedes solicitar un asesor desde este chat. Conservaremos tu pregunta y el historial para que no tengas que explicar nuevamente el caso.',
        'category': 'Atención',
        'intent': 'contactar_asesor',
        'tags': ['asesor', 'ayuda', 'persona', 'atención'],
    },
]

ARTICLES = [
    {
        'title': 'Guía de matrícula académica',
        'summary': 'Pasos generales para revisar fechas, requisitos y pago de matrícula.',
        'content': 'Consulta el calendario académico, verifica los requisitos de tu programa, completa el proceso de matrícula y realiza el pago dentro de la fecha límite. Guarda el comprobante.',
        'category': 'Matrícula',
        'intent': 'consultar_matricula',
        'tags': ['matrícula', 'requisitos', 'pago', 'fechas', 'semestre'],
    },
    {
        'title': 'Calendario académico institucional',
        'summary': 'El calendario reúne las fechas principales de cada periodo académico.',
        'content': 'El calendario académico incluye inscripción, matrícula, inicio de clases, cancelaciones, evaluaciones y cierre del periodo. Consulta siempre la versión vigente publicada por la institución.',
        'category': 'Calendario académico',
        'intent': 'consultar_calendario',
        'tags': ['calendario', 'periodo', 'fechas', 'clases'],
    },
]


def _manager(model):
    return getattr(model, 'objects')


class Command(BaseCommand):
    help = 'Carga categorías, intenciones, FAQ y artículos iniciales sin borrar información existente.'

    def handle(self, *args, **options):
        categories = {}
        for name, description in CATEGORIES.items():
            category, _ = _manager(Category).update_or_create(
                name=name,
                defaults={'description': description, 'is_active': True},
            )
            categories[name] = category

        intents = {}
        for name, description in INTENTS.items():
            intent, _ = _manager(Intent).update_or_create(
                name=name,
                defaults={'description': description, 'is_active': True},
            )
            intents[name] = intent

        for item in FAQS:
            _manager(FAQ).update_or_create(
                question=item['question'],
                defaults={
                    'answer': item['answer'],
                    'category': categories[item['category']],
                    'intent': intents[item['intent']],
                    'is_active': True,
                    'order': 0,
                },
            )

        for item in ARTICLES:
            article, _ = _manager(KnowledgeArticle).update_or_create(
                title=item['title'],
                defaults={
                    'summary': item['summary'],
                    'content': item['content'],
                    'category': categories[item['category']],
                    'intent': intents[item['intent']],
                    'tags': item['tags'],
                    'status': 'published',
                    'published': True,
                },
            )
            article.save()

        success_style = getattr(self.style, 'SUCCESS')
        self.stdout.write(success_style(
            f'Base cargada: {len(categories)} categorías, {len(intents)} intenciones, '
            f'{len(FAQS)} FAQ y {len(ARTICLES)} artículos.'
        ))