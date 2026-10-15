from django.core.management.base import BaseCommand

from knowledge.chatbot.whatsapp import close_inactive_whatsapp_conversations


class Command(BaseCommand):
    help = 'Cierra conversaciones de WhatsApp inactivas durante cinco minutos.'

    def handle(self, *args, **options):
        closed_count = close_inactive_whatsapp_conversations()
        self.stdout.write(f'Conversaciones de WhatsApp cerradas por inactividad: {closed_count}')
