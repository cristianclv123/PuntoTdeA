from django.test import TestCase

from notifications.models import Notification
from notifications.services import notify


class NotificationEstadoTests(TestCase):
    def test_nivel_por_defecto_es_info(self):
        item = notify(
            module=Notification.Module.CASES,
            event="chat.new",
            title="Llegó un nuevo chat",
        )
        self.assertEqual(item.level, Notification.Level.INFO)
        self.assertFalse(item.reads.exists())
