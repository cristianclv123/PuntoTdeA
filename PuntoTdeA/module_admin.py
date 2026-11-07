"""Bases de Django Admin que aplican los permisos de acceso modular."""

from django.contrib import admin

from PuntoTdeA.access import user_has_explicit_permission


MODULE_PERMISSION_BY_APP = {
    "announcements": "announcements.access_announcements",
    "cases": "cases.access_cases",
    "communications": "communications.access_communications",
    "knowledge": "knowledge.access_knowledge",
}


class ModuleAccessAdminMixin:
    """Combina el permiso modular con los permisos estándar del Admin."""

    def _has_module_access(self, request):
        permission_name = MODULE_PERMISSION_BY_APP.get(self.model._meta.app_label)
        return permission_name is None or user_has_explicit_permission(
            request.user,
            permission_name,
        )

    def _module_and_standard_permission(self, method_name, request, *args, **kwargs):
        if not self._has_module_access(request):
            return False
        standard_check = getattr(super(), method_name, None)
        return standard_check(*args, **kwargs) if standard_check else True

    def has_module_permission(self, request):
        return self._module_and_standard_permission(
            "has_module_permission",
            request,
            request,
        )

    def has_view_permission(self, request, *args, **kwargs):
        return self._module_and_standard_permission(
            "has_view_permission",
            request,
            request,
            *args,
            **kwargs,
        )

    def has_add_permission(self, request, *args, **kwargs):
        return self._module_and_standard_permission(
            "has_add_permission",
            request,
            request,
            *args,
            **kwargs,
        )

    def has_change_permission(self, request, *args, **kwargs):
        return self._module_and_standard_permission(
            "has_change_permission",
            request,
            request,
            *args,
            **kwargs,
        )

    def has_delete_permission(self, request, *args, **kwargs):
        return self._module_and_standard_permission(
            "has_delete_permission",
            request,
            request,
            *args,
            **kwargs,
        )


class ModuleAccessModelAdmin(ModuleAccessAdminMixin, admin.ModelAdmin):
    pass


class ModuleAccessTabularInline(ModuleAccessAdminMixin, admin.TabularInline):
    pass
