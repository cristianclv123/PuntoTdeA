from __future__ import annotations

from django.utils.text import slugify

from ..models import Category, FAQ, Intent, KnowledgeArticle

ACADEMIC_CALENDAR_ITEMS = [
    {
        'title': 'Matrícula y pago de semestre',
        'summary': 'Información sobre fechas de matrícula, pago y requisitos del semestre académico.',
        'content': 'Para matricularse en el semestre, el estudiante debe revisar el calendario académico institucional, confirmar la disponibilidad del programa, completar el registro y pagar la matrícula antes de la fecha límite.',
        'tags': ['matrícula', 'pago', 'semestre'],
    },
    {
        'title': 'Fecha límite de retiro académico',
        'summary': 'Plazo para solicitar retiro o cancelación del semestre.',
        'content': 'El retiro académico debe gestionarse antes de la fecha indicada por la institución. El estudiante debe verificar el calendario institucional y seguir los procedimientos del programa.',
        'tags': ['retiro', 'académico', 'calendario'],
    },
    {
        'title': 'Inscripción a programas',
        'summary': 'Requisitos y proceso de inscripción para programas de formación.',
        'content': 'La inscripción al programa se realiza de acuerdo con los plazos del calendario académico y la disponibilidad de cupos. Los estudiantes deben revisar requisitos, documentación y fechas.',
        'tags': ['inscripción', 'programa', 'cupos'],
    },
]


def ensure_academic_defaults():
    category, _ = getattr(Category, 'objects').get_or_create(
        name='Académico',
        defaults={'description': 'Información institucional sobre calendario, matrículas, programas y trámites académicos.'},
    )
    intent, _ = getattr(Intent, 'objects').get_or_create(
        name='matricula',
        defaults={
            'description': 'Consultas relacionadas con matrículas, calendario y procesos de admisión.',
            'confidence_threshold': 0.75,
        },
    )
    return category, intent


def index_academic_calendar():
    category, intent = ensure_academic_defaults()
    created_count = 0
    updated_count = 0

    for item in ACADEMIC_CALENDAR_ITEMS:
        _, created = getattr(KnowledgeArticle, 'objects').update_or_create(
            slug=slugify(item['title']),
            defaults={
                'title': item['title'],
                'summary': item['summary'],
                'content': item['content'],
                'category': category,
                'intent': intent,
                'tags': item['tags'],
                'published': True,
                'status': 'published',
                'embedding': [],
            },
        )
        if created:
            created_count += 1
        else:
            updated_count += 1

    faq_items = [
        (
            '¿Cuándo se realiza la matrícula?',
            'La matrícula se realiza dentro del calendario académico institucional y se debe revisar la fecha establecida por el programa.',
        ),
        (
            '¿Dónde consulto el calendario académico?',
            'El calendario se publica en la plataforma institucional y en la información oficial del programa.',
        ),
    ]

    for index, (question, answer) in enumerate(faq_items):
        getattr(FAQ, 'objects').update_or_create(
            question=question,
            defaults={
                'answer': answer,
                'category': category,
                'intent': intent,
                'is_active': True,
                'order': index,
            },
        )

    return {'created': created_count, 'updated': updated_count, 'items': len(ACADEMIC_CALENDAR_ITEMS)}
