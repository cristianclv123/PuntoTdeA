from PuntoTdeA.access import HasModulePermission


KNOWLEDGE_PERMISSION = "knowledge.access_knowledge"


class HasKnowledgeAccess(HasModulePermission):
    permission_name = KNOWLEDGE_PERMISSION
