from django.contrib.auth import get_user_model
from django.templatetags.static import static
from django.test import TestCase
from django.urls import reverse

User = get_user_model()


class CampaignWizardPageTests(TestCase):
    """Página de nueva campaña: usa el selector de audiencia compartido."""

    def test_requires_login(self):
        response = self.client.get(reverse("communications:campaign_new"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("login", response.url)

    def test_campaign_new_renders_audience_picker(self):
        user = User.objects.create_user(username="camp", password="secret")
        self.client.force_login(user)

        response = self.client.get(reverse("communications:campaign_new"))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("campaignAudiencePicker", content)
        self.assertIn('id="personalizationFile"', content)
        self.assertIn('id="inspectPersonalizationFile"', content)
        self.assertIn('id="validatePersonalization"', content)
        self.assertIn('id="confirmPartialSend"', content)
        # Con DEBUG=false whitenoise sirve el asset con hash en el nombre; se
        # compara contra la ruta real del manifest, no contra el nombre literal.
        self.assertIn(static("js/audience-picker.js"), content)
        # No debe renderizar el input de archivo inline ni chips de segmentos.
        self.assertNotIn('id="loadRecipientsFileBtn"', content)
        self.assertNotIn('id="recipientsFileInput"', content)
        self.assertNotIn('id="includeSegments"', content)
        self.assertNotIn('id="excludeSegments"', content)
        # El asistente ya no pide "Tipo" ni "Cuenta de envío": el modelo de
        # campaña no tiene esos campos, así que eran solo decorativos.
        self.assertNotIn('id="campaignType"', content)
        self.assertNotIn('id="senderAccount"', content)
