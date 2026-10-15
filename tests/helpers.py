"""Fábricas compartidas para la suite `tests/`."""

from django.contrib.auth import get_user_model

from cases.models import Channel, Contact, Conversation, Department
from communications.adapters.base import SendResult

User = get_user_model()


def make_user(username, *, staff=False, first_name="", last_name="", password="secret123"):
    return User.objects.create_user(
        username=username,
        password=password,
        email=f"{username}@tdea.edu.co",
        first_name=first_name,
        last_name=last_name,
        is_staff=staff,
    )


def make_contact(document, *, phone="573001000000", name="Estudiante Prueba"):
    return Contact.objects.create(
        full_name=name,
        document_number=document,
        email=f"{document.lower()}@tdea.edu.co",
        phone=phone,
        academic_program="Sistemas",
        semester=3,
    )


def make_conversation(*, document="DOC-T-1", phone="573001000000", channel="whatsapp", **kwargs):
    ch = Channel.objects.get(code=channel)
    contact = kwargs.pop("contact", None) or make_contact(document, phone=phone)
    defaults = {
        "channel": ch,
        "contact": contact,
        "external_thread_id": kwargs.pop("external_thread_id", f"{channel}-{document}"),
        "status": Conversation.Status.PENDIENTE,
    }
    defaults.update(kwargs)
    return Conversation.objects.create(**defaults)


def department():
    return Department.objects.get(code="registro_academico")


def meta_ok(wamid="wamid.test"):
    return SendResult(success=True, provider_message_id=wamid)


def meta_fail(error="Meta rechazó"):
    return SendResult(success=False, error=error)
