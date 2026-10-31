from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse


class CampaignPagesTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user(
            username="campaign-pages-user"
        )
        user.user_permissions.add(
            Permission.objects.get(
                content_type__app_label="communications",
                codename="access_communications",
            )
        )
        self.client.force_login(user)

    def test_audiences_page_is_available(self):
        response = self.client.get("/campanas/audiencias/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="segmentsGrid"')
        self.assertContains(response, 'id="audiencesStatus"')


    def test_removed_interactions_page_returns_not_found(self):
        response = self.client.get("/campanas/interacciones/")

        self.assertEqual(response.status_code, 404)

    def test_campaign_list_is_the_campaign_management_page(self):
        response = self.client.get(reverse("communications:campaigns"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="campaignsList"')
        self.assertContains(
            response,
            reverse("communications:campaign_new"),
        )
        self.assertContains(
            response,
            f'href="{reverse("plantillas")}"',
        )
        self.assertContains(response, "Gestionar plantillas")
        self.assertNotContains(response, "/campanas/audiencias/")
        self.assertNotContains(response, "/campanas/interacciones/")

    def test_campaign_wizard_keeps_segment_and_template_selectors(self):
        response = self.client.get(reverse("communications:campaign_new"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="campaignAudiencePicker"')
        self.assertContains(response, 'data-audience-picker')
        self.assertContains(response, 'data-api-base="/campanas/api"')
        self.assertContains(response, 'id="templateGrid"')
        self.assertContains(response, "OutboundUI.initWizard()")

        content = response.content.decode()
        template_step = (
            content.split('data-pane="2"', 1)[1]
            .split('data-pane="3"', 1)[0]
        )

        self.assertIn('href="/plantillas/"', template_step)
        self.assertIn("Gestionar plantillas", template_step)
        self.assertNotContains(response, 'id="includeSegments"')
        self.assertNotContains(response, 'id="excludeSegments"')
