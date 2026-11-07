# Presupuesto de Difusión de Avisos Institucionales

## Mediante Estados de WhatsApp — Punto TdeA

**Destinatario:** Rectoría de Punto TdeA  
**Elaborado por:** Consultoría financiera y tecnológica  
**Fecha:** 4 de noviembre de 2026  
**Versión:** 1.0  
**Moneda:** Pesos colombianos (COP)  
**Clasificación:** Documento de trabajo — uso interno

> **Advertencia metodológica.** Este documento estima un presupuesto de **publicidad** en el placement de estados de WhatsApp. No es un presupuesto de mensajería por API. Meta no publica una tarifa de CPM para este placement: el costo se determina en una subasta. Los valores de CPM, frecuencia y alcance son supuestos de planificación, no tarifas oficiales. Los impuestos no se incluyen y quedan pendientes de validación contable.

---

## Ficha técnica

| Elemento | Detalle |
|---|---|
| Documento | Presupuesto de avisos institucionales mediante estados de WhatsApp |
| Alcance | Publicidad en el placement de WhatsApp Status, con destino a WhatsApp o sitio web |
| Documento complementario | Informe general de costos de mensajería |
| Mecanismo | Meta Ads / Marketing API, no Cloud API |
| Fuente principal | Documentación oficial de Meta sobre anuncios en estados |
| Fecha de consulta | 3 y 4 de noviembre de 2026 |
| Método | Presupuesto por impresiones, con escenarios de CPM, frecuencia y alcance |
| Redondeo | Cálculos con precisión completa; presentación al peso |

---

## Resumen ejecutivo

Punto TdeA quiere estimar cuánto costaría difundir avisos institucionales a distintos volúmenes de estudiantes utilizando los **estados de WhatsApp**. La primera conclusión es de alcance: **los estados de WhatsApp no son un canal de envío masivo de mensajes**. Son un espacio de publicidad de Meta Ads. La Cloud API que usa Punto TdeA para el chatbot y las campañas **no puede publicar estados** ni garantizar que un estado sea visto por un número determinado de estudiantes.

Las tres vías reales son:

1. **Anuncios en estados (Ads in Status):** publicidad pagada, gestionada desde Meta Ads o la Marketing API. Se cobra por impresiones, en subasta. Es la única vía que permite ampliar el alcance más allá de los contactos.
2. **Anuncios Click to WhatsApp:** un tipo de anuncio que puede aparecer en el estado y lleva al usuario a una conversación de WhatsApp. Se paga como publicidad, no como mensaje.
3. **Estados orgánicos:** publicaciones gratuitas desde la app de WhatsApp Business. Solo las ven los contactos que tienen guardado el número y según la configuración de privacidad. No se automatizan con la Cloud API y no garantizan alcance.

Meta no publica una tarifa de CPM específica para los estados. El costo depende de la subasta, la audiencia, la competencia, la temporada, el creativo, la frecuencia y la duración. Para presupuestar se usan escenarios de planificación basados en referencias del mercado colombiano.

### Cifras de referencia

| Escenario | 100.000 estudiantes | Costo por estudiante |
|---|---:|---:|
| Conservador | $ 1.647.059 | $ 16 |
| Intermedio | $ 4.800.000 | $ 48 |
| Alto | $ 13.333.333 | $ 133 |

Estas cifras **no son tarifas oficiales**. Son estimaciones con supuestos explícitos. El presupuesto real debe recalibrarse con los primeros resultados de la cuenta.

### Hallazgo principal

Para listas pequeñas y conocidas, la mensajería directa con plantillas es más barata y controlable. Para audiencias grandes, los anuncios en estados pueden ser competitivos, pero no garantizan que todos los estudiantes vean el aviso. La decisión depende del objetivo: **entrega garantizada a una lista** o **alcance amplio con menor control**.

---

## 1. Objetivo y alcance

### 1.1 Objetivo

Estimar el presupuesto necesario para difundir avisos institucionales a diferentes cantidades de estudiantes mediante los estados de WhatsApp, explicando:

- Qué mecanismos existen realmente.
- Cuáles se pueden ejecutar con la integración de Punto TdeA.
- Cuáles no.
- Cómo se calcula un presupuesto de publicidad.
- Qué limitaciones tiene el alcance.
- Cuándo conviene usar publicidad y cuándo conviene usar mensajería directa.

### 1.2 Alcance

El documento cubre el placement de **WhatsApp Status** dentro de Meta Ads, con destino a una conversación de WhatsApp o a un sitio web. Se apoya en la implementación documentada en el proyecto Punto TdeA:

- `publisher_platforms`: `["instagram", "whatsapp"]`
- `instagram_positions`: `["story"]`
- `whatsapp_positions`: `["status"]`
- `objective`: `OUTCOME_ENGAGEMENT`
- `optimization_goal`: `CONVERSATIONS`
- `billing_event`: `IMPRESSIONS`
- `bid_strategy`: `LOWEST_COST_WITHOUT_CAP`
- Estado por defecto: `PAUSED`
- Presupuesto diario por defecto: $ 2.000.000 COP

### 1.3 Exclusiones

No forman parte de este documento:

- El costo de los mensajes de WhatsApp enviados por Cloud API. Se tratan en el Documento 1.
- El IVA, las retenciones y el GMF. Quedan pendientes de validación contable.
- La producción de creativos, la gestión de campañas y el personal.
- La inversión en otras plataformas publicitarias.
- La compra de bases de datos o la consecución de consentimientos.

---

## 2. Qué son los estados de WhatsApp y qué se puede hacer

### 2.1 Tres conceptos que no deben confundirse

| Concepto | Qué es | Quién lo controla | Costo | Alcance |
|---|---|---|---|---|
| Estado orgánico | Publicación de foto, video o texto que dura 24 horas | La app de WhatsApp Business | Gratis | Contactos que guarden el número y según privacidad |
| Anuncio en estado | Anuncio pagado que aparece entre los estados | Meta Ads / Marketing API | Subasta por impresiones | Audiencia segmentada; no garantizado |
| Mensaje de Cloud API | Mensaje directo a un número | Cloud API | Por mensaje entregado | Número específico con opt-in |

**La diferencia es esencial.** Un estado orgánico no es un mensaje masivo. Un anuncio en estado no es un mensaje. Un mensaje de Cloud API no aparece en el estado.

### 2.2 Estado orgánico

La app de WhatsApp Business permite publicar estados que duran 24 horas. Son visibles para los contactos que tienen guardado el número de la institución y según la configuración de privacidad (todos los contactos, mis contactos excepto, solo compartir con, etc.).

Ventajas:

- Es gratuito.
- Es inmediato.
- Sirve para mantener presencia entre los contactos.

Limitaciones:

- No se puede automatizar con la Cloud API.
- No se puede segmentar por base de datos.
- No hay garantía de que los estudiantes lo vean.
- No hay métricas comparables a las de un anuncio.
- Solo llega a quienes tienen el número guardado y no lo han restringido.
- No es un canal de difusión masiva.

### 2.3 Anuncio en estado (Ads in Status)

Meta permite mostrar anuncios en la pestaña Novedades de WhatsApp, entre los estados orgánicos. Los anuncios pueden llevar a una conversación de WhatsApp, a un sitio web o, próximamente, a una app.

Ventajas:

- Permite ampliar el alcance más allá de los contactos.
- Se integra con Meta Ads y la Marketing API.
- Permite segmentar por ubicación, edad, intereses y audiencias personalizadas.
- Se puede medir por impresiones, alcance, frecuencia y conversaciones.

Limitaciones:

- Es publicidad pagada.
- No garantiza que un estudiante específico vea el anuncio.
- No permite segmentar directamente por “estudiante de Punto TdeA”; se requieren audiencias personalizadas u otros criterios.
- El inventario es limitado y la subasta varía.
- Requiere cuenta publicitaria, medio de pago y configuración adicional.
- Los anuncios no están cifrados de extremo a extremo, aunque los mensajes personales sí.

### 2.4 Cloud API

La Cloud API envía mensajes directos a números de WhatsApp. Es el mecanismo que usa Punto TdeA para el chatbot, los tickets y las campañas.

Ventajas:

- Entrega directa a un número con opt-in.
- Medición de entrega y lectura.
- Automatización completa.
- Plantillas aprobadas.

Limitaciones:

- No publica estados.
- No garantiza lectura.
- Requiere opt-in y plantillas para iniciar conversaciones.
- Tiene costo por mensaje entregado.
- Fuera de la ventana de 24 horas, requiere plantilla.

### 2.5 Lo que no se puede hacer

- **Publicar un estado desde la Cloud API.** No existe esa función.
- **Garantizar que un estado sea visto por N estudiantes.** La publicidad se compra por impresiones, no por personas garantizadas.
- **Segmentar directamente por la base de datos de estudiantes.** Meta no tiene un criterio “estudiante de Punto TdeA”. Se puede cargar una audiencia personalizada con teléfonos hasheados, sujeta a consentimiento y a la tasa de coincidencia.
- **Usar el token de WhatsApp para crear anuncios.** Se requiere un token con `ads_management`.
- **Publicar un estado orgánico de forma automática desde el backend.** La app de WhatsApp Business es manual.

### 2.6 Modalidades oficiales disponibles

| Modalidad | Disponible | Mecanismo | Uso recomendado |
|---|---|---|---|
| Anuncio en estado | Sí | Meta Ads / Marketing API | Alcance amplio |
| Anuncio Click to WhatsApp | Sí | Meta Ads | Llevar tráfico a una conversación |
| Estado orgánico | Sí | App de WhatsApp Business | Presencia entre contactos |
| Canal promocionado | Anunciado por Meta, no disponible de forma general | Meta Ads | No aplica al alcance actual |
| Envío masivo de estados por API | No | — | No existe |

---

## 3. Cómo funciona la publicidad en estados

### 3.1 Subasta y CPM

Meta no fija un precio por ver un anuncio. El anunciante compra **impresiones** en una subasta. El costo por mil impresiones se conoce como **CPM** (cost per mille).

El CPM depende de:

- La audiencia y su tamaño.
- La competencia por esa audiencia.
- La temporada (por ejemplo, Q4 suele ser más caro).
- La calidad y relevancia del creativo.
- La frecuencia y la duración.
- El objetivo de la campaña.
- El inventario disponible en el placement.

Por eso no existe una tarifa oficial de CPM para estados. Cualquier cifra debe tratarse como un supuesto de planificación.

### 3.2 Impresiones, alcance y frecuencia

| Métrica | Definición | Ejemplo |
|---|---|---|
| Impresión | Una vez que el anuncio se muestra | Un estudiante ve el anuncio tres veces = 3 impresiones |
| Alcance | Personas únicas que vieron el anuncio al menos una vez | 100 estudiantes únicos |
| Frecuencia | Promedio de impresiones por persona alcanzada | 3 impresiones / 1 persona = frecuencia 3 |
| CPM | Costo por mil impresiones | $ 12.000 por 1.000 impresiones |

**Impresiones ≠ alcance ≠ estudiantes únicos.** Un presupuesto puede generar muchas impresiones y pocas personas únicas si la frecuencia es alta. Por eso el presupuesto debe dimensionarse con frecuencia y eficiencia de alcance, no solo con CPM.

### 3.3 Objetivos y optimización

La implementación de Punto TdeA usa:

- Objetivo: `OUTCOME_ENGAGEMENT`.
- Optimización: `CONVERSATIONS`.
- Facturación: `IMPRESSIONS`.
- Estrategia de puja: `LOWEST_COST_WITHOUT_CAP`.

Esto significa que el anuncio se paga por impresiones, pero Meta optimiza la entrega para conseguir conversaciones. El costo por conversación es un resultado, no una tarifa fija.

### 3.4 Placement

El placement de estados se configura con:

```json
{
  "publisher_platforms": ["instagram", "whatsapp"],
  "instagram_positions": ["story"],
  "whatsapp_positions": ["status"]
}
```

La inclusión de Instagram Story es necesaria porque Meta agrupa el placement de estados con las historias de Instagram. Esto no significa que el anuncio se muestre solo en WhatsApp: puede mostrarse en ambos placements según la configuración y la subasta.

### 3.5 Segmentación y audiencias

Meta no ofrece un criterio demográfico llamado “estudiantes de Punto TdeA”. Las opciones reales son:

1. **Audiencia personalizada por lista de teléfonos.** Se cargan los teléfonos hasheados (SHA-256) de los contactos con opt-in. Meta busca coincidencias con usuarios de sus plataformas. La tasa de coincidencia no es 100 %.
2. **Audiencia similar (lookalike).** Se construye a partir de una audiencia personalizada. Amplía el alcance, pero no garantiza que sean estudiantes.
3. **Segmentación amplia.** Ubicación, edad, género e intereses. No garantiza que sean estudiantes de la institución.
4. **Retargeting.** Personas que interactuaron con la institución, visitaron el sitio o vieron un anuncio.

La implementación de Punto TdeA crea audiencias personalizadas a partir de segmentos de contactos, con teléfonos normalizados y hasheados, y filtra por `whatsapp_opt_in = SUSCRITO`. Por defecto, `advantage_audience = 0`, lo que limita la entrega a la lista; el comando `--publico-amplio` permite ampliarla.

### 3.6 Requisitos

| Requisito | Detalle |
|---|---|
| Cuenta publicitaria de Meta | Con método de pago y moneda configurada |
| Página de Facebook | Vinculada a la cuenta de WhatsApp Business |
| Negocio verificado | Necesario para usar el número y el placement |
| Cuenta de Instagram | Conectada a la Página, porque el placement incluye Instagram Story |
| App de Meta en modo Live | No en modo desarrollo |
| Token con `ads_management` | El token de sistema de WhatsApp no sirve |
| Cuenta de WhatsApp Business | Con el número y la cuenta publicitaria vinculados |
| Política de privacidad y consentimiento | Para cargar teléfonos en audiencias personalizadas |
| Revisión de anuncios | Meta revisa el creativo y el destino |

### 3.7 Implementación en Punto TdeA

El proyecto ya tiene un servicio de Marketing API (`communications/services/ads_service.py`) que:

- Crea la campaña, el ad set, el creativo y el anuncio.
- Usa el placement de estados.
- Carga audiencias personalizadas con teléfonos hasheados.
- Filtra por opt-in.
- Crea todo en `PAUSED` por defecto.
- Usa un presupuesto diario por defecto de $ 2.000.000 COP.
- Requiere un token con `ads_management`.

**Riesgo operativo:** el presupuesto por defecto de $ 2.000.000 COP/día es un valor técnico, no una recomendación. Si se activa sin ajustarlo, una campaña de 7 días puede costar $ 14.000.000 COP. La institución debe definir el presupuesto antes de activar.

---

## 4. Metodología del presupuesto

### 4.1 Fórmula

Para estimar el presupuesto necesario para alcanzar N estudiantes únicos:

**Presupuesto = (N × F / R) × CPM / 1.000**

Donde:

- **N** = estudiantes únicos que se quieren alcanzar.
- **F** = frecuencia media (impresiones por estudiante alcanzado).
- **R** = eficiencia de alcance (proporción del objetivo que efectivamente se alcanza al menos una vez).
- **CPM** = costo por mil impresiones.

**Costo por estudiante alcanzado = Presupuesto / N**

La división por R reconoce que no todos los estudiantes objetivo serán alcanzados: para llegar a N únicos, se debe impactar un universo mayor (N/R).

### 4.2 Escenarios

| Escenario | CPM | Frecuencia | Eficiencia de alcance | Costo por estudiante |
|---|---:|---:|---:|---:|
| Conservador | $ 7.000 | 2 | 85 % | $ 16 |
| Intermedio | $ 12.000 | 3 | 75 % | $ 48 |
| Alto (prudente) | $ 20.000 | 4 | 60 % | $ 133 |

**Justificación de los supuestos:**

- **CPM.** Las referencias públicas para Colombia ubican el CPM de Meta Ads entre $ 5.000 y $ 12.000 COP en la mayoría de industrias, con rangos de $ 9.000 a $ 18.000 en educación y picos en Q4. Para el placement de estados, que es relativamente nuevo y tiene inventario limitado, se adoptan $ 7.000 (optimista), $ 12.000 (medio) y $ 20.000 (prudente). No son tarifas oficiales.
- **Frecuencia.** Se asume que un estudiante ve el anuncio 2, 3 o 4 veces. Una frecuencia muy baja reduce el recuerdo; una muy alta desperdicia presupuesto.
- **Eficiencia de alcance.** Se asume que se alcanza al 85 %, 75 % o 60 % del objetivo. Depende de la tasa de coincidencia de la audiencia, la actividad de los usuarios, el inventario y la optimización.

### 4.3 Presupuesto mínimo operativo

Meta exige un presupuesto diario mínimo por ad set, que depende de la moneda y del objetivo. Como referencia pública para COP:

| Objetivo | Mínimo diario por ad set |
|---|---:|
| Impresiones | $ 3.171 |
| Clics y engagement | $ 7.926 |
| Conversiones y leads | $ 63.403 |

La campaña de Punto TdeA optimiza por `CONVERSATIONS`, por lo que el mínimo aplicable debe confirmarse en Ads Manager; puede ubicarse entre el tramo de engagement y el de conversiones.

Para planificar, se adopta un **piso operativo de $ 450.000 COP por campaña**, equivalente a 7 días con una inversión diaria de aproximadamente $ 64.286 COP. Es un supuesto de planificación, no un mínimo oficial garantizado. El mínimo real debe validarse en la cuenta.

**Implicación:** para audiencias de 100 a 1.000 estudiantes, el piso operativo supera ampliamente lo que la audiencia puede absorber. Meta limitará la entrega y el costo por estudiante será alto. Para esos volúmenes, la mensajería directa es la opción recomendada.

### 4.4 Por qué no hay una tarifa oficial de CPM

Meta no publica un CPM para estados porque el precio se forma en una subasta. La documentación oficial explica el mecanismo de puja, pero no garantiza un precio. Cualquier proveedor que ofrezca un CPM fijo está estimando, no citando una tarifa oficial.

### 4.5 Supuestos y limitaciones del modelo

- No se asume que todos los estudiantes tengan WhatsApp activo.
- No se asume que todos vean el anuncio.
- No se asume una tasa de coincidencia del 100 % en las audiencias personalizadas.
- No se asume un inventario ilimitado.
- No se asume que el CPM se mantenga constante durante la campaña.
- No se asume que la frecuencia sea exacta.
- No se asume que el anuncio esté exento de revisión o de restricciones de política.
- No se incluyen impuestos, producción de creativos ni gestión.

---

## 5. Tabla 3 — Presupuesto estimado (escenario intermedio)

**Criterio de lectura.** La columna “Alcance estimado” es el objetivo de planificación: los estudiantes únicos que se quieren alcanzar. El presupuesto ya incorpora la eficiencia de alcance (R) y la frecuencia (F). El alcance real no está garantizado y puede ser menor.

| Número de estudiantes objetivo | Alcance estimado | CPM estimado | Presupuesto estimado | Costo por estudiante alcanzado |
|---:|---:|---:|---:|---:|
| 100 | 100 únicos planificados | $ 12.000 | $ 450.000 | $ 4.500 |
| 500 | 500 únicos planificados | $ 12.000 | $ 450.000 | $ 900 |
| 1.000 | 1.000 únicos planificados | $ 12.000 | $ 450.000 | $ 450 |
| 5.000 | 5.000 únicos planificados | $ 12.000 | $ 450.000 | $ 90 |
| 10.000 | 10.000 únicos planificados | $ 12.000 | $ 480.000 | $ 48 |
| 20.000 | 20.000 únicos planificados | $ 12.000 | $ 960.000 | $ 48 |
| 50.000 | 50.000 únicos planificados | $ 12.000 | $ 2.400.000 | $ 48 |
| 100.000 | 100.000 únicos planificados | $ 12.000 | $ 4.800.000 | $ 48 |

**Fórmulas aplicadas:**

- Presupuesto teórico = (N × 3 / 0,75) × $ 12.000 / 1.000 = N × $ 48.
- Presupuesto aplicable = máximo entre el presupuesto teórico y el piso operativo de $ 450.000.
- Costo por estudiante = presupuesto aplicable / N.

**Verificación:**

- Para 10.000 estudiantes: 10.000 × $ 48 = $ 480.000.
- Para 100.000 estudiantes: 100.000 × $ 48 = $ 4.800.000.
- Para 1.000 estudiantes: el teórico es $ 48.000; como es inferior al piso, se presupuesta $ 450.000, y el costo por estudiante sube a $ 450.

### 5.1 Explicación de la Tabla 3

- **Para 100 a 5.000 estudiantes, manda el piso operativo.** El presupuesto teórico es muy bajo, pero una campaña no se puede ejecutar con $ 4.800 o $ 240.000. El piso de $ 450.000 refleja el mínimo razonable para que Meta entregue y aprenda.
- **Para 10.000 estudiantes en adelante, manda el CPM.** El presupuesto crece linealmente con el volumen: $ 48 por estudiante alcanzado.
- **El costo por estudiante se estabiliza en $ 48.** Es el resultado de la fórmula: 3 impresiones × $ 12.000 / 1.000 / 0,75.
- **Para audiencias pequeñas, el costo por estudiante es alto.** No porque el CPM sea alto, sino porque el presupuesto mínimo se reparte entre pocas personas. En esos casos, la mensajería directa es más eficiente.

---

## 6. Tabla de los tres escenarios presupuestales

| Número de estudiantes | Escenario | CPM | Frecuencia | Eficiencia | Presupuesto teórico | Presupuesto aplicable | Costo por estudiante |
|---:|---|---:|---:|---:|---:|---:|---:|
| 100 | Conservador | $ 7.000 | 2 | 85 % | $ 1.647 | $ 450.000 | $ 4.500 |
| 100 | Intermedio | $ 12.000 | 3 | 75 % | $ 4.800 | $ 450.000 | $ 4.500 |
| 100 | Alto | $ 20.000 | 4 | 60 % | $ 13.333 | $ 450.000 | $ 4.500 |
| 500 | Conservador | $ 7.000 | 2 | 85 % | $ 8.235 | $ 450.000 | $ 900 |
| 500 | Intermedio | $ 12.000 | 3 | 75 % | $ 24.000 | $ 450.000 | $ 900 |
| 500 | Alto | $ 20.000 | 4 | 60 % | $ 66.667 | $ 450.000 | $ 900 |
| 1.000 | Conservador | $ 7.000 | 2 | 85 % | $ 16.471 | $ 450.000 | $ 450 |
| 1.000 | Intermedio | $ 12.000 | 3 | 75 % | $ 48.000 | $ 450.000 | $ 450 |
| 1.000 | Alto | $ 20.000 | 4 | 60 % | $ 133.333 | $ 450.000 | $ 450 |
| 5.000 | Conservador | $ 7.000 | 2 | 85 % | $ 82.353 | $ 450.000 | $ 90 |
| 5.000 | Intermedio | $ 12.000 | 3 | 75 % | $ 240.000 | $ 450.000 | $ 90 |
| 5.000 | Alto | $ 20.000 | 4 | 60 % | $ 666.667 | $ 666.667 | $ 133 |
| 10.000 | Conservador | $ 7.000 | 2 | 85 % | $ 164.706 | $ 450.000 | $ 45 |
| 10.000 | Intermedio | $ 12.000 | 3 | 75 % | $ 480.000 | $ 480.000 | $ 48 |
| 10.000 | Alto | $ 20.000 | 4 | 60 % | $ 1.333.333 | $ 1.333.333 | $ 133 |
| 20.000 | Conservador | $ 7.000 | 2 | 85 % | $ 329.412 | $ 450.000 | $ 23 |
| 20.000 | Intermedio | $ 12.000 | 3 | 75 % | $ 960.000 | $ 960.000 | $ 48 |
| 20.000 | Alto | $ 20.000 | 4 | 60 % | $ 2.666.667 | $ 2.666.667 | $ 133 |
| 50.000 | Conservador | $ 7.000 | 2 | 85 % | $ 823.529 | $ 823.529 | $ 16 |
| 50.000 | Intermedio | $ 12.000 | 3 | 75 % | $ 2.400.000 | $ 2.400.000 | $ 48 |
| 50.000 | Alto | $ 20.000 | 4 | 60 % | $ 6.666.667 | $ 6.666.667 | $ 133 |
| 100.000 | Conservador | $ 7.000 | 2 | 85 % | $ 1.647.059 | $ 1.647.059 | $ 16 |
| 100.000 | Intermedio | $ 12.000 | 3 | 75 % | $ 4.800.000 | $ 4.800.000 | $ 48 |
| 100.000 | Alto | $ 20.000 | 4 | 60 % | $ 13.333.333 | $ 13.333.333 | $ 133 |

### 6.1 Lectura de los escenarios

- **Conservador:** asume un CPM bajo, frecuencia baja y buena eficiencia. Es el escenario más favorable. Solo es realista si el inventario de estados es barato y la audiencia responde bien.
- **Intermedio:** usa referencias medias del mercado colombiano. Es el escenario base para presupuestar.
- **Alto:** asume un CPM alto, mayor frecuencia y menor eficiencia. Es el escenario prudente para la aprobación presupuestal. Si el resultado real es mejor, se libera presupuesto.

### 6.2 Efecto del piso operativo

En los primeros rangos, los tres escenarios convergen en $ 450.000 porque el piso domina. Esto no significa que el CPM sea irrelevante: significa que, por debajo de cierto volumen, el presupuesto mínimo pesa más que la eficiencia de la subasta. Para 5.000 estudiantes, el escenario alto ya supera el piso; para 10.000, solo el conservador sigue en el piso; para 50.000, todos superan el piso.

---

## 7. Comparación con mensajería directa y estado orgánico

### 7.1 Tabla comparativa

| Criterio | Plantilla de marketing | Plantilla de utilidad | Anuncio en estado | Estado orgánico |
|---|---|---|---|---|
| Costo | $ 46,0227 por mensaje | $ 2,9455 por mensaje | CPM en subasta | Gratis |
| Alcance | Lista con opt-in | Lista con opt-in | Audiencia segmentada; no garantizado | Contactos que guarden el número |
| Control | Alto | Alto | Medio | Bajo |
| Medición | Entrega y lectura | Entrega y lectura | Impresiones, alcance, frecuencia | Limitada |
| Requisito | Opt-in y plantilla | Opt-in y plantilla | Cuenta publicitaria y configuración | App de WhatsApp Business |
| Automatización | Sí, Cloud API | Sí, Cloud API | Sí, Marketing API | No, manual |
| Garantía de entrega | Alta, si el número es válido | Alta, si el número es válido | Ninguna | Ninguna |
| Ideal para | Promoción segmentada | Notificaciones operativas | Alcance amplio | Complemento de presencia |

### 7.2 Comparación de costos

| Estudiantes | Plantilla de marketing | Anuncio en estado (intermedio) | Relación |
|---:|---:|---:|---:|
| 100 | $ 4.602 | $ 450.000 | 97,8× |
| 500 | $ 23.011 | $ 450.000 | 19,6× |
| 1.000 | $ 46.023 | $ 450.000 | 9,8× |
| 5.000 | $ 230.114 | $ 450.000 | 2,0× |
| 10.000 | $ 460.227 | $ 480.000 | 1,04× |
| 20.000 | $ 920.454 | $ 960.000 | 1,04× |
| 50.000 | $ 2.301.135 | $ 2.400.000 | 1,04× |
| 100.000 | $ 4.602.270 | $ 4.800.000 | 1,04× |

**Lectura:** el punto de cruce está alrededor de 10.000 estudiantes. Por debajo, la plantilla es más barata. Por encima, los costos son comparables. Pero la comparación no es equivalente:

- La plantilla entrega a un número con opt-in; el anuncio no garantiza que una persona específica lo vea.
- La plantilla se mide por entrega; el anuncio se mide por impresiones y alcance.
- La plantilla requiere una lista; el anuncio puede ampliar el alcance más allá de la lista.
- La plantilla tiene un costo variable por mensaje; el anuncio tiene un costo variable por subasta.

### 7.3 Cuándo usar cada modalidad

| Objetivo | Modalidad recomendada | Razón |
|---|---|---|
| Notificar un trámite o estado | Plantilla de utilidad | Bajo costo, entrega directa, medición |
| Promocionar un programa a estudiantes conocidos | Plantilla de marketing segmentada | Control y medición; evitar audiencias frías |
| Difundir un aviso a toda la comunidad | Anuncio en estado + plantilla de utilidad | Alcance amplio + entrega garantizada a la lista |
| Atraer nuevos estudiantes | Anuncio en estado / Click to WhatsApp | Alcance más allá de la base actual |
| Mantener presencia cotidiana | Estado orgánico | Gratuito, complementario |
| Comunicación urgente | Plantilla de utilidad + anuncio | Cobertura y velocidad |

---

## 8. Requisitos operativos y configuración

### 8.1 Cuenta publicitaria

- Cuenta de Meta Ads activa.
- Método de pago válido.
- Moneda configurada (COP o USD).
- Límite de gasto definido.
- Roles y permisos.

### 8.2 Página y WhatsApp

- Página de Facebook vinculada a la cuenta de WhatsApp Business.
- Número de WhatsApp verificado.
- Negocio verificado.

### 8.3 Instagram

- Cuenta de Instagram conectada a la Página.
- Necesaria porque el placement incluye Instagram Story.

### 8.4 Token y app

- App de Meta en modo Live.
- Token con `ads_management`.
- El token de sistema de WhatsApp no sirve para la Marketing API.

### 8.5 Facturación

- Método de pago en el Billing Hub.
- Confirmar la entidad facturadora y el tratamiento de impuestos.
- Si la cuenta está en USD, prever TRM y comisiones.

### 8.6 Lista de verificación

- [ ] Cuenta publicitaria activa.
- [ ] Método de pago configurado.
- [ ] Página vinculada a WhatsApp.
- [ ] Negocio verificado.
- [ ] Instagram conectado.
- [ ] App en Live.
- [ ] Token con `ads_management`.
- [ ] Audiencia personalizada cargada y con opt-in.
- [ ] Creativo revisado.
- [ ] Presupuesto diario definido (no dejar el valor por defecto de $ 2.000.000).
- [ ] Campaña creada en `PAUSED`.
- [ ] Revisión de política superada.
- [ ] Métricas de medición configuradas.

---

## 9. Limitaciones y riesgos

### 9.1 Alcance no garantizado

La publicidad compra impresiones, no personas. Un estudiante puede ver el anuncio varias veces; otro puede no verlo nunca. La columna “alcance estimado” es un objetivo de planificación, no una promesa.

### 9.2 Segmentación por base de datos

Meta no tiene un criterio “estudiante de Punto TdeA”. La audiencia personalizada por teléfonos depende de:

- Que el teléfono esté asociado a una cuenta de Meta.
- Que el usuario haya dado su consentimiento.
- Que la tasa de coincidencia sea suficiente.
- Que Meta pueda entregar el anuncio.

Una lista de 100.000 teléfonos no garantiza 100.000 impresiones únicas.

### 9.3 Consentimiento y privacidad

- La carga de teléfonos en audiencias personalizadas requiere consentimiento y cumplimiento de las políticas de Meta.
- Los anuncios en estados no están cifrados de extremo a extremo, aunque los mensajes personales sí.
- La institución debe tener una política de privacidad y un mecanismo de baja.

### 9.4 Inventario

El inventario de estados es limitado. No es comparable con el feed de Facebook o Instagram. La entrega puede ser más lenta o más cara de lo esperado.

### 9.5 Frecuencia y fase de aprendizaje

- Una frecuencia muy alta desperdicia presupuesto.
- Una frecuencia muy baja reduce el impacto.
- Meta necesita eventos suficientes para salir de la fase de aprendizaje; con presupuestos muy bajos, la entrega puede ser inestable.

### 9.6 Presupuesto mínimo

- Meta exige un mínimo diario por ad set.
- El mínimo depende de la moneda y del objetivo.
- El valor por defecto del proyecto ($ 2.000.000/día) es mucho más alto que el mínimo y debe ajustarse.

### 9.7 Políticas y revisión

- Meta revisa los anuncios.
- Un anuncio puede ser rechazado o limitado.
- Las categorías especiales de anuncios pueden aplicar restricciones.
- La institución debe revisar las políticas antes de publicar.

### 9.8 Medición

- Medir impresiones, alcance, frecuencia, CPM, costo por conversación y costo por estudiante alcanzado.
- No confundir impresiones con alcance.
- No confundir alcance con estudiantes únicos de la institución.
- Recalibrar los supuestos con los primeros resultados.

### 9.9 Otras limitaciones

- La cuenta publicitaria puede tener restricciones.
- El token puede caducar.
- La verificación del negocio puede tardar.
- La cuenta de Instagram puede no estar disponible.
- El inventario puede variar por temporada.
- Los impuestos y cargos adicionales no están incluidos.

---

## 10. Conclusiones y recomendación

### 10.1 Conclusiones

1. **Los estados de WhatsApp no son un canal de mensajería masiva.** Son un placement publicitario.
2. **La Cloud API no puede publicar estados.** Solo envía mensajes directos.
3. **Meta no publica un CPM para estados.** El costo se determina en subasta.
4. **El alcance no está garantizado.** Se compran impresiones, no personas.
5. **Para listas pequeñas, la plantilla es más barata.** A 1.000 estudiantes, la diferencia es de casi 10 veces.
6. **Para audiencias grandes, el anuncio es competitivo.** A partir de 10.000 estudiantes, los costos son comparables.
7. **El estado orgánico es gratuito pero limitado.** No reemplaza una campaña de alcance.
8. **La configuración es exigente.** Cuenta publicitaria, Página, WhatsApp, Instagram, verificación, token y facturación.
9. **El presupuesto por defecto del proyecto es riesgoso.** $ 2.000.000/día puede llevar a $ 14.000.000 en 7 días.
10. **La medición es obligatoria.** Sin datos reales, los escenarios son solo supuestos.

### 10.2 Recomendación

Para una institución educativa que necesita comunicar avisos a sus estudiantes, la estrategia más conveniente es **híbrida y escalonada**:

1. **Notificaciones operativas y urgentes:** usar plantillas de utilidad por Cloud API. Son baratas ($ 2,9455), medibles y llegan a la lista con opt-in.
2. **Campañas promocionales a estudiantes conocidos:** usar plantillas de marketing segmentadas. Son más caras ($ 46,0227), pero controlables y medibles. No usarlas para toda la base si el objetivo es solo informar.
3. **Difusión amplia o captación:** usar anuncios en estados con destino a WhatsApp o al sitio web. Permiten ampliar el alcance, pero no garantizan que un estudiante específico vea el aviso.
4. **Presencia cotidiana:** usar el estado orgánico desde la app de WhatsApp Business. Es gratuito y complementario, pero limitado a los contactos.
5. **Piloto:** comenzar con una campaña de $ 450.000 a $ 900.000, medir CPM, alcance, frecuencia y costo por conversación, y escalar solo si los indicadores son favorables.

**No se recomienda** usar anuncios en estados para audiencias de 100 a 1.000 estudiantes: el piso operativo hace que el costo por estudiante sea muy alto y la entrega sea limitada. Para esos volúmenes, la mensajería directa es la mejor opción.

### 10.3 Próximos pasos

| Paso | Responsable | Resultado |
|---|---|---|
| Definir objetivo de la campaña | Rectoría / Comunicaciones | Alcance, conversaciones o tráfico |
| Validar presupuesto | Rectoría | Techo aprobado |
| Revisar requisitos | Tecnología | Cuenta, token, Página, Instagram |
| Cargar audiencia | Mercadeo | Lista con opt-in |
| Crear campaña en PAUSED | Tecnología | Campaña lista para revisión |
| Pilotar | Mercadeo | CPM y alcance reales |
| Recalibrar | Finanzas / Mercadeo | Presupuesto definitivo |

---

## 11. Fuentes consultadas

### 11.1 Fuentes oficiales

| Fuente | URL | Uso | Fecha |
|---|---|---|---|
| Anuncios en estados y canales | https://whatsappbusiness.com/whatsapp-ads/ | Mecanismo, destinos, alcance | 3 nov 2026 |
| Placement targeting | https://developers.facebook.com/documentation/ads-commerce/marketing-api/audiences/reference/placement-targeting | Disponibilidad del placement | 3 nov 2026 |
| Ayuda: crear anuncios en estados | https://www.facebook.com/business/help/1074444721456755 | Configuración en Ads Manager | 3 nov 2026 |
| Anuncios Click to WhatsApp | https://developers.facebook.com/documentation/ads-commerce/marketing-api/ad-creative/messaging-ads/click-to-whatsapp | Destino a conversación | 3 nov 2026 |
| Ayuda: presupuestos mínimos | https://www.facebook.com/business/help/203183363050448 | Mínimos de campaña | 3 nov 2026 |
| Precios de WhatsApp | https://developers.facebook.com/docs/whatsapp/pricing/ | Costo de mensajería (Documento 1) | 3 nov 2026 |
| Términos de WhatsApp Business | https://www.whatsapp.com/legal/meta-terms-whatsapp-business | Facturación e impuestos | 3 nov 2026 |

### 11.2 Documentación del proyecto

| Fuente | Uso |
|---|---|
| `docs/anuncios-status-whatsapp.md` | Requisitos, placement, presupuesto por defecto |
| `docs/whatsapp-meta.md` | Integración Cloud API, ventana de 24 horas |
| `docs/modulos/communications.md` | Arquitectura del módulo |
| `communications/services/ads_service.py` | Implementación de la Marketing API, audiencias y placement |

### 11.3 Referencias de mercado (no oficiales)

| Fuente | URL | Uso |
|---|---|---|
| Acuarius — CPM en Colombia | https://acuarius.app/benchmarks/costo-meta-ads-colombia/ | Rango de CPM |
| AVISPA'O — inversión en pauta | https://avispao.com/inversion-pauta-redes-sociales-colombia/ | CPM y presupuestos mínimos |
| Dani Arbeláez — presupuesto Meta Ads | https://daniarbelaez.com/cuanto-invertir-en-meta-ads-segun-tu-presupuesto-guia-para-colombia-2026/ | Rangos por sector |
| Hostli — mínimos por moneda | https://www.hostli.ai/en/tools/ad-minimums | Mínimos diarios en COP |
| Stephen Ellul — WhatsApp Status ads | https://www.stephenellul.co/insights/whatsapp-status-ads-malta-2026 | Referencia cualitativa del placement |

> **Nota sobre las referencias de mercado.** Los valores de CPM y presupuestos mínimos de estas fuentes son orientativos. No son tarifas oficiales de Meta ni garantizan resultados en Colombia. Se usan solo para construir escenarios de planificación.

---

## Anexo A — Glosario

| Término | Definición |
|---|---|
| Ads in Status | Anuncios que aparecen en la pestaña Novedades de WhatsApp |
| Alcance | Personas únicas que vieron un anuncio al menos una vez |
| Audiencia personalizada | Lista de usuarios cargada por la empresa para segmentar |
| CPM | Costo por mil impresiones |
| Click to WhatsApp | Anuncio que lleva al usuario a una conversación de WhatsApp |
| Frecuencia | Promedio de impresiones por persona alcanzada |
| Impresión | Visualización de un anuncio |
| Lookalike | Audiencia similar a una lista de origen |
| Marketing API | API de Meta para gestionar anuncios |
| Placement | Ubicación donde se muestra un anuncio |
| Subasta | Mecanismo por el cual Meta asigna impresiones |
| Estado orgánico | Publicación gratuita desde la app de WhatsApp Business |

---

## Anexo B — Fórmulas y redondeo

### B.1 Presupuesto

**Presupuesto = (N × F / R) × CPM / 1.000**

### B.2 Costo por estudiante

**Costo por estudiante = Presupuesto / N**

### B.3 Impresiones

**Impresiones = N × F / R**

### B.4 Redondeo

- Cálculos con precisión completa.
- Presentación al peso.
- Las diferencias de $ 1 pueden deberse al redondeo.
- Los porcentajes se presentan con un decimal cuando aporta precisión.

---

## Anexo C — Detalle de los escenarios

### C.1 Conservador

- CPM: $ 7.000.
- Frecuencia: 2.
- Eficiencia: 85 %.
- Costo por estudiante: 2 × $ 7.000 / 1.000 / 0,85 = $ 16,47.
- Presupuesto para 100.000: 100.000 × 2 / 0,85 × $ 7.000 / 1.000 = $ 1.647.059.

### C.2 Intermedio

- CPM: $ 12.000.
- Frecuencia: 3.
- Eficiencia: 75 %.
- Costo por estudiante: 3 × $ 12.000 / 1.000 / 0,75 = $ 48,00.
- Presupuesto para 100.000: 100.000 × 3 / 0,75 × $ 12.000 / 1.000 = $ 4.800.000.

### C.3 Alto

- CPM: $ 20.000.
- Frecuencia: 4.
- Eficiencia: 60 %.
- Costo por estudiante: 4 × $ 20.000 / 1.000 / 0,60 = $ 133,33.
- Presupuesto para 100.000: 100.000 × 4 / 0,60 × $ 20.000 / 1.000 = $ 13.333.333.

---

## Anexo D — Lista de verificación para la campaña

- [ ] Objetivo definido: alcance, conversaciones o tráfico.
- [ ] Audiencia definida y con opt-in.
- [ ] Creativo revisado y aprobado.
- [ ] Presupuesto diario definido.
- [ ] Duración definida.
- [ ] Placement de estados configurado.
- [ ] Destino (WhatsApp o sitio web) verificado.
- [ ] Campaña creada en `PAUSED`.
- [ ] Revisión de política superada.
- [ ] Métricas configuradas.
- [ ] Responsable de monitoreo asignado.
- [ ] Criterio de escala definido.

---

**Fin del Documento 2.**

*Este documento es una herramienta de planificación. No reemplaza la facturación oficial de Meta ni la validación contable de Punto TdeA.*
