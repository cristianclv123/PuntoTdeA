from PuntoTdeA.access import HasModulePermission


CASES_PERMISSION = "cases.access_cases"


class HasCasesAccess(HasModulePermission):
    permission_name = CASES_PERMISSION
