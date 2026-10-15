"""Contactos por audiencia para la UI de /campanas/.

Regresión: la acción usaba ``get_paginated_response`` sin tener paginación
configurada, por lo que devolvía HTTP 500 y la página de Audiencias mostraba
"No fue posible cargar los contactos".
"""

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from communications.models import AudienceSegment, Contact, SegmentMembership


@override_settings(ALLOWED_HOSTS=["testserver"])
class SegmentContactsApiTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user(
            username="segmentos", password="clave-prueba", is_staff=True
        )
        self.client.force_login(user)
        self.segment = AudienceSegment.objects.create(name="Aspirantes")
        self.contact = Contact.objects.create(
            full_name="Camila Test",
            document_number="CC-SEG-1",
            phone="573001112233",
        )
        SegmentMembership.objects.create(segment=self.segment, contact=self.contact)

    def test_contacts_endpoint_returns_contacts(self):
        response = self.client.get(
            f"/campanas/api/segments/{self.segment.id}/contacts/"
        )
        self.assertEqual(response.status_code, 200)
        contacts = response.json()
        self.assertEqual(len(contacts), 1)
        self.assertEqual(contacts[0]["full_name"], "Camila Test")

    def test_contacts_endpoint_without_contacts_returns_empty_list(self):
        empty = AudienceSegment.objects.create(name="Vacía")
        response = self.client.get(f"/campanas/api/segments/{empty.id}/contacts/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])
