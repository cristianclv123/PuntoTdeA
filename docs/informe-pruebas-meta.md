# Informe de pruebas unitarias — Integración Meta

Lista de las pruebas unitarias del módulo de integración Meta (adapter, webhook y
servicios) y lo que cada una espera. **No es un informe de ejecución**: no incluye
resultados ni tiempos.

**Alcance**: `communications/adapters/meta_adapter.py`,
`communications/webhooks/meta_webhook.py` y `communications/services/`
(`meta_templates`, `meta_config`, `meta_diagnostics`, `ads_service`,
`test_send_registry`), más los modelos que persisten los eventos.

**Convenciones**: todas las pruebas mockean `requests` y el chatbot; nunca llaman a
la Graph API real. El webhook se prueba con `@override_settings` y firma HMAC.

---

## `communications/tests/test_adapters.py` — 115 pruebas

### `ConfigurationErrorTests`
| Prueba | Qué espera |
| --- | --- |
| `test_returns_empty_string_when_configured` | Con token y phone id, no reporta nada. |
| `test_reports_only_missing_token` | Reporta solo `META_ACCESS_TOKEN`. |
| `test_reports_only_missing_phone_number_id` | Reporta solo `WHATSAPP_PHONE_NUMBER_ID`. |
| `test_reports_both_missing_secrets` | Reporta ambas variables. |

### `UrlBuilderTests`
| Prueba | Qué espera |
| --- | --- |
| `test_messages_url_strips_trailing_slash` | La URL de mensajes no queda con `/` duplicado. |
| `test_media_url_without_trailing_slash` | La URL de medios no queda con `/` duplicado. |

### `NormalizePhoneTests`
| Prueba | Qué espera |
| --- | --- |
| `test_strips_plus_spaces_and_punctuation` | Deja solo dígitos. |
| `test_empty_string_returns_empty` | Vacío → vacío. |
| `test_none_returns_empty` | `None` → vacío. |
| `test_only_plus_returns_empty` | Solo `+` → vacío. |
| `test_keeps_only_digits` | Conserva los dígitos. |

### `RequestErrorTests`
| Prueba | Qué espera |
| --- | --- |
| `test_uses_meta_error_message` | Usa el mensaje de error de Meta. |
| `test_falls_back_to_response_text_when_json_is_invalid` | Si el JSON es inválido, usa `response.text`. |
| `test_uses_exception_message_when_response_is_none` | Si no hay respuesta, usa la excepción. |
| `test_uses_exception_when_meta_detail_is_empty` | Si Meta no da detalle, usa la excepción. |
| `test_translates_known_meta_error_code` | Traduce el código `131026` con `explain()`. |

### `PostMessageTests`
| Prueba | Qué espera |
| --- | --- |
| `test_success_returns_provider_message_id` | Devuelve `SendResult` exitoso con el `wamid`. |
| `test_posts_to_messages_url_with_auth_and_timeout` | POST a la URL con `Bearer` y timeout. |
| `test_returns_meta_error_on_http_failure` | HTTP error → `SendResult` con error de Meta. |
| `test_returns_error_when_post_raises_request_exception` | Excepción de red → error. |
| `test_returns_response_text_when_response_json_is_invalid` | JSON inválido → texto de la respuesta. |
| `test_returns_error_when_meta_does_not_return_message_id` | Sin `messages[0].id` → error. |
| `test_returns_error_when_message_entry_has_empty_id` | `id` vacío → error. |
| `test_returns_configuration_error_without_calling_api` | Sin config, no llama a la API. |

### `SendTextMessageTests`
| Prueba | Qué espera |
| --- | --- |
| `test_builds_text_payload` | Arma el payload de texto. |
| `test_preview_url_flag_adds_preview_key` | `preview_url=True` añade la clave. |
| `test_preview_url_defaults_to_false` | Por defecto no incluye `preview_url`. |
| `test_strips_body_whitespace` | Recorta espacios del cuerpo. |
| `test_rejects_empty_text` | Texto vacío → error. |
| `test_rejects_empty_phone` | Teléfono vacío → error. |

### `InteractiveEnvelopeTests`
| Prueba | Qué espera |
| --- | --- |
| `test_empty_body_returns_error` | Cuerpo vacío → error. |
| `test_body_longer_than_1024_returns_error` | Cuerpo >1024 → error. |
| `test_header_longer_than_60_returns_error` | Header >60 → error. |
| `test_footer_longer_than_60_returns_error` | Footer >60 → error. |
| `test_builds_envelope_with_header_and_footer` | Incluye header y footer. |
| `test_omits_empty_header_and_footer` | Omite header/footer vacíos. |

### `SendInteractiveButtonsTests`
| Prueba | Qué espera |
| --- | --- |
| `test_builds_buttons_payload` | Arma el payload de botones. |
| `test_strips_button_id_and_title` | Recorta id y título. |
| `test_rejects_duplicate_button_ids` | Ids duplicados → error. |
| `test_rejects_button_without_id` | Botón sin id → error. |
| `test_rejects_button_without_title` | Botón sin título → error. |
| `test_rejects_title_longer_than_20_chars` | Título >20 → error. |
| `test_rejects_empty_body` | Cuerpo vacío → error. |
| `test_rejects_empty_phone` | Teléfono vacío → error. |
| `test_rejects_zero_buttons` | Cero botones → error. |

### `SendInteractiveListTests`
| Prueba | Qué espera |
| --- | --- |
| `test_builds_list_payload` | Arma el payload de lista. |
| `test_rejects_empty_button_label` | Etiqueta vacía → error. |
| `test_rejects_button_label_longer_than_20_chars` | Etiqueta >20 → error. |
| `test_rejects_empty_phone` | Teléfono vacío → error. |
| `test_rejects_section_title_longer_than_24_chars` | Título de sección >24 → error. |
| `test_rejects_row_without_id` | Fila sin id → error. |
| `test_rejects_row_without_title` | Fila sin título → error. |
| `test_rejects_duplicate_row_ids_across_sections` | Ids duplicados entre secciones → error. |
| `test_rejects_row_title_longer_than_24_chars` | Título de fila >24 → error. |
| `test_rejects_row_description_longer_than_72_chars` | Descripción >72 → error. |
| `test_rejects_section_with_empty_rows` | Sección con `rows: []` → error. |
| `test_rejects_section_without_rows_key` | Sección sin `rows` → error. |
| `test_rejects_more_than_ten_rows` | Más de 10 filas → error. |
| `test_rejects_empty_sections` | `sections: []` → error. |

### `SendImageMessageTests`
| Prueba | Qué espera |
| --- | --- |
| `test_uploads_and_sends_image` | Sube la imagen y la envía con caption. |
| `test_omits_caption_when_empty` | Sin caption, no la incluye. |
| `test_rejects_empty_phone` | Teléfono vacío → error. |
| `test_rejects_empty_image_data` | Imagen vacía → error. |
| `test_rejects_missing_configuration` | Sin config → error. |
| `test_returns_error_when_upload_fails` | Fallo de subida → error. |
| `test_returns_meta_error_when_upload_http_fails` | HTTP error en la subida → error de Meta. |
| `test_returns_error_when_upload_response_has_no_id` | Subida sin `id` → error. |
| `test_rejects_caption_longer_than_1024_chars` | Caption >1024 → error. |

### `UploadWhatsappMediaTests`
| Prueba | Qué espera |
| --- | --- |
| `test_uploads_media_and_returns_id` | Sube el binario y devuelve el `media_id`. |
| `test_rejects_missing_configuration` | Sin config → error. |
| `test_rejects_empty_file_bytes` | Bytes vacíos → error. |
| `test_returns_response_text_when_json_is_invalid` | JSON inválido → texto de la respuesta. |
| `test_returns_error_when_response_has_empty_id` | `id` vacío → error. |
| `test_returns_error_when_response_has_no_id_key` | Sin clave `id` → error. |
| `test_returns_meta_error_on_http_failure` | HTTP error → error de Meta. |
| `test_converts_numeric_media_id_to_string` | `media_id` numérico → `str`. |

### `SendUploadedImageMessageTests`
| Prueba | Qué espera |
| --- | --- |
| `test_delegates_to_send_media_message` | Delega en `send_media_message` con los kwargs exactos. |
| `test_propagates_error_from_send_media_message` | Propaga el error del envío. |
| `test_builds_image_payload` | Arma el payload de imagen. |

### `SendMediaMessageTests`
| Prueba | Qué espera |
| --- | --- |
| `test_rejects_unsupported_media_type` | Tipo no soportado → error. |
| `test_rejects_empty_media_id` | `media_id` vacío → error. |
| `test_rejects_empty_phone` | Teléfono vacío → error. |
| `test_builds_document_payload_with_filename` | Documento con `filename`. |
| `test_omits_filename_for_document_when_not_provided` | Documento sin `filename` no lo incluye. |
| `test_omits_filename_for_non_document_media` | No incluye `filename` en imagen/video. |
| `test_builds_video_payload_with_caption` | Video con caption. |

### `MetaAdapterTemplateFieldsTests`
| Prueba | Qué espera |
| --- | --- |
| `test_reads_template_ref_fields` | Lee los campos de un `TemplateRef`. |
| `test_prefers_meta_template_name_and_applies_defaults` | Prefiere `meta_template_name` y aplica defaults. |
| `test_falls_back_to_empty_name` | Sin nombre → vacío. |

### `MetaAdapterParameterValuesTests`
| Prueba | Qué espera |
| --- | --- |
| `test_orders_parameters_numerically` | Ordena los parámetros por índice. |
| `test_accepts_integer_keys` | Acepta claves `int`. |
| `test_accepts_brace_keys` | Acepta claves `{{n}}`. |
| `test_rejects_missing_parameter` | Falta un parámetro → error. |
| `test_repeated_parameter_is_emitted_once` | Parámetro repetido se emite una vez. |
| `test_without_parameters_returns_empty_list` | Sin parámetros → lista vacía. |
| `test_none_body_text_returns_empty_list` | `body_text` `None` → lista vacía. |

### `MetaAdapterPayloadTests`
| Prueba | Qué espera |
| --- | --- |
| `test_builds_template_payload_with_body_parameters` | Arma el payload con parámetros de cuerpo. |
| `test_omits_components_when_template_has_no_parameters` | Sin parámetros, no incluye `components`. |
| `test_orders_body_parameters_numerically` | Ordena los parámetros del cuerpo. |
| `test_rejects_empty_phone` | Teléfono vacío → error. |
| `test_rejects_template_without_name` | Plantilla sin nombre → error. |
| `test_rejects_missing_body_parameter` | Falta un parámetro del cuerpo → error. |
| `test_rejects_text_header_without_text` | Header de texto vacío → error. |
| `test_rejects_text_header_with_dynamic_variables` | Header de texto con variables → error. |
| `test_builds_text_header_component` | Arma el componente de header de texto. |
| `test_rejects_media_header_without_url` | Header multimedia sin URL → error. |
| `test_builds_image_header_component` | Arma el header de imagen. |
| `test_builds_video_header_component` | Arma el header de video. |
| `test_builds_document_header_component` | Arma el header de documento. |
| `test_rejects_unsupported_header_type` | Tipo de header no soportado → error. |
| `test_uses_es_co_when_language_is_empty` | Idioma vacío → `es_CO`. |
| `test_normalizes_phone_number` | Normaliza el teléfono. |

### `MetaAdapterSendTemplateTests`
| Prueba | Qué espera |
| --- | --- |
| `test_delegates_payload_to_post_message` | Delega el payload en `_post_message`. |
| `test_propagates_validation_error_without_posting` | Error de validación → no publica. |
| `test_sends_template_with_image_header_end_to_end` | Envía una plantilla con header de imagen. |

---

## `communications/tests/test_webhooks.py` — 60 pruebas

### `VerifySubscriptionTests`
| Prueba | Qué espera |
| --- | --- |
| `test_token_correcto_devuelve_el_challenge` | Token correcto → devuelve el challenge. |
| `test_token_incorrecto_devuelve_403` | Token incorrecto → 403. |
| `test_hub_mode_invalido_devuelve_403` | `hub.mode` inválido → 403. |
| `test_sin_secreto_configurado_devuelve_403` | Sin secreto → 403. |

### `SignatureTests`
| Prueba | Qué espera |
| --- | --- |
| `test_firma_correcta` | Firma HMAC correcta → válida. |
| `test_firma_incorrecta` | Firma incorrecta → inválida. |
| `test_header_sin_prefijo_sha256` | Header sin `sha256=` → inválido. |
| `test_header_ausente` | Header ausente → inválido. |
| `test_secreto_vacio` | Secreto vacío → inválido. |

### `EventTests`
| Prueba | Qué espera |
| --- | --- |
| `test_crea_evento_con_defaults` | Crea el evento con valores por defecto. |
| `test_evento_sin_payload_no_incluye_la_clave` | Sin payload, no incluye la clave. |
| `test_segunda_llamada_procesado_devuelve_duplicate` | Evento ya procesado → `duplicate`. |
| `test_registro_existente_sin_procesar_se_vuelve_a_procesar` | Evento sin procesar se vuelve a procesar. |
| `test_integrity_error_recupera_el_evento_existente` | `IntegrityError` → recupera el evento. |

### `CompactHelpersTests`
| Prueba | Qué espera |
| --- | --- |
| `test_finish_event_marca_processed_y_guarda_payload` | Marca `processed_at` y guarda `payload`. |
| `test_compact_status_guarda_pricing_y_errors` | Guarda `pricing`, `errors` y `conversation_id`. |
| `test_compact_status_sin_pricing_errores_ni_conversacion` | No agrega claves vacías. |
| `test_compact_inbound_texto_se_trunca_a_500` | Trunca el texto a 500. |
| `test_compact_inbound_interactive_recorta_id_y_title` | Recorta id y título del interactivo. |
| `test_timestamp_valido` | Convierte el epoch a UTC. |
| `test_timestamp_invalido_devuelve_now` | Valor inválido → `timezone.now()`. |
| `test_error_message_une_titulos_mensajes_y_codigos` | Une títulos, mensajes y códigos. |
| `test_error_message_sin_errores_usa_fallback` | Sin errores → mensaje de respaldo. |

### `ProcessStatusTests`
| Prueba | Qué espera |
| --- | --- |
| `test_sent_marca_enviado_y_fecha` | `sent` marca estado y `sent_at`. |
| `test_delivered_marca_entregado` | `delivered` marca estado. |
| `test_read_marca_leido` | `read` marca estado. |
| `test_failed_marca_fallido_con_error` | `failed` marca estado y error. |
| `test_duplicado_no_vuelve_a_procesar` | Duplicado no se reprocesa. |
| `test_unmatched_conserva_el_motivo` | Sin destinatario, conserva el motivo. |
| `test_read_no_revierte_con_delivered` | `delivered` después de `read` no revierte. |
| `test_failed_despues_de_read_no_revierte` | `failed` después de `read` no aplica. |
| `test_sent_no_sobrescribe_sent_at` | `sent_at` no se sobrescribe. |
| `test_estatus_invalido_o_id_vacio_se_ignora` | Estado inválido o id vacío → ignora. |

### `ProcessInboundTests`
| Prueba | Qué espera |
| --- | --- |
| `test_texto_se_envia_al_chatbot` | El texto se envía al chatbot. |
| `test_duplicado_no_llama_al_chatbot` | Duplicado no llama al chatbot. |
| `test_phone_number_id_no_configurado_se_ignora` | `phone_number_id` no configurado → ignora. |
| `test_sin_phone_id_configurado_acepta_cualquiera` | Sin phone configurada, acepta cualquiera. |
| `test_interactivo_no_soportado_se_ignora` | Interactivo no soportado → ignora. |
| `test_tipo_no_textual_se_ignora` | Tipo no textual → ignora. |
| `test_texto_vacio_se_ignora` | Texto vacío → ignora. |
| `test_interactivo_sin_id_ni_title_se_ignora` | Interactivo sin id/title → ignora. |
| `test_sin_id_o_remitente_se_ignora` | Sin id o remitente → ignora. |
| `test_excepcion_del_chatbot_se_propaga_y_no_marca_el_evento` | Excepción del chatbot → no marca el evento. |
| `test_interactivo_button_reply` | Procesa `button_reply`. |

### `ProcessTemplateStatusTests`
| Prueba | Qué espera |
| --- | --- |
| `test_status_update_notifica` | `message_template_status_update` notifica. |
| `test_duplicado_no_notifica_dos_veces` | Duplicado no notifica dos veces. |
| `test_calidad_update_usa_new_quality_score` | `quality_update` usa `new_quality_score`. |
| `test_sin_nombre_usa_valor_por_defecto` | Sin nombre, usa valor por defecto. |
| `test_sin_nombre_ni_evento_se_ignora` | Sin nombre ni evento → ignora. |

### `ProcessPayloadTests`
| Prueba | Qué espera |
| --- | --- |
| `test_procesa_mensajes_estados_y_plantillas` | Procesa mensajes, estados y plantillas. |
| `test_duplicados_se_cuentan` | Los duplicados se cuentan. |
| `test_entrada_vacia_no_procesa_nada` | Entrada vacía no procesa nada. |

### `WebhookViewTests`
| Prueba | Qué espera |
| --- | --- |
| `test_metodo_no_permitido_devuelve_405` | Método no permitido → 405. |
| `test_get_con_token_invalido_devuelve_403` | GET con token inválido → 403. |
| `test_json_invalido_devuelve_400` | JSON inválido → 400. |
| `test_json_no_dict_devuelve_400` | JSON no-dict → 400. |
| `test_excepcion_interna_devuelve_500` | Excepción interna → 500. |
| `test_excepcion_del_chatbot_devuelve_500` | Excepción del chatbot → 500. |
| `test_post_firmado_procesa_y_responde_ok` | POST firmado → 200 con `ok`. |
| `test_post_firmado_de_template_status` | POST firmado de plantilla → 200. |

---

## `communications/tests/test_models.py` — 40 pruebas

### `WhatsAppWebhookEventTests`
| Prueba | Qué espera |
| --- | --- |
| `test_event_key_es_unico` | `event_key` repetido → `IntegrityError`. |
| `test_processed_at_nace_nulo_y_se_puede_marcar` | `processed_at` nace nulo y se puede marcar. |
| `test_registra_inbound_y_status` | Registra tipos `inbound` y `status`. |
| `test_actualizacion_de_plantilla_se_guarda_como_status` | Actualización de plantilla se guarda como `status`. |
| `test_payload_por_defecto_y_motivo_de_failed` | `payload` por defecto `{}` y conserva el motivo. |
| `test_str_y_orden_descendente_por_created_at` | `__str__` y orden por `created_at`. |

### `BroadcastRecipientTests`
| Prueba | Qué espera |
| --- | --- |
| `test_estado_inicial_y_valores_por_defecto` | Estado `pending` y valores por defecto. |
| `test_progresion_pending_a_read` | Progresión `pending → read` con fechas. |
| `test_estado_opted_out_y_failed` | Estados `opted_out` y `failed`. |
| `test_provider_message_id_identifica_el_mensaje_de_meta` | `provider_message_id` identifica el mensaje. |
| `test_unicidad_campaña_contacto` | Unicidad por campaña/contacto. |
| `test_phone_snapshot_no_cambia_con_el_contacto` | `phone_snapshot` no cambia con el contacto. |
| `test_str_y_orden_por_id` | `__str__` y orden por id. |

### `ContactEventTests`
| Prueba | Qué espera |
| --- | --- |
| `test_creacion_y_relacion_con_contacto` | Crea el evento y lo vincula al contacto. |
| `test_se_puede_vincular_a_campaña_y_destinatario` | Vincula campaña y destinatario. |
| `test_tipos_de_evento` | Acepta los 8 tipos de evento. |
| `test_payload_por_defecto_y_str` | `payload` por defecto y `__str__`. |
| `test_orden_descendente_por_created_at` | Orden por `created_at`. |
| `test_eliminar_contacto_borra_sus_eventos` | Borrar contacto → `CASCADE`. |
| `test_al_borrar_la_campaña_las_referencias_quedan_en_null` | Borrar campaña → `SET_NULL`. |
| `test_al_borrar_el_destinatario_la_referencia_queda_en_null` | Borrar destinatario → `SET_NULL`. |

### `MessageTemplateTests`
| Prueba | Qué espera |
| --- | --- |
| `test_categorias_y_valor_por_defecto` | Categorías y default `utility`. |
| `test_tipos_de_header_y_valores_por_defecto` | Tipos de header y defaults. |
| `test_param_count_cuenta_variables_distintas` | `param_count` cuenta variables distintas. |
| `test_param_count_ignora_llaves_sin_numero` | Ignora llaves sin número. |
| `test_el_borrador_no_replica_el_estado_de_meta` | El borrador no guarda `status` ni `meta_template_name`. |
| `test_valores_por_defecto_de_campos_json` | Campos JSON con defaults. |
| `test_orden_por_nombre_y_str` | Orden por nombre y `__str__`. |

### `CampaignMetaTests`
| Prueba | Qué espera |
| --- | --- |
| `test_estado_inicial_y_canal_fijo` | Estado `draft` y canal `whatsapp` no editable. |
| `test_valores_por_defecto` | Snapshot, `rate_limit_per_minute=60`, fechas nulas. |
| `test_snapshot_guarda_la_plantilla_para_enviarla` | El snapshot guarda la plantilla. |
| `test_estados_disponibles` | Los 7 estados. |
| `test_metricas_de_destinatarios` | `total_recipients`, `sent_count`, `delivered_count`, `read_count`, `failed_count`. |
| `test_el_segmento_esta_protegido` | Borrar segmento → `ProtectedError`. |
| `test_str` | `__str__`. |

### `AudienceSegmentTests`
| Prueba | Qué espera |
| --- | --- |
| `test_origen_por_defecto_y_valores` | Origen por defecto y valores. |
| `test_contact_count_y_miembros` | `contact_count` y miembros. |
| `test_miembros_unicos_por_segmento` | Miembro repetido → `IntegrityError`. |
| `test_eliminar_segmento_borra_miembros_pero_no_contactos` | Borra miembros, no contactos. |
| `test_str_y_orden_descendente` | `__str__` y orden. |

---

## `communications/tests/test_meta_templates.py` — 25 pruebas nuevas

### `MetaTemplateComponentTests`
| Prueba | Qué espera |
| --- | --- |
| `test_meta_buttons_is_limited_to_three` | Máximo 3 botones. |
| `test_meta_buttons_ignores_non_dict_entries_and_incomplete_buttons` | Ignora no-dict y botones incompletos. |
| `test_build_components_rejects_empty_text_header` | Header de texto vacío → error. |
| `test_build_components_rejects_text_header_longer_than_60_characters` | Header >60 → error. |
| `test_build_components_limits_buttons_to_three` | Más de 3 botones → se limita. |

### `MetaTemplateVerificationEdgeTests`
| Prueba | Qué espera |
| --- | --- |
| `test_verify_campaign_template_rejects_empty_meta_id` | `meta_id` vacío/espacios/`None` → error. |
| `test_verify_campaign_template_rejects_meta_id_with_whitespace` | `meta_id` con espacios → error. |
| `test_verify_campaign_template_rejects_snapshot_that_is_not_an_object` | Snapshot no-dict → error. |
| `test_verify_campaign_template_rejects_another_template_returned_by_meta` | Meta devuelve otra plantilla → error. |

### `MetaTemplateNormalizeEdgeTests`
| Prueba | Qué espera |
| --- | --- |
| `test_normalize_maps_multimedia_headers` | Mapea headers image/video/document. |
| `test_normalize_keeps_quick_reply_buttons_and_ignores_other_types` | Conserva `QUICK_REPLY` y URL. |
| `test_normalize_preserves_real_rejection_reason` | Conserva `rejected_reason` real. |
| `test_normalize_computes_indexes_and_param_count` | Calcula `indexes` y `param_count`. |

### `MetaTemplateServiceErrorTests`
| Prueba | Qué espera |
| --- | --- |
| `test_list_templates_handles_network_error` | Error de red al listar → error controlado. |
| `test_list_templates_handles_invalid_json` | JSON inválido al listar → error controlado. |
| `test_get_template_handles_network_error` | Error de red al consultar → error controlado. |
| `test_get_template_handles_invalid_json` | JSON inválido al consultar → error controlado. |
| `test_create_from_draft_handles_network_error` | Error de red al crear → error controlado. |
| `test_create_from_draft_handles_invalid_json` | JSON inválido al crear → error controlado. |
| `test_edit_template_reports_build_error` | Error de build al editar → error controlado. |
| `test_edit_template_handles_network_error` | Error de red al editar → error controlado. |
| `test_edit_template_reports_meta_error` | Error de Meta al editar → error controlado. |
| `test_delete_template_handles_network_error` | Error de red al eliminar → error controlado. |
| `test_delete_template_reports_meta_error` | Error de Meta al eliminar → error controlado. |
| `test_delete_template_reports_missing_config` | Sin config → error controlado. |

---

## `communications/tests/test_meta_diagnostics.py` — 11 pruebas nuevas

### `MetaDiagnosticsCoverageTests`
| Prueba | Qué espera |
| --- | --- |
| `test_request_error_classifies_http_error` | Clasifica `HTTPError`. |
| `test_request_error_classifies_generic_request_exception` | Clasifica `RequestException`. |
| `test_request_error_uses_custom_target` | Usa el target personalizado. |
| `test_run_all_returns_token_and_phone_results_in_order` | Devuelve token y teléfono en orden. |
| `test_is_ready_requires_both_config_and_webhook` | `is_ready` exige config y webhook. |
| `test_check_access_token_without_token` | Sin token → error. |
| `test_check_phone_number_without_phone_id` | Sin phone id → error. |
| `test_check_phone_number_without_token` | Sin token → error. |
| `test_check_access_token_rejects_non_dict_payload` | Payload no-dict → error. |
| `test_check_phone_number_rejects_non_dict_payload` | Payload no-dict → error. |
| `test_webhook_reachable_reports_non_200_status` | HTTP no-200 → error. |

---

## `communications/tests/test_ads_service.py` — 46 pruebas nuevas

### `AdsServiceConfigurationTests`
| Prueba | Qué espera |
| --- | --- |
| `test_configuration_errors_lists_all_four_missing_variables` | Lista las 4 variables faltantes. |
| `test_configuration_errors_empty_when_everything_is_configured` | Todo configurado → sin errores. |
| `test_configuration_errors_detects_whitespace_only_values` | Detecta valores con solo espacios. |
| `test_ad_account_id_adds_act_prefix_to_numeric_id` | Añade `act_` al id numérico. |
| `test_ad_account_id_keeps_existing_prefix` | Conserva el prefijo `act_`. |
| `test_ad_account_id_empty_stays_empty` | Id vacío → vacío. |

### `AdsServiceTargetingTests`
| Prueba | Qué espera |
| --- | --- |
| `test_build_targeting_with_age_range` | Incluye `age_min`/`age_max`. |
| `test_build_targeting_defaults_missing_age_bounds` | Defaults 18/65 si faltan. |
| `test_build_targeting_with_genders` | Incluye `genders`. |
| `test_build_targeting_without_age_or_genders_omits_keys` | Omite claves si no hay edad/géneros. |

### `AdsServiceSegmentPhonesTests`
| Prueba | Qué espera |
| --- | --- |
| `test_phones_from_segment_includes_every_contact_when_not_only_subscribed` | `only_subscribed=False` incluye todos. |
| `test_phones_from_segment_excludes_non_subscribed_by_default` | Por defecto excluye no suscritos. |

### `AdsServiceTransportTests`
| Prueba | Qué espera |
| --- | --- |
| `test_exception_category_maps_http_error_and_value_error` | Clasifica `HTTPError` y `ValueError`. |
| `test_call_without_token_returns_error_and_does_not_call_meta` | Sin token → error sin llamar. |

### `AdsServiceDebugTokenTests`
| Prueba | Qué espera |
| --- | --- |
| `test_debug_token_requires_app_id_and_secret` | Falta `META_APP_ID`/`META_APP_SECRET` → error. |
| `test_debug_token_requires_both_app_credentials` | Exige ambas credenciales. |

### `AdsServiceObjectTests`
| Prueba | Qué espera |
| --- | --- |
| `test_get_ad_account_labels_known_status` | Etiqueta el estado conocido. |
| `test_get_ad_account_keeps_raw_value_for_unknown_status` | Estado desconocido → valor crudo. |
| `test_get_ad_account_reports_communication_error` | Error de comunicación → error. |
| `test_get_business_reads_business` | Lee el portafolio. |
| `test_get_business_requires_business_id` | Falta `META_BUSINESS_ID` → error. |
| `test_create_custom_audience_posts_payload` | Crea la audiencia con el payload. |
| `test_create_custom_audience_without_id_reports_error` | Sin id → error. |
| `test_create_custom_audience_reports_timeout` | Timeout → error. |
| `test_create_status_ad_creative_posts_expected_payload` | Crea el creativo con el payload. |
| `test_create_status_ad_creative_without_page_reports_config_error` | Falta página → error. |
| `test_create_status_ad_creative_without_id_reports_error` | Sin id → error. |
| `test_create_ad_posts_expected_payload` | Crea el anuncio con el payload. |
| `test_create_ad_without_id_reports_error` | Sin id → error. |

### `AdsServiceAudienceBatchTests`
| Prueba | Qué espera |
| --- | --- |
| `test_add_phones_to_audience_without_phones_reports_error` | Sin teléfonos → error. |
| `test_add_phones_to_audience_ignores_blank_numbers` | Ignora números vacíos. |
| `test_add_phones_to_audience_splits_batches_over_5000` | Divide lotes >5000. |
| `test_add_phones_to_audience_stops_on_batch_failure` | Fallo de lote → error con `added` parcial. |

### `AdsServiceAdSetValidationTests`
| Prueba | Qué espera |
| --- | --- |
| `test_create_status_ad_set_without_page_reports_config_error` | Falta página → error. |
| `test_create_status_ad_set_without_phone_reports_config_error` | Falta teléfono → error. |
| `test_create_status_ad_set_validates_page_before_phone` | Valida la página antes que el teléfono. |
| `test_create_status_ad_set_without_id_reports_error` | Sin id → error. |

### `AdsServiceUploadImageTests`
| Prueba | Qué espera |
| --- | --- |
| `test_upload_ad_image_reports_oserror_for_missing_file` | Archivo no encontrado → error. |
| `test_upload_ad_image_without_hash_reports_error` | Sin hash → error. |
| `test_upload_ad_image_passed_content_type_overrides_inference` | `content_type` pasado manda. |
| `test_upload_ad_image_passed_content_type_adds_extension` | Agrega extensión según el MIME. |

### `AdsServiceCreateStatusAdFlowTests`
| Prueba | Qué espera |
| --- | --- |
| `test_create_status_ad_full_flow_creates_every_object` | Crea campaña + ad set + creativo + anuncio. |
| `test_create_status_ad_reuses_campaign_and_ad_set` | Reutiliza `campaign_id`/`ad_set_id`. |
| `test_create_status_ad_with_image_hash_skips_upload` | Con `image_hash`, no sube imagen. |
| `test_create_status_ad_without_configuration_reports_missing_variables` | Sin config → error con las variables. |
| `test_create_status_ad_stops_when_image_upload_fails` | Fallo de imagen → se detiene con traza. |

---

## `communications/tests/test_test_send.py` — 4 pruebas nuevas

### `RecordTestSendRegistryTests`
| Prueba | Qué espera |
| --- | --- |
| `test_record_test_send_returns_none_without_wamid` | Sin `wamid` → `None`. |
| `test_record_test_send_returns_none_when_wamid_is_none` | `wamid` `None` → `None`. |
| `test_record_test_send_creates_event_with_expected_fields` | Crea el evento con los campos esperados. |
| `test_record_test_send_duplicate_wamid_reuses_existing_event` | Duplicado → reutiliza el evento con `get_or_create`. |
