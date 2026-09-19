from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from django.core.cache import cache

from .models import Category, FAQ, Intent, KnowledgeArticle


@receiver(post_save, sender=KnowledgeArticle)
@receiver(post_delete, sender=KnowledgeArticle)
@receiver(post_save, sender=FAQ)
@receiver(post_delete, sender=FAQ)
@receiver(post_save, sender=Category)
@receiver(post_delete, sender=Category)
@receiver(post_save, sender=Intent)
@receiver(post_delete, sender=Intent)
def invalidate_knowledge_cache(**_kwargs):
    try:
        cache.clear()
    except (ConnectionError, OSError, RuntimeError, ValueError):
        pass
