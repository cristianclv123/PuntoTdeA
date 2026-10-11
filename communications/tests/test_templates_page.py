from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

User = get_user_model()


class TemplatesPageTests(TestCase):
    """La página de plantillas es un módulo independiente (no cuelga de
    Campañas) que lista los borradores locales y las plantillas de Meta."""

    def test_requires_login(self):
        response = self.client.get(reverse("plantillas"))

        self.assertEqual(response.status_code, 302)
        self.assertIn("login", response.url)

    def test_renders_standalone_template_page(self):
        user = User.objects.create_user(username="tpl-user", password="secret")
        self.client.force_login(user)

        response = self.client.get(reverse("plantillas"))

        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn('id="templateList"', content)
        self.assertIn('id="newTemplateBtn"', content)
        self.assertIn("initTemplatesPage", content)
        # No debe estar envuelta en la barra de pestañas de Campañas.
        self.assertNotIn("outbound-tabs", content)

    def test_renders_template_filters(self):
        user = User.objects.create_user(username="tpl-filter", password="secret")
        self.client.force_login(user)

        response = self.client.get(reverse("plantillas"))

        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn('id="templatesFilterTabs"', content)
        self.assertIn('data-filter="all"', content)
        self.assertIn('data-filter="draft"', content)
        self.assertIn('data-filter="meta"', content)
        self.assertIn('id="templateStatusFilters"', content)

    def test_campaigns_link_points_to_standalone_page(self):
        user = User.objects.create_user(username="tpl-user-2", password="secret")
        self.client.force_login(user)

        response = self.client.get(reverse("communications:campaigns"))

        self.assertEqual(response.status_code, 200)
        self.assertIn(reverse("plantillas"), response.content.decode())
