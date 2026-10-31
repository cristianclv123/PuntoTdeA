from PuntoTdeA.access import module_access_required
from .permissions import COMMUNICATIONS_PERMISSION, user_has_explicit_permission


communications_required = module_access_required(
    COMMUNICATIONS_PERMISSION,
    module_name="Communications",
)
communications_api_required = module_access_required(
    COMMUNICATIONS_PERMISSION,
    api=True,
    staff_only=True,
    module_name="Communications",
)
communications_staff_required = module_access_required(
    COMMUNICATIONS_PERMISSION,
    staff_only=True,
    module_name="Communications",
)
