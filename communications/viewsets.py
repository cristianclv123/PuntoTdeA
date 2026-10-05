# API interna (consumida solo por el BFF)
from django.conf import settings
from django.db.models import Q
from django.db.models.deletion import ProtectedError
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

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
from .services import campaign_service, segmentation_service
from .services.test_send_registry import record_test_send


class TestSendRequestSerializer(serializers.Serializer):
    template = serializers.IntegerField(min_value=1)
    params = serializers.JSONField(required=False, default=dict)

    def validate_params(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("Los parámetros deben ser un objeto JSON.")
        return value


class TestSendAPIView(APIView):
    permission_classes = [IsInternalService]
    parser_classes = [JSONParser]

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

        template = MessageTemplate.objects.filter(pk=payload.validated_data["template"]).first()
        if template is None:
            return Response(
                {"success": False, "message": "La plantilla indicada no existe."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if template.status != MessageTemplate.Status.APPROVED:
            return Response(
                {
                    "success": False,
                    "message": "La plantilla debe estar aprobada por Meta para enviar una prueba.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

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
                f"{template.meta_template_name} {payload.validated_data['params']}",
            )

        return Response(
            {
                "success": True,
                "message": "Mensaje de prueba enviado correctamente.",
                "provider_message_id": result.provider_message_id,
            },
            status=status.HTTP_200_OK,
        )


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


class MessageTemplateViewSet(viewsets.ModelViewSet):
    queryset = MessageTemplate.objects.all()
    serializer_class = MessageTemplateSerializer
    permission_classes = [IsInternalService]

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        try:
            instance.delete()
        except ProtectedError:
            return Response(
                {
                    "detail": "No se puede eliminar esta plantilla porque está siendo utilizada por una campaña."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)


class AudienceSegmentViewSet(viewsets.ModelViewSet):
    queryset = AudienceSegment.objects.all()
    serializer_class = AudienceSegmentSerializer
    permission_classes = [IsInternalService]

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
        page = self.paginate_queryset(segment.contacts.all())
        serializer = ContactSerializer(page, many=True)
        return self.get_paginated_response(serializer.data)


class CampaignViewSet(viewsets.ModelViewSet):
    queryset = Campaign.objects.select_related("template", "segment").all()
    serializer_class = CampaignSerializer
    permission_classes = [IsInternalService]

    def perform_create(self, serializer):
        scheduled_at = serializer.validated_data.get("scheduled_at")
        initial_status = Campaign.Status.SCHEDULED if scheduled_at else Campaign.Status.DRAFT
        serializer.save(status=initial_status)

    @action(detail=True, methods=["post"])
    def send(self, request, pk=None):
        """HU-06: dispara el envío ahora mismo (síncrono, vía MockAdapter por ahora)."""
        campaign = self.get_object()
        if campaign.status not in (Campaign.Status.DRAFT, Campaign.Status.SCHEDULED):
            return Response(
                {"detail": f"No se puede enviar una campaña en estado '{campaign.status}'."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        campaign_service.send_campaign(campaign)
        campaign.refresh_from_db()
        return Response(self.get_serializer(campaign).data)

    @action(detail=True, methods=["post"])
    def pause(self, request, pk=None):
        campaign = campaign_service.pause_campaign(self.get_object())
        return Response(self.get_serializer(campaign).data)

    @action(detail=True, methods=["post"])
    def resume(self, request, pk=None):
        campaign = campaign_service.resume_campaign(self.get_object())
        return Response(self.get_serializer(campaign).data)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        campaign = campaign_service.cancel_campaign(self.get_object())
        return Response(self.get_serializer(campaign).data)

    @extend_schema(responses=BroadcastRecipientSerializer(many=True))
    @action(detail=True, methods=["get"])
    def recipients(self, request, pk=None):
        campaign = self.get_object()
        page = self.paginate_queryset(campaign.recipients.select_related("contact").all())
        serializer = BroadcastRecipientSerializer(page, many=True)
        return self.get_paginated_response(serializer.data)