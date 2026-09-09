import math
import re
from typing import Any

from django.conf import settings
from django.core.cache import cache
from django.utils.text import slugify

from knowledge.models import FAQ, KnowledgeArticle


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", ' ', (text or '')).strip()


def _tokenize(text: str):
    text = _normalize_text(text).lower()
    return [token for token in re.findall(r"[a-záéíóúüñ0-9]+", text) if len(token) > 2]


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


def search_knowledge(query: str, limit: int | None = None):
    if not query:
        return []

    limit = limit or settings.KNOWLEDGE_SETTINGS.get('MAX_RESULTS', 5)
    cache_key = f"knowledge:search:{slugify(query)[:40]}:{limit}"

    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    articles = KnowledgeArticle.objects.filter(status='published', published=True).select_related('category', 'intent')
    results = []
    for article in articles:
        score = _cosine_similarity(query, article.indexable_text)
        if score <= 0:
            continue
        results.append({
            'id': article.id,
            'title': article.title,
            'summary': article.summary,
            'content': article.content[:250],
            'category': article.category.name if article.category else 'General',
            'score': round(score, 4),
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


def _find_faq_matches(query: str):
    tokens = set(_tokenize(query))
    matches = []
    for faq in FAQ.objects.filter(is_active=True):
        faq_text = ' '.join([faq.question, faq.answer])
        faq_tokens = set(_tokenize(faq_text))
        overlap = len(tokens & faq_tokens)
        if overlap:
            matches.append({'question': faq.question, 'answer': faq.answer, 'score': overlap})
    matches.sort(key=lambda item: item['score'], reverse=True)
    return matches[:3]


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
        best_result = results[0]
        confidence = evaluate_confidence(question, best_result)
        answer = best_result.get('summary') or best_result.get('content') or 'No encontré una respuesta formulada.'
        return {
            'answer': answer,
            'confidence': confidence,
            'needs_human_attention': confidence < settings.KNOWLEDGE_SETTINGS.get('MIN_CONFIDENCE', 0.7),
            'sources': results,
        }

    faq_matches = _find_faq_matches(question)
    if faq_matches:
        top_faq = faq_matches[0]
        confidence = min(0.92, 0.5 + (top_faq['score'] * 0.1))
        return {
            'answer': top_faq['answer'],
            'confidence': round(confidence, 4),
            'needs_human_attention': confidence < settings.KNOWLEDGE_SETTINGS.get('MIN_CONFIDENCE', 0.7),
            'sources': faq_matches,
        }

    return {
        'answer': 'No encontré información suficiente en la base de conocimiento para responder con alta confianza. Se puede derivar el caso a atención humana.',
        'confidence': 0.0,
        'needs_human_attention': True,
        'sources': [],
    }
