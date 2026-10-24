# API interna (consumida solo por el BFF)
from django.conf import settings
from django.db.models import Q
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.pagination import PageNumberPagination

from .adapters.meta_adapter import MetaAdapter
from .models import AudienceSegment, BroadcastRecipient, Campaign, Contact, MessageTemplate
from .permissions import IsInternalService
from .serializers import (
    AudienceSegmentSerializer,
    BroadcastRecipientSerializer,
    CampaignSerializer,
    ContactSerializer,
    MessageTemplateSerializer,
    SegmentImportSerializer,
)
from .services import campaign_service, meta_templates, segmentation_service
from .services import campaign_personalization_service
from .services.test_send_registry import record_test_send


class TestSendRequestSerializer(serializers.Serializer):
    # El id de la plantilla es el que asigna Meta (string), no una fila local.
    template = serializers.CharField(max_length=64)
    params = serializers.JSONField(required=False, default=dict)

    def validate_params(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("Los parámetros deben ser un objeto JSON.")
        return value


class PersonalizationInspectSerializer(serializers.Serializer):
    file = serializers.FileField()


class PersonalizationValidateSerializer(serializers.Serializer):
    file = serializers.FileField()
    segment = serializers.PrimaryKeyRelatedField(queryset=AudienceSegment.objects.all())
    template = serializers.CharField(max_length=64)
    template_name = serializers.CharField(max_length=150)
    template_language = serializers.CharField(max_length=10, default="es_CO")
    template_snapshot = serializers.JSONField()
    default_params = serializers.JSONField(required=False, default=dict)
    document_column = serializers.IntegerField(min_value=0)
    variable_mappings = serializers.JSONField()

    def validate_template_snapshot(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("La copia de la plantilla debe ser un objeto JSON.")
        return value

    def validate_default_params(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("Los parámetros generales deben ser un objeto JSON.")
        return value

    def validate_variable_mappings(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("El mapeo de variables debe ser un objeto JSON.")
        return value


INTERNAL_AUTH = [{"cookieAuth": []}, {"internalToken": []}]

_test_send_error = inline_serializer(
    name="TestSendError",
    fields={
        "success": serializers.BooleanField(),
        "message": serializers.CharField(),
        "errors": serializers.DictField(required=False),
    },
)


class TestSendAPIView(APIView):
    permission_classes = [IsInternalService]
    parser_classes = [JSONParser]

    @extend_schema(
        summary="Enviar plantilla de prueba",
        description=(
            "Envía una plantilla aprobada por Meta al número de pruebas "
            "configurado en `WHATSAPP_TEST_RECIPIENT`."
        ),
        request=TestSendRequestSerializer,
        responses={
            200: inline_serializer(
                name="TestSendResponse",
                fields={
                    "success": serializers.BooleanField(),
                    "message": serializers.CharField(),
                    "provider_message_id": serializers.CharField(allow_null=True),
                },
            ),
            400: _test_send_error,
            404: _test_send_error,
            502: _test_send_error,
            503: _test_send_error,
        },
        auth=INTERNAL_AUTH,
    )
    def post(self, request):
        payload = TestSendRequestSerializer(data=request.data)
        if not payload.is_valid():
            return Response(
                {"success": False, "message": "La solicitud no es válida.", "errors": payload.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        test_recipient = settings.WHATSAPP_TEST_RECIPIENT
        if not test_recipient:
            return Response(
                {
                    "success": False,
                    "message": "No está configurado el destinatario de pruebas de WhatsApp.",
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        meta_id = payload.validated_data["template"]
        fetched = meta_templates.get_template(meta_id)
        if not fetched.ok or not fetched.template:
            http_status = (
                status.HTTP_502_BAD_GATEWAY
                if fetched.kind == meta_templates.KIND_META
                else status.HTTP_404_NOT_FOUND
            )
            return Response(
                {
                    "success": False,
                    "message": fetched.message or "La plantilla indicada no existe.",
                },
                status=http_status,
            )
        if fetched.template.get("status") != "APPROVED":
            return Response(
                {
                    "success": False,
                    "message": "La plantilla debe estar aprobada por Meta para enviar una prueba.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        template = meta_templates.to_template_ref(fetched.template)
        result = MetaAdapter().send_template_message(
            test_recipient,
            template,
            payload.validated_data["params"],
        )
        if not result.success:
            return Response(
                {
                    "success": False,
                    "message": result.error or "Meta no pudo enviar el mensaje de prueba.",
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )

        if result.provider_message_id:
            record_test_send(
                test_recipient,
                result.provider_message_id,
                "test_template",
                f"{template.name} {payload.validated_data['params']}",
            )

        return Response(
            {
                "success": True,
                "message": "Mensaje de prueba enviado correctamente.",
                "provider_message_id": result.provider_message_id,
            },
            status=status.HTTP_200_OK,
        )


@extend_schema(auth=INTERNAL_AUTH)
class ContactViewSet(viewsets.ReadOnlyModelViewSet):
    """Solo lectura: los contactos se crean vía importación de Excel o desde
    otros módulos (Backend CRUD), no directamente desde esta API."""

    queryset = Contact.objects.all()
    serializer_class = ContactSerializer
    permission_classes = [IsInternalService]

    def get_queryset(self):
        qs = super().get_queryset()
        search = self.request.query_params.get("search")
        if search:
            qs = qs.filter(
                Q(full_name__icontains=search)
                | Q(phone__icontains=search)
                | Q(document_number__icontains=search)
                | Q(email__icontains=search)
            )
        return qs


@extend_schema(auth=INTERNAL_AUTH)
class MessageTemplateViewSet(viewsets.ModelViewSet):
    """Borradores locales de plantilla (aún no enviadas a Meta).

    La base local solo guarda trabajo en progreso. Al enviar un borrador a Meta
    y recibir respuesta correcta, el borrador se elimina: la plantilla pasa a
    vivir únicamente en Meta.
    """

    queryset = MessageTemplate.objects.all()
    serializer_class = MessageTemplateSerializer
    permission_classes = [IsInternalService]

    @extend_schema(request=None)
    @action(detail=True, methods=["post"], url_path="enviar-a-meta")
    def enviar_a_meta(self, request, pk=None):
        """POST /api/templates/{id}/enviar-a-meta/: crea la plantilla en Meta.

        Si Meta la acepta, el borrador local se elimina.
        """
        draft = self.get_object()
        result = meta_templates.create_from_draft(draft)
        payload = {
            "success": result.ok,
            "message": result.message,
            "meta_id": result.meta_id,
            "meta_status": result.meta_status,
        }
        if result.ok:
            payload["meta_name"] = meta_templates.slugify_meta_name(draft.name)
            draft.delete()
            return Response(payload, status=status.HTTP_200_OK)

        http_status = {
            meta_templates.KIND_CONFIG: status.HTTP_503_SERVICE_UNAVAILABLE,
            meta_templates.KIND_BUILD: status.HTTP_400_BAD_REQUEST,
        }.get(result.kind, status.HTTP_502_BAD_GATEWAY)
        return Response(payload, status=http_status)


class MetaTemplateListView(APIView):
    """GET /api/templates/meta/: lista las plantillas reales de la cuenta de Meta."""

    permission_classes = [IsInternalService]

    def get(self, request):
        result = meta_templates.list_templates()
        if not result.ok:
            http_status = (
                status.HTTP_503_SERVICE_UNAVAILABLE
                if result.kind == meta_templates.KIND_CONFIG
                else status.HTTP_502_BAD_GATEWAY
            )
            return Response(
                {"success": False, "message": result.message, "templates": []},
                status=http_status,
            )
        return Response({"success": True, "templates": result.templates})


class MetaTemplateDetailView(APIView):
    """GET/POST/DELETE de una plantilla concreta en Meta."""

    permission_classes = [IsInternalService]

    def _error_status(self, kind):
        return {
            meta_templates.KIND_CONFIG: status.HTTP_503_SERVICE_UNAVAILABLE,
            meta_templates.KIND_BUILD: status.HTTP_400_BAD_REQUEST,
        }.get(kind, status.HTTP_502_BAD_GATEWAY)

    def get(self, request, meta_id):
        result = meta_templates.get_template(meta_id)
        if not result.ok:
            return Response(
                {"success": False, "message": result.message},
                status=self._error_status(result.kind),
            )
        return Response({"success": True, "template": result.template})

    def post(self, request, meta_id):
        """Edita el cuerpo de una plantilla existente en Meta."""
        body_text = request.data.get("body_text")
        if not isinstance(body_text, str) or not body_text.strip():
            return Response(
                {"success": False, "message": "El cuerpo de la plantilla es obligatorio."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        result = meta_templates.edit_template(
            meta_id,
            body_text,
            request.data.get("variable_types") or {},
            request.data.get("buttons") or [],
            request.data.get("header_type") or "none",
            request.data.get("header_text") or "",
        )
        if not result.ok:
            return Response(
                {"success": False, "message": result.message},
                status=self._error_status(result.kind),
            )
        return Response(
            {
                "success": True,
                "message": result.message,
                "meta_id": result.meta_id,
                "meta_status": result.meta_status,
            }
        )

    def delete(self, request, meta_id):
        result = meta_templates.delete_template(
            meta_id, request.query_params.get("name", "")
        )
        if not result.ok:
            return Response(
                {"success": False, "message": result.message},
                status=self._error_status(result.kind),
            )
        return Response({"success": True, "message": result.message})

class CommunicationsPagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = "page_size"
    max_page_size = 100

@extend_schema(auth=INTERNAL_AUTH)
class AudienceSegmentViewSet(viewsets.ModelViewSet):
    queryset = AudienceSegment.objects.all()
    serializer_class = AudienceSegmentSerializer
    permission_classes = [IsInternalService]
    pagination_class = CommunicationsPagination

    @extend_schema(
        request=SegmentImportSerializer,
        responses=inline_serializer(
            name="SegmentImportResponse",
            fields={
                "segment": AudienceSegmentSerializer(),
                "created": serializers.IntegerField(),
                "updated": serializers.IntegerField(),
                "skipped": serializers.IntegerField(),
                "errors": serializers.ListField(child=serializers.CharField()),
            },
        ),
    )
    @action(detail=False, methods=["post"], parser_classes=[MultiPartParser, FormParser])
    def import_excel(self, request):
        """POST /api/segments/import_excel/  (multipart: name, description?, file)

        T-06.3: crea un AudienceSegment a partir de un Excel exportado de Campus.
        """
        payload = SegmentImportSerializer(data=request.data)
        payload.is_valid(raise_exception=True)

        segment, result = segmentation_service.import_segment_from_excel(
            file_obj=payload.validated_data["file"],
            segment_name=payload.validated_data["name"],
            description=payload.validated_data.get("description", ""),
        )
        return Response(
            {
                "segment": AudienceSegmentSerializer(segment).data,
                "created": result.created,
                "updated": result.updated,
                "skipped": result.skipped,
                "errors": result.errors,
            },
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(responses=ContactSerializer(many=True))
    @action(detail=True, methods=["get"])
    def contacts(self, request, pk=None):
        segment = self.get_object()
        queryset = segment.contacts.all().order_by("pk")
        page = self.paginate_queryset(queryset)
        if page is not None:
            return self.get_paginated_response(ContactSerializer(page, many=True).data)
        return Response(ContactSerializer(queryset, many=True).data)


@extend_schema(auth=INTERNAL_AUTH)
class CampaignViewSet(viewsets.ModelViewSet):
    queryset = Campaign.objects.select_related("segment").all()
    serializer_class = CampaignSerializer
    permission_classes = [IsInternalService]
    pagination_class = CommunicationsPagination

    @extend_schema(
        summary="Inspeccionar columnas de un Excel de personalización",
        request=PersonalizationInspectSerializer,
        responses={200: serializers.ListField(child=serializers.DictField())},
        auth=INTERNAL_AUTH,
    )
    @action(
        detail=False,
        methods=["post"],
        url_path="personalization/inspect",
        parser_classes=[MultiPartParser, FormParser],
    )
    def personalization_inspect(self, request):
        payload = PersonalizationInspectSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        columns = campaign_personalization_service.inspect_columns(
            payload.validated_data["file"]
        )
        return Response({"columns": columns})

    @extend_schema(
        summary="Validar un Excel de personalización",
        request=PersonalizationValidateSerializer,
        responses={201: serializers.DictField()},
        auth=INTERNAL_AUTH,
    )
    @action(
        detail=False,
        methods=["post"],
        url_path="personalization/validate",
        parser_classes=[MultiPartParser, FormParser],
    )
    def personalization_validate(self, request):
        payload = PersonalizationValidateSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data
        campaign_data = {
            "segment": data["segment"],
            "template_meta_id": data["template"],
            "template_name": data["template_name"],
            "template_language": data["template_language"],
            "template_snapshot": data["template_snapshot"],
            "default_params": data["default_params"],
        }
        _, report = campaign_personalization_service.validate_personalization(
            file_obj=data["file"],
            segment=data["segment"],
            campaign_data=campaign_data,
            document_column=data["document_column"],
            variable_mappings=data["variable_mappings"],
        )
        return Response(report, status=status.HTTP_201_CREATED)

    def perform_create(self, serializer):
        scheduled_at = serializer.validated_data.get("scheduled_at")
        initial_status = Campaign.Status.SCHEDULED if scheduled_at else Campaign.Status.DRAFT
        serializer.save(status=initial_status)
        from notifications.events import notify_campaign
        from notifications.models import Notification

        campaign = serializer.instance
        notify_campaign(
            "Se creó una campaña",
            campaign.name,
            event="campaign.created",
            level=Notification.Level.INFO,
            campaign_id=campaign.id,
        )

    @extend_schema(
        summary="Enviar campaña ahora",
        description="Dispara el envío síncrono por Meta. Solo para campañas en borrador o programadas.",
        request=None,
        responses=CampaignSerializer,
    )
    @action(detail=True, methods=["post"])
    def send(self, request, pk=None):
        """HU-06: dispara el envío ahora mismo (síncrono, vía MetaAdapter)."""
        campaign = self.get_object()
        if campaign.status not in (Campaign.Status.DRAFT, Campaign.Status.SCHEDULED):
            return Response(
                {"detail": f"No se puede enviar una campaña en estado '{campaign.status}'."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            campaign_service.send_campaign(campaign)
        except campaign_service.CampaignSendError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        campaign.refresh_from_db()
        return Response(self.get_serializer(campaign).data)

    @extend_schema(summary="Pausar campaña", request=None, responses=CampaignSerializer)
    @action(detail=True, methods=["post"])
    def pause(self, request, pk=None):
        campaign = campaign_service.pause_campaign(self.get_object())
        return Response(self.get_serializer(campaign).data)

    @extend_schema(summary="Reanudar campaña", request=None, responses=CampaignSerializer)
    @action(detail=True, methods=["post"])
    def resume(self, request, pk=None):
        campaign = campaign_service.resume_campaign(self.get_object())
        return Response(self.get_serializer(campaign).data)

    @extend_schema(summary="Cancelar campaña", request=None, responses=CampaignSerializer)
    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        campaign = campaign_service.cancel_campaign(self.get_object())
        return Response(self.get_serializer(campaign).data)

    @extend_schema(responses=BroadcastRecipientSerializer(many=True))
    @action(detail=True, methods=["get"])
    def recipients(self, request, pk=None):
        campaign = self.get_object()
        queryset = campaign.recipients.select_related("contact").all()
        page = self.paginate_queryset(queryset)
        if page is not None:
            return self.get_paginated_response(
                BroadcastRecipientSerializer(page, many=True).data
            )
        return Response(BroadcastRecipientSerializer(queryset, many=True).data)