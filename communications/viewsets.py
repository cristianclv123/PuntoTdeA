# API interna (consumida solo por el BFF)
from django.db.models import Q
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response

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


class AudienceSegmentViewSet(viewsets.ModelViewSet):
    queryset = AudienceSegment.objects.all()
    serializer_class = AudienceSegmentSerializer
    permission_classes = [IsInternalService]

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

    @action(detail=True, methods=["get"])
    def recipients(self, request, pk=None):
        campaign = self.get_object()
        page = self.paginate_queryset(campaign.recipients.select_related("contact").all())
        serializer = BroadcastRecipientSerializer(page, many=True)
        return self.get_paginated_response(serializer.data)