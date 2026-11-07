# Informe Ejecutivo de Costos

## Integración de WhatsApp Business Platform — Punto TdeA

**Destinatario:** Rectoría de Punto TdeA  
**Elaborado por:** Consultoría financiera y tecnológica  
**Fecha:** 4 de noviembre de 2026  
**Versión:** 1.0  
**Moneda:** Pesos colombianos (COP)  
**Clasificación:** Documento de trabajo — uso interno

> **Advertencia metodológica.** Las tarifas de Meta se tomaron de la tarjeta oficial en COP vigente al 1 de octubre de 2026. Los valores de CPM, frecuencia y alcance del Documento 2 son supuestos de planificación, no tarifas oficiales. Los impuestos no se incluyen y quedan pendientes de validación contable. Las tablas suponen 100 % de entrega; Meta solo cobra por mensajes entregados.

---

## Ficha técnica

| Elemento | Detalle |
|---|---|
| Documento | Informe general de costos de mensajería |
| Alcance | Chatbot, atención con asesores, campañas de utilidad y campañas de marketing |
| Documento complementario | Presupuesto de avisos mediante estados de WhatsApp |
| Fuente principal | Tarjeta de tarifas de Meta para Colombia, COP, vigente 1 oct 2026 |
| Fecha de consulta | 3 y 4 de noviembre de 2026 |
| Método | Costo por mensaje entregado, con escenarios y supuestos explícitos |
| Redondeo | Cálculos con precisión completa; presentación al peso |

---

## Resumen ejecutivo

Punto TdeA utiliza la **WhatsApp Business Platform (Cloud API de Meta)** para atender estudiantes mediante un chatbot, gestionar tickets con asesores y enviar campañas institucionales con plantillas aprobadas. La institución no utiliza un proveedor intermediario (BSP): la integración se conecta directamente con Meta.

El modelo de cobro vigente es **por mensaje entregado**, no por conversación. Meta cobra únicamente los mensajes que la empresa envía al usuario y que efectivamente se entregan; no cobra los mensajes que el usuario envía a la empresa. Las tarifas dependen de la categoría del mensaje y del país del número destinatario.

Para Colombia, la tarjeta oficial en COP vigente desde el **1 de octubre de 2026** establece:

| Categoría | Tarifa oficial | Condición general |
|---|---:|---|
| Marketing | $ 46,0227 COP por mensaje | Siempre se cobra, salvo ventana FEP |
| Utilidad | $ 2,9455 COP por mensaje | Siempre se cobra, salvo ventana FEP |
| Autenticación | $ 2,9455 COP por mensaje | Siempre se cobra, salvo ventana FEP |
| Servicio | $ 2,9455 COP por mensaje | Después de 1.000 mensajes de servicio gratis al mes por número |

Los hallazgos que más inciden en el presupuesto son:

1. **El servicio ya no es gratuito.** Desde el 1 de octubre de 2026, los mensajes de servicio y las plantillas de utilidad enviadas dentro de la ventana de 24 horas se cobran. Antes de esa fecha eran gratuitos.
2. **Los 1.000 mensajes gratis generales no existen.** Solo existen **1.000 mensajes de servicio gratis al mes por número de teléfono de empresa**. No aplican a marketing, utilidad ni autenticación.
3. **El beneficio de 1.000 conversaciones gratis** pertenece al modelo de cobro por conversación, derogado el 30 de junio de 2025. No debe confundirse con el beneficio actual.
4. **Marketing cuesta 15,6 veces más que utilidad o servicio.** Una plantilla mal clasificada puede multiplicar el costo de una campaña.
5. **La ventana gratuita de entrada (FEP) es de hasta 7 días**, según la documentación oficial para desarrolladores. Solo se activa con anuncios Click to WhatsApp y no es una regla general para campañas de marketing.
6. **Los impuestos no están incluidos.** Meta factura desde Meta Platforms Ireland Limited y los términos indican que los impuestos pueden aplicarse. El IVA y las retenciones quedan pendientes de validación contable.

### Cifras de referencia

| Escenario | Volumen | Costo estimado |
|---|---:|---:|
| Chatbot + asesores + utilidad | 100.000 mensajes de cada modalidad (300.000 en total) | $ 880.705 |
| Marketing | 100.000 mensajes | $ 4.602.270 |
| Avisos en estados de WhatsApp | 100.000 estudiantes, escenario intermedio | $ 4.800.000 |

Las cifras anteriores son estimaciones de planificación. No incluyen impuestos, cargos bancarios, producción de creativos, gestión de campañas ni costos de personal.

---

## 1. Objetivo y alcance

### 1.1 Objetivo

Explicar, en lenguaje institucional y con trazabilidad técnica, cuánto cuesta utilizar la integración de WhatsApp de Punto TdeA en distintos escenarios de volumen, diferenciando:

- Las tarifas oficiales de Meta.
- Los supuestos de planificación.
- Los beneficios gratuitos vigentes.
- Los costos que quedan pendientes de validación.

El informe busca sustentar una decisión presupuestal informada, no reemplazar la facturación real de Meta ni la validación contable de la institución.

### 1.2 Alcance

El documento cubre la mensajería enviada por Punto TdeA a través de la Cloud API:

- Respuestas del chatbot.
- Atención humana mediante tickets.
- Campañas de utilidad.
- Campañas de marketing.

El **Apartado C** (avisos mediante estados de WhatsApp) se desarrolla en el documento independiente `PRESUPUESTO_AVISOS_ESTADOS_WHATSAPP_PUNTOTDEA.md`, porque utiliza un mecanismo publicitario distinto: la Marketing API de Meta, no el envío de mensajes.

### 1.3 Exclusiones

No forman parte de este informe:

- El IVA, las retenciones y el Gravamen a los Movimientos Financieros (GMF), por quedar pendientes de validación contable.
- La TRM y las comisiones bancarias, si la cuenta se factura en USD.
- El margen de un proveedor intermediario (BSP), porque la integración es directa con Meta.
- La producción de creativos, la gestión de campañas, el personal, el hosting y las licencias.
- La consecución de consentimientos (opt-in) y la gestión de bajas.
- Los costos de la publicidad en estados de WhatsApp, que se tratan en el Documento 2.

### 1.4 Método

1. Se identificó la implementación real en el proyecto Punto TdeA.
2. Se consultaron las fuentes oficiales de Meta para Colombia.
3. Se extrajo la tarjeta de tarifas en COP vigente.
4. Se construyeron escenarios unitarios por categoría, sin inventar una distribución de tráfico.
5. Se aplicaron los beneficios gratuitos una sola vez.
6. Se redondearon los resultados únicamente al presentarlos.

---

## 2. Descripción de la integración en Punto TdeA

### 2.1 Arquitectura general

La integración usa la **WhatsApp Cloud API** de Meta de forma directa. El proyecto no contrata un BSP ni revende la plataforma: la cuenta de WhatsApp Business se conecta a la app de Meta y el backend de Punto TdeA envía y recibe mensajes mediante la Graph API.

Los componentes relevantes para el costo son:

| Componente | Función | Efecto en el costo |
|---|---|---|
| Chatbot | Responde consultas automáticas dentro de la conversación | Mensajes de servicio; pueden ser gratuitos si están dentro de los 1.000 mensajes/mes |
| Tickets con asesor | Escala la conversación a atención humana | Mensajes de servicio dentro de la ventana; plantillas si se responde fuera |
| Campañas de utilidad | Envían recordatorios y notificaciones operativas | Plantillas de utilidad, siempre cobradas |
| Campañas de marketing | Envían promociones e invitaciones | Plantillas de marketing, siempre cobradas |
| Webhooks | Reciben mensajes y estados de entrega | No generan costo de mensajería |
| Anuncios en estados | Publicidad en el Status de WhatsApp | Costo publicitario por impresiones, no por mensaje |

### 2.2 Flujo de una conversación

1. El estudiante escribe al número de Punto TdeA.
2. El webhook recibe el mensaje y lo entrega al chatbot.
3. El chatbot responde con texto libre dentro de la ventana de atención de 24 horas.
4. Si el estudiante pide hablar con un asesor, se crea un ticket.
5. El asesor responde dentro de la misma ventana o, si ya pasaron 24 horas, mediante una plantilla aprobada.
6. Si el asesor intenta responder con texto libre fuera de la ventana, Meta rechaza el envío con el error `131047`.

### 2.3 Campañas

Las campañas se envían con plantillas aprobadas previamente por Meta. La plantilla define la categoría (utilidad o marketing) y el contenido. Meta puede revisar y reclasificar la plantilla si considera que el contenido no corresponde a la categoría declarada.

La institución debe mantener un inventario de plantillas, su categoría y su vigencia. Una plantilla de utilidad mal redactada puede convertirse en marketing y multiplicar el costo por 15,6.

### 2.4 Lo que la integración no hace

- No publica estados orgánicos de WhatsApp: la Cloud API no tiene esa función.
- No garantiza que un mensaje sea entregado: solo cobra si se entrega.
- No garantiza que un anuncio sea visto por un número determinado de estudiantes.
- No reemplaza la validación contable ni la facturación oficial de Meta.

---

## 3. Modelo de cobro de Meta

### 3.1 Del modelo por conversación al modelo por mensaje

| Periodo | Modelo | Beneficio gratuito | Estado |
|---|---|---|---|
| Antes del 1 de julio de 2025 | Cobro por conversación | 1.000 conversaciones de servicio gratis al mes | Obsoleto |
| 1 de julio de 2025 – 30 de septiembre de 2026 | Cobro por mensaje | Servicio gratis; utilidad dentro de la ventana gratis | Reemplazado |
| Desde el 1 de octubre de 2026 | Cobro por mensaje | 1.000 mensajes de servicio gratis al mes por número | Vigente |

> **Precisión importante.** El beneficio actual no es “1.000 mensajes gratis” de cualquier categoría. Es un beneficio acotado a **mensajes de servicio**. Una campaña de marketing o de utilidad no consume ni agota ese beneficio, pero tampoco se beneficia de él.

### 3.2 Quién paga y cuándo

Meta cobra a la empresa cuando un mensaje enviado por la empresa **se entrega** al usuario. No cobra:

- Los mensajes que el usuario envía a la empresa.
- Los mensajes que la empresa envía pero no se entregan.
- Los mensajes que se encuentran dentro de una ventana gratuita aplicable.
- Los primeros 1.000 mensajes de servicio del mes, por número de teléfono.

### 3.3 Categorías de mensaje

| Categoría | Uso típico | Tarifa Colombia | ¿Tiene beneficio gratuito? |
|---|---|---:|---|
| Marketing | Promoción de programas, invitaciones, difusión de servicios, retargeting | $ 46,0227 | No, salvo FEP |
| Utilidad | Seguimiento de una acción o solicitud del estudiante: confirmaciones, recordatorios, estados de trámite | $ 2,9455 | No, salvo FEP |
| Autenticación | Verificación de identidad o códigos de un solo uso | $ 2,9455 | No, salvo FEP |
| Servicio | Respuestas a mensajes del estudiante dentro de la ventana de 24 horas | $ 2,9455 | 1.000 mensajes/mes por número; FEP |
| Meta Business Agent | IA nativa de Meta, facturada por tokens | USD 2,00 por 1 millón de tokens | No |

Meta Business Agent no forma parte de la integración de Punto TdeA, que usa un chatbot propio. Se incluye solo para completar el mapa de categorías.

### 3.4 País y moneda

La tarifa aplicable depende del **código de país del número destinatario**. Para números colombianos (+57) se aplica la tarifa de Colombia. Si Punto TdeA envía mensajes a otros países, debe usar la tarifa del país correspondiente.

La tarjeta oficial de Colombia está publicada en **COP** desde el 1 de abril de 2026. Esto evita la conversión desde USD, aunque la cuenta puede estar configurada en otra moneda. Si la cuenta está en USD, el valor en pesos dependerá de la TRM y del margen del emisor.

### 3.5 Beneficios gratuitos vigentes

**a) 1.000 mensajes de servicio gratis al mes**

- Aplican por **número de teléfono de empresa**, no por cuenta de WhatsApp Business ni por portafolio.
- Se reinician cada mes y no se acumulan.
- Solo aplican a mensajes de la categoría **servicio**.
- No aplican a marketing, utilidad ni autenticación.
- Valor máximo del beneficio: 1.000 × $ 2,9455 = **$ 2.946 COP al mes** por número.

**b) Ventana de entrada gratuita (FEP)**

- Se activa cuando un usuario escribe a la empresa desde un **anuncio Click to WhatsApp**.
- La empresa debe responder dentro de la ventana de servicio de 24 horas con un mensaje de marketing, utilidad, autenticación o servicio.
- Esa primera respuesta es gratuita y abre la FEP.
- La FEP puede permanecer abierta **hasta 7 días**.
- Durante la FEP, los mensajes de marketing, utilidad, autenticación y servicio no se cobran.
- Los mensajes de Meta Business Agent sí se cobran.
- Solo aplica a usuarios que escriben desde la app de WhatsApp en Android o iOS; las versiones web y de escritorio no son compatibles.
- La FEP se rastrea por par usuario-empresa y se comparte entre cuentas de mensajería que usan el mismo número.

> **Discrepancia de fuentes.** La página comercial de Meta todavía indica 72 horas para la FEP. La página oficial de precios para desarrolladores indica “hasta 7 días”. Este informe adopta la página para desarrolladores como fuente principal y recomienda confirmar el estado de la FEP en la cuenta antes de planificar una campaña que dependa de ella.

### 3.6 Niveles de volumen

Los niveles de volumen aplican solo a mensajes de **utilidad** y **autenticación**. No aplican a marketing ni a servicio.

| Mensajes de utilidad al mes | Tarifa unitaria | Variación |
|---:|---:|---:|
| 0 – 100.000 | $ 2,9455 | Tarifa de lista |
| 100.001 – 1.000.000 | $ 2,7982 | −5 % |
| 1.000.001 – 4.500.000 | $ 2,6510 | −10 % |
| 4.500.001 – 15.000.000 | $ 2,5037 | −15 % |
| 15.000.001 – 30.000.000 | $ 2,3564 | −20 % |
| 30.000.001 en adelante | $ 2,2091 | −25 % |

Para autenticación, los tramos comienzan en 120.000 mensajes. Como las tablas de este informe llegan hasta 100.000 mensajes, **todas las estimaciones usan la tarifa de lista**. El descuento por volumen solo sería relevante por encima de 100.000 mensajes de utilidad o 120.000 de autenticación.

### 3.7 Tarjeta oficial de Colombia

| Concepto | Valor |
|---|---:|
| Marketing | $ 46,0227 COP |
| Utilidad | $ 2,9455 COP |
| Autenticación | $ 2,9455 COP |
| Servicio | $ 2,9455 COP |
| Autenticación internacional | No aplica |
| Meta Business Agent | USD 2,00 / 1 millón de tokens |
| Vigencia | 1 de octubre de 2026 |
| Moneda | COP |
| País | Colombia |

### 3.8 Mensajes enviados y mensajes entregados

Meta cobra por mensaje **entregado**, no por mensaje enviado. Un mensaje puede no entregarse por número inválido, bloqueo del usuario, rechazo de la plataforma o fallas temporales.

Las tablas de este informe suponen **100 % de entrega** para mostrar un techo conservador. Si la entrega real es menor, el costo también será menor. La institución debe medir su tasa de entrega en la cuenta y aplicar la fórmula:

**Costo real estimado = Mensajes enviados × Tarifa × Tasa de entrega**

No se asume una tasa de entrega porque no existe un dato oficial aplicable a Punto TdeA. Inventarla distorsionaría el presupuesto.

---

## 4. Apartado A — Chatbot, atención con asesores y campañas de utilidad

Este apartado responde a la operación habitual de Punto TdeA: la conversación con estudiantes y las notificaciones operativas.

### 4.1 Mensajería del chatbot

El chatbot responde consultas de estudiantes sobre información institucional, servicios académicos, preguntas frecuentes y orientación general.

**¿Cuándo tiene costo cero?**

- Cuando el mensaje del estudiante es entrante: Meta no cobra los mensajes del usuario a la empresa.
- Cuando la respuesta del chatbot se envía dentro de los primeros 1.000 mensajes de servicio del mes por número.
- Cuando la conversación está dentro de una FEP activa.

**¿Cuándo genera cobro?**

- Cuando la respuesta del chatbot es un mensaje de servicio y ya se agotaron los 1.000 mensajes gratis del mes.
- Cuando el chatbot envía una plantilla de utilidad: se cobra como utilidad.
- Cuando el chatbot envía una plantilla de marketing: se cobra como marketing.
- Cuando el chatbot intenta responder fuera de la ventana de 24 horas con texto libre: Meta rechaza el envío con el error `131047`; se requiere una plantilla.

**Ejemplo.** Un estudiante pregunta por el calendario académico. El mensaje del estudiante es gratuito. El chatbot responde con texto libre dentro de la ventana de 24 horas: es un mensaje de servicio. Si es el mensaje de servicio 1.001 del mes, cuesta $ 2,9455.

### 4.2 Atención mediante tickets con asesor

El flujo típico es:

1. El estudiante solicita hablar con un asesor.
2. Se crea un ticket.
3. El asesor responde.
4. El estudiante envía información adicional.
5. Se resuelve la solicitud.

**Ventana de atención de 24 horas.** La ventana comienza con el último mensaje del estudiante. Dentro de ella, el asesor puede responder con texto libre sin plantilla. Cada nuevo mensaje del estudiante reinicia la ventana.

**Diferencia entre mensajes dentro y fuera de la ventana:**

| Situación | Tipo de mensaje | Tarifa | Requisito |
|---|---|---:|---|
| Asesor responde dentro de las 24 horas | Servicio | $ 2,9455 | Texto libre; después de 1.000 gratis |
| Asesor responde fuera de las 24 horas | Utilidad o marketing | $ 2,9455 o $ 46,0227 | Plantilla aprobada |
| Asesor envía una plantilla de utilidad dentro de la ventana | Utilidad | $ 2,9455 | Plantilla aprobada |
| Asesor envía una plantilla de marketing dentro de la ventana | Marketing | $ 46,0227 | Plantilla aprobada |

En Colombia, la tarifa de utilidad y la de servicio son iguales. La diferencia práctica está en el beneficio de 1.000 mensajes de servicio y en el requisito de plantilla.

### 4.3 Campañas de utilidad

Son comunicaciones institucionales de carácter operativo o informativo, sin finalidad promocional. Ejemplos:

- Recordatorios de trámites.
- Notificaciones de solicitudes.
- Avisos de vencimientos.
- Información sobre procesos académicos.
- Confirmaciones de registros.
- Actualizaciones de estados.
- Notificaciones relacionadas con un servicio solicitado por el estudiante.

**Requisitos para que Meta clasifique una plantilla como utilidad:**

- Debe estar relacionada con una acción o solicitud previa del usuario.
- No debe contener promoción, publicidad ni contenido comercial.
- Debe ser específica y accionable.
- Debe cumplir las políticas de contenido de Meta.
- Debe estar aprobada como plantilla.

**No es utilidad:**

- Una invitación a un evento abierto.
- La promoción de un programa académico.
- Un descuento o beneficio comercial.
- Una comunicación cuyo propósito principal sea incentivar la participación.

Esos casos son marketing, aunque se envíen a estudiantes de la institución.

### 4.4 Tabla 1 — Chatbot, tickets con asesor y campañas de utilidad

**Criterio de lectura.** Cada columna representa un escenario unitario independiente de N mensajes. Las columnas muestran el costo bruto, sin aplicar el beneficio de 1.000 mensajes de servicio. La columna **Total** aplica el beneficio una sola vez sobre la operación conjunta de N mensajes de chatbot, N de asesor y N de utilidad (3N mensajes en total). Las columnas no deben sumarse sin considerar este ajuste.

| Cantidad de mensajes | Chatbot | Tickets con asesor | Campañas de utilidad | Costo total estimado |
|---:|---:|---:|---:|---:|
| 100 | $ 295 | $ 295 | $ 295 | $ 295 |
| 500 | $ 1.473 | $ 1.473 | $ 1.473 | $ 1.473 |
| 1.000 | $ 2.946 | $ 2.946 | $ 2.946 | $ 5.891 |
| 5.000 | $ 14.728 | $ 14.728 | $ 14.728 | $ 41.237 |
| 10.000 | $ 29.455 | $ 29.455 | $ 29.455 | $ 85.420 |
| 20.000 | $ 58.910 | $ 58.910 | $ 58.910 | $ 173.785 |
| 50.000 | $ 147.275 | $ 147.275 | $ 147.275 | $ 438.880 |
| 100.000 | $ 294.550 | $ 294.550 | $ 294.550 | $ 880.705 |

**Fórmulas aplicadas:**

- Chatbot = N × $ 2,9455.
- Tickets = N × $ 2,9455.
- Utilidad = N × $ 2,9455.
- Total = (Chatbot + Tickets + Utilidad) − (1.000 × $ 2,9455), cuando el volumen de servicio supera 1.000 mensajes. Si el volumen de servicio es menor, se descuenta el valor completo de esos mensajes.

**Verificación de algunos valores:**

- Para 1.000 mensajes: 3 × $ 2.946 = $ 8.837; menos $ 2.946 de beneficio = $ 5.891.
- Para 100.000 mensajes: 3 × $ 294.550 = $ 883.650; menos $ 2.946 = $ 880.705.
- Para 100 mensajes: los 200 mensajes de servicio (chatbot + asesores) caben en los 1.000 gratis; solo se paga la utilidad: $ 295.

### 4.5 Explicación de la Tabla 1

**¿Por qué el chatbot puede costar distinto de una campaña de utilidad?**

En Colombia, la tarifa unitaria es la misma ($ 2,9455). La diferencia no está en el precio por mensaje, sino en:

1. **El beneficio de 1.000 mensajes de servicio.** El chatbot y los asesores generan mensajes de servicio y pueden beneficiarse; las campañas de utilidad no.
2. **El volumen.** El chatbot suele generar más mensajes por conversación; una campaña de utilidad envía un mensaje por estudiante.
3. **La categoría real del contenido.** Si el chatbot responde con una promoción, pasa a marketing ($ 46,0227). Si una campaña supuestamente utilitaria contiene promoción, Meta puede reclasificarla como marketing.
4. **La ventana de atención.** El chatbot responde dentro de la ventana de 24 horas; una campaña de utilidad es proactiva y siempre requiere plantilla.

**¿Por qué las columnas de chatbot y asesor son iguales?**

Porque ambas son mensajes de servicio y comparten la misma tarifa. La diferencia es operativa: el chatbot automatiza y el asesor atiende casos complejos. El costo por mensaje es idéntico; el costo total depende de cuántos mensajes genere cada canal.

**¿Por qué el total no es la suma exacta de las tres columnas?**

Porque el beneficio de 1.000 mensajes de servicio se aplica una sola vez. Si se sumaran las tres columnas, se estaría aplicando el beneficio dos veces (una por chatbot y otra por asesores). La columna Total corrige esa doble aplicación.

**Advertencia sobre la distribución del tráfico.** La tabla no supone una proporción entre chatbot, asesores y utilidad. Presenta escenarios unitarios para que la institución los compare. Si Punto TdeA conoce su mezcla real, puede calcular el costo combinado con la fórmula del anexo B.

---

## 5. Apartado B — Mensajes de campañas de marketing

### 5.1 Qué es una campaña de marketing

Es una comunicación con finalidad promocional o de difusión. Ejemplos:

- Promoción de matrículas.
- Invitaciones a eventos.
- Campañas institucionales.
- Promoción de programas académicos.
- Invitaciones a actividades.
- Comunicaciones para incentivar la participación.
- Campañas de difusión de servicios.

### 5.2 Diferencia entre utilidad y marketing

| Criterio | Utilidad | Marketing |
|---|---|---|
| Propósito | Acompañar una acción o solicitud del usuario | Promover, invitar, difundir o vender |
| Disparador | Acción o solicitud previa del usuario | Iniciativa de la empresa |
| Contenido | Operativo, informativo, específico | Promocional, comercial, persuasivo |
| Tarifa Colombia | $ 2,9455 | $ 46,0227 |
| Beneficio gratuito | Ninguno, salvo FEP | Ninguno, salvo FEP |
| Requisito | Plantilla aprobada | Plantilla aprobada |

La diferencia de tarifa es de **15,6 veces**. Por eso, la clasificación correcta de la plantilla es una decisión financiera, no solo técnica.

### 5.3 Tabla 2 — Campañas de marketing

La tabla supone 100 % de entrega. Meta solo cobra por mensajes entregados; si la entrega es menor, el costo baja.

| Cantidad de mensajes | Tarifa por mensaje | Costo total estimado |
|---:|---:|---:|
| 100 | $ 46,0227 | $ 4.602 |
| 500 | $ 46,0227 | $ 23.011 |
| 1.000 | $ 46,0227 | $ 46.023 |
| 5.000 | $ 46,0227 | $ 230.114 |
| 10.000 | $ 46,0227 | $ 460.227 |
| 20.000 | $ 46,0227 | $ 920.454 |
| 50.000 | $ 46,0227 | $ 2.301.135 |
| 100.000 | $ 46,0227 | $ 4.602.270 |

### 5.4 Explicación de la Tabla 2

- **No hay volumen gratuito.** Los 1.000 mensajes de servicio no aplican a marketing.
- **No hay descuento por volumen.** La tarifa de marketing es plana.
- **Solo la FEP puede hacer gratuitos los mensajes de marketing.** La FEP se activa con anuncios Click to WhatsApp, no con una campaña de plantillas a una lista.
- **La respuesta del estudiante no vuelve gratuita la campaña.** Si el estudiante responde, se abre una ventana de servicio de 24 horas; los mensajes de la empresa dentro de esa ventana son de servicio (con su propio costo), no de marketing gratuito.
- **El costo es por mensaje entregado.** Si se envían 10.000 mensajes y se entregan 9.500, el costo es 9.500 × $ 46,0227 = $ 437.216, no $ 460.227.

### 5.5 Ejemplos de costo

| Campaña | Mensajes | Costo estimado |
|---|---:|---:|
| Invitación a un evento | 1.000 | $ 46.023 |
| Promoción de un programa | 5.000 | $ 230.114 |
| Difusión de matrículas | 20.000 | $ 920.454 |
| Campaña masiva | 100.000 | $ 4.602.270 |

Estos valores son el costo de mensajería de Meta. No incluyen diseño, producción, gestión, impuestos ni pauta publicitaria.

---

## 6. Apartado C — Presupuesto de avisos mediante estados de WhatsApp

El tercer apartado sustantivo es la difusión de avisos institucionales mediante **anuncios en los estados de WhatsApp**. Se desarrolla en el documento independiente `PRESUPUESTO_AVISOS_ESTADOS_WHATSAPP_PUNTOTDEA.md` por tres razones:

1. **No es un envío de mensajes.** Es un placement publicitario de Meta Ads.
2. **No tiene tarifa por mensaje.** Se paga por impresiones, en una subasta.
3. **No garantiza alcance.** Un anuncio puede ser visto muchas veces por unas personas y no ser visto por otras.

### 6.1 Diferencia esencial

| Mecanismo | Qué hace | Cómo se cobra | ¿Garantiza alcance? |
|---|---|---|---|
| Cloud API | Envía un mensaje a un número | Por mensaje entregado | Sí, si el número es válido y el usuario no bloqueó |
| Anuncio en Status | Muestra un anuncio en la pestaña Novedades | Por impresiones, en subasta | No |
| Estado orgánico | Publicación desde la app de WhatsApp Business | Gratis | No; solo contactos que guarden el número |

### 6.2 Cifras de referencia del Documento 2

| Escenario | 100.000 estudiantes | Costo por estudiante |
|---|---:|---:|
| Conservador | $ 1.647.059 | $ 16 |
| Intermedio | $ 4.800.000 | $ 48 |
| Alto | $ 13.333.333 | $ 133 |

Estas cifras son supuestos de planificación, no tarifas oficiales. El CPM de los anuncios en estados no está publicado por Meta: se determina en la subasta.

### 6.3 Recomendación preliminar

Para listas pequeñas y conocidas, la mensajería directa con plantillas es más barata y controlable. Para audiencias grandes, los anuncios en estados pueden ser competitivos, pero no garantizan que todos los estudiantes vean el aviso. La comparación completa está en el Documento 2.

---

## 7. Mensajes gratuitos y ventanas de atención

### 7.1 Ventana de servicio de 24 horas

- Comienza con el último mensaje del estudiante.
- Permite responder con texto libre, sin plantilla.
- No es gratuita: los mensajes de servicio se cobran después de los 1.000 gratis del mes.
- Si la empresa responde después de 24 horas, debe usar una plantilla aprobada.
- Si intenta texto libre fuera de la ventana, Meta rechaza el envío con el error `131047`.

### 7.2 Ventana de entrada gratuita (FEP)

| Condición | Detalle |
|---|---|
| Disparador | El usuario escribe a la empresa desde un anuncio Click to WhatsApp |
| Dispositivo | App de WhatsApp en Android o iOS; no aplica en web ni escritorio |
| Requisito | La empresa responde dentro de la ventana de servicio de 24 horas |
| Primer mensaje | Gratuito; abre la FEP |
| Duración | Hasta 7 días |
| Categorías cubiertas | Marketing, utilidad, autenticación y servicio |
| Excepción | Meta Business Agent sigue cobrando |
| Alcance | Par usuario-empresa; se comparte entre cuentas con el mismo número |
| Fuente | Página oficial de precios para desarrolladores |
| Discrepancia | La página comercial todavía dice 72 horas |

### 7.3 Conversaciones derivadas de una campaña de marketing

La afirmación histórica de que “los mensajes derivados de una campaña de marketing tienen 24 horas gratis” **no es una regla vigente** en el modelo por mensaje.

Lo que ocurre realmente:

1. Punto TdeA envía una plantilla de marketing: se cobra $ 46,0227 si se entrega.
2. El estudiante responde: su mensaje es gratuito.
3. Se abre una ventana de servicio de 24 horas.
4. El chatbot o el asesor responde con texto libre: es un mensaje de servicio, con costo de $ 2,9455 después de los 1.000 gratis.
5. Si la empresa envía una plantilla de utilidad: se cobra $ 2,9455.
6. Si la empresa envía otra plantilla de marketing: se cobra $ 46,0227.
7. No hay una ventana gratuita de 24 horas por el solo hecho de haber enviado marketing. La única ventana gratuita general es la FEP, y solo aplica a conversaciones originadas en anuncios Click to WhatsApp.

### 7.4 Ejemplo práctico completo

**Caso A: campaña de marketing a un estudiante que no viene de un anuncio**

| Paso | Acción | Costo |
|---|---|---:|
| 1 | Punto TdeA envía plantilla de marketing | $ 46,0227 |
| 2 | El estudiante responde | $ 0 |
| 3 | Se abre ventana de 24 horas | $ 0 |
| 4 | El chatbot responde con texto libre | $ 2,9455 |
| 5 | El asesor envía una plantilla de utilidad con el detalle del programa | $ 2,9455 |
| 6 | El estudiante responde de nuevo | $ 0 |
| 7 | El asesor responde con texto libre | $ 2,9455 |
| **Total** | **2 mensajes de servicio + 1 de utilidad + 1 de marketing** | **$ 54,8592** |

Si los 1.000 mensajes de servicio del mes ya se agotaron, el costo es el anterior. Si aún hay beneficio, los dos mensajes de servicio pueden ser gratuitos; el total baja a $ 48,9682 (marketing + utilidad).

**Caso B: conversación originada en un anuncio Click to WhatsApp**

| Paso | Acción | Costo |
|---|---|---:|
| 1 | El estudiante ve el anuncio y hace clic | Costo publicitario, no de mensajería |
| 2 | El estudiante escribe a la empresa | $ 0 |
| 3 | La empresa responde dentro de 24 horas | $ 0; abre la FEP |
| 4 | La empresa envía marketing, utilidad o servicio durante la FEP | $ 0 |
| 5 | La FEP se mantiene hasta 7 días | $ 0 |
| **Total de mensajería** | **Dentro de la FEP** | **$ 0** |

El costo del anuncio se paga aparte, como publicidad. La FEP no elimina el costo del anuncio; solo elimina el costo de los mensajes de la empresa durante la ventana.

### 7.5 Mitos y realidades

| Afirmación frecuente | Realidad |
|---|---|
| “Los primeros 1.000 mensajes del mes son gratis” | Solo los primeros 1.000 mensajes de **servicio** por número. No aplican a marketing, utilidad ni autenticación. |
| “La ventana de 24 horas es gratis” | La ventana existe, pero los mensajes de servicio se cobran después de los 1.000 gratis. |
| “Si el estudiante responde a una campaña, todo es gratis por 24 horas” | No. Se abre una ventana de servicio, pero los mensajes de la empresa tienen costo. |
| “La FEP dura 72 horas” | La página oficial para desarrolladores indica hasta 7 días. La página comercial está desactualizada. |
| “La utilidad siempre es gratis” | No. Desde el 1 de octubre de 2026, la utilidad se cobra. |
| “Se cobra por mensaje enviado” | No. Se cobra por mensaje **entregado**. |
| “Todavía aplica el cobro por conversación” | No. El modelo por mensaje rige desde el 1 de julio de 2025. |
| “Los anuncios en estados son mensajes de WhatsApp” | No. Son un placement publicitario; se cobran por impresiones. |

### 7.6 Cómo verificar en la cuenta

- Revisar la tarjeta de tarifas vigente en el Billing Hub.
- Confirmar la moneda de facturación (COP o USD).
- Revisar la categoría asignada a cada plantilla.
- Medir la tasa de entrega en los reportes de mensajes.
- Confirmar si la FEP está activa en la cuenta y su duración.
- Revisar el consumo de los 1.000 mensajes de servicio del mes.
- Verificar el método de pago y la entidad facturadora.

---

## 8. Impuestos y cargos adicionales

### 8.1 Tarifas netas

Todas las tarifas de este informe son **netas, antes de impuestos**. No se agregó IVA, retención ni GMF.

### 8.2 IVA y retenciones

Meta Platforms Ireland Limited es la entidad contratante para Colombia, según los términos de WhatsApp Business. Los términos indican que los importes pueden incluir impuestos y que la empresa es responsable de asumirlos y remitirlos.

Posibles conceptos aplicables:

- IVA del 19 % sobre servicios importados.
- Retención en la fuente.
- Retención de IVA.
- GMF, si aplica al medio de pago.

**Estado:** pendiente de validación contable. No se incluye un porcentaje en las tablas porque la aplicación depende del régimen tributario de Punto TdeA, de la naturaleza del servicio y de la factura emitida por Meta. Agregar un 19 % automáticamente podría sobreestimar o subestimar el costo.

### 8.3 Proveedor intermediario (BSP)

Punto TdeA usa la API de Meta directamente, sin BSP. Por eso no se incluye margen de intermediario. Si en el futuro se contrata un BSP, debe agregarse su margen (referencia de mercado: 15 % a 35 %) y verificar si el BSP cobra en USD o en COP.

### 8.4 TRM y comisiones bancarias

Si la cuenta está configurada en USD, el valor en COP dependerá de la TRM del día de la transacción y del margen del emisor de la tarjeta. La tarjeta oficial en COP reduce este riesgo, pero no lo elimina si la cuenta sigue en USD.

### 8.5 GMF y comisiones de tarjeta

El GMF (4 × 1.000) y las comisiones de la tarjeta dependen del medio de pago y de la naturaleza de la cuenta. No se incluyen. Deben validarse con tesorería.

### 8.6 Costos de publicidad

Los anuncios en estados de WhatsApp se cobran aparte, por impresiones. No forman parte de las tarifas de mensajería. Se detallan en el Documento 2.

### 8.7 Costos operativos no incluidos

- Diseño y producción de creativos.
- Gestión de campañas.
- Personal de atención.
- Hosting, licencias y software.
- Creación y mantenimiento de plantillas.
- Gestión de opt-in y bajas.
- Auditoría y consultoría.

### 8.8 Resumen de tratamiento

| Concepto | ¿Incluido en las tablas? | Tratamiento |
|---|---|---|
| Tarifa base de Meta | Sí | Tarjeta oficial COP |
| IVA | No | Pendiente de validación contable |
| Retenciones | No | Pendiente de validación contable |
| GMF | No | Pendiente de validación con tesorería |
| TRM | No | Solo si la cuenta está en USD |
| BSP | No | No aplica a la integración directa |
| Publicidad en estados | No | Documento 2 |
| Creativos y gestión | No | Costo operativo interno |
| Personal y hosting | No | Costo operativo interno |

---

## 9. Consideraciones y supuestos

| Supuesto | Valor | Tipo | Fuente o estado |
|---|---|---|---|
| Volumen mensual | 100 a 100.000 mensajes | Escenario | Rangos solicitados |
| Entrega | 100 % | Techo conservador | Supuesto; medir en la cuenta |
| Chatbot y asesores | Categoría servicio | Supuesto | Reglas de Meta |
| Campañas de utilidad | Categoría utilidad | Supuesto | Reglas de Meta |
| Campañas de marketing | Categoría marketing | Supuesto | Reglas de Meta |
| Tarifa de marketing | $ 46,0227 | Oficial | Tarjeta COP, 1 oct 2026 |
| Tarifa de utilidad | $ 2,9455 | Oficial | Tarjeta COP, 1 oct 2026 |
| Tarifa de servicio | $ 2,9455 | Oficial | Tarjeta COP, 1 oct 2026 |
| Tarifa de autenticación | $ 2,9455 | Oficial | Tarjeta COP, 1 oct 2026 |
| 1.000 mensajes de servicio gratis | Sí, por número y por mes | Oficial | Página de precios |
| FEP | Hasta 7 días | Oficial | Página de precios |
| IVA | No incluido | Pendiente | Validación contable |
| CPM de estados | No aplica en este documento | Supuesto | Documento 2 |
| Fecha de consulta | 3 y 4 de noviembre de 2026 | Dato | Fuentes consultadas |

### 9.1 Lo que el informe no supone

- No supone una tasa de entrega distinta de 100 %.
- No supone un número de estudiantes.
- No supone una distribución de tráfico entre chatbot, asesores y campañas.
- No supone un CPM oficial para estados.
- No supone un porcentaje de IVA.
- No supone descuentos por volumen por encima de 100.000 mensajes.
- No supone un margen de BSP.
- No supone que todos los mensajes se entreguen ni que todos los anuncios se vean.

---

## 10. Conclusiones y recomendaciones

### 10.1 Conclusiones

1. **El modelo vigente es por mensaje entregado.** El cobro por conversación es historia y no debe usarse para presupuestar.
2. **Las tarifas de Colombia son bajas para utilidad y servicio, y altas para marketing.** La relación es de 15,6 veces.
3. **El servicio dejó de ser gratuito.** Desde el 1 de octubre de 2026, la atención del chatbot y de los asesores tiene costo después de 1.000 mensajes de servicio al mes.
4. **El beneficio de 1.000 mensajes es acotado.** Solo aplica a servicio, por número y por mes; su valor máximo es $ 2.946.
5. **La utilidad es la categoría más eficiente para comunicaciones operativas.** A $ 2,9455, permite notificar trámites y estados sin el costo de marketing.
6. **Marketing debe usarse con un objetivo claro.** A $ 46,0227 por mensaje, una campaña masiva puede costar millones de pesos.
7. **La clasificación de plantillas es el principal riesgo financiero.** Una plantilla de utilidad reclasificada como marketing multiplica el costo por 15,6.
8. **La ventana de 24 horas no es gratuita.** Solo la FEP, de hasta 7 días, elimina el costo de los mensajes, y solo para conversaciones originadas en anuncios Click to WhatsApp.
9. **El costo real depende de la entrega.** Las tablas son un techo; la factura será menor si la entrega es menor.
10. **Los impuestos siguen pendientes.** No se debe presupuestar el IVA sin validación contable.

### 10.2 Recomendaciones

1. **Crear una línea presupuestal mensual** para mensajería, separada de la publicidad y de los costos operativos.
2. **Revisar la categoría de cada plantilla** antes de enviarla y después de cualquier cambio de contenido.
3. **Preferir utilidad para comunicaciones operativas** y reservar marketing para campañas con objetivo comercial medible.
4. **Medir la tasa de entrega** y calcular el costo real con la fórmula del anexo B.
5. **Confirmar la FEP en la cuenta** antes de planificar campañas que dependan de ella.
6. **Validar el tratamiento de IVA y retenciones** con contabilidad.
7. **Mantener el opt-in actualizado** y respetar las bajas; una lista limpia reduce el costo y mejora la entrega.
8. **Monitorear los cambios de precios de Meta** cada trimestre.
9. **Usar los anuncios en estados solo para alcance amplio**, no para notificaciones operativas.
10. **Definir una reserva de contingencia** para reclasificaciones, crecimiento del volumen y variaciones de TRM; la reserva no se incluye en las tablas y debe ser aprobada por la institución.

### 10.3 Próximos pasos

| Paso | Responsable | Resultado |
|---|---|---|
| Validar IVA y retenciones | Contabilidad | Costo total con impuestos |
| Medir entrega real | Operación | Tasa de entrega y costo real |
| Revisar plantillas | Comunicaciones | Categorías correctas |
| Confirmar FEP | Operación | Ventana real disponible |
| Definir presupuesto | Rectoría | Techo mensual aprobado |
| Pilotar anuncios en estados | Mercadeo | CPM y alcance reales |

---

## 11. Fuentes oficiales consultadas

| Fuente | URL | Uso en el informe | Fecha |
|---|---|---|---|
| Precios de WhatsApp Business Platform | https://developers.facebook.com/docs/whatsapp/pricing/ | Modelo por mensaje, tarifas, beneficios, FEP | 3 y 4 nov 2026 |
| Precios de Business Platform | https://business.whatsapp.com/products/platform-pricing | Confirmación del modelo y categorías | 3 nov 2026 |
| Categorización de plantillas | https://developers.facebook.com/documentation/business-messaging/whatsapp/templates/template-categorization | Utilidad vs marketing | 3 nov 2026 |
| Niveles de volumen | https://developers.facebook.com/documentation/business-messaging/whatsapp/pricing#volume-tiers-for-utility-and-authentication-messages | Descuentos por volumen | 3 nov 2026 |
| Términos de WhatsApp Business | https://www.whatsapp.com/legal/meta-terms-whatsapp-business | Entidad facturadora e impuestos | 3 nov 2026 |
| Anuncios en estados de WhatsApp | https://whatsappbusiness.com/whatsapp-ads/ | Mecanismo publicitario | 3 nov 2026 |
| Placement targeting | https://developers.facebook.com/documentation/ads-commerce/marketing-api/audiences/reference/placement-targeting | Disponibilidad del placement | 3 nov 2026 |
| Ayuda de Meta: presupuestos mínimos | https://www.facebook.com/business/help/203183363050448 | Mínimos de campaña | 3 nov 2026 |
| Ayuda de Meta: impuestos | https://www.facebook.com/business/help/459201562169682 | Tratamiento tributario | 3 nov 2026 |
| Documentación del proyecto | `docs/whatsapp-meta.md` | Integración Cloud API, ventana de 24 h, error 131047 | 1 nov 2026 |
| Documentación del proyecto | `docs/anuncios-status-whatsapp.md` | Anuncios en estados, requisitos, presupuesto por defecto | 1 nov 2026 |
| Documentación del proyecto | `docs/modulos/communications.md` | Arquitectura del módulo de comunicaciones | 1 nov 2026 |
| Código del proyecto | `communications/services/ads_service.py` | Placement, objetivo, optimización, audiencias | 4 nov 2026 |

### 11.1 Fuentes secundarias

Las referencias de CPM y presupuestos mínimos de mercado se usan únicamente en el Documento 2 y se identifican como supuestos de planificación. No son tarifas oficiales de Meta.

---

## Anexo A — Glosario

| Término | Definición |
|---|---|
| API | Interfaz que permite a un sistema comunicarse con otro |
| Cloud API | API de WhatsApp Business alojada por Meta |
| BSP | Proveedor de servicios de WhatsApp Business; intermediario |
| WABA | Cuenta de WhatsApp Business |
| Plantilla | Mensaje preaprobado por Meta para iniciar o continuar una conversación |
| Utilidad | Categoría para mensajes operativos vinculados a una acción del usuario |
| Marketing | Categoría para mensajes promocionales o de difusión |
| Autenticación | Categoría para verificación de identidad |
| Servicio | Categoría para respuestas dentro de la ventana de 24 horas |
| CSW | Ventana de servicio al cliente de 24 horas |
| FEP | Ventana de entrada gratuita, activada por anuncios Click to WhatsApp |
| Entregado | Mensaje que llegó al dispositivo del usuario |
| Impresión | Visualización de un anuncio |
| Alcance | Personas únicas que vieron un anuncio al menos una vez |
| Frecuencia | Promedio de impresiones por persona alcanzada |
| CPM | Costo por mil impresiones |
| Opt-in | Consentimiento del usuario para recibir mensajes |
| Error 131047 | Error de Meta al intentar enviar texto libre fuera de la ventana de 24 horas |

---

## Anexo B — Fórmulas y redondeo

### B.1 Costo de mensajería

**Costo por categoría = Mensajes entregados × Tarifa de la categoría**

**Costo total = Suma de los costos de todas las categorías**

**Ajuste por beneficio de servicio = Restar 1.000 × Tarifa de servicio, si el volumen de servicio supera 1.000 mensajes**

### B.2 Costo con mezcla de tráfico

Si la institución conoce su mezcla:

**Costo = (Mensajes de servicio × $ 2,9455) + (Mensajes de utilidad × $ 2,9455) + (Mensajes de marketing × $ 46,0227) − Beneficio de servicio**

Donde el beneficio de servicio es el menor valor entre:

- 1.000 × $ 2,9455, y
- Mensajes de servicio × $ 2,9455.

### B.3 Redondeo

- Los cálculos se hicieron con precisión completa.
- Los valores se redondearon al peso en la presentación.
- Las tarifas unitarias se muestran con cuatro decimales para preservar la precisión.
- Las diferencias de $ 1 en las tablas pueden deberse al redondeo.

---

## Anexo C — Tarjeta de tarifas y niveles de volumen

### C.1 Tarjeta de Colombia

| Categoría | Tarifa | Vigencia |
|---|---:|---|
| Marketing | $ 46,0227 | 1 oct 2026 |
| Utilidad | $ 2,9455 | 1 oct 2026 |
| Autenticación | $ 2,9455 | 1 oct 2026 |
| Servicio | $ 2,9455 | 1 oct 2026 |
| Autenticación internacional | No aplica | — |

### C.2 Niveles de utilidad

| Rango | Tarifa | Variación |
|---:|---:|---:|
| 0 – 100.000 | $ 2,9455 | Lista |
| 100.001 – 1.000.000 | $ 2,7982 | −5 % |
| 1.000.001 – 4.500.000 | $ 2,6510 | −10 % |
| 4.500.001 – 15.000.000 | $ 2,5037 | −15 % |
| 15.000.001 – 30.000.000 | $ 2,3564 | −20 % |
| 30.000.001 en adelante | $ 2,2091 | −25 % |

### C.3 Niveles de autenticación

| Rango | Tarifa | Variación |
|---:|---:|---:|
| 0 – 120.000 | $ 2,9455 | Lista |
| 120.001 – 400.000 | $ 2,7982 | −5 % |
| 400.001 – 1.000.000 | $ 2,6510 | −10 % |
| 1.000.001 – 5.000.000 | $ 2,5037 | −15 % |
| 5.000.001 – 10.000.000 | $ 2,3564 | −20 % |
| 10.000.001 en adelante | $ 2,2091 | −25 % |

---

## Anexo D — Lista de verificación para la institución

- [ ] Confirmar la moneda de facturación de la cuenta.
- [ ] Confirmar la entidad facturadora y el tratamiento de IVA.
- [ ] Revisar la categoría de cada plantilla.
- [ ] Medir la tasa de entrega de los últimos 30 días.
- [ ] Verificar el consumo de los 1.000 mensajes de servicio.
- [ ] Confirmar la vigencia de la FEP.
- [ ] Revisar el método de pago y el GMF.
- [ ] Definir el presupuesto mensual de mensajería.
- [ ] Definir la reserva de contingencia.
- [ ] Revisar los cambios de precios de Meta cada trimestre.

---

**Fin del Documento 1.**

*Este informe es una herramienta de planificación. No reemplaza la facturación oficial de Meta ni la validación contable de Punto TdeA.*
