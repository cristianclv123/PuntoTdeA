from django.core.management.base import BaseCommand
from knowledge.models import Category, Intent, FAQ

class Command(BaseCommand):
    help = 'Importa las preguntas frecuentes institucionales a la base de datos'

    def handle(self, *args, **options):
        # 1. Crear o asegurar una categoría e intent por defecto para agruparlas
        category, _ = Category.objects.get_or_create(
            name='Información Institucional',
            defaults={
                'description': 'Preguntas frecuentes generales y de admisiones del TdeA.',
                'is_active': True
            }
        )

        intent, _ = Intent.objects.get_or_create(
            name='Consulta General TdeA',
            defaults={
                'description': 'Intención genérica para consultas institucionales y admisiones.',
                'confidence_threshold': 0.75,
                'is_active': True
            }
        )

        # 2. Definir la lista de FAQs extraídas del documento
        faqs_data = [
            {
                "question": "Reglamento estudiantil",
                "answer": "Puedes consultar el reglamento estudiantil en el siguiente enlace: https://tdea.edu.co/wp-content/uploads/2025/06/ReglamentoEstudiantilGeneral2022_compressed-1.pdf"
            },
            {
                "question": "¿Cuáles son las direcciones de las sedes?",
                "answer": "Sede principal: Calle 78B No. 72A – 220 Medellín - Robledo.\nCampus Universitario TdeA Aburrá Sur: Carrera 63 No. 38 – 100."
            },
            {
                "question": "¿Cuál es el horario de atención de las sedes?",
                "answer": "• Medellín - Robledo: Lunes a jueves de 8am a 12m y de 1pm a 5:30pm; viernes de 8am a 12m y de 1pm a 4pm.\n• Campus Universitario TdeA Aburrá Sur: Lunes a jueves de 8am a 12m y de 1pm a 7:30pm; viernes de 8am a 12m y de 1pm a 7pm."
            },
            {
                "question": "¿Cuál es la oferta académica?",
                "answer": "En el siguiente enlace podrás encontrar las facultades y dando clic en cada una encontrarás los programas ofertados: https://tdea.edu.co/facultades/"
            },
            {
                "question": "¿Cuáles son las jornadas disponibles?",
                "answer": "• DIURNA: Lunes a sábado de 6:00 a.m. a 6:00 p.m.\n• MIXTA: Lunes a viernes de 6:00 a.m. a 8:00 a.m. y de 6:00 p.m. a 10:00 p.m. y sábado de 6:00 a.m. a 10:00 p.m.\n• 2D: Viernes 12:00 m. a 10:00 p.m. y sábado de 6:00 a.m. a 10:00 p.m.\n• VIRTUAL: De lunes a sábado de 6:00 a.m. a 10:00 p.m. (según programación académica)."
            },
            {
                "question": "¿Cuáles son los requisitos de inscripción para pregrado?",
                "answer": "• Resultados de las pruebas SABER 11 (Obligatorio).\n• Documento de identidad por ambos lados (Obligatorio).\n• Acta o Diploma de Bachiller (con convalidación del MEN si el título es del exterior) (Obligatorio).\n• Cuenta de servicios públicos o predial de los últimos tres meses donde sea legible el estrato y dirección (Obligatorio)."
            },
            {
                "question": "¿Cuáles son los requisitos de inscripción para extranjeros?",
                "answer": "Se exige documento de identidad (Cédula de extranjería vigente, Pasaporte vigente o PPT para venezolanos), permiso de estudio / visa vigente o PPT, título de bachiller con convalidación del Ministerio de Educación de Colombia (o examen ICFES de validación) y resultados de pruebas ICFES o examen equivalente homologado en el exterior."
            },
            {
                "question": "¿Cuál es el valor de la inscripción?",
                "answer": "El valor es de $17,400. NOTA: En caso de no continuar con el proceso de inscripción, el valor pagado NO es reembolsable."
            },
            {
                "question": "¿Qué debe hacer un aspirante próximo a grados de bachiller?",
                "answer": "Deben pedir en su institución un certificado que acredite la terminación de asignaturas y fecha de graduación (sirve temporalmente como reemplazo del acta de grado). Se recomienda tener todo listo para subir la documentación y realizar el pago en cuanto salgan los resultados del ICFES."
            },
            {
                "question": "El aspirante se equivoca de programa o jornada y ya realizó el pago",
                "answer": "El valor de la inscripción no es reembolsable ni transferible. Si desea cambiar su aspiración, esta debe ser eliminada y se debe pagar el valor de inscripción nuevamente."
            },
            {
                "question": "¿Cómo es la guía de inscripción como NUEVO?",
                "answer": "Puedes consultar el paso a paso y el calendario con fechas (inscripciones del 15 de septiembre al 16 de noviembre de 2026) en: https://tdea.edu.co/tramites/guia-aspirantes-nuevos-pregrado/"
            },
            {
                "question": "¿Qué hacer después de adjuntar la documentación y pagar la inscripción como NUEVO?",
                "answer": "Puedes consultar el proceso de selección y fechas importantes en el siguiente enlace: https://tdea.edu.co/tramites/guia-aspirantes-nuevos-pregrado/"
            },
            {
                "question": "¿Cómo es la inscripción como reingreso y transferencia interna?",
                "answer": "Inscripciones abiertas del 15 de septiembre al 30 de octubre de 2026. Enlace de guía: https://tdea.edu.co/tramites/guia-aspirantes-reingreso-y-transferencia-interna-pregrado/"
            },
            {
                "question": "¿Cómo retomar los estudios?",
                "answer": "Debes inscribirte nuevamente como reingreso en las fechas establecidas (o como transferencia interna si el sistema lo requiere), pagar el valor de inscripción, actualizar documentación y esperar admisión. Puedes acceder a la misma malla curricular hasta dos años después de la cancelación."
            },
            {
                "question": "¿Cómo funciona la doble titulación?",
                "answer": "Debes realizar el primer semestre de uno de los dos programas y al finalizar solicitar a la Facultad la aprobación. Si se aprueba, realizas inscripción como transferencia interna, actualizas documentación y pagas en las fechas establecidas."
            },
            {
                "question": "¿Cómo es la inscripción por transferencia externa?",
                "answer": "Inscripciones abiertas del 15 de septiembre al 30 de octubre de 2026 para solicitar homologación. Enlace de guía: https://tdea.edu.co/tramites/guia-aspirantes-transferencia-externa-pregrado/"
            },
            {
                "question": "¿Cómo es la inscripción a Posgrados (Especialización y Maestría)?",
                "answer": "Inscripciones abiertas del 15 de septiembre al 25 de noviembre de 2026. Enlace de guía: https://tdea.edu.co/tramites/guia-aspirantes-posgrados/"
            },
            {
                "question": "¿Cómo es la inscripción a Posgrados (Doctorado)?",
                "answer": "Inscripciones abiertas hasta el 30 de septiembre. Enlace de guía: https://educacion.tdea.edu.co/tramite/guia-aspirantes-doctorado/"
            },
            {
                "question": "¿Qué son los ciclos propedéuticos?",
                "answer": "Consisten en realizar la técnica, graduarse e inmediatamente matricularse al siguiente semestre para continuar con la tecnología con homologación previa (2 semestres más para finalizar), facilitando la inserción laboral."
            },
            {
                "question": "¿Cómo consulto el horario para estudiantes nuevos?",
                "answer": "El horario es asignado por la institución. Lo puedes consultar ingresando al campus - información - agenda estudiante - botón de imprimir a partir del 31 de julio."
            },
            {
                "question": "¿Cómo realizar una solicitud financiera?",
                "answer": "Ingresando al campus: servicios – atención – crear contacto – procedimientos financieros y allí radicas tu solicitud (respuesta en orden de llegada) o de forma presencial en el bloque 2 piso 4."
            },
            {
                "question": "¿Cómo realizar la renovación y legalización de becas?",
                "answer": "Ingrese a su Sistema Campus, vaya al menú Info – Hoja de vida – personal, seleccione 'Ingresar Solicitud', elija su programa y la beca o convenio correspondiente, adjunte en PDF la carta de renovación/legalización y haga clic en 'Solicitar Beneficio'."
            },
            {
                "question": "¿Qué hacer si tengo un inconveniente con la renovación de beca?",
                "answer": "Debes comunicarte al correo becarios@tdea.edu.co con tus datos completos y exponiendo el inconveniente."
            },
            {
                "question": "¿Qué pasa si realicé el pago de matrícula pero NO se ve reflejado en el sistema?",
                "answer": "Debes comunicarte con el área financiera adjuntando el comprobante de pago donde se evidencie el código CUSS a través del campus (servicios – atención – crear contacto – procedimientos financieros) o presencialmente en el bloque 2 piso 4."
            },
            {
                "question": "¿Cómo realizar un pago con cesantías?",
                "answer": "Solicita al fondo de cesantías que el cheque salga a nombre del Tecnológico de Antioquia. Dirígete a un Banco Popular o Davivienda con el cheque y la liquidación. Si el cheque es inferior al valor del semestre, debes hacer un pago mixto (cheque y efectivo)."
            },
            {
                "question": "¿Cómo realizar un pago directo en línea?",
                "answer": "Debes ingresar tus datos en el enlace oficial de pagos: https://campus.tdea.edu.co/extranet/pagos.do?idEmpresa=1 (recibirás un código por correo o celular para ver la información financiera)."
            },
            {
                "question": "¿Cómo consultar la liquidación de matrícula?",
                "answer": "Ingresa al campus - menú - servicios - financiero - financiero; abajo en el periodo actual a la derecha encuentras el botón de imprimir y de pago en línea."
            },
            {
                "question": "¿Qué son los derechos académicos?",
                "answer": "Artículo 14. Son los valores pecuniarios que debe cancelar el estudiante a la institución por concepto de costos de matrícula y servicios o costos complementarios."
            },
            {
                "question": "¿Qué son los costos de matrícula?",
                "answer": "Artículo 15. Corresponden al valor pecuniario que debe cancelar el estudiante por las actividades académicas del período. Equivalen al 80% de la totalidad de los derechos académicos."
            },
            {
                "question": "¿Qué son los servicios y costos complementarios?",
                "answer": "Artículo 16. Valor pecuniario por el uso de escenarios deportivos, biblioteca, salas de cómputo y bienestar universitario. Equivalen al 20% del total de los derechos académicos."
            },
            {
                "question": "¿Dónde consulto los valores pecuniarios vigentes para 2026?",
                "answer": "Puedes consultarlos en el siguiente enlace: https://tdea.edu.co/wp-content/uploads/2025/12/Resolucion-000890-27112025.pdf"
            },
            {
                "question": "¿Cuál es el valor de la carga académica adicional?",
                "answer": "El valor por crédito adicional es de $122.563 para el año 2026."
            },
            {
                "question": "¿Cómo acceder a la política de gratuidad (Matrícula Cero)?",
                "answer": "Debes realizar el proceso de inscripción. Internamente se validan requisitos y se envía el listado al Ministerio de Educación. Sabrás si eres beneficiario al consultar la liquidación del semestre (verás el descuento por matrícula cero). Nota: No cubre carné ni seguro estudiantil. Más info: https://tdea.edu.co/estudiantes/"
            },
            {
                "question": "¿Si pierdo asignaturas pierdo el beneficio de gratuidad?",
                "answer": "No pierdes el beneficio ya que no exige promedio ni créditos aprobados mínimos, pero ten en cuenta que solo cubre los periodos estipulados del programa; si te atrazas, debes asumir con recursos propios los créditos reprobados."
            },
            {
                "question": "¿Qué pasa si estudié en otra Institución con el beneficio de gratuidad?",
                "answer": "Los semestres cursados previamente en otra institución se restarán del programa actual y deberás asumirlos con recursos propios. Debes solicitar el traslado del beneficio ante el Ministerio de Educación."
            },
            {
                "question": "¿Cómo descargar un certificado de estudio?",
                "answer": "Ruta en el campus (sin costo): Servicios – Financiero - Servicios Financieros – Selecciona tipo de certificado y programa – liquidar – Descargar PDF. Si presenta inconsistencias, escribe a certificados@tdea.edu.co (plazo de 5 a 10 días hábiles)."
            },
            {
                "question": "¿Cómo solicitar un certificado de estudio con especificaciones?",
                "answer": "Debes solicitarlo al correo certificados@tdea.edu.co indicando nombre, documento, programa y todas las especificaciones. Respuesta en un plazo de 5 a 10 días hábiles."
            },
            {
                "question": "¿Cómo solicitar la verificación de título?",
                "answer": "Debes comunicarte al correo certificados@tdea.edu.co adjuntando la autorización de tratamiento de datos. Respuesta en un plazo de 5 a 10 días hábiles."
            },
            {
                "question": "¿Cómo solicitar el certificado de valor pagado o por convenio/beca?",
                "answer": "Direcciona tu solicitud al correo del área financiera: certi.financiera@tdea.edu.co indicando nombre completo, identificación e información clara del certificado."
            },
            {
                "question": "¿Cómo solicitar un certificado laboral?",
                "answer": "Debes solicitarlo al correo certificado.laboral@tdea.edu.co con nombre, documento y especificaciones."
            },
            {
                "question": "¿Cómo solicitar el certificado tributario?",
                "answer": "Debes solicitarlo al correo apoyo.contabilidad1@tdea.edu.co con tus datos completos."
            },
            {
                "question": "¿Cómo solicitar colillas de pago para contratistas?",
                "answer": "Debes solicitarlas al correo auxiliar.financiera1@tdea.edu.co con tus datos completos y los periodos requeridos."
            },
            {
                "question": "¿Cómo solicitar certificados de ingresos y retenciones?",
                "answer": "Debes solicitarlo con tus datos completos al correo auxiliar.financiera4@tdea.edu.co"
            },
            {
                "question": "¿Cómo inscribirme a la convocatoria de Docentes de cátedra y ocasionales 2026-2?",
                "answer": "Para ser incluido en la base de datos institucional, debes diligenciar completamente el siguiente formulario: https://docs.google.com/forms/d/e/1FAIpQLSds-mBvVarP3Bvt8RMyoZTRMK9hCodHuGKAT5D_NTrTBVbe-g/viewform?usp=dialog"
            },
            {
                "question": "¿Cómo actualizar mis datos personales?",
                "answer": "Debes solicitar la actualización enviando un correo a auxadmisiones@tdea.edu.co o acercarte presencialmente a las ventanillas de admisiones y registro."
            },
            {
                "question": "¿Cómo actualizar datos por cambio de nombre?",
                "answer": "Debes solicitarlo en admisiones@tdea.edu.co o presencialmente anexando documento anterior, documento actualizado, escritura pública, resultados ICFES actualizados y acta/diploma de bachiller actualizado."
            },
            {
                "question": "¿Cómo actualizar datos por cambio de nombre si soy EGRESADO?",
                "answer": "Debes enviar los documentos (documento anterior, actual, escritura pública, ICFES actualizado y acta/diploma de bachiller actualizado) al correo grados@tdea.edu.co"
            },
            {
                "question": "¿Cómo acceder al correo institucional?",
                "answer": "A tu usuario de campus le agregas @correo.tdea.edu.co e ingresas con la misma contraseña del campus en www.outlook.com (debe ser desde página web, ya que en la aplicación móvil a veces no lo permite)."
            },
            {
                "question": "¿Cuáles son los requisitos para la restauración de contraseña por primera vez?",
                "answer": "Al ingresar al campus por primera vez te pide cambiar la contraseña cumpliendo con: 8 a 12 caracteres, contener letras y números, mayúsculas, minúsculas, y no contener parte del nombre, apellido o usuario de campus."
            },
            {
                "question": "¿Por qué un estudiante inactivo no puede acceder al correo institucional?",
                "answer": "Por políticas institucionales y directrices de Microsoft, el acceso al correo está vinculado exclusivamente a la vigencia de una relación activa, por lo que no es posible habilitar acceso temporal a cuentas sin vínculo vigente."
            },
            {
                "question": "¿Qué sucede con la licencia de Microsoft Office de escritorio?",
                "answer": "Debido a políticas y cambios de licenciamiento aplicados por Microsoft para cuentas educativas, ya no se garantiza el uso permanente de aplicaciones de escritorio, orientando el acceso principalmente a través de su entorno web de forma gradual."
            },
            {
                "question": "¿Qué hacer si tengo inconvenientes con los sistemas institucionales?",
                "answer": "Debes comunicarte al correo area.tecnica@tdea.edu.co manifestando tus inconvenientes con tus datos completos."
            },
            {
                "question": "¿Qué hacer si tengo inconvenientes con TdeA Virtual?",
                "answer": "Debes comunicarte al correo virtual@tdea.edu.co con tus datos completos y las especificaciones del problema."
            },
            {
                "question": "¿Cómo ingresar a las clases virtuales?",
                "answer": "Debes estar atento a tu correo electrónico personal o institucional, donde se enviará el enlace de acceso aproximadamente 30 minutos antes. También puedes revisar Microsoft Teams para verificar si el docente creó el grupo de la asignatura."
            },
            {
                "question": "¿Cómo funciona el préstamo de Chromebook?",
                "answer": "La entrega se realiza en el bloque 1-308. Para más información debes escribir a prestamo.pc@tdea.edu.co"
            },
            {
                "question": "¿Qué es un prerrequisito?",
                "answer": "Son aquellas asignaturas cuyos contenidos son necesarios para cursar otra u otras materias, cuya aprobación es indispensable para matricularse en ellas."
            },
            {
                "question": "¿Qué es un levantamiento de prerrequisito?",
                "answer": "Es una solicitud que realizas vía campus en fechas establecidas para pedir a la Coordinación del programa permiso de cursar una asignatura sin haber aprobado el prerrequisito."
            },
            {
                "question": "¿Cuáles son las fechas de solicitud de levantamiento de prerrequisitos?",
                "answer": "Inicia el 28/10/2026 hasta el 17/11/2026."
            },
            {
                "question": "¿Cuáles son las fechas de solicitud de cambio de sede o jornada?",
                "answer": "Inicia el 28/10/2026 hasta el 17/11/2026."
            },
            {
                "question": "¿Qué pasa si se aprueba el levantamiento de prerrequisitos?",
                "answer": "El coordinador selecciona la asignatura en el sistema y tú solo debes seleccionar el grupo en tu matrícula. Si eliminas la asignatura de la matrícula, deberás solicitar el levantamiento nuevamente a la Coordinación."
            }
        ]

        # 3. Iterar e insertar/actualizar registros evitando duplicados por pregunta
        count = 0
        for index, item in enumerate(faqs_data, start=1):
            faq_obj, created = FAQ.objects.update_or_create(
                question=item["question"],
                defaults={
                    "answer": item["answer"],
                    "category": category,
                    "intent": intent,
                    "is_active": True,
                    "order": index
                }
            )
            action = "Creada" if created else "Actualizada"
            self.stdout.write(self.style.SUCCESS(f"FAQ {action}: {faq_obj.question} (Orden: {index})"))
            count += 1

        self.stdout.write(self.style.SUCCESS(f"\n¡Proceso finalizado con éxito! Se procesaron {count} preguntas frecuentes."))