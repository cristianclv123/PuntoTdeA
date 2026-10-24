"""Contactos por audiencia para la UI de /campanas/.

Regresión: la acción usaba ``get_paginated_response`` sin tener paginación
configurada, por lo que devolvía HTTP 500 y la página de Audiencias mostraba
"No fue posible cargar los contactos".
"""

from io import BytesIO

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from openpyxl import Workbook

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

        payload = response.json()
        self.assertEqual(payload["count"], 1)
        self.assertIsNone(payload["next"])
        self.assertIsNone(payload["previous"])
        self.assertEqual(len(payload["results"]), 1)
        self.assertEqual(payload["results"][0]["full_name"], "Camila Test")

    def test_contacts_endpoint_without_contacts_returns_empty_list(self):
        empty = AudienceSegment.objects.create(name="Vacía")

        response = self.client.get(
            f"/campanas/api/segments/{empty.id}/contacts/"
        )

        self.assertEqual(response.status_code, 200)

        payload = response.json()
        self.assertEqual(payload["count"], 0)
        self.assertEqual(payload["results"], [])
        self.assertIsNone(payload["next"])
        self.assertIsNone(payload["previous"])


@override_settings(ALLOWED_HOSTS=["testserver"])
class SegmentImportNameValidationTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user(
            username="importar_segmentos",
            password="test-password",
            is_staff=True,
        )
        self.client.force_login(user)
        AudienceSegment.objects.create(name="Aspirantes")

    @staticmethod
    def _excel_file():
        workbook = Workbook()
        sheet = workbook.active
        sheet.append(["Documento identidad", "Nombre", "Celular", "Email"])
        sheet.append(["12345", "Ana Pérez", "3001112233", "ana@example.com"])
        content = BytesIO()
        workbook.save(content)
        return SimpleUploadedFile(
            "audiencia.xlsx",
            content.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    def _import(self, name):
        return self.client.post(
            "/campanas/api/segments/import_excel/",
            {"name": name, "file": self._excel_file()},
        )

    def test_rejects_existing_name_ignoring_outer_spaces_and_case(self):
        response = self._import("  aSpIrAnTeS  ")

        self.assertEqual(response.status_code, 400)
        self.assertIn("Ya existe una audiencia con ese nombre", str(response.json()["name"]))
        self.assertEqual(AudienceSegment.objects.count(), 1)

    def test_accepts_unique_name_and_stores_it_trimmed(self):
        response = self._import("  Nueva audiencia  ")

        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.json()["segment"]["name"], "Nueva audiencia")
        self.assertEqual(AudienceSegment.objects.count(), 2)