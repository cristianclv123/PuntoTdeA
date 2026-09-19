"""Configuración y evaluación del horario de atención."""

from dataclasses import dataclass
from datetime import datetime, time

from django.conf import settings
from django.utils import timezone


@dataclass(frozen=True)
class BusinessSchedule:
    weekdays: frozenset[int] = frozenset({0, 1, 2, 3, 4})
    opening_time: time = time(8, 0)
    closing_time: time = time(17, 0)

    def is_open(self, current_time: datetime | None = None) -> bool:
        current_time = current_time or timezone.localtime()
        if timezone.is_aware(current_time):
            current_time = timezone.localtime(current_time)
        else:
            current_time = timezone.make_aware(current_time)
        return (
            current_time.weekday() in self.weekdays
            and self.opening_time <= current_time.time() < self.closing_time
        )


def get_business_schedule() -> BusinessSchedule:
    configured = getattr(settings, 'KNOWLEDGE_CHATBOT_SETTINGS', {})
    return BusinessSchedule(
        weekdays=frozenset(configured.get('BUSINESS_DAYS', {0, 1, 2, 3, 4})),
        opening_time=configured.get('BUSINESS_START', time(8, 0)),
        closing_time=configured.get('BUSINESS_END', time(17, 0)),
    )