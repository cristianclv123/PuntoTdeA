import math
import re
import unicodedata
from typing import Any

from django.conf import settings
from django.core.cache import cache
from django.db import models
from django.utils.text import slugify
from django.utils import timezone

from .. import models as knowledge_models


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", ' ', (text or '')).strip()


def _tokenize(text: str):
    text = unicodedata.normalize('NFKD', _normalize_text(text).lower())
    text = ''.join(character for character in text if not unicodedata.combining(character))
    stopwords = {
        'para', 'como', 'donde', 'cuando', 'quien', 'cual', 'cuanto', 'esta',
        'este', 'estos', 'estas', 'una', 'uno', 'unos', 'unas', 'los', 'las',
        'del', 'por', 'con', 'que', 'hay', 'son', 'sobre', 'puedo', 'necesito',
    }
    return [
        token for token in re.findall(r"[a-z0-9]+", text)
        if len(token) > 2 and token not in stopwords
    ]


def _vectorize(text: str):
    tokens = _tokenize(text)
    vector: dict[str, int] = {}
    for token in tokens:
        vector[token] = vector.get(token, 0) + 1
    return vector


def _cosine_similarity(left: str, right: str) -> float:
    left_vector = _vectorize(left)
    right_vector = _vectorize(right)
    if not left_vector or not right_vector:
        return 0.0

    common_terms = set(left_vector) & set(right_vector)
    if not common_terms:
        return 0.0

    numerator = sum(left_vector[token] * right_vector[token] for token in common_terms)
    left_norm = math.sqrt(sum(value * value for value in left_vector.values()))
    right_norm = math.sqrt(sum(value * value for value in right_vector.values()))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return numerator / (left_norm * right_norm)


def _relevance_score(query: str, title: str, body: str) -> float:
    query_tokens = set(_tokenize(query))
    if not query_tokens:
        return 0.0

    title_tokens = set(_tokenize(title))
    body_tokens = set(_tokenize(body))
    title_overlap = len(query_tokens & title_tokens) / len(query_tokens)
    body_overlap = len(query_tokens & body_tokens) / len(query_tokens)
    phrase_boost = 0.15 if _normalize_text(query).lower() in _normalize_text(body).lower() else 0.0
    cosine = _cosine_similarity(query, f'{title} {body}')
    return min(1.0, (title_overlap * 0.55) + (body_overlap * 0.25) + (cosine * 0.2) + phrase_boost)


def search_knowledge(query: str, limit: int | None = None):
    if not query:
        return []

    limit = limit or settings.KNOWLEDGE_SETTINGS.get('MAX_RESULTS', 5)
    cache_key = f"knowledge:search:{slugify(query)[:40]}:{limit}"

    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    articles = getattr(knowledge_models.KnowledgeArticle, 'objects').filter(
        status='published', published=True
    ).select_related('category', 'intent')
    results = []
    for article in articles:
        score = _relevance_score(query, article.title, article.indexable_text)
        if score <= 0:
            continue
        results.append({
            'id': article.id,
            'title': article.title,
            'summary': article.summary,
            'content': article.content[:250],
            'category': article.category.name if article.category else 'General',
            'score': round(score, 4),
            'source_type': 'article',
        })

    now = timezone.now()
    faq_queryset = getattr(knowledge_models.FAQ, 'objects').filter(
        is_active=True,
    ).filter(
        models.Q(valid_from__isnull=True) | models.Q(valid_from__lte=now),
    ).filter(
        models.Q(valid_until__isnull=True) | models.Q(valid_until__gte=now),
    ).select_related('category', 'intent')
    for faq in faq_queryset:
        score = _relevance_score(query, faq.question, f'{faq.question} {faq.answer}')
        if score <= 0:
            continue
        results.append({
            'id': faq.id,
            'title': faq.question,
            'summary': faq.answer,
            'content': faq.answer[:250],
            'category': faq.category.name if faq.category else 'General',
            'score': round(score, 4),
            'source_type': 'faq',
            'image_url': faq.image.url if faq.image else None,
        })

    results.sort(key=lambda item: item['score'], reverse=True)
    results = results[:limit]
    cache.set(cache_key, results, timeout=300)
    return results


def evaluate_confidence(query: str, result: dict[str, Any] | None) -> float:
    if not result:
        return 0.0

    base_score = float(result.get('score', 0.0))
    query_terms = _tokenize(query)
    result_text = ' '.join(filter(None, [result.get('title', ''), result.get('summary', ''), result.get('content', '')]))
    matched_terms = set(_tokenize(result_text)) & set(query_terms)
    boost = min(0.35, len(matched_terms) * 0.05)
    return round(min(1.0, max(0.0, base_score + boost)), 4)


def answer_query(question: str) -> dict[str, Any]:
    question = (question or '').strip()
    if not question:
        return {
            'answer': 'No recibí una pregunta para responder.',
            'confidence': 0.0,
            'needs_human_attention': True,
            'sources': [],
        }

    results = search_knowledge(question, limit=5)
    if results:
        faq_results = [result for result in results if result.get('source_type') == 'faq']
        best_result = faq_results[0] if faq_results else results[0]
        confidence = evaluate_confidence(question, best_result)
        answer = best_result.get('summary') or best_result.get('content') or 'No encontré una respuesta formulada.'
        return {
            'answer': answer,
            'confidence': confidence,
            'needs_human_attention': confidence < settings.KNOWLEDGE_SETTINGS.get('MIN_CONFIDENCE', 0.7),
            'sources': results,
        }

    return {
        'answer': 'No encontré información suficiente en la base de conocimiento para responder con alta confianza. Se puede derivar el caso a atención humana.',
        'confidence': 0.0,
        'needs_human_attention': True,
        'sources': [],
    }
