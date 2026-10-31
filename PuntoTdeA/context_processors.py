from PuntoTdeA.access import user_has_explicit_permission


def module_access(request):
    user = getattr(request, "user", None)
    if user is None or not getattr(user, "is_authenticated", False):
        return {
            "can_access_announcements": False,
            "can_access_cases": False,
            "can_access_communications": False,
            "can_access_knowledge": False,
        }

    return {
        "can_access_announcements": user_has_explicit_permission(
            user,
            "announcements.access_announcements",
        ),
        "can_access_cases": user_has_explicit_permission(
            user,
            "cases.access_cases",
        ),
        "can_access_communications": user_has_explicit_permission(
            user,
            "communications.access_communications",
        ),
        "can_access_knowledge": user_has_explicit_permission(
            user,
            "knowledge.access_knowledge",
        ),
    }
