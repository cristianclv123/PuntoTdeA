from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from unittest.mock import patch

from cases.models import Channel, Contact, Conversation
from PuntoTdeA.module_admin import MODULE_PERMISSION_BY_APP


User = get_user_model()
PROTECTED_APP_LABELS = tuple(MODULE_PERMISSION_BY_APP)


def protected_admin_models():
    return [
        model
        for model in admin.site._registry
        if model._meta.app_label in PROTECTED_APP_LABELS
    ]


def model_permission(model, action):
    return Permission.objects.get(
        content_type=ContentType.objects.get_for_model(model),
        codename=f"{action}_{model._meta.model_name}",
    )


def module_permission(app_label):
    _permission_app, codename = MODULE_PERMISSION_BY_APP[app_label].split(".", 1)
    return Permission.objects.get(
        content_type__app_label=app_label,
        codename=codename,
    )


class ModuleAdminAccessTests(TestCase):
    def setUp(self):
        self.models = protected_admin_models()
        self.urls = {
            model: reverse(
                f"admin:{model._meta.app_label}_{model._meta.model_name}_changelist"
            )
            for model in self.models
        }

    def _staff_with_model_view_permissions(self, username):
        user = User.objects.create_user(
            username=username,
            password="test-password",
            is_staff=True,
        )
        user.user_permissions.add(
            *(model_permission(model, "view") for model in self.models)
        )
        return user

    def test_superuser_can_access_all_module_admins_and_shared_auth_admin(self):
        user = User.objects.create_superuser(
            username="module-admin-superuser",
            email="admin@example.com",
            password="test-password",
        )
        self.client.force_login(user)

        for model, url in self.urls.items():
            with self.subTest(model=model):
                self.assertEqual(self.client.get(url).status_code, 200)

        self.assertEqual(
            self.client.get(reverse("admin:auth_user_changelist")).status_code,
            200,
        )
        self.assertEqual(
            self.client.get(reverse("admin:auth_group_changelist")).status_code,
            200,
        )

    def test_standard_model_permissions_without_module_permission_are_denied(self):
        user = self._staff_with_model_view_permissions("module-admin-no-module")
        self.client.force_login(user)

        for model, url in self.urls.items():
            with self.subTest(model=model):
                self.assertEqual(self.client.get(url).status_code, 403)

    def test_direct_module_permissions_and_standard_model_permissions_allow_access(self):
        user = self._staff_with_model_view_permissions("module-admin-direct")
        user.user_permissions.add(
            *(module_permission(app_label) for app_label in PROTECTED_APP_LABELS)
        )
        self.client.force_login(user)

        for model, url in self.urls.items():
            with self.subTest(model=model):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_group_module_permissions_and_standard_model_permissions_allow_access(self):
        user = self._staff_with_model_view_permissions("module-admin-group")
        group = Group.objects.create(name="all-module-admin-access")
        group.permissions.add(
            *(module_permission(app_label) for app_label in PROTECTED_APP_LABELS)
        )
        user.groups.add(group)
        self.client.force_login(user)

        for model, url in self.urls.items():
            with self.subTest(model=model):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_one_module_permission_does_not_authorize_other_module_admins(self):
        user = self._staff_with_model_view_permissions("module-admin-isolation")
        user.user_permissions.add(module_permission("announcements"))
        self.client.force_login(user)

        for model, url in self.urls.items():
            expected = 200 if model._meta.app_label == "announcements" else 403
            with self.subTest(model=model):
                self.assertEqual(self.client.get(url).status_code, expected)

    def test_module_permission_does_not_replace_standard_model_permission(self):
        user = User.objects.create_user(
            username="module-admin-standard-permission",
            password="test-password",
            is_staff=True,
        )
        user.user_permissions.add(module_permission("cases"))
        self.client.force_login(user)

        case_model_url = next(
            url
            for model, url in self.urls.items()
            if model._meta.app_label == "cases"
        )
        self.assertEqual(self.client.get(case_model_url).status_code, 403)

    def test_shared_user_and_group_admin_keep_standard_administration_permissions(self):
        user = User.objects.create_user(
            username="shared-admin-operator",
            password="test-password",
            is_staff=True,
        )
        auth_permissions = Permission.objects.filter(
            content_type__app_label="auth",
            codename__in={
                "view_user",
                "add_user",
                "change_user",
                "view_group",
                "add_group",
                "change_group",
            },
        )
        user.user_permissions.add(*auth_permissions)
        group = Group.objects.create(name="editable-group")
        self.client.force_login(user)

        self.assertEqual(
            self.client.get(reverse("admin:auth_user_changelist")).status_code,
            200,
        )
        self.assertEqual(
            self.client.get(reverse("admin:auth_group_changelist")).status_code,
            200,
        )
        permission_form = self.client.get(
            reverse("admin:auth_group_change", args=[group.pk])
        )
        self.assertEqual(permission_form.status_code, 200)
        self.assertContains(permission_form, 'id="id_permissions"')


class DashboardAndPublicHomeAccessTests(TestCase):
    def test_authenticated_user_without_module_permissions_gets_empty_dashboard_shell(self):
        user = User.objects.create_user(
            username="dashboard-no-module-access",
            password="test-password",
        )
        self.client.force_login(user)

        response = self.client.get(reverse("dashboard:index"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("dashboard:index"))
        self.assertNotContains(response, "Casos abiertos")
        self.assertNotContains(response, "Campañas WhatsApp")

    @patch("dashboard.views.dashboard_service.recent_activity", return_value=[])
    @patch("dashboard.views.dashboard_service.recent_campaigns", return_value=[])
    @patch("dashboard.views.dashboard_service.campaign_kpis")
    @patch("dashboard.views._advisor_workload", return_value=[])
    @patch("dashboard.views._case_metrics")
    def test_dashboard_panels_follow_the_module_permissions(
        self,
        case_metrics,
        _advisor_workload,
        campaign_kpis,
        _recent_campaigns,
        _recent_activity,
    ):
        case_metrics.return_value = [
            {"label": "CASE_METRIC_PRIVATE", "value": "1", "sub": "", "icon": "inbox", "bg": "", "fg": ""}
        ]
        campaign_kpis.return_value = [
            {"label": "CAMPAIGN_METRIC_PRIVATE", "value": "1", "sub": ""}
        ]
        user = User.objects.create_user(
            username="dashboard-case-only",
            password="test-password",
        )
        user.user_permissions.add(module_permission("cases"))
        self.client.force_login(user)

        response = self.client.get(reverse("dashboard:index"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "CASE_METRIC_PRIVATE")
        self.assertNotContains(response, "CAMPAIGN_METRIC_PRIVATE")
        case_metrics.assert_called_once()
        campaign_kpis.assert_not_called()

    @patch("dashboard.views.dashboard_service.recent_activity", return_value=[])
    @patch("dashboard.views.dashboard_service.recent_campaigns", return_value=[])
    @patch("dashboard.views.dashboard_service.campaign_kpis", return_value=[])
    @patch("dashboard.views._advisor_workload", return_value=[])
    @patch("dashboard.views._case_metrics", return_value=[])
    def test_active_superuser_sees_all_dashboard_panels(self, *unused_mocks):
        user = User.objects.create_superuser(
            username="dashboard-superuser",
            email="dashboard-superuser@example.com",
            password="test-password",
        )
        self.client.force_login(user)

        response = self.client.get(reverse("dashboard:index"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Cola WhatsApp")
        self.assertContains(response, "Campañas WhatsApp")

    def test_public_home_keeps_aggregate_counts_without_contact_details(self):
        contact = Contact.objects.create(
            full_name="Dato Personal No Mostrar",
            document_number="DOC-PUBLIC-COUNT",
            email="private@example.com",
            phone="573001234567",
            semester="5",
        )
        channel = Channel.objects.get(code="whatsapp")
        Conversation.objects.create(
            channel=channel,
            contact=contact,
            external_thread_id="public-home-open-count",
        )
        closed = Conversation.objects.create(
            channel=channel,
            contact=contact,
            external_thread_id="public-home-closed-count",
            status=Conversation.Status.CERRADO,
            closed_at=timezone.now(),
        )
        self.assertIsNotNone(closed.pk)

        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["stats"]["open_cases"], 1)
        self.assertEqual(response.context["stats"]["closed_today"], 1)
        self.assertNotContains(response, contact.full_name)
        self.assertNotContains(response, contact.document_number)
        self.assertNotContains(response, contact.email)
        self.assertNotContains(response, contact.phone)
