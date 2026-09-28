import openpyxl
import xlrd
from django.contrib import messages
from django.db import transaction
from django.shortcuts import redirect, render

from .models import AudienceSegment, Contact, SegmentMembership


def campaigns(request):
    return render(request, "communications/campaigns.html")


def campaign_new(request):
    return render(request, "communications/campaign_new.html")


def campaign_detail(request):
    return render(request, "communications/campaign_detail.html")


def segments(request):
    return render(request, "communications/segments.html")


def interactions(request):
    return render(request, "communications/interactions.html")


def upload_segment_excel(request):
    if request.method == "POST":
        excel_file = request.FILES.get("file")
        nombre_segmento = request.POST.get(
            "nombre_segmento", "Segmento Importado"
        )

        if not excel_file:
            messages.error(request, "Por favor, selecciona un archivo Excel.")
            return redirect("communications:campaign_new")

        file_name = excel_file.name.lower()
        if not file_name.endswith((".xlsx", ".xls")):
            messages.error(
                request,
                "El archivo debe tener una extensión válida (.xlsx o .xls).",
            )
            return redirect("communications:campaign_new")

        try:
            contactos_procesados = []

            if file_name.endswith(".xlsx"):
                workbook = openpyxl.load_workbook(excel_file, data_only=True)
                sheet = workbook.active

                for row in sheet.iter_rows(min_row=2, values_only=True):
                    if not any(row):
                        continue

                    documento = str(row[0]).strip() if row[0] is not None else ""
                    nombre = str(row[1]).strip() if row[1] is not None else ""
                    telefono = str(row[2]).strip() if row[2] is not None else ""
                    correo = str(row[3]).strip() if len(row) > 3 and row[3] is not None else ""
                    programa = str(row[4]).strip() if len(row) > 4 and row[4] is not None else ""
                    semestre = str(row[5]).strip() if len(row) > 5 and row[5] is not None else ""

                    if not documento or not telefono:
                        continue

                    contactos_procesados.append({
                        "documento": documento,
                        "nombre": nombre,
                        "telefono": telefono,
                        "correo": correo,
                        "programa": programa,
                        "semestre": semestre,
                    })

            elif file_name.endswith(".xls"):
                workbook = xlrd.open_workbook(file_contents=excel_file.read())
                sheet = workbook.sheet_by_index(0)

                for row_idx in range(1, sheet.nrows):
                    row = sheet.row_values(row_idx)
                    if not any(row):
                        continue

                    documento = str(row[0]).strip() if row[0] is not None else ""
                    nombre = str(row[1]).strip() if row[1] is not None else ""
                    telefono = str(row[2]).strip() if row[2] is not None else ""
                    correo = str(row[3]).strip() if len(row) > 3 and row[3] is not None else ""
                    programa = str(row[4]).strip() if len(row) > 4 and row[4] is not None else ""
                    semestre = str(row[5]).strip() if len(row) > 5 and row[5] is not None else ""

                    if not documento or not telefono:
                        continue

                    contactos_procesados.append({
                        "documento": documento,
                        "nombre": nombre,
                        "telefono": telefono,
                        "correo": correo,
                        "programa": programa,
                        "semestre": semestre,
                    })

            if not contactos_procesados:
                messages.warning(
                    request,
                    "No se encontraron contactos válidos en el archivo.",
                )
                return redirect("communications:campaign_new")

            with transaction.atomic():
                segmento = AudienceSegment.objects.create(
                    name=nombre_segmento,
                    description=f"Importado desde Excel: {excel_file.name}",
                    source_type=AudienceSegment.SourceType.EXCEL_IMPORT,
                )

                contactos_guardados = []
                for datos in contactos_procesados:
                    contacto, _ = Contact.objects.update_or_create(
                        document_number=datos["documento"],
                        defaults={
                            "full_name": datos["nombre"],
                            "phone": datos["telefono"],
                            "email": datos["correo"],
                            "academic_program": datos["programa"],
                            "semester": datos["semestre"],
                            "source": "excel_campus",
                        },
                    )
                    contactos_guardados.append(contacto)

                memberships = [
                    SegmentMembership(segment=segmento, contact=contacto)
                    for contacto in contactos_guardados
                ]
                SegmentMembership.objects.bulk_create(
                    memberships, ignore_conflicts=True
                )

            messages.success(
                request,
                f"Segmento '{segmento.name}' creado con {len(contactos_guardados)} contactos exitosamente.",
            )
            return redirect("communications:segments")

        except Exception as e:
            messages.error(
                request, f"Ocurrió un error al procesar el archivo: {str(e)}"
            )
            return redirect("communications:campaign_new")

    return redirect("communications:campaign_new")