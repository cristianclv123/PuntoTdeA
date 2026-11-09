# PRESUPUESTO DE DIFUSIÓN DE AVISOS INSTITUCIONALES MEDIANTE ESTADOS DE WHATSAPP
## Punto TdeA – Publicidad en WhatsApp Status (Meta Marketing API)

---

**Institución:** Punto TdeA
**Documento:** Presupuesto de difusión de avisos institucionales mediante estados de WhatsApp (Tabla 3)
**Fecha de elaboración:** 4 de noviembre de 2026
**Fecha de consulta de referencias:** 4 de noviembre de 2026
**Tarifa cambiaria de referencia:** TRM del 4 de noviembre de 2026: $ 3.235,59 COP por USD
**Elaborado para:** Rectoría de la institución
**Alcance:** Estimación presupuestal para difundir avisos institucionales mediante publicidad en estados de WhatsApp. Este documento no modifica código, configuraciones ni bases de datos.

---

## 1. Resumen ejecutivo

El presente documento estima el presupuesto que requeriría la institución para difundir avisos institucionales a los estudiantes mediante **estados de WhatsApp** (también llamados historias). Este mecanismo es **publicidad pagada**, no un envío masivo de mensajes por la API de WhatsApp.

Los hallazgos principales son los siguientes:

1. **Los estados de WhatsApp no se envían como mensajes.** Los avisos en estados son **anuncios publicitarios** que se muestran en la sección de estados de WhatsApp y Instagram, dentro de la plataforma de Meta Ads. No son mensajes que lleguen al chat del estudiante.

2. **No existe una tarifa pública específica para los anuncios en estados de WhatsApp.** Meta no publica un CPM (costo por mil impresiones) exclusivo para este tipo de anuncio. Para este informe se utilizaron referencias de publicidad comparable: Meta Ads en Colombia e Instagram Stories.

3. **El mecanismo disponible en Punto TdeA** es la creación de anuncios en estados de WhatsApp mediante la **Meta Marketing API**, con el placement combinado de Instagram Story y WhatsApp Status. Este mecanismo está implementado en el módulo `announcements` y en el servicio `communications/services/ads_service.py`.

4. **Requisitos para publicar anuncios en estados:**
   - Cuenta de anuncios de Meta con método de pago registrado.
   - Negocio verificado en Meta.
   - Página de Facebook vinculada a la cuenta de WhatsApp.
   - Aplicación de Meta en modo Live (público).
   - Cuenta de Instagram conectada a la página (el placement de estados exige Instagram Story además de WhatsApp Status).
   - Token de usuario con permiso `ads_management` (el token de sistema de WhatsApp no sirve para anuncios).

5. **El presupuesto estimado para el escenario intermedio** (CPM de referencia de USD 7,00, equivalente a $ 22.649 COP) es:

   | Estudiantes objetivo | Presupuesto estimado (COP) |
   | ---: | ---: |
   | 100 | $ 2.174 |
   | 500 | $ 10.872 |
   | 1.000 | $ 21.743 |
   | 5.000 | $ 108.716 |
   | 10.000 | $ 217.432 |
   | 20.000 | $ 434.863 |
   | 50.000 | $ 1.087.158 |
   | 100.000 | $ 2.174.316 |

6. **El alcance no está garantizado.** La publicidad en estados no permite asegurar que un número determinado de estudiantes verá el aviso. El alcance real depende de la segmentación, la calidad del creativo, la competencia en la subasta, la temporada y la disponibilidad de inventario publicitario.

7. **Los estados orgánicos** (publicaciones gratuitas desde la app de WhatsApp Business) son una alternativa sin costo directo, pero no garantizan alcance ni permiten segmentación, y no se gestionan desde la API de WhatsApp de Punto TdeA.

8. **Los valores de este documento no incluyen impuestos ni cargos adicionales.** Los CPM de referencia son valores brutos de subasta y deben validarse con la cuenta publicitaria real de la institución.

---

## 2. Objetivo

El objetivo de este documento es estimar el presupuesto que requeriría la institución para difundir avisos institucionales a los estudiantes mediante estados de WhatsApp, en diferentes escenarios de alcance y costo publicitario.

El documento también explica las alternativas de difusión que ofrece Meta para los estados de WhatsApp, las limitaciones del mecanismo disponible en Punto TdeA y la comparación con otras formas de comunicación institucional.

---

## 3. Alternativas de difusión en estados de WhatsApp

### 3.1. ¿Qué son los estados de WhatsApp?

Los estados de WhatsApp son publicaciones (imágenes, texto, video) que desaparecen después de 24 horas, similares a las historias de Instagram. Se muestran en la pestaña "Estados" de la aplicación.

Existen dos formas de publicar en estados:

1. **Estados orgánicos:** publicaciones gratuitas que se crean desde la aplicación de WhatsApp Business del número de la institución. Se muestran a los contactos que tengan el número guardado y no hayan silenciado el estado. No se pueden segmentar y no garantizan alcance.

2. **Anuncios en estados de WhatsApp:** publicidad pagada que se muestra en la sección de estados de los usuarios de WhatsApp e Instagram. Se gestionan a través de la plataforma de Meta Ads.

### 3.2. Mecanismo disponible en Punto TdeA

Punto TdeA implementa la creación de **anuncios en estados de WhatsApp** mediante la **Meta Marketing API**, a través del módulo `announcements` y del servicio `communications/services/ads_service.py`. Las características técnicas son:

| Aspecto | Configuración |
| --- | --- |
| Tipo de campaña | Anuncio publicitario (no envío de mensajes). |
| Placement | Instagram Story + WhatsApp Status. |
| Objetivo de optimización | CONVERSATIONS (conversaciones de WhatsApp). |
| Evento de facturación | IMPRESSIONS (impresiones). |
| Tipo de destino | WHATSAPP. |
| Llamada a la acción | WHATSAPP_MESSAGE. |
| Audiencia | Audiencia personalizada cargada con teléfonos hasheados (SHA-256) o público amplio. |
| Presupuesto | Diario, configurado en el ad set. |
| Estado inicial | PAUSED (pausado, no gasta hasta activarse). |

**Importante:** este mecanismo **no es un envío de mensajes por WhatsApp Cloud API**. No genera mensajes en el chat del estudiante. Muestra un anuncio en la sección de estados, y el estudiante puede decidir tocar el anuncio para iniciar una conversación de WhatsApp con la institución.

### 3.3. Alternativas que no se pueden ejecutar mediante la API de Punto TdeA

| Alternativa | ¿Disponible en Punto TdeA? | Observación |
| --- | --- | --- |
| Publicidad en estados de WhatsApp | Sí | Mediante Meta Marketing API (anuncios en estados). |
| Anuncios que redirigen a WhatsApp (Click to WhatsApp) | No implementado | Sería otra campaña publicitaria, no un envío por API. |
| Publicaciones orgánicas en estados | No | Se publican desde la app de WhatsApp Business, no desde la API. |
| Envío masivo de mensajes por API | No es este mecanismo | Es el canal de campañas de plantillas (documento 1). |
| Publicar estados directamente desde la Cloud API | No existe | Meta no ofrece API para publicar estados. |

### 3.4. Limitaciones del mecanismo

1. **No garantiza la llegada a un número específico de estudiantes.** La entrega depende de la subasta publicitaria y del inventario disponible.
2. **No permite segmentar directamente por una base de datos de estudiantes sin cargar una audiencia personalizada.** La institución debe cargar los teléfonos hasheados en una audiencia de Meta Ads. La entrega queda sujeta a que Meta encuentre coincidencias y a que los estudiantes no hayan desactivado la visibilidad de estados.
3. **No todos los estudiantes tienen WhatsApp activo ni ven los estados.** No se puede asumir que el 100 % del objetivo verá el anuncio.
4. **Requiere inversión publicitaria continua.** Sin presupuesto, el anuncio no se muestra.
5. **Requiere configuración adicional:** cuenta de anuncios, método de pago, negocio verificado, página vinculada, app en modo Live y cuenta de Instagram conectada.
6. **El CPM no es una tarifa fija.** Depende de la subasta en tiempo real y varía según la segmentación, la calidad del creativo, la temporada y el objetivo de la campaña.

---

## 4. Metodología

### 4.1. Enfoque

Para estimar el presupuesto se utilizó el siguiente enfoque:

1. **Identificar el mecanismo disponible:** publicidad en estados de WhatsApp mediante Meta Marketing API.
2. **Determinar la métrica de costo:** CPM (costo por mil impresiones), que es la métrica de facturación configurada en los anuncios de Punto TdeA (billing event IMPRESSIONS).
3. **Buscar referencias de CPM en Colombia:** se consultaron fuentes de la industria publicitaria y reportes de herramientas de análisis de Meta Ads.
4. **Definir escenarios de planificación:** conservador, intermedio y alto, basados en las referencias encontradas.
5. **Convertir a pesos colombianos:** se utilizó la TRM del 4 de noviembre de 2026 ($ 3.235,59 COP por USD).
6. **Calcular el presupuesto:** se aplicó el CPM a las impresiones estimadas necesarias para alcanzar el objetivo de estudiantes.

### 4.2. ¿Qué es el CPM?

**CPM** son las siglas de "Costo por Mil Impresiones" (Cost Per Mille). Es el valor que el anunciante paga por cada 1.000 veces que se muestra su anuncio.

**Ejemplo:** si el CPM es de $ 22.649 COP y el anuncio se muestra 10.000 veces, el costo es:

`10.000 impresiones ÷ 1.000 × $ 22.649 = $ 226.490 COP`

**Diferencia entre impresiones, alcance y estudiantes únicos:**

| Concepto | Definición |
| --- | --- |
| **Impresión** | Cada vez que el anuncio se muestra a un usuario. Un mismo estudiante puede generar varias impresiones si ve el anuncio varias veces. |
| **Alcance** | El número de usuarios únicos que vieron el anuncio al menos una vez. |
| **Estudiantes únicos** | La cantidad de estudiantes diferentes que se quiere alcanzar. Cada estudiante se cuenta una sola vez, aunque vea el anuncio varias veces. |

**Frecuencia:** es el número promedio de veces que cada estudiante ve el anuncio. Si la frecuencia es 1,2, significa que en promedio cada estudiante lo ve 1,2 veces. Una frecuencia alta puede hacer que el anuncio se muestre muchas veces a las mismas personas, lo que puede aumentar el cansancio publicitario.

### 4.3. Fuentes de referencia de CPM

Las siguientes fuentes fueron consultadas el 4 de noviembre de 2026:

| Fuente | Referencia | Valor |
| --- | --- | --- |
| Superads (Facebook Ads CPM Benchmarks in Colombia) | Media de 13 meses (noviembre 2025 – octubre 2026), todas las industrias, Colombia. | USD 3,20 por mil impresiones. |
| Consolidación Digital (¿Cuánto cuesta hacer publicidad en Meta Ads en Colombia?) | Rango de CPM para Colombia, abril de 2026. | USD 4 a USD 12 por mil impresiones. |
| Referencias de Instagram Stories (karolakarlson.com, influee.co) | CPM de Instagram Stories a nivel internacional, 2026. | USD 6 a USD 10 por mil impresiones. |

**Nota importante:** estas referencias son de **Meta Ads en general e Instagram Stories**, no del placement específico de WhatsApp Status. Meta no publica un CPM oficial para los anuncios en estados de WhatsApp. Los valores de este documento son **estimaciones de planificación** y no tarifas garantizadas.

### 4.4. Escenarios de planificación

Se definieron tres escenarios basados en las referencias anteriores:

| Escenario | CPM de referencia (USD) | CPM de referencia (COP) | Fundamento |
| --- | ---: | ---: | --- |
| **Conservador** | USD 3,20 | $ 10.354 | Media de 13 meses de CPM en Colombia (Superads). |
| **Intermedio** | USD 7,00 | $ 22.649 | Valor intermedio entre el rango de Meta Ads Colombia (USD 4–12) y el rango de Instagram Stories (USD 6–10). |
| **Alto** | USD 12,00 | $ 38.827 | Límite superior del rango de Meta Ads Colombia (Consolidación Digital). |

**Conversión a COP:** TRM del 4 de noviembre de 2026 = $ 3.235,59 COP por USD.

### 4.5. Supuestos de planificación

Para calcular los presupuestos se utilizaron los siguientes supuestos:

1. **Alcance estimado:** el 80 % del número de estudiantes objetivo verá el anuncio al menos una vez. Este es un supuesto de planificación, no una garantía.
2. **Frecuencia estimada:** cada estudiante alcanzado verá el anuncio 1,2 veces en promedio.
3. **Impresiones estimadas:** `estudiantes objetivo × 80 % × 1,2`.
4. **Presupuesto estimado:** `impresiones estimadas ÷ 1.000 × CPM`.
5. **Costo por estudiante alcanzado:** `presupuesto estimado ÷ (estudiantes objetivo × 80 %)`.

**Nota:** el costo por estudiante alcanzado depende del CPM y de la frecuencia, no del porcentaje de alcance. Si la frecuencia es constante, el costo por estudiante alcanzado es el mismo en todos los rangos de estudiantes objetivo.

---

## 5. Tabla 3. Presupuesto estimado de difusión de avisos institucionales

La siguiente tabla muestra el escenario **intermedio** (CPM de USD 7,00 / $ 22.649 COP) para diferentes cantidades de estudiantes objetivo.

| Número de estudiantes objetivo | Alcance estimado | CPM estimado (COP) | Presupuesto estimado (COP) | Costo por estudiante alcanzado (COP) |
| ---: | ---: | ---: | ---: | ---: |
| 100 | 80 | $ 22.649 | $ 2.174 | $ 27 |
| 500 | 400 | $ 22.649 | $ 10.872 | $ 27 |
| 1.000 | 800 | $ 22.649 | $ 21.743 | $ 27 |
| 5.000 | 4.000 | $ 22.649 | $ 108.716 | $ 27 |
| 10.000 | 8.000 | $ 22.649 | $ 217.432 | $ 27 |
| 20.000 | 16.000 | $ 22.649 | $ 434.863 | $ 27 |
| 50.000 | 40.000 | $ 22.649 | $ 1.087.158 | $ 27 |
| 100.000 | 80.000 | $ 22.649 | $ 2.174.316 | $ 27 |

**Notas:**

- **Alcance estimado:** se asume que el 80 % de los estudiantes objetivo verá el anuncio al menos una vez. El valor de la columna corresponde al número de estudiantes alcanzados (80 % del objetivo).
- **CPM estimado:** escenario intermedio (USD 7,00 por mil impresiones, convertido a $ 22.649 COP).
- **Presupuesto estimado:** calculado con una frecuencia de 1,2 impresiones por estudiante alcanzado.
- **Costo por estudiante alcanzado:** resultado de dividir el presupuesto estimado entre el número de estudiantes alcanzados.
- **Los valores están redondeados al peso colombiano más cercano.**

**Ejemplo de cálculo (10.000 estudiantes objetivo):**

1. Alcance estimado: 10.000 × 80 % = 8.000 estudiantes.
2. Impresiones estimadas: 8.000 × 1,2 = 9.600 impresiones.
3. Presupuesto estimado: 9.600 ÷ 1.000 × $ 22.649 = $ 217.432 COP.
4. Costo por estudiante alcanzado: $ 217.432 ÷ 8.000 = $ 27,18 COP.

---

## 6. Tabla 3B. Tres escenarios presupuestales

La siguiente tabla muestra el presupuesto estimado para los tres escenarios (conservador, intermedio y alto), con los mismos supuestos de alcance y frecuencia.

| Número de estudiantes objetivo | Presupuesto conservador (COP) | Presupuesto intermedio (COP) | Presupuesto alto (COP) |
| ---: | ---: | ---: | ---: |
| 100 | $ 994 | $ 2.174 | $ 3.727 |
| 500 | $ 4.970 | $ 10.872 | $ 18.637 |
| 1.000 | $ 9.940 | $ 21.743 | $ 37.274 |
| 5.000 | $ 49.699 | $ 108.716 | $ 186.370 |
| 10.000 | $ 99.397 | $ 217.432 | $ 372.740 |
| 20.000 | $ 198.795 | $ 434.863 | $ 745.480 |
| 50.000 | $ 496.987 | $ 1.087.158 | $ 1.863.700 |
| 100.000 | $ 993.973 | $ 2.174.316 | $ 3.727.400 |

**CPM de cada escenario:**

| Escenario | CPM (COP) | Costo por estudiante alcanzado (COP) |
| --- | ---: | ---: |
| Conservador | $ 10.354 | $ 12 |
| Intermedio | $ 22.649 | $ 27 |
| Alto | $ 38.827 | $ 47 |

**Interpretación:**

- El **escenario conservador** utiliza el CPM más bajo de las referencias (USD 3,20), cercano a la media de 13 meses de CPM en Colombia.
- El **escenario intermedio** utiliza un CPM de USD 7,00, que representa un valor razonable para planificar campañas en Colombia.
- El **escenario alto** utiliza el límite superior del rango de referencias (USD 12,00), aplicable a segmentaciones muy específicas, sectores competitivos o temporadas de alta demanda publicitaria.

---

## 7. Limitaciones y supuestos

### 7.1. Limitaciones

1. **No existe una tarifa pública específica para los anuncios en estados de WhatsApp.** Los CPM utilizados son referencias de publicidad comparable (Meta Ads Colombia e Instagram Stories), no tarifas oficiales de Meta para este placement.
2. **El CPM real es dinámico.** Depende de la subasta en tiempo real, la competencia, la calidad del creativo, la segmentación, la temporada y el objetivo de la campaña. Los valores de este documento son estimaciones de planificación.
3. **El alcance no está garantizado.** No se puede asegurar que un número determinado de estudiantes verá el anuncio. La entrega depende de la disponibilidad de inventario y del comportamiento de los usuarios.
4. **No todos los estudiantes tienen WhatsApp activo ni ven los estados.** El porcentaje de alcance real puede ser inferior al 80 % supuesto.
5. **La segmentación por base de datos tiene limitaciones.** Para llegar a una lista específica de estudiantes, es necesario cargar sus teléfonos hasheados en una audiencia personalizada de Meta Ads. La entrega está sujeta a que Meta encuentre coincidencias y a que los estudiantes no hayan desactivado la visibilidad de estados.
6. **Los anuncios en estados no reemplazan el envío de mensajes.** Un anuncio en estados puede generar una conversación de WhatsApp, pero no garantiza que el estudiante la inicie.
7. **Se requiere inversión publicitaria continua.** Sin presupuesto, el anuncio no se muestra.
8. **Los valores no incluyen impuestos ni cargos adicionales.** Los CPM son valores brutos de subasta.

### 7.2. Supuestos

1. **Alcance estimado:** 80 % del número de estudiantes objetivo.
2. **Frecuencia estimada:** 1,2 impresiones por estudiante alcanzado.
3. **CPM de referencia:** conservador USD 3,20; intermedio USD 7,00; alto USD 12,00.
4. **TRM:** $ 3.235,59 COP por USD (4 de noviembre de 2026).
5. **Estudiantes objetivo:** rangos hipotéticos de 100 a 100.000, no corresponden a la base real de estudiantes de la institución.
6. **Sin costos de producción:** no se incluyen costos de diseño, fotografía, video ni producción del creativo.
7. **Sin impuestos:** los valores son brutos, antes de impuestos y cargos adicionales.

---

## 8. Comparación de modalidades de comunicación institucional

A continuación se comparan las cuatro modalidades disponibles para comunicar avisos a los estudiantes:

| Modalidad | ¿Qué es? | Ventajas | Limitaciones | Costo |
| --- | --- | --- | --- | --- |
| **Mensajes individuales mediante WhatsApp Business Platform** | Plantillas de utilidad o marketing, o mensajes de servicio dentro de la ventana de atención. | Comunicación directa en el chat del estudiante. Ideal para trámites, confirmaciones y atención personalizada. | Requiere plantilla aprobada o ventana de atención abierta. El marketing es costoso ($ 46,0227 COP/mensaje). | Utilidad: $ 2,9455 COP/mensaje. Servicio: $ 2,9455 COP (tras 1.000 gratis/mes). Marketing: $ 46,0227 COP/mensaje. |
| **Campañas de marketing mediante plantillas** | Envío masivo de plantillas de marketing a estudiantes que aceptaron recibir mensajes. | Alto alcance, ideal para promoción de matrículas, eventos y programas. | Costo alto por mensaje. Riesgo de reclasificación si el contenido no es claramente marketing. | $ 46,0227 COP/mensaje. |
| **Publicidad en estados de WhatsApp** | Anuncios en la sección de estados de WhatsApp e Instagram, gestionados con Meta Ads. | Formatos visuales atractivos, alcance amplio, posibilidad de segmentación por audiencia. | No garantiza llegada a un número específico de estudiantes. Requiere inversión publicitaria y configuración adicional. | CPM de referencia: USD 3,20–12,00 ($ 10.354–38.827 COP por mil impresiones). |
| **Estados orgánicos desde WhatsApp Business** | Publicaciones gratuitas en el estado del número de la institución, visibles para los contactos. | Sin costo directo. Fácil de publicar desde la app. | No permite segmentación. No garantiza alcance ni visualización. No se gestiona desde la API de Punto TdeA. | Gratuito (sin costo de publicidad). |

### 8.1. ¿Cuál es la modalidad más conveniente?

No existe una modalidad única que sea mejor en todos los casos. La elección depende del objetivo de la comunicación:

- **Para avisos operativos y trámites** (confirmaciones, recordatorios, vencimientos): los **mensajes individuales de utilidad** son los más adecuados, porque son directos, de bajo costo y no requieren inversión publicitaria.
- **Para promoción de matrículas, eventos o programas**: las **campañas de marketing por plantillas** son las más directas, aunque las más costosas. Los estados de WhatsApp pueden ser un complemento visual para generar conciencia.
- **Para avisos institucionales de difusión masiva**: los **estados de WhatsApp** (publicidad) pueden ser una alternativa visual y de amplio alcance, pero sin garantía de llegada individual. Su costo depende del CPM y del presupuesto.
- **Para presencia orgánica y comunicación cercana**: los **estados orgánicos** son gratuitos y fáciles de usar, pero no garantizan alcance ni permiten segmentación.

**Recomendación general:** combinar las modalidades según el objetivo. Utilizar mensajes de utilidad para la operación diaria, campañas de marketing para la promoción y estados de WhatsApp como complemento de difusión visual. Mantener los estados orgánicos como canal de presencia institucional sin costo.

---

## 9. Conclusiones y recomendaciones

### 9.1. Conclusiones

1. **Los estados de WhatsApp son publicidad, no mensajería.** No deben confundirse con el envío masivo de mensajes por la API. Su objetivo es mostrar un aviso en la sección de estados, no entregar un mensaje en el chat del estudiante.

2. **No existe una tarifa pública específica para los anuncios en estados de WhatsApp.** Los presupuestos de este documento se basan en referencias de publicidad comparable (Meta Ads Colombia e Instagram Stories), que son estimaciones de planificación.

3. **El presupuesto estimado para el escenario intermedio** varía desde $ 2.174 COP para 100 estudiantes objetivo hasta $ 2.174.316 COP para 100.000 estudiantes objetivo, con un CPM de $ 22.649 COP.

4. **El alcance no está garantizado.** La publicidad en estados no permite asegurar que un número determinado de estudiantes verá el aviso. El alcance real depende de la subasta, la segmentación y el comportamiento de los usuarios.

5. **La publicidad en estados requiere configuración adicional:** cuenta de anuncios, método de pago, negocio verificado, página vinculada, app en modo Live y cuenta de Instagram conectada.

6. **Los estados orgánicos son una alternativa gratuita**, pero sin garantía de alcance ni segmentación.

### 9.2. Recomendaciones

1. **Definir el objetivo de la comunicación antes de elegir el canal.** No todas las comunicaciones requieren publicidad. Los avisos operativos se gestionan mejor con mensajes de utilidad; los avisos de promoción, con campañas de marketing; los avisos de difusión visual, con estados.

2. **Presupuestar los anuncios en estados como una partida independiente.** Considerar los tres escenarios (conservador, intermedio, alto) y seleccionar el que mejor se ajuste al apetito de gasto y a la urgencia del aviso.

3. **Iniciar con un presupuesto de prueba.** Se recomienda comenzar con un presupuesto moderado, medir el CPM real y el alcance obtenido, y ajustar la estrategia antes de escalar.

4. **Cargar la base de estudiantes como audiencia personalizada.** Para llegar a los estudiantes de la institución, es necesario cargar los teléfonos hasheados en una audiencia de Meta Ads. Verificar que la base cumpla las normas de privacidad y consentimiento.

5. **Mantener la cuenta publicitaria al día.** Registrar el método de pago, verificar el negocio y mantener la aplicación en modo Live para evitar interrupciones en la entrega.

6. **Medir los resultados.** Revisar el CPM real, el alcance, la frecuencia y las conversaciones generadas. Comparar estos indicadores con los de otros canales (mensajes de utilidad, campañas de marketing).

7. **Validar los impuestos con contabilidad.** Solicitar a la dirección contable la revisión de los cargos publicitarios para determinar IVA, retenciones y su tratamiento.

8. **Capacitar al equipo de comunicaciones.** Asegurar que el equipo comprenda la diferencia entre mensajería, publicidad en estados y estados orgánicos.

---

## 10. Fuentes

Las siguientes fuentes fueron consultadas el **4 de noviembre de 2026**:

1. **Meta for Developers. Pricing on the WhatsApp Business Platform.** Documentación oficial de precios y modelo de cobro por mensaje.
   - https://developers.facebook.com/docs/whatsapp/pricing/

2. **WhatsApp Business. Business Platform Pricing.** Página comercial oficial de precios.
   - https://business.whatsapp.com/products/platform-pricing

3. **Meta for Business. Ads in Status and Channels.** Información oficial sobre publicidad en estados de WhatsApp.
   - https://whatsappbusiness.com/whatsapp-ads/

4. **Meta for Developers. WhatsApp Business Management API.** Documentación de la API de anuncios y plantillas.
   - https://developers.facebook.com/docs/whatsapp/

5. **Superads. Facebook Ads CPM Benchmarks in Colombia (2026).** Media de 13 meses de CPM en Colombia (noviembre 2025 – octubre 2026).
   - https://www.superads.ai/facebook-ads-costs/cpm-cost-per-mille/colombia

6. **Consolidación Digital. ¿Cuánto cuesta hacer publicidad en Meta Ads en Colombia? Precios reales 2026.** Rango de CPM para Colombia (abril de 2026).
   - https://www.consolidaciondigital.com/blog/performance-marketing/cuanto-cuesta-meta-ads-colombia

7. **Karola Karlson. Instagram Ads Cost in 2026: Real CPC & CPM Benchmarks.** Referencia de CPM de Instagram Stories.
   - https://karolakarlson.com/instagram-ads-cost-and-bidding/

8. **Influee. How Much Do Instagram Ads Cost in 2026? CPC, CPM.** Referencia de CPM de Instagram Stories.
   - https://influee.co/blog/how-much-do-instagram-ads-cost

9. **Banco de la República. Tasa Representativa del Mercado (TRM).** Consultada el 4 de noviembre de 2026.
   - https://suameca.banrep.gov.co/estadisticas-economicas/informacionSerie/1/tasa_cambio_peso_colombiano_trm_dolar_usd

10. **Documentación interna de Punto TdeA.** Para la descripción del mecanismo de anuncios en estados:
    - `D:\PuntoTdeA\docs\anuncios-status-whatsapp.md`
    - `D:\PuntoTdeA\docs\modulos\announcements.md`
    - `D:\PuntoTdeA\communications\services\ads_service.py`

---

**Fin del documento 2.**
