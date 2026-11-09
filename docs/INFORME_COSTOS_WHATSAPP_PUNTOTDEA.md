# INFORME EJECUTIVO DE COSTOS DE MENSAJERÍA DE WHATSAPP
## Integración de Punto TdeA con WhatsApp Business Platform (Meta Cloud API)

---

**Institución:** Punto TdeA
**Documento:** Informe general de costos de mensajería (Tablas 1 y 2)
**Fecha de elaboración:** 4 de noviembre de 2026
**Fecha de consulta de tarifas:** 4 de noviembre de 2026
**Tarifas vigentes:** 1 de octubre de 2026
**Elaborado para:** Rectoría de la institución
**Alcance:** Análisis financiero de los costos de mensajería asociados al uso de la integración de WhatsApp de Punto TdeA. Este documento no modifica código, configuraciones ni bases de datos.

---

## 1. Resumen ejecutivo

Punto TdeA utiliza la plataforma oficial de WhatsApp Business (Meta Cloud API) para atender a los estudiantes mediante chatbot, tickets con asesores y campañas institucionales. Este informe explica, en lenguaje ejecutivo, cuánto cuesta cada tipo de mensaje y cómo se comporta el costo en distintos volúmenes.

Los hallazgos principales son los siguientes:

1. **Meta cobra por mensaje entregado, no por mensaje enviado.** Si un mensaje no se entrega, no genera cobro. La tarifa depende de la categoría del mensaje (marketing, utilidad, autenticación o servicio) y del mercado del número del destinatario (Colombia, código +57).

2. **Las tarifas oficiales vigentes para Colombia, en pesos colombianos (COP), son:**

   | Categoría | Tarifa por mensaje (COP) |
   | --- | --- |
   | Marketing | $ 46,0227 |
   | Utilidad | $ 2,9455 |
   | Autenticación | $ 2,9455 |
   | Servicio | $ 2,9455 |

   Estas tarifas corresponden a la tarjeta oficial de Meta vigente desde el 1 de octubre de 2026. Los valores en esta tabla son los publicados por Meta en moneda colombiana.

3. **A partir del 1 de octubre de 2026, Meta volvió a cobrar por dos tipos de mensajes que antes eran gratuitos:**
   - Los **mensajes de servicio** (respuestas no plantilla dentro de la ventana de atención).
   - Las **plantillas de utilidad enviadas dentro de la ventana de atención**.
   
   Para suavizar este cambio, Meta otorga **1.000 mensajes de servicio gratuitos por mes por cada número de negocio**. Este beneficio **no aplica** para mensajes de marketing, utilidad o autenticación.

4. **Los mensajes de marketing no tienen volumen gratuito.** El único caso en que un mensaje de marketing puede ser gratuito es cuando la conversación se origina desde un anuncio que redirige a WhatsApp (Click to WhatsApp) y se encuentra dentro de la ventana de entrada gratuita.

5. **El chatbot y la atención con asesores ahora generan costo.** Antes del 1 de octubre de 2026, las respuestas automáticas y las respuestas de los asesores dentro de la ventana de atención no tenían costo. Desde esa fecha, cada respuesta cuenta como un mensaje de servicio: los primeros 1.000 mensajes de servicio del mes son gratis y, a partir del mensaje 1.001, se cobran a la tarifa de servicio ($ 2,9455 COP por mensaje en Colombia).

6. **Las campañas de utilidad sí generan costo.** Cada plantilla de utilidad entregada se cobra a la tarifa de utilidad, con descuentos por volumen mensual (tiers) para volúmenes superiores a 100.000 mensajes.

7. **Las campañas de marketing son las más costosas.** Cada mensaje de marketing entregado cuesta $ 46,0227 COP, sin descuentos por volumen.

8. **Los valores presentados en este informe no incluyen impuestos ni cargos de proveedores.** La integración de Punto TdeA se realiza directamente con Meta Cloud API, sin un proveedor intermediario (BSP). La aplicabilidad de impuestos (IVA, retenciones) debe validarse con la dirección contable de la institución.

9. **Las ventanas de atención son las siguientes:**
   - **Ventana de servicio al cliente (CSW):** 24 horas, se abre con cada mensaje del estudiante y se reinicia con cada nueva interacción. Dentro de esta ventana, el negocio puede enviar mensajes de texto libre (no plantilla).
   - **Ventana de entrada gratuita (FEP):** se abre cuando el estudiante escribe primero desde un anuncio Click to WhatsApp. La documentación oficial para desarrolladores vigente establece que puede permanecer abierta **hasta 7 días**; la página comercial de WhatsApp menciona 72 horas. Esta diferencia debe validarse en la consola de Meta de la institución.

10. **El presente informe se acompaña de un documento independiente** sobre el presupuesto para difundir avisos institucionales mediante **estados de WhatsApp** (publicidad), que no debe confundirse con el envío de mensajes por la API.

---

## 2. Objetivo del análisis

El objetivo de este informe es presentar a la rectoría una estimación clara, verificable y financieramente coherente de los costos de mensajería de WhatsApp de Punto TdeA, en diferentes escenarios de volumen, diferenciando:

- La mensajería del chatbot.
- La atención mediante tickets con asesores.
- Las campañas de utilidad.
- Las campañas de marketing.

El informe no pretende sustituir la asesoría contable ni la revisión de los términos comerciales específicos de la cuenta de Meta de la institución. Su finalidad es servir de base para la toma de decisiones presupuestales.

---

## 3. Descripción general de la integración de WhatsApp en Punto TdeA

Punto TdeA es un sistema web desarrollado en Django que integra los siguientes módulos relacionados con WhatsApp:

| Módulo | Función |
| --- | --- |
| `knowledge` | Base de conocimiento y chatbot que responde automáticamente a los estudiantes. |
| `cases` | Bandeja de casos y conversaciones con asesores (tickets). |
| `communications` | Campañas, plantillas, audiencias y adaptador de Meta Cloud API. |
| `announcements` | Avisos institucionales y su publicación opcional en estados de WhatsApp. |
| `dashboard` | Indicadores y seguimiento. |

La integración con WhatsApp se realiza mediante **Meta WhatsApp Cloud API**, con las siguientes características:

- **Un único webhook** recibe los mensajes entrantes del chatbot y los estados de entrega de las campañas.
- **El chatbot** responde automáticamente a los mensajes de texto de los estudiantes dentro de la ventana de atención.
- **Los casos con asesor** se atienden mediante mensajes de texto libre dentro de la ventana de atención.
- **Las campañas** se envían mediante plantillas aprobadas por Meta (categorías marketing o utilidad).
- **Los avisos** pueden publicarse como anuncios en estados de WhatsApp mediante la Meta Marketing API (este mecanismo se trata en el documento independiente).

Esta integración **no utiliza un proveedor intermediario (BSP)**: Punto TdeA se conecta directamente con la API de Meta. Por lo tanto, los costos de mensajería son los tarifados directamente por Meta, sin margen de intermediario.

---

## 4. Modelo de cobro de Meta

### 4.1. Cobro por mensaje (per-message pricing)

Desde el **1 de julio de 2025**, Meta cobra por mensaje, no por conversación. Este modelo reemplazó al esquema anterior de cobro por conversación de 24 horas. Las reglas esenciales son:

- **Se cobra cuando el mensaje es entregado** al estudiante. No se cobra por mensajes enviados que no se entregan.
- **No se cobran los mensajes del estudiante al negocio** (mensajes entrantes). Solo se cobran los mensajes del negocio al estudiante.
- **La tarifa depende de dos factores:** la categoría del mensaje y el mercado del número del destinatario (código de país). Para Colombia, el código es +57.
- **Cada mensaje pertenece a una sola categoría** y, por tanto, genera un solo cargo.

### 4.2. Categorías de mensajes

| Categoría | Descripción | ¿Cuándo se usa? |
| --- | --- | --- |
| **Marketing** | Mensajes con fines promocionales: ofertas, invitaciones, promoción de programas, difusión comercial. | Plantillas de marketing, enviadas en cualquier momento (requieren opt-in). |
| **Utilidad** | Mensajes transaccionales o informativos no promocionales: confirmaciones, recordatorios, avisos de trámites, actualizaciones de estado. | Plantillas de utilidad, enviadas en cualquier momento. |
| **Autenticación** | Mensajes de verificación de identidad (códigos de un solo uso). | Plantillas de autenticación. |
| **Servicio** | Mensajes no plantilla (texto libre, imágenes, etc.) enviados en respuesta al estudiante dentro de la ventana de atención. | Chatbot y asesores. |
| **Meta Business Agent** | Mensajes no plantilla generados por la plataforma de agentes de IA de Meta. | No aplica a PuntoTdeA en su configuración actual. |

### 4.3. Tarifas oficiales vigentes para Colombia (COP)

Las siguientes tarifas fueron consultadas el 4 de noviembre de 2026 en el servicio oficial de precios de WhatsApp Business y corresponden a la tarjeta vigente desde el 1 de octubre de 2026:

| Categoría | Tarifa por mensaje (COP) | Equivalente en USD (referencia) | Volumen tiers |
| --- | --- | --- | --- |
| Marketing | $ 46,0227 | $ 0,0125 | No aplica |
| Utilidad | $ 2,9455 | $ 0,0008 | Sí (desde 100.001 mensajes/mes) |
| Autenticación | $ 2,9455 | $ 0,0008 | Sí (desde 120.001 mensajes/mes) |
| Servicio | $ 2,9455 | $ 0,0008 | No aplica |

**Nota sobre la moneda:** Meta publica tarifas en COP desde el 1 de abril de 2026. La moneda de facturación de cada cuenta de Meta se define al crear la cuenta y no puede cambiarse sin un proceso de migración. Si la cuenta de Punto TdeA factura en USD, el valor en COP dependerá de la tasa de cambio de facturación. Los valores en COP de este informe son la referencia oficial de Meta y deben entenderse como la base tarifaria.

### 4.4. Descuentos por volumen (volume tiers)

Los descuentos por volumen aplican **únicamente** a las categorías de **utilidad** y **autenticación**. No aplican para marketing ni para servicio.

Para Colombia, los tramos de utilidad vigentes son:

| Mensajes de utilidad por mes | Tarifa (COP) |
| --- | --- |
| 0 – 100.000 | $ 2,9455 |
| 100.001 – 1.000.000 | $ 2,7982 |
| 1.000.001 – 4.500.000 | $ 2,6510 |
| 4.500.001 – 15.000.000 | $ 2,5037 |
| 15.000.001 – 30.000.000 | $ 2,3564 |
| 30.000.001 o más | $ 2,2091 |

**Importante:** el descuento se aplica de forma progresiva: cada tramo de mensajes recibe la tarifa del tramo que le corresponde. Por ejemplo, si en un mes se envían 150.000 mensajes de utilidad, los primeros 100.000 se cobran a $ 2,9455 y los 50.000 siguientes a $ 2,7982. Los tramos se calculan a nivel de portafolio de negocio (sumando todas las cuentas de Meta de la institución) y se reinician cada mes.

En los volúmenes considerados en la Tabla 1 de este informe (hasta 100.000 mensajes), **no se alcanza el segundo tramo**, por lo que se utiliza la tarifa de lista ($ 2,9455 COP).

---

## 5. Tabla 1. Chatbot, atención con asesores y campañas de utilidad

### 5.1. Presentación de la tabla

La siguiente tabla muestra el costo estimado de tres escenarios de operación, evaluados de forma **independiente** para la misma cantidad de mensajes. No se asume una distribución fija de los mensajes entre las tres categorías, porque la institución no ha definido una proporción de uso.

**Columnas:**

- **Chatbot:** mensajes de servicio (respuestas automáticas del bot) enviados dentro de la ventana de atención.
- **Tickets con asesor:** mensajes de servicio (respuestas humanas) enviados dentro de la ventana de atención.
- **Campañas de utilidad:** plantillas de utilidad enviadas a los estudiantes (normalmente fuera de la ventana de atención).
- **Costo total estimado:** escenario combinado que asume que los tres flujos ocurren en el mismo mes, con el mismo volumen y un solo número de negocio. El beneficio de 1.000 mensajes de servicio gratuitos se aplica **una sola vez**.

| Cantidad de mensajes por escenario | Chatbot | Tickets con asesor | Campañas de utilidad | Costo total estimado |
| --- | ---: | ---: | ---: | ---: |
| 100 | $ 0 | $ 0 | $ 295 | $ 295 |
| 500 | $ 0 | $ 0 | $ 1.473 | $ 1.473 |
| 1.000 | $ 0 | $ 0 | $ 2.946 | $ 5.891 |
| 5.000 | $ 11.782 | $ 11.782 | $ 14.728 | $ 41.237 |
| 10.000 | $ 26.510 | $ 26.510 | $ 29.455 | $ 85.420 |
| 20.000 | $ 55.965 | $ 55.965 | $ 58.910 | $ 173.785 |
| 50.000 | $ 144.330 | $ 144.330 | $ 147.275 | $ 438.880 |
| 100.000 | $ 291.605 | $ 291.605 | $ 294.550 | $ 880.705 |

**Todos los valores están expresados en pesos colombianos (COP), redondeados al peso más cercano.**

### 5.2. Metodología de cálculo

**Chatbot y tickets con asesor (mensajes de servicio):**

- Los mensajes del bot y los del asesor son mensajes no plantilla enviados dentro de la ventana de atención. Meta los clasifica como **servicio**.
- Cada número de negocio tiene **1.000 mensajes de servicio gratuitos por mes**. El beneficio no acumula y se reinicia cada mes.
- El costo se calcula así:

  `Costo de servicio = max(0, cantidad de mensajes de servicio − 1.000) × $ 2,9455`

- En la tabla, las columnas Chatbot y Tickets muestran el costo de cada escenario **por separado**, aplicando el beneficio de 1.000 gratis a cada escenario unitario.

**Campañas de utilidad (plantillas de utilidad):**

- Cada plantilla de utilidad entregada se cobra a la tarifa de utilidad.
- Para volúmenes de hasta 100.000 mensajes mensuales, la tarifa es $ 2,9455 COP.
- El costo se calcula así:

  `Costo de utilidad = cantidad de mensajes × $ 2,9455`

**Costo total estimado (escenario combinado):**

- Se asume que los tres flujos ocurren en el mismo mes y con un solo número de negocio.
- El beneficio de 1.000 mensajes de servicio gratuitos se aplica **una sola vez**, compartido entre chatbot y tickets:

  `Servicio combinado = max(0, (mensajes de chatbot + mensajes de tickets) − 1.000) × $ 2,9455`

  `Total = Servicio combinado + Costo de utilidad`

**Ejemplo numérico (1.000 mensajes por escenario):**

- Chatbot: 1.000 mensajes de servicio.
- Tickets: 1.000 mensajes de servicio.
- Servicio total: 2.000 mensajes. Se restan los 1.000 gratuitos: 1.000 mensajes cobrados × $ 2,9455 = **$ 2.945,50**.
- Campañas de utilidad: 1.000 × $ 2,9455 = **$ 2.945,50**.
- **Total estimado: $ 5.891.**

**Nota sobre la suma de escenarios unitarios:** si se sumaran las tres columnas como escenarios completamente independientes (aplicando el beneficio de 1.000 gratis a cada escenario), el resultado sería $ 2.946 COP menor para cantidades de 1.000 o más, porque el beneficio se estaría aplicando dos veces. Para no duplicar el beneficio gratuito, la columna "Costo total estimado" utiliza la fórmula del escenario combinado.

### 5.3. Explicación de la tabla 1

**¿Por qué el chatbot puede costar diferente que una campaña de utilidad?**

Aunque ambos mensajes se cobran a la misma tarifa en Colombia ($ 2,9455 COP), su tratamiento es distinto:

1. **Los mensajes del chatbot son de servicio.** Se envían como respuesta al estudiante dentro de la ventana de atención y se benefician de los primeros 1.000 mensajes gratuitos por mes. Por eso, para volúmenes pequeños (hasta 1.000 mensajes), el chatbot no tiene costo.

2. **Las campañas de utilidad son plantillas.** Se envían de forma masiva, normalmente fuera de la ventana de atención, y **no** se benefician del cupo de 1.000 mensajes gratuitos. Cada mensaje de utilidad se cobra, aunque el volumen sea bajo.

3. **A partir del 1 de octubre de 2026, los mensajes de servicio ya no son gratuitos** (salvo el cupo de 1.000). Este es un cambio reciente que debe considerarse en el presupuesto.

**¿Qué pasa si el chatbot o el asesor envían una plantilla de utilidad dentro de la ventana de atención?**

Si en lugar de responder con texto libre se envía una plantilla de utilidad, el mensaje se clasifica como **utilidad** y se cobra a la tarifa de utilidad, sin beneficiarse del cupo de 1.000 mensajes de servicio gratuitos. Por el contrario, si se envía texto libre dentro de la ventana, se clasifica como **servicio** y sí puede beneficiarse del cupo.

**¿Qué pasa si se envía una plantilla de utilidad fuera de la ventana de atención?**

Se cobra igual: la tarifa de utilidad no depende de si la plantilla se envía dentro o fuera de la ventana. La ventana solo determina si se puede usar texto libre (no plantilla) o si es obligatorio usar una plantilla.

---

## 6. Tabla 2. Campañas de marketing

### 6.1. Presentación de la tabla

Las campañas de marketing son las que tienen un costo más alto por mensaje, porque su tarifa es significativamente superior a la de utilidad y servicio. La siguiente tabla muestra el costo estimado de enviar campañas de marketing a los estudiantes, utilizando la tarifa oficial vigente para Colombia.

| Cantidad de mensajes | Tarifa por mensaje (COP) | Costo total estimado (COP) |
| ---: | ---: | ---: |
| 100 | $ 46,0227 | $ 4.602 |
| 500 | $ 46,0227 | $ 23.011 |
| 1.000 | $ 46,0227 | $ 46.023 |
| 5.000 | $ 46,0227 | $ 230.114 |
| 10.000 | $ 46,0227 | $ 460.227 |
| 20.000 | $ 46,0227 | $ 920.454 |
| 50.000 | $ 46,0227 | $ 2.301.135 |
| 100.000 | $ 46,0227 | $ 4.602.270 |

**Todos los valores están expresados en pesos colombianos (COP), redondeados al peso más cercano.**

### 6.2. Explicación de la tabla 2

**Cálculo:**

`Costo total = cantidad de mensajes entregados × $ 46,0227`

**Reglas aplicables a los mensajes de marketing:**

1. **No hay mensajes gratuitos.** A diferencia de los mensajes de servicio, los mensajes de marketing no tienen un cupo mensual gratuito. Cada mensaje de marketing entregado se cobra.

2. **Solo se cobra si el mensaje se entrega.** Si el estudiante no tiene WhatsApp, bloqueó el número o no aceptó recibir mensajes, el mensaje no se entrega y no se cobra.

3. **Se requiere opt-in.** La institución solo puede enviar plantillas de marketing a estudiantes que hayan aceptado recibir mensajes de WhatsApp.

4. **Se requiere una plantilla de marketing aprobada.** No se puede enviar marketing con texto libre; debe usarse una plantilla de la categoría marketing aprobada por Meta.

5. **No hay descuento por volumen.** La tarifa de marketing es fija por mensaje, independientemente del volumen mensual.

**Diferencia entre plantilla de utilidad y plantilla de marketing:**

| Aspecto | Plantilla de utilidad | Plantilla de marketing |
| --- | --- | --- |
| Contenido | No promocional: confirmaciones, recordatorios, avisos de trámites, actualizaciones. | Promocional: ofertas, invitaciones, promoción de programas, difusión comercial. |
| Tarifa en Colombia | $ 2,9455 COP | $ 46,0227 COP |
| Descuento por volumen | Sí | No |
| ¿Puede incluir promoción? | No. Si incluye promoción, Meta la reclasifica como marketing. | Sí. |
| Ejemplo | "Su solicitud de matrícula fue recibida. Fecha límite: 15 de noviembre." | "¡Matrículas abiertas! Obtenga un 10 % de descuento en programas de posgrado." |

**Advertencia:** Meta revisa el contenido de las plantillas y puede reclasificar una plantilla de utilidad como marketing si detecta contenido promocional. Una plantilla de utilidad que se reclasifica como marketing pasa a cobrarse a la tarifa de marketing ($ 46,0227 COP), lo que representa un aumento de más de 15 veces en el costo por mensaje.

---

## 7. Mensajes gratuitos y ventanas de atención

### 7.1. Los primeros 1.000 mensajes gratuitos

**¿Existe algún volumen mensual gratuito?**

Sí, pero **únicamente para mensajes de servicio**. A partir del 1 de octubre de 2026, cada número de negocio de WhatsApp tiene un cupo de **1.000 mensajes de servicio gratuitos por mes**.

**Condiciones del beneficio:**

- Se aplica **por número de negocio**, no por cuenta de Meta ni por institución. Si la institución usa varios números, cada uno tendrá su propio cupo.
- Se reinicia cada mes (al inicio del mes, según la zona horaria de la cuenta de Meta). **No acumula**: los mensajes no usados no pasan al mes siguiente.
- **No aplica** a mensajes de marketing, utilidad o autenticación.
- **No aplica** a los mensajes de Meta Business Agent.
- Si la cuenta de Meta no tiene un método de pago registrado, Meta entrega los mensajes de servicio dentro del cupo gratuito, pero **no entrega** los mensajes de servicio una vez superado el cupo. Es indispensable registrar un método de pago para garantizar la continuidad del servicio.

**¿Los primeros 1.000 mensajes de marketing tienen algún tratamiento gratuito?**

**No.** Los mensajes de marketing no tienen ningún cupo gratuito. El beneficio de 1.000 mensajes gratuitos es exclusivo de los mensajes de servicio.

**¿Qué pasa con los mensajes derivados de campañas de marketing?**

Si un estudiante responde a una campaña de marketing, su respuesta abre una ventana de servicio de 24 horas. Los mensajes que el negocio envíe dentro de esa ventana (texto libre) se clasifican como **servicio** y pueden beneficiarse del cupo de 1.000 mensajes de servicio gratuitos. Pero esto no significa que los mensajes de marketing originales sean gratuitos: la campaña de marketing se cobró a la tarifa de marketing.

### 7.2. Ventana de servicio al cliente (CSW)

- **Duración:** 24 horas.
- **Se abre:** cuando el estudiante envía un mensaje al negocio (o llama).
- **Se reinicia:** cada vez que el estudiante envía un nuevo mensaje o llamada antes de que expire la ventana.
- **Qué permite:** enviar mensajes no plantilla (texto libre, imágenes, documentos, etc.) al estudiante.
- **Qué no permite:** enviar mensajes de texto libre fuera de la ventana. Fuera de la ventana, solo se pueden enviar plantillas aprobadas.
- **Facturación:** los mensajes no plantilla enviados dentro de la ventana son **servicio**. Se benefician del cupo de 1.000 gratuitos y, a partir del mensaje 1.001, se cobran a la tarifa de servicio ($ 2,9455 COP en Colombia).

### 7.3. Ventana de entrada gratuita (FEP)

- **Requisito:** que el estudiante escriba primero desde un **anuncio que redirige a WhatsApp (Click to WhatsApp)** o desde un botón de llamada a la acción de una página de Facebook, usando un dispositivo Android o iOS.
- **Qué hace:** abre una ventana de entrada gratuita. Mientras está abierta, los mensajes de marketing, utilidad, autenticación o servicio enviados por el negocio **no se cobran**.
- **Duración:** la documentación oficial para desarrolladores vigente (actualizada el 30 de septiembre de 2026) establece que la ventana puede permanecer abierta **hasta 7 días**. La página comercial de WhatsApp menciona 72 horas. **Esta diferencia debe validarse en la consola de Meta de la institución.**
- **Limitaciones:** los mensajes de Meta Business Agent siguen cobrándose. La ventana se rastrea por la pareja negocio-usuario, no por cuenta de Meta; si varias cuentas envían al mismo número, todas comparten la ventana.
- **No aplica** a las campañas de plantillas enviadas desde la API. El FEP solo se origina desde un anuncio Click to WhatsApp.

### 7.4. Ejemplo práctico: campaña de marketing y respuesta del estudiante

**Situación:**

1. Punto TdeA envía una **plantilla de marketing** a un estudiante: "¡Matrículas abiertas! Obtenga un 10 % de descuento en programas de posgrado."
2. El estudiante recibe el mensaje (se entrega). **Costo: $ 46,0227 COP** (tarifa de marketing).
3. El estudiante responde: "¿Cuáles son los programas disponibles?"
4. La respuesta del estudiante **abre una ventana de servicio de 24 horas**.
5. El chatbot o un asesor responde con texto libre: "Los programas disponibles son...". **Este mensaje se clasifica como servicio.** Si el número de negocio aún no ha superado los 1.000 mensajes de servicio del mes, es gratis. Si ya los superó, cuesta $ 2,9455 COP.
6. El estudiante sigue preguntando dentro de las 24 horas. Cada respuesta del negocio es un mensaje de servicio, con el mismo tratamiento.
7. Si el estudiante no responde en 24 horas y el negocio quiere continuar la conversación, debe enviar una **plantilla aprobada** (utilidad o marketing). El costo dependerá de la categoría de la plantilla.

**Conclusión del ejemplo:** la campaña de marketing se cobra a la tarifa de marketing. La respuesta del estudiante no hace gratuitos los mensajes de marketing. Las respuestas del negocio dentro de la ventana son mensajes de servicio, que pueden ser gratuitos solo dentro del cupo mensual de 1.000.

**Sobre la afirmación histórica de la "ventana de 24 horas sin costo" para mensajes derivados de campañas de marketing:** esta afirmación no es una regla universal. La ventana de 24 horas permite enviar mensajes no plantilla sin necesidad de plantilla, pero desde el 1 de octubre de 2026 esos mensajes de servicio se cobran una vez superado el cupo de 1.000 mensajes gratuitos. La ventana gratuita de hasta 7 días (o 72 horas, según la fuente) solo aplica cuando la conversación se origina desde un anuncio Click to WhatsApp.

---

## 8. Impuestos y cargos adicionales

### 8.1. Valores presentados

Todos los valores de este informe son **tarifas base publicadas por Meta**, expresadas en pesos colombianos (COP). **No incluyen** impuestos, retenciones ni cargos adicionales.

### 8.2. Conceptos que deben validarse

| Concepto | Tratamiento en este informe |
| --- | --- |
| Tarifa base de Meta | Incluida (marketing, utilidad, autenticación, servicio). |
| IVA | No incluido. Su aplicabilidad depende de la naturaleza del servicio y de la residencia del proveedor. Debe validarse con la dirección contable. |
| Retención en la fuente | No incluida. Los servicios digitales del exterior pueden estar sujetos a retención. Debe validarse con la dirección contable. |
| Cargos del proveedor o intermediario | No aplican. Punto TdeA se integra directamente con Meta Cloud API, sin BSP. |
| Costos de infraestructura y operación | No incluidos. Servidores, almacenamiento, desarrollo y soporte son costos internos de la institución. |
| Impuestos en publicidad (documento 2) | No incluidos. Los CPM de referencia son valores brutos de subasta. |

### 8.3. Recomendación

Se recomienda que la dirección contable de la institución revise la facturación real de Meta en la consola de facturación (Billing Hub) para determinar los impuestos y retenciones aplicables a cada concepto. Los valores de este informe son una base tarifaria, no una proyección de la factura final.

---

## 9. Consideraciones y supuestos

### 9.1. Supuestos generales

1. **Mercado:** todos los mensajes se envían a números colombianos (+57). Si la institución envía mensajes a números de otros países, la tarifa será la del mercado correspondiente.
2. **Categoría:** los costos se calcularon con las tarifas oficiales de Colombia vigentes al 1 de octubre de 2026.
3. **Entrega:** se asume que el 100 % de los mensajes se entregan. En la práctica, los mensajes no entregados no se cobran, por lo que el costo real podría ser menor.
4. **Moneda:** los valores se expresan en COP. Si la cuenta de Meta factura en USD, el valor en COP dependerá de la tasa de cambio de facturación.
5. **Sin distribución de volumen:** no se asume una proporción fija entre chatbot, tickets y campañas de utilidad. La Tabla 1 presenta escenarios unitarios.
6. **Un solo número de negocio:** se asume que la operación usa un número de WhatsApp. Si se usan varios, cada uno tiene su propio cupo de 1.000 mensajes de servicio gratuitos.
7. **Opt-in:** se asume que los estudiantes han aceptado recibir mensajes de WhatsApp de la institución.
8. **Plantillas aprobadas:** se asume que las plantillas de marketing y utilidad están aprobadas por Meta y que su categoría es correcta.
9. **Sin impuestos:** los valores no incluyen impuestos ni cargos adicionales.
10. **Sin costos de infraestructura:** no se incluyen servidores, licencias, desarrollo ni soporte técnico.

### 9.2. Exclusiones

Este informe no incluye:

- Costos de desarrollo, implementación o mantenimiento de Punto TdeA.
- Costos de infraestructura (servidores, bases de datos, certificados, dominios).
- Costos de publicidad en estados de WhatsApp (se tratan en el documento independiente).
- Costos de llamadas de voz o video (WhatsApp Business Calling API).
- Costos de mensajes de Meta Business Agent.
- Impuestos, retenciones ni cargos de terceros.

### 9.3. Escenarios

Los escenarios de este informe son:

- **Escenario unitario por categoría:** el costo de N mensajes de chatbot, N mensajes de tickets o N mensajes de utilidad, evaluados por separado.
- **Escenario combinado:** los tres flujos ocurren en el mismo mes con el mismo volumen y un solo número de negocio.
- **Escenario de marketing:** N mensajes de marketing, sin cupo gratuito.

---

## 10. Conclusiones y recomendaciones

### 10.1. Conclusiones

1. **El costo de la mensajería de WhatsApp es ahora más sensible al volumen.** El cambio del 1 de octubre de 2026, que restablece el cobro por mensajes de servicio y por plantillas de utilidad enviadas en ventana, convierte al chatbot y a la atención con asesores en partidas presupuestales que antes no existían.

2. **Las campañas de marketing son el costo más alto.** A $ 46,0227 COP por mensaje, una campaña de 10.000 mensajes cuesta $ 460.227 COP, mientras que 10.000 mensajes de utilidad cuestan $ 29.455 COP.

3. **El cupo de 1.000 mensajes de servicio gratuitos es una protección importante, pero limitada.** Para operaciones pequeñas (menos de 1.000 mensajes de servicio al mes), el chatbot y los asesores pueden seguir sin costo. Para operaciones más grandes, cada mensaje adicional cuesta $ 2,9455 COP.

4. **La clasificación correcta de las plantillas es decisiva.** Una plantilla de utilidad que Meta reclasifica como marketing puede multiplicar el costo por 15. La institución debe revisar periódicamente el estado de sus plantillas.

5. **El beneficio de la ventana de entrada gratuita (FEP) es poco aprovechable para campañas masivas.** Solo aplica cuando el estudiante escribe primero desde un anuncio Click to WhatsApp, no desde una campaña de plantillas.

### 10.2. Recomendaciones

1. **Presupuestar los mensajes de servicio.** Incluir en el presupuesto anual una partida para los mensajes de servicio del chatbot y los asesores, considerando el cupo de 1.000 gratuitos por número y por mes.

2. **Medir el volumen real de mensajes.** Implementar un seguimiento mensual de los mensajes por categoría (servicio, utilidad, marketing) para ajustar el presupuesto y detectar desviaciones.

3. **Revisar la clasificación de plantillas.** Auditar las plantillas aprobadas y verificar que no contengan contenido promocional que Meta pueda reclasificar como marketing.

4. **Evaluar el uso de plantillas de utilidad en lugar de texto libre.** Cuando el caso lo permita, las plantillas de utilidad pueden ser más eficientes que el texto libre, porque no dependen de la ventana de atención y su tarifa es baja.

5. **Mantener un método de pago registrado en la consola de Meta.** Sin método de pago, los mensajes de servicio no se entregarán después del cupo gratuito.

6. **Validar los impuestos con contabilidad.** Solicitar a la dirección contable la revisión de la facturación de Meta para determinar IVA, retenciones y su tratamiento.

7. **Capacitar al equipo de campañas.** Asegurar que el equipo comprenda la diferencia entre marketing y utilidad, y el impacto financiero de cada categoría.

8. **Considerar la publicidad en estados como un canal complementario.** Para avisos institucionales de difusión, los estados de WhatsApp pueden ser una alternativa a las campañas de marketing. Su presupuesto se presenta en el documento independiente.

---

## 11. Fuentes oficiales consultadas

Las siguientes fuentes fueron consultadas el **4 de noviembre de 2026**:

1. **Meta for Developers. Pricing on the WhatsApp Business Platform.** Documentación oficial de precios, actualizada el 30 de septiembre de 2026. Incluye el modelo de cobro por mensaje, las categorías, las ventanas de atención, el cupo de 1.000 mensajes de servicio gratuitos y los cambios del 1 de octubre de 2026.
   - https://developers.facebook.com/docs/whatsapp/pricing/

2. **Meta for Developers. Template categorization.** Criterios oficiales para clasificar plantillas como marketing, utilidad o autenticación.
   - https://developers.facebook.com/documentation/business-messaging/whatsapp/templates/template-categorization

3. **WhatsApp Business. Business Platform Pricing.** Página comercial oficial de precios, con tarifas interactivas por mercado y moneda.
   - https://business.whatsapp.com/products/platform-pricing

4. **Servicio REST oficial de tarifas de WhatsApp Business.** Consulta directa de las tarifas de Colombia (mercado CO) en COP, vigentes al 1 de octubre de 2026:
   - https://whatsappbusiness.com/wp-json/wab/v1/pricing?market=CO&currency=COP&category=Marketing
   - https://whatsappbusiness.com/wp-json/wab/v1/pricing?market=CO&currency=COP&category=Utility
   - https://whatsappbusiness.com/wp-json/wab/v1/pricing?market=CO&currency=COP&category=Authentication
   - https://whatsappbusiness.com/wp-json/wab/v1/pricing?market=CO&currency=COP&category=Service

5. **Meta for Developers. Documentación de WhatsApp Business Platform.** Información general sobre la plataforma, plantillas, webhooks y buenas prácticas.
   - https://developers.facebook.com/docs/whatsapp/

6. **Banco de la República. Tasa Representativa del Mercado (TRM).** Consultada el 4 de noviembre de 2026 para referencia cambiaria.
   - https://suameca.banrep.gov.co/estadisticas-economicas/informacionSerie/1/tasa_cambio_peso_colombiano_trm_dolar_usd

7. **Documentación interna de Punto TdeA.** Para la descripción de la integración:
   - `D:\PuntoTdeA\docs\whatsapp-meta.md`
   - `D:\PuntoTdeA\docs\arquitectura.md`
   - `D:\PuntoTdeA\docs\anuncios-status-whatsapp.md`
   - `D:\PuntoTdeA\AGENTS.md`

---

**Fin del documento 1.**
