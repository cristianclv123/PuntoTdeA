from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from cases.models import Channel, Contact, Conversation, Department, Message


DEMO_CHATS = [
    {
        "document": "DEMO-1001",
        "full_name": "Laura Mendoza",
        "email": "laura.mendoza@estudiante.tdea.edu.co",
        "phone": "3001112233",
        "program": "Ingeniería de Software",
        "semester": 5,
        "theme": "Matrícula",
        "priority": Conversation.Priority.ALTA,
        "status": Conversation.Status.PENDIENTE,
        "unassigned": True,
        "department": "admisiones",
        "minutes_ago": 12,
        "messages": [
            ("inbound", "Hola, ¿hasta cuándo puedo matricularme este semestre?"),
            ("inbound", "También necesito saber el costo de derechos pecuniarios."),
        ],
    },
    {
        "document": "DEMO-1002",
        "full_name": "Carlos Restrepo",
        "email": "carlos.restrepo@estudiante.tdea.edu.co",
        "phone": "3014445566",
        "program": "Administración de Empresas",
        "semester": 3,
        "theme": "Certificados",
        "priority": Conversation.Priority.MEDIA,
        "status": Conversation.Status.PENDIENTE,
        "unassigned": False,
        "department": "registro",
        "minutes_ago": 45,
        "messages": [
            ("inbound", "Buenas tardes, quiero solicitar un certificado de notas."),
            ("outbound", "Con gusto. ¿Lo necesitas digital o físico?"),
            ("inbound", "Digital, por favor."),
        ],
    },
    {
        "document": "DEMO-1003",
        "full_name": "Valentina Gómez",
        "email": "valentina.gomez@aspirante.tdea.edu.co",
        "phone": "3027778899",
        "program": "Aspirante — Psicología",
        "semester": 1,
        "theme": "Admisiones",
        "priority": Conversation.Priority.URGENTE,
        "status": Conversation.Status.PENDIENTE,
        "unassigned": True,
        "department": "admisiones",
        "minutes_ago": 5,
        "messages": [
            ("inbound", "Hola, soy aspirante. ¿Cuál es la fecha del examen de admisión?"),
        ],
    },
    {
        "document": "DEMO-1004",
        "full_name": "Andrés Quintero",
        "email": "andres.quintero@egresado.tdea.edu.co",
        "phone": "3102223344",
        "program": "Egresado — Contaduría",
        "semester": 10,
        "theme": "Grados",
        "priority": Conversation.Priority.MEDIA,
        "status": Conversation.Status.ESCALADO,
        "unassigned": False,
        "department": "registro",
        "escalated": "registro",
        "minutes_ago": 120,
        "messages": [
            ("inbound", "Necesito información sobre la ceremonia de grados."),
            ("outbound", "Voy a escalar tu caso a Registro académico."),
            ("inbound", "Perfecto, quedo atento."),
        ],
    },
    {
        "document": "DEMO-1005",
        "full_name": "María Fernanda López",
        "email": "mf.lopez@estudiante.tdea.edu.co",
        "phone": "3155556677",
        "program": "Derecho",
        "semester": 7,
        "theme": "Bienestar",
        "priority": Conversation.Priority.BAJA,
        "status": Conversation.Status.COMPLETADO,
        "unassigned": False,
        "department": "bienestar",
        "minutes_ago": 180,
        "messages": [
            ("inbound", "¿Cómo agendo cita con psicología de bienestar?"),
            ("outbound", "Puedes hacerlo desde el portal de Bienestar o te ayudo a coordinar."),
            ("inbound", "Ya lo hice, muchas gracias."),
            ("outbound", "Con gusto. Quedo atento si necesitas algo más."),
        ],
    },
    {
        "document": "DEMO-1006",
        "full_name": "Julián Castro",
        "email": "julian.castro@estudiante.tdea.edu.co",
        "phone": "3208889900",
        "program": "Diseño Gráfico",
        "semester": 2,
        "theme": "Biblioteca",
        "priority": Conversation.Priority.MEDIA,
        "status": Conversation.Status.PENDIENTE,
        "unassigned": True,
        "department": "biblioteca",
        "minutes_ago": 28,
        "messages": [
            ("inbound", "Hola, ¿pueden renovar un préstamo de libro por WhatsApp?"),
            ("inbound", "El código es BIB-2024-8841."),
        ],
    },
]


class Command(BaseCommand):
    help = "Crea conversaciones de ejemplo por WhatsApp con mensajes (idempotente por documento DEMO-*)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Elimina chats DEMO-* existentes y los vuelve a crear.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        channel, _ = Channel.objects.get_or_create(
            code=Channel.Code.WHATSAPP,
            defaults={"name": "WhatsApp", "is_active": True},
        )
        User = get_user_model()
        advisor = (
            User.objects.filter(username="asesor").first()
            or User.objects.filter(is_staff=True).first()
            or User.objects.filter(is_active=True).first()
        )

        if options["reset"]:
            docs = [item["document"] for item in DEMO_CHATS]
            Conversation.objects.filter(contact__document_number__in=docs).delete()
            Contact.objects.filter(document_number__in=docs).delete()
            self.stdout.write("Chats DEMO anteriores eliminados.")

        created_count = 0
        skipped = 0
        now = timezone.now()

        for item in DEMO_CHATS:
            contact, contact_created = Contact.objects.update_or_create(
                document_number=item["document"],
                defaults={
                    "full_name": item["full_name"],
                    "email": item["email"],
                    "phone": item["phone"],
                    "academic_program": item["program"],
                    "semester": item["semester"],
                },
            )
            existing = Conversation.objects.filter(
                contact=contact,
                channel=channel,
                external_thread_id=f"demo-wa-{item['document']}",
            ).first()
            if existing and not options["reset"]:
                skipped += 1
                continue

            dept = None
            if item.get("department"):
                dept = Department.objects.filter(code=item["department"]).first()
            escalated = None
            if item.get("escalated"):
                escalated = Department.objects.filter(code=item["escalated"]).first()

            last_at = now - timedelta(minutes=item["minutes_ago"])
            conversation = Conversation.objects.create(
                channel=channel,
                contact=contact,
                external_thread_id=f"demo-wa-{item['document']}",
                status=item["status"],
                priority=item["priority"],
                department=dept,
                escalated_to=escalated,
                theme=item["theme"],
                assigned_to=None if item["unassigned"] else advisor,
                last_message_at=last_at,
            )

            for idx, (direction, body) in enumerate(item["messages"]):
                sent_at = last_at - timedelta(minutes=max(len(item["messages"]) - idx - 1, 0) * 3)
                Message.objects.create(
                    conversation=conversation,
                    direction=direction,
                    body=body,
                    external_id=f"demo-{item['document']}-m{idx + 1}",
                    sent_at=sent_at,
                )

            created_count += 1
            owner = "cola" if item["unassigned"] else (advisor.username if advisor else "sin asesor")
            self.stdout.write(
                f"  · {conversation.ticket_number} — {contact.full_name} ({owner})"
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Listo: {created_count} chats creados, {skipped} ya existían."
            )
        )
