"""Contactos por audiencia para la UI de /campanas/.

Regresión: la acción usaba ``get_paginated_response`` sin tener paginación
configurada, por lo que devolvía HTTP 500 y la página de Audiencias mostraba
"No fue posible cargar los contactos".
"""

from io import BytesIO

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
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
        permission = Permission.objects.get(
            content_type__app_label="communications",
            codename="access_communications",
        )
        user.user_permissions.add(permission)
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
        permission = Permission.objects.get(
            content_type__app_label="communications",
            codename="access_communications",
        )
        user.user_permissions.add(permission)
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


class AnnouncementSegmentReadOnlyAccessTests(TestCase):
    def setUp(self):
        self.permission = Permission.objects.get(
            content_type__app_label="announcements",
            codename="access_announcements",
        )
        self.segment = AudienceSegment.objects.create(
            name="Avisos",
            description="Descripción privada de campaña",
            filter_rules={"document_number": "DOC-INTERNO"},
        )
        self.contact = Contact.objects.create(
            full_name="Contacto de prueba",
            document_number="DOC-PREVIEW-1",
            email="contacto@example.com",
            phone="573001112233",
            academic_program="Sistemas",
            semester="5",
            attributes={"internal_note": "No exponer"},
            source="excel_campus",
        )
        SegmentMembership.objects.create(segment=self.segment, contact=self.contact)

    def _login_with_announcement_permission(self, *, via_group=False, is_staff=False):
        user = get_user_model().objects.create_user(
            username=f"announcement-segment-{Group.objects.count()}-{via_group}",
            password="test-password",
            is_staff=is_staff,
        )
        if via_group:
            group = Group.objects.create(name=f"announcements-{Group.objects.count()}")
            group.permissions.add(self.permission)
            user.groups.add(group)
        else:
            user.user_permissions.add(self.permission)
        self.client.force_login(user)
        return user

    def test_announcement_permission_lists_only_picker_fields(self):
        self._login_with_announcement_permission()

        response = self.client.get("/campanas/api/segments/")

        self.assertEqual(response.status_code, 200)
        segment = response.json()["results"][0]
        self.assertEqual(
            set(segment),
            {"id", "name", "contact_count"},
        )
        self.assertEqual(segment["name"], "Avisos")
        self.assertEqual(segment["contact_count"], 1)

    def test_announcement_permission_previews_only_widget_contact_fields(self):
        self._login_with_announcement_permission(via_group=True)

        response = self.client.get(
            f"/campanas/api/segments/{self.segment.pk}/contacts/"
        )

        self.assertEqual(response.status_code, 200)
        contact = response.json()["results"][0]
        self.assertEqual(
            set(contact),
            {
                "full_name",
                "document_number",
                "phone",
                "email",
                "academic_program",
                "semester",
                "role",
                "whatsapp_opt_in",
                "source",
            },
        )
        self.assertEqual(contact["full_name"], "Contacto de prueba")
        self.assertNotIn("attributes", contact)
        self.assertNotIn("id", contact)

    def test_announcement_permission_cannot_read_details_or_mutate_segments(self):
        self._login_with_announcement_permission()
        detail_url = f"/campanas/api/segments/{self.segment.pk}/"

        self.assertEqual(self.client.get(detail_url).status_code, 403)
        self.assertEqual(
            self.client.post("/campanas/api/segments/", {"name": "Nueva"}).status_code,
            403,
        )
        self.assertEqual(
            self.client.patch(detail_url, {"name": "Cambiada"}, content_type="application/json").status_code,
            403,
        )
        self.assertEqual(self.client.delete(detail_url).status_code, 403)
        self.assertEqual(
            self.client.post(
                "/campanas/api/segments/import_excel/",
                {"name": "Importada"},
            ).status_code,
            403,
        )

    def test_staff_without_either_module_permission_cannot_list_or_preview(self):
        user = get_user_model().objects.create_user(
            username="segment-reader-no-permissions",
            password="test-password",
            is_staff=True,
        )
        self.client.force_login(user)

        self.assertEqual(self.client.get("/campanas/api/segments/").status_code, 403)
        self.assertEqual(
            self.client.get(
                f"/campanas/api/segments/{self.segment.pk}/contacts/"
            ).status_code,
            403,
        )
