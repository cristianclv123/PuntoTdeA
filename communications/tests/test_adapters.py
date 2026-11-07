"""Pruebas unitarias de ``communications/adapters/meta_adapter.py``.

Todas las peticiones a la Graph API se mockean; nunca se llama a la API real.
"""

from types import SimpleNamespace
from unittest.mock import Mock, patch

import requests
from django.test import SimpleTestCase, override_settings

from communications.adapters.base import SendResult, TemplateRef
from communications.adapters.meta_adapter import (
    MetaAdapter,
    _configuration_error,
    _interactive_envelope,
    _media_url,
    _messages_url,
    _normalize_phone,
    _post_message,
    _request_error,
    send_image_message,
    send_interactive_buttons,
    send_interactive_list,
    send_media_message,
    send_text_message,
    send_uploaded_image_message,
    upload_whatsapp_media,
)

_META_OK = {
    "META_ACCESS_TOKEN": "meta-access-token",
    "WHATSAPP_PHONE_NUMBER_ID": "123456789",
    "WHATSAPP_API_VERSION": "v21.0",
    "META_GRAPH_API_URL": "https://graph.facebook.com",
}

_POST_PATH = "communications.adapters.meta_adapter.requests.post"


def _ok_response(json_body):
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = json_body
    response.text = ""
    return response


def _invalid_json_response(text=""):
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.side_effect = ValueError("invalid json")
    response.text = text
    return response


def _http_error_response(json_body, error):
    response = Mock()
    response.raise_for_status.side_effect = error
    response.json.return_value = json_body
    response.text = ""
    return response


class ConfigurationErrorTests(SimpleTestCase):
    @override_settings(META_ACCESS_TOKEN="token", WHATSAPP_PHONE_NUMBER_ID="123")
    def test_returns_empty_string_when_configured(self):
        self.assertEqual(_configuration_error(), "")

    @override_settings(META_ACCESS_TOKEN="", WHATSAPP_PHONE_NUMBER_ID="123")
    def test_reports_only_missing_token(self):
        self.assertEqual(_configuration_error(), "Falta configurar: META_ACCESS_TOKEN.")

    @override_settings(META_ACCESS_TOKEN="token", WHATSAPP_PHONE_NUMBER_ID="")
    def test_reports_only_missing_phone_number_id(self):
        self.assertEqual(
            _configuration_error(), "Falta configurar: WHATSAPP_PHONE_NUMBER_ID."
        )

    @override_settings(META_ACCESS_TOKEN="", WHATSAPP_PHONE_NUMBER_ID="")
    def test_reports_both_missing_secrets(self):
        self.assertEqual(
            _configuration_error(),
            "Falta configurar: META_ACCESS_TOKEN, WHATSAPP_PHONE_NUMBER_ID.",
        )


class UrlBuilderTests(SimpleTestCase):
    @override_settings(
        META_GRAPH_API_URL="https://graph.facebook.com/",
        WHATSAPP_API_VERSION="v21.0",
        WHATSAPP_PHONE_NUMBER_ID="123456789",
    )
    def test_messages_url_strips_trailing_slash(self):
        self.assertEqual(
            _messages_url(), "https://graph.facebook.com/v21.0/123456789/messages"
        )

    @override_settings(
        META_GRAPH_API_URL="https://graph.facebook.com",
        WHATSAPP_API_VERSION="v2.0",
        WHATSAPP_PHONE_NUMBER_ID="999",
    )
    def test_media_url_without_trailing_slash(self):
        self.assertEqual(_media_url(), "https://graph.facebook.com/v2.0/999/media")


class NormalizePhoneTests(SimpleTestCase):
    def test_strips_plus_spaces_and_punctuation(self):
        self.assertEqual(_normalize_phone("+57 300 111 2233"), "573001112233")

    def test_empty_string_returns_empty(self):
        self.assertEqual(_normalize_phone(""), "")

    def test_none_returns_empty(self):
        self.assertEqual(_normalize_phone(None), "")

    def test_only_plus_returns_empty(self):
        self.assertEqual(_normalize_phone("+"), "")

    def test_keeps_only_digits(self):
        self.assertEqual(
            _normalize_phone("(57) 300-111-2233 ext. 4"), "5730011122334"
        )


class RequestErrorTests(SimpleTestCase):
    @patch("communications.adapters.meta_adapter.explain", return_value="explicación")
    def test_uses_meta_error_message(self, explain):
        response = Mock()
        response.json.return_value = {"error": {"message": "el token expiró"}}

        result = _request_error(response, Exception("falló la red"))

        explain.assert_called_once_with("el token expiró")
        self.assertEqual(result, "explicación")

    @patch("communications.adapters.meta_adapter.explain", return_value="explicación")
    def test_falls_back_to_response_text_when_json_is_invalid(self, explain):
        response = _invalid_json_response("Bad Gateway")

        _request_error(response, Exception("falló la red"))

        explain.assert_called_once_with("Bad Gateway")

    @patch("communications.adapters.meta_adapter.explain", return_value="explicación")
    def test_uses_exception_message_when_response_is_none(self, explain):
        _request_error(None, Exception("conexión rechazada"))

        explain.assert_called_once_with("conexión rechazada")

    @patch("communications.adapters.meta_adapter.explain", return_value="explicación")
    def test_uses_exception_when_meta_detail_is_empty(self, explain):
        response = Mock()
        response.json.return_value = {"error": {"message": ""}}

        _request_error(response, Exception("timeout"))

        explain.assert_called_once_with("timeout")

    def test_translates_known_meta_error_code(self):
        response = Mock()
        response.json.return_value = {
            "error": {"message": "Message failed #131026"}
        }

        result = _request_error(response, Exception("http 400"))

        self.assertIn("no pudo entregar", result)
        self.assertIn("131026", result)


@override_settings(**_META_OK)
class PostMessageTests(SimpleTestCase):
    @patch(_POST_PATH)
    def test_success_returns_provider_message_id(self, post):
        post.return_value = _ok_response({"messages": [{"id": "wamid.1"}]})

        result = _post_message({"to": "573001112233"})

        self.assertTrue(result.success)
        self.assertEqual(result.provider_message_id, "wamid.1")
        self.assertEqual(result.error, "")

    @patch(_POST_PATH)
    def test_posts_to_messages_url_with_auth_and_timeout(self, post):
        post.return_value = _ok_response({"messages": [{"id": "wamid.1"}]})

        _post_message({"to": "573001112233", "type": "text"})

        args, kwargs = post.call_args
        self.assertEqual(
            args[0], "https://graph.facebook.com/v21.0/123456789/messages"
        )
        self.assertEqual(
            kwargs["headers"]["Authorization"], "Bearer meta-access-token"
        )
        self.assertEqual(kwargs["headers"]["Content-Type"], "application/json")
        self.assertEqual(kwargs["json"], {"to": "573001112233", "type": "text"})
        self.assertEqual(kwargs["timeout"], 10.0)

    @patch(_POST_PATH)
    def test_returns_meta_error_on_http_failure(self, post):
        post.return_value = _http_error_response(
            {"error": {"message": "token inválido"}},
            requests.HTTPError("400 Client Error"),
        )

        result = _post_message({"to": "573001112233"})

        self.assertFalse(result.success)
        self.assertIn("token inválido", result.error)

    @patch(_POST_PATH)
    def test_returns_error_when_post_raises_request_exception(self, post):
        post.side_effect = requests.ConnectionError("sin conexión")

        result = _post_message({"to": "573001112233"})

        self.assertFalse(result.success)
        self.assertIn("sin conexión", result.error)

    @patch(_POST_PATH)
    def test_returns_response_text_when_response_json_is_invalid(self, post):
        post.return_value = _invalid_json_response("Internal Server Error")

        result = _post_message({"to": "573001112233"})

        self.assertFalse(result.success)
        self.assertIn("Internal Server Error", result.error)

    @patch(_POST_PATH)
    def test_returns_error_when_meta_does_not_return_message_id(self, post):
        post.return_value = _ok_response({"messages": []})

        result = _post_message({"to": "573001112233"})

        self.assertFalse(result.success)
        self.assertIn("no devolvió el identificador del mensaje", result.error)

    @patch(_POST_PATH)
    def test_returns_error_when_message_entry_has_empty_id(self, post):
        post.return_value = _ok_response({"messages": [{"id": ""}]})

        result = _post_message({"to": "573001112233"})

        self.assertFalse(result.success)
        self.assertIn("no devolvió el identificador del mensaje", result.error)

    @override_settings(META_ACCESS_TOKEN="", WHATSAPP_PHONE_NUMBER_ID="")
    @patch(_POST_PATH)
    def test_returns_configuration_error_without_calling_api(self, post):
        result = _post_message({"to": "573001112233"})

        self.assertFalse(result.success)
        self.assertIn("Falta configurar", result.error)
        post.assert_not_called()


@override_settings(**_META_OK)
class SendTextMessageTests(SimpleTestCase):
    @patch("communications.adapters.meta_adapter._post_message")
    def test_builds_text_payload(self, post_message):
        post_message.return_value = SendResult(
            success=True, provider_message_id="wamid.text.1"
        )

        result = send_text_message("+57 300 111 2233", "Hola Ana")

        self.assertTrue(result.success)
        self.assertEqual(result.provider_message_id, "wamid.text.1")
        self.assertEqual(
            post_message.call_args.args[0],
            {
                "messaging_product": "whatsapp",
                "to": "573001112233",
                "type": "text",
                "text": {"body": "Hola Ana"},
            },
        )

    @patch("communications.adapters.meta_adapter._post_message")
    def test_preview_url_flag_adds_preview_key(self, post_message):
        post_message.return_value = SendResult(success=True)

        send_text_message("+573001112233", "Mira https://example.com", preview_url=True)

        payload = post_message.call_args.args[0]
        self.assertIs(payload["text"]["preview_url"], True)

    @patch("communications.adapters.meta_adapter._post_message")
    def test_preview_url_defaults_to_false(self, post_message):
        post_message.return_value = SendResult(success=True)

        send_text_message("+573001112233", "Sin preview")

        payload = post_message.call_args.args[0]
        self.assertNotIn("preview_url", payload["text"])

    @patch("communications.adapters.meta_adapter._post_message")
    def test_strips_body_whitespace(self, post_message):
        post_message.return_value = SendResult(success=True)

        send_text_message("+573001112233", "  Hola Ana  ")

        payload = post_message.call_args.args[0]
        self.assertEqual(payload["text"], {"body": "Hola Ana"})

    @patch("communications.adapters.meta_adapter._post_message")
    def test_rejects_empty_text(self, post_message):
        result = send_text_message("+573001112233", "   ")

        self.assertFalse(result.success)
        self.assertEqual(result.error, "El texto del mensaje está vacío.")
        post_message.assert_not_called()

    @patch("communications.adapters.meta_adapter._post_message")
    def test_rejects_empty_phone(self, post_message):
        result = send_text_message("", "Hola")

        self.assertFalse(result.success)
        self.assertEqual(result.error, "Número de teléfono vacío.")
        post_message.assert_not_called()


class InteractiveEnvelopeTests(SimpleTestCase):
    def test_empty_body_returns_error(self):
        payload, error = _interactive_envelope("573001112233", "   ")

        self.assertEqual(payload, {})
        self.assertEqual(error, "El cuerpo del mensaje interactivo está vacío.")

    def test_body_longer_than_1024_returns_error(self):
        payload, error = _interactive_envelope("573001112233", "x" * 1025)

        self.assertEqual(payload, {})
        self.assertEqual(
            error, "El cuerpo del mensaje interactivo supera los 1024 caracteres."
        )

    def test_header_longer_than_60_returns_error(self):
        payload, error = _interactive_envelope(
            "573001112233", "Cuerpo", header_text="h" * 61
        )

        self.assertEqual(payload, {})
        self.assertEqual(error, "El encabezado supera los 60 caracteres.")

    def test_footer_longer_than_60_returns_error(self):
        payload, error = _interactive_envelope(
            "573001112233", "Cuerpo", footer_text="f" * 61
        )

        self.assertEqual(payload, {})
        self.assertEqual(error, "El pie supera los 60 caracteres.")

    def test_builds_envelope_with_header_and_footer(self):
        payload, error = _interactive_envelope(
            "573001112233",
            "Cuerpo del mensaje",
            header_text="Encabezado",
            footer_text="Pie de página",
        )

        self.assertEqual(error, "")
        self.assertEqual(payload["messaging_product"], "whatsapp")
        self.assertEqual(payload["recipient_type"], "individual")
        self.assertEqual(payload["to"], "573001112233")
        self.assertEqual(payload["type"], "interactive")
        self.assertEqual(payload["interactive"]["body"]["text"], "Cuerpo del mensaje")
        self.assertEqual(
            payload["interactive"]["header"], {"type": "text", "text": "Encabezado"}
        )
        self.assertEqual(payload["interactive"]["footer"], {"text": "Pie de página"})

    def test_omits_empty_header_and_footer(self):
        payload, error = _interactive_envelope("573001112233", "Cuerpo")

        self.assertEqual(error, "")
        self.assertNotIn("header", payload["interactive"])
        self.assertNotIn("footer", payload["interactive"])


@override_settings(**_META_OK)
class SendInteractiveButtonsTests(SimpleTestCase):
    @patch("communications.adapters.meta_adapter._post_message")
    def test_builds_buttons_payload(self, post_message):
        post_message.return_value = SendResult(
            success=True, provider_message_id="wamid.buttons.1"
        )

        result = send_interactive_buttons(
            "+57 300 111 2233",
            "¿Qué deseas hacer?",
            [
                {"id": "chat_more", "title": "Otra consulta"},
                {"id": "chat_finish", "title": "Finalizar"},
            ],
            header_text="Hola",
            footer_text="Gracias",
        )

        self.assertTrue(result.success)
        payload = post_message.call_args.args[0]
        self.assertEqual(payload["to"], "573001112233")
        self.assertEqual(payload["interactive"]["type"], "button")
        self.assertEqual(payload["interactive"]["body"]["text"], "¿Qué deseas hacer?")
        self.assertEqual(payload["interactive"]["header"]["text"], "Hola")
        self.assertEqual(payload["interactive"]["footer"]["text"], "Gracias")
        self.assertEqual(
            payload["interactive"]["action"]["buttons"],
            [
                {"type": "reply", "reply": {"id": "chat_more", "title": "Otra consulta"}},
                {"type": "reply", "reply": {"id": "chat_finish", "title": "Finalizar"}},
            ],
        )

    @patch("communications.adapters.meta_adapter._post_message")
    def test_strips_button_id_and_title(self, post_message):
        post_message.return_value = SendResult(success=True)

        send_interactive_buttons(
            "573001112233", "Cuerpo", [{"id": "  opcion  ", "title": "  Opción  "}]
        )

        payload = post_message.call_args.args[0]
        self.assertEqual(
            payload["interactive"]["action"]["buttons"],
            [{"type": "reply", "reply": {"id": "opcion", "title": "Opción"}}],
        )

    @patch("communications.adapters.meta_adapter._post_message")
    def test_rejects_duplicate_button_ids(self, post_message):
        result = send_interactive_buttons(
            "573001112233",
            "Cuerpo",
            [
                {"id": "same", "title": "Uno"},
                {"id": "same", "title": "Dos"},
            ],
        )

        self.assertFalse(result.success)
        self.assertEqual(
            result.error, "Los identificadores de botón deben ser únicos."
        )
        post_message.assert_not_called()

    @patch("communications.adapters.meta_adapter._post_message")
    def test_rejects_button_without_id(self, post_message):
        result = send_interactive_buttons(
            "573001112233", "Cuerpo", [{"id": "   ", "title": "Uno"}]
        )

        self.assertFalse(result.success)
        self.assertEqual(result.error, "Cada botón necesita id y título.")
        post_message.assert_not_called()

    @patch("communications.adapters.meta_adapter._post_message")
    def test_rejects_button_without_title(self, post_message):
        result = send_interactive_buttons(
            "573001112233", "Cuerpo", [{"id": "ok", "title": ""}]
        )

        self.assertFalse(result.success)
        self.assertEqual(result.error, "Cada botón necesita id y título.")
        post_message.assert_not_called()

    @patch("communications.adapters.meta_adapter._post_message")
    def test_rejects_title_longer_than_20_chars(self, post_message):
        result = send_interactive_buttons(
            "573001112233", "Cuerpo", [{"id": "ok", "title": "x" * 21}]
        )

        self.assertFalse(result.success)
        self.assertEqual(
            result.error, "El título de un botón supera los 20 caracteres."
        )
        post_message.assert_not_called()

    @patch("communications.adapters.meta_adapter._post_message")
    def test_rejects_empty_body(self, post_message):
        result = send_interactive_buttons(
            "573001112233", "   ", [{"id": "ok", "title": "Uno"}]
        )

        self.assertFalse(result.success)
        self.assertEqual(
            result.error, "El cuerpo del mensaje interactivo está vacío."
        )
        post_message.assert_not_called()

    @patch("communications.adapters.meta_adapter._post_message")
    def test_rejects_empty_phone(self, post_message):
        result = send_interactive_buttons("", "Cuerpo", [{"id": "ok", "title": "Uno"}])

        self.assertFalse(result.success)
        self.assertEqual(result.error, "Número de teléfono vacío.")
        post_message.assert_not_called()

    @patch("communications.adapters.meta_adapter._post_message")
    def test_rejects_zero_buttons(self, post_message):
        result = send_interactive_buttons("573001112233", "Cuerpo", [])

        self.assertFalse(result.success)
        self.assertEqual(
            result.error, "WhatsApp admite entre 1 y 3 botones de respuesta."
        )
        post_message.assert_not_called()


@override_settings(**_META_OK)
class SendInteractiveListTests(SimpleTestCase):
    @patch("communications.adapters.meta_adapter._post_message")
    def test_builds_list_payload(self, post_message):
        post_message.return_value = SendResult(
            success=True, provider_message_id="wamid.list.1"
        )

        result = send_interactive_list(
            "+57 300 111 2233",
            "Elige una opción",
            "Ver opciones",
            [
                {
                    "title": "Sección 1",
                    "rows": [
                        {
                            "id": "chat_advisor",
                            "title": "Hablar con asesor",
                            "description": "Te conectamos con un asesor",
                        }
                    ],
                },
                {"rows": [{"id": "chat_finish", "title": "Finalizar"}]},
            ],
        )

        self.assertTrue(result.success)
        payload = post_message.call_args.args[0]
        self.assertEqual(payload["to"], "573001112233")
        self.assertEqual(payload["interactive"]["type"], "list")
        self.assertEqual(
            payload["interactive"]["action"]["button"], "Ver opciones"
        )
        sections = payload["interactive"]["action"]["sections"]
        self.assertEqual(len(sections), 2)
        self.assertEqual(sections[0]["title"], "Sección 1")
        self.assertEqual(
            sections[0]["rows"],
            [
                {
                    "id": "chat_advisor",
                    "title": "Hablar con asesor",
                    "description": "Te conectamos con un asesor",
                }
            ],
        )
        self.assertNotIn("title", sections[1])
        self.assertEqual(
            sections[1]["rows"], [{"id": "chat_finish", "title": "Finalizar"}]
        )

    @patch("communications.adapters.meta_adapter._post_message")
    def test_rejects_empty_button_label(self, post_message):
        result = send_interactive_list("573001112233", "Cuerpo", "   ", [])

        self.assertFalse(result.success)
        self.assertEqual(
            result.error,
            "La etiqueta del botón de la lista debe tener entre 1 y 20 caracteres.",
        )
        post_message.assert_not_called()

    @patch("communications.adapters.meta_adapter._post_message")
    def test_rejects_button_label_longer_than_20_chars(self, post_message):
        result = send_interactive_list("573001112233", "Cuerpo", "x" * 21, [])

        self.assertFalse(result.success)
        self.assertEqual(
            result.error,
            "La etiqueta del botón de la lista debe tener entre 1 y 20 caracteres.",
        )
        post_message.assert_not_called()

    @patch("communications.adapters.meta_adapter._post_message")
    def test_rejects_empty_phone(self, post_message):
        result = send_interactive_list("", "Cuerpo", "Botón", [])

        self.assertFalse(result.success)
        self.assertEqual(result.error, "Número de teléfono vacío.")
        post_message.assert_not_called()

    @patch("communications.adapters.meta_adapter._post_message")
    def test_rejects_section_title_longer_than_24_chars(self, post_message):
        result = send_interactive_list(
            "573001112233",
            "Cuerpo",
            "Botón",
            [{"title": "x" * 25, "rows": [{"id": "r1", "title": "Uno"}]}],
        )

        self.assertFalse(result.success)
        self.assertEqual(
            result.error, "El título de una sección supera los 24 caracteres."
        )
        post_message.assert_not_called()

    @patch("communications.adapters.meta_adapter._post_message")
    def test_rejects_row_without_id(self, post_message):
        result = send_interactive_list(
            "573001112233",
            "Cuerpo",
            "Botón",
            [{"rows": [{"id": "", "title": "Uno"}]}],
        )

        self.assertFalse(result.success)
        self.assertEqual(
            result.error, "Cada fila de la lista necesita id y título."
        )
        post_message.assert_not_called()

    @patch("communications.adapters.meta_adapter._post_message")
    def test_rejects_row_without_title(self, post_message):
        result = send_interactive_list(
            "573001112233",
            "Cuerpo",
            "Botón",
            [{"rows": [{"id": "r1", "title": "   "}]}],
        )

        self.assertFalse(result.success)
        self.assertEqual(
            result.error, "Cada fila de la lista necesita id y título."
        )
        post_message.assert_not_called()

    @patch("communications.adapters.meta_adapter._post_message")
    def test_rejects_duplicate_row_ids_across_sections(self, post_message):
        result = send_interactive_list(
            "573001112233",
            "Cuerpo",
            "Botón",
            [
                {"rows": [{"id": "r1", "title": "Uno"}]},
                {"rows": [{"id": "r1", "title": "Otro"}]},
            ],
        )

        self.assertFalse(result.success)
        self.assertEqual(
            result.error, "Los identificadores de fila deben ser únicos."
        )
        post_message.assert_not_called()

    @patch("communications.adapters.meta_adapter._post_message")
    def test_rejects_row_title_longer_than_24_chars(self, post_message):
        result = send_interactive_list(
            "573001112233",
            "Cuerpo",
            "Botón",
            [{"rows": [{"id": "r1", "title": "x" * 25}]}],
        )

        self.assertFalse(result.success)
        self.assertEqual(
            result.error, "El título de una fila supera los 24 caracteres."
        )
        post_message.assert_not_called()

    @patch("communications.adapters.meta_adapter._post_message")
    def test_rejects_row_description_longer_than_72_chars(self, post_message):
        result = send_interactive_list(
            "573001112233",
            "Cuerpo",
            "Botón",
            [{"rows": [{"id": "r1", "title": "Uno", "description": "x" * 73}]}],
        )

        self.assertFalse(result.success)
        self.assertEqual(
            result.error, "La descripción de una fila supera los 72 caracteres."
        )
        post_message.assert_not_called()

    @patch("communications.adapters.meta_adapter._post_message")
    def test_rejects_section_with_empty_rows(self, post_message):
        result = send_interactive_list(
            "573001112233",
            "Cuerpo",
            "Botón",
            [{"title": "Vacía", "rows": []}],
        )

        self.assertFalse(result.success)
        self.assertEqual(
            result.error, "Cada sección de la lista debe tener al menos una fila."
        )
        post_message.assert_not_called()

    @patch("communications.adapters.meta_adapter._post_message")
    def test_rejects_section_without_rows_key(self, post_message):
        result = send_interactive_list(
            "573001112233", "Cuerpo", "Botón", [{"title": "Vacía"}]
        )

        self.assertFalse(result.success)
        self.assertEqual(
            result.error, "Cada sección de la lista debe tener al menos una fila."
        )
        post_message.assert_not_called()

    @patch("communications.adapters.meta_adapter._post_message")
    def test_rejects_more_than_ten_rows(self, post_message):
        rows = [{"id": f"r{i}", "title": f"Opción {i}"} for i in range(11)]

        result = send_interactive_list(
            "573001112233", "Cuerpo", "Botón", [{"rows": rows}]
        )

        self.assertFalse(result.success)
        self.assertEqual(
            result.error, "WhatsApp admite entre 1 y 10 opciones en una lista."
        )
        post_message.assert_not_called()

    @patch("communications.adapters.meta_adapter._post_message")
    def test_rejects_empty_sections(self, post_message):
        result = send_interactive_list("573001112233", "Cuerpo", "Botón", [])

        self.assertFalse(result.success)
        self.assertEqual(
            result.error, "WhatsApp admite entre 1 y 10 opciones en una lista."
        )
        post_message.assert_not_called()


@override_settings(**_META_OK)
class SendImageMessageTests(SimpleTestCase):
    @patch(_POST_PATH)
    def test_uploads_and_sends_image(self, post):
        post.side_effect = [
            _ok_response({"id": "media-image-1"}),
            _ok_response({"messages": [{"id": "wamid.image.1"}]}),
        ]

        result = send_image_message(
            "+57 300 111 2233",
            b"image-content",
            "calendario.png",
            "image/png",
            "Consulta el calendario.",
        )

        self.assertTrue(result.success)
        self.assertEqual(result.provider_message_id, "wamid.image.1")
        self.assertEqual(post.call_count, 2)
        upload_args, upload_kwargs = post.call_args_list[0]
        self.assertEqual(
            upload_args[0], "https://graph.facebook.com/v21.0/123456789/media"
        )
        self.assertEqual(
            upload_kwargs["headers"]["Authorization"], "Bearer meta-access-token"
        )
        self.assertEqual(
            upload_kwargs["data"], {"messaging_product": "whatsapp"}
        )
        self.assertEqual(
            upload_kwargs["files"]["file"],
            ("calendario.png", b"image-content", "image/png"),
        )
        self.assertEqual(
            post.call_args_list[1].kwargs["json"],
            {
                "messaging_product": "whatsapp",
                "to": "573001112233",
                "type": "image",
                "image": {
                    "id": "media-image-1",
                    "caption": "Consulta el calendario.",
                },
            },
        )

    @patch(_POST_PATH)
    def test_omits_caption_when_empty(self, post):
        post.side_effect = [
            _ok_response({"id": "media-image-1"}),
            _ok_response({"messages": [{"id": "wamid.image.1"}]}),
        ]

        result = send_image_message(
            "+573001112233", b"image-content", "foto.jpg", "image/jpeg"
        )

        self.assertTrue(result.success)
        self.assertEqual(
            post.call_args_list[1].kwargs["json"]["image"], {"id": "media-image-1"}
        )

    @patch(_POST_PATH)
    def test_rejects_empty_phone(self, post):
        result = send_image_message("", b"image-content", "foto.jpg", "image/jpeg")

        self.assertFalse(result.success)
        self.assertEqual(result.error, "Número de teléfono vacío.")
        post.assert_not_called()

    @patch(_POST_PATH)
    def test_rejects_empty_image_data(self, post):
        result = send_image_message("+573001112233", b"", "foto.jpg", "image/jpeg")

        self.assertFalse(result.success)
        self.assertEqual(result.error, "El archivo de imagen está vacío.")
        post.assert_not_called()

    @override_settings(META_ACCESS_TOKEN="", WHATSAPP_PHONE_NUMBER_ID="")
    @patch(_POST_PATH)
    def test_rejects_missing_configuration(self, post):
        result = send_image_message(
            "+573001112233", b"image-content", "foto.jpg", "image/jpeg"
        )

        self.assertFalse(result.success)
        self.assertIn("Falta configurar", result.error)
        post.assert_not_called()

    @patch(_POST_PATH)
    def test_returns_error_when_upload_fails(self, post):
        post.side_effect = requests.ConnectionError("sin red")

        result = send_image_message(
            "+573001112233", b"image-content", "foto.jpg", "image/jpeg"
        )

        self.assertFalse(result.success)
        self.assertIn("sin red", result.error)
        self.assertEqual(post.call_count, 1)

    @patch(_POST_PATH)
    def test_returns_meta_error_when_upload_http_fails(self, post):
        post.return_value = _http_error_response(
            {"error": {"message": "subida rechazada"}},
            requests.HTTPError("400 Client Error"),
        )

        result = send_image_message(
            "+573001112233", b"image-content", "foto.jpg", "image/jpeg"
        )

        self.assertFalse(result.success)
        self.assertIn("subida rechazada", result.error)
        self.assertEqual(post.call_count, 1)

    @patch(_POST_PATH)
    def test_returns_error_when_upload_response_has_no_id(self, post):
        post.return_value = _ok_response({})

        result = send_image_message(
            "+573001112233", b"image-content", "foto.jpg", "image/jpeg"
        )

        self.assertFalse(result.success)
        self.assertEqual(
            result.error, "Meta no devolvió el identificador de la imagen."
        )
        self.assertEqual(post.call_count, 1)

    @patch(_POST_PATH)
    def test_rejects_caption_longer_than_1024_chars(self, post):
        post.return_value = _ok_response({"id": "media-image-1"})

        result = send_image_message(
            "+573001112233",
            b"image-content",
            "foto.jpg",
            "image/jpeg",
            "x" * 1025,
        )

        self.assertFalse(result.success)
        self.assertEqual(
            result.error,
            "La respuesta supera el límite de 1024 caracteres del pie de imagen.",
        )
        self.assertEqual(post.call_count, 1)


@override_settings(**_META_OK)
class UploadWhatsappMediaTests(SimpleTestCase):
    @patch(_POST_PATH)
    def test_uploads_media_and_returns_id(self, post):
        post.return_value = _ok_response({"id": "media-file-1"})

        result = upload_whatsapp_media(b"%PDF-1.4", "documento.pdf", "application/pdf")

        self.assertTrue(result.success)
        self.assertEqual(result.provider_message_id, "media-file-1")
        args, kwargs = post.call_args
        self.assertEqual(
            args[0], "https://graph.facebook.com/v21.0/123456789/media"
        )
        self.assertEqual(
            kwargs["headers"]["Authorization"], "Bearer meta-access-token"
        )
        self.assertEqual(kwargs["data"], {"messaging_product": "whatsapp"})
        self.assertEqual(
            kwargs["files"]["file"],
            ("documento.pdf", b"%PDF-1.4", "application/pdf"),
        )

    @override_settings(META_ACCESS_TOKEN="", WHATSAPP_PHONE_NUMBER_ID="")
    @patch(_POST_PATH)
    def test_rejects_missing_configuration(self, post):
        result = upload_whatsapp_media(b"data", "archivo.pdf", "application/pdf")

        self.assertFalse(result.success)
        self.assertIn("Falta configurar", result.error)
        post.assert_not_called()

    @patch(_POST_PATH)
    def test_rejects_empty_file_bytes(self, post):
        result = upload_whatsapp_media(b"", "archivo.pdf", "application/pdf")

        self.assertFalse(result.success)
        self.assertEqual(result.error, "El archivo está vacío.")
        post.assert_not_called()

    @patch(_POST_PATH)
    def test_returns_response_text_when_json_is_invalid(self, post):
        post.return_value = _invalid_json_response("Service Unavailable")

        result = upload_whatsapp_media(b"data", "archivo.pdf", "application/pdf")

        self.assertFalse(result.success)
        self.assertIn("Service Unavailable", result.error)

    @patch(_POST_PATH)
    def test_returns_error_when_response_has_empty_id(self, post):
        post.return_value = _ok_response({"id": ""})

        result = upload_whatsapp_media(b"data", "archivo.pdf", "application/pdf")

        self.assertFalse(result.success)
        self.assertEqual(
            result.error, "Meta no devolvió el ID del medio subido."
        )

    @patch(_POST_PATH)
    def test_returns_error_when_response_has_no_id_key(self, post):
        post.return_value = _ok_response({})

        result = upload_whatsapp_media(b"data", "archivo.pdf", "application/pdf")

        self.assertFalse(result.success)
        self.assertEqual(
            result.error, "Meta no devolvió el ID del medio subido."
        )

    @patch(_POST_PATH)
    def test_returns_meta_error_on_http_failure(self, post):
        post.return_value = _http_error_response(
            {"error": {"message": "solo se admiten archivos menores a 10MB"}},
            requests.HTTPError("413 Request Entity Too Large"),
        )

        result = upload_whatsapp_media(b"data", "archivo.pdf", "application/pdf")

        self.assertFalse(result.success)
        self.assertIn("10MB", result.error)

    @patch(_POST_PATH)
    def test_converts_numeric_media_id_to_string(self, post):
        post.return_value = _ok_response({"id": 12345})

        result = upload_whatsapp_media(b"data", "archivo.pdf", "application/pdf")

        self.assertTrue(result.success)
        self.assertEqual(result.provider_message_id, "12345")


@override_settings(**_META_OK)
class SendUploadedImageMessageTests(SimpleTestCase):
    @patch("communications.adapters.meta_adapter.send_media_message")
    def test_delegates_to_send_media_message(self, send_media):
        send_media.return_value = SendResult(
            success=True, provider_message_id="wamid.image.1"
        )

        result = send_uploaded_image_message(
            "+57 300 111 2233", "media-1", "Pie de foto"
        )

        self.assertTrue(result.success)
        self.assertEqual(result.provider_message_id, "wamid.image.1")
        send_media.assert_called_once_with(
            "+57 300 111 2233",
            media_type="image",
            media_id="media-1",
            caption="Pie de foto",
        )

    @patch("communications.adapters.meta_adapter.send_media_message")
    def test_propagates_error_from_send_media_message(self, send_media):
        send_media.return_value = SendResult(
            success=False, error="El medio ya no existe."
        )

        result = send_uploaded_image_message("+573001112233", "media-1")

        self.assertFalse(result.success)
        self.assertEqual(result.error, "El medio ya no existe.")

    @patch("communications.adapters.meta_adapter._post_message")
    def test_builds_image_payload(self, post_message):
        post_message.return_value = SendResult(
            success=True, provider_message_id="wamid.image.1"
        )

        send_uploaded_image_message("+57 300 111 2233", "media-1", "Pie de foto")

        self.assertEqual(
            post_message.call_args.args[0],
            {
                "messaging_product": "whatsapp",
                "to": "573001112233",
                "type": "image",
                "image": {"id": "media-1", "caption": "Pie de foto"},
            },
        )


@override_settings(**_META_OK)
class SendMediaMessageTests(SimpleTestCase):
    @patch("communications.adapters.meta_adapter._post_message")
    def test_rejects_unsupported_media_type(self, post_message):
        result = send_media_message(
            "+573001112233", media_type="audio", media_id="media-1"
        )

        self.assertFalse(result.success)
        self.assertEqual(result.error, "Tipo de medio no soportado.")
        post_message.assert_not_called()

    @patch("communications.adapters.meta_adapter._post_message")
    def test_rejects_empty_media_id(self, post_message):
        result = send_media_message(
            "+573001112233", media_type="image", media_id="   "
        )

        self.assertFalse(result.success)
        self.assertEqual(result.error, "Falta el id del medio.")
        post_message.assert_not_called()

    @patch("communications.adapters.meta_adapter._post_message")
    def test_rejects_empty_phone(self, post_message):
        result = send_media_message(
            "", media_type="image", media_id="media-1"
        )

        self.assertFalse(result.success)
        self.assertEqual(result.error, "Número de teléfono vacío.")
        post_message.assert_not_called()

    @patch("communications.adapters.meta_adapter._post_message")
    def test_builds_document_payload_with_filename(self, post_message):
        post_message.return_value = SendResult(
            success=True, provider_message_id="wamid.doc.1"
        )

        result = send_media_message(
            "+57 300 111 2233",
            media_type="document",
            media_id="media-doc-1",
            caption="Documento adjunto",
            filename="reglamento.pdf",
        )

        self.assertTrue(result.success)
        self.assertEqual(
            post_message.call_args.args[0],
            {
                "messaging_product": "whatsapp",
                "to": "573001112233",
                "type": "document",
                "document": {
                    "id": "media-doc-1",
                    "caption": "Documento adjunto",
                    "filename": "reglamento.pdf",
                },
            },
        )

    @patch("communications.adapters.meta_adapter._post_message")
    def test_omits_filename_for_document_when_not_provided(self, post_message):
        post_message.return_value = SendResult(success=True)

        send_media_message(
            "+573001112233", media_type="document", media_id="media-doc-1"
        )

        media = post_message.call_args.args[0]["document"]
        self.assertEqual(media, {"id": "media-doc-1"})
        self.assertNotIn("filename", media)

    @patch("communications.adapters.meta_adapter._post_message")
    def test_omits_filename_for_non_document_media(self, post_message):
        post_message.return_value = SendResult(success=True)

        send_media_message(
            "+573001112233",
            media_type="image",
            media_id="media-1",
            filename="foto.png",
        )

        media = post_message.call_args.args[0]["image"]
        self.assertEqual(media, {"id": "media-1"})
        self.assertNotIn("filename", media)

    @patch("communications.adapters.meta_adapter._post_message")
    def test_builds_video_payload_with_caption(self, post_message):
        post_message.return_value = SendResult(
            success=True, provider_message_id="wamid.video.1"
        )

        send_media_message(
            "+573001112233",
            media_type="video",
            media_id="media-video-1",
            caption="  Video de inducción  ",
        )

        self.assertEqual(
            post_message.call_args.args[0],
            {
                "messaging_product": "whatsapp",
                "to": "573001112233",
                "type": "video",
                "video": {
                    "id": "media-video-1",
                    "caption": "Video de inducción",
                },
            },
        )


class MetaAdapterTemplateFieldsTests(SimpleTestCase):
    def test_reads_template_ref_fields(self):
        template = TemplateRef(
            name="bienvenida",
            language="es_CO",
            body_text="Hola {{1}}",
            header_type="text",
            header_text="Aviso",
            header_media_url="",
        )

        fields = MetaAdapter._template_fields(template)

        self.assertEqual(
            fields,
            {
                "name": "bienvenida",
                "language": "es_CO",
                "body_text": "Hola {{1}}",
                "header_type": "text",
                "header_text": "Aviso",
                "header_media_url": "",
            },
        )

    def test_prefers_meta_template_name_and_applies_defaults(self):
        template = SimpleNamespace(
            meta_template_name="meta_welcome",
            name="bienvenida_local",
            language="",
            body_text="",
            header_type="",
            header_text="",
            header_media_url="",
        )

        fields = MetaAdapter._template_fields(template)

        self.assertEqual(fields["name"], "meta_welcome")
        self.assertEqual(fields["language"], "es_CO")
        self.assertEqual(fields["header_type"], "none")
        self.assertEqual(fields["body_text"], "")

    def test_falls_back_to_empty_name(self):
        template = SimpleNamespace(
            meta_template_name="",
            name="",
            language="en_US",
            body_text="Hi",
            header_type="none",
            header_text="",
            header_media_url="",
        )

        fields = MetaAdapter._template_fields(template)

        self.assertEqual(fields["name"], "")
        self.assertEqual(fields["language"], "en_US")


class MetaAdapterParameterValuesTests(SimpleTestCase):
    def test_orders_parameters_numerically(self):
        values, error = MetaAdapter._parameter_values(
            "Hola {{2}} y {{1}}", {"2": "B", "1": "A"}
        )

        self.assertEqual(
            values,
            [{"type": "text", "text": "A"}, {"type": "text", "text": "B"}],
        )
        self.assertEqual(error, "")

    def test_accepts_integer_keys(self):
        values, error = MetaAdapter._parameter_values("Hola {{1}}", {1: "A"})

        self.assertEqual(values, [{"type": "text", "text": "A"}])
        self.assertEqual(error, "")

    def test_accepts_brace_keys(self):
        values, error = MetaAdapter._parameter_values(
            "Hola {{1}}", {"{{1}}": "A"}
        )

        self.assertEqual(values, [{"type": "text", "text": "A"}])
        self.assertEqual(error, "")

    def test_rejects_missing_parameter(self):
        values, error = MetaAdapter._parameter_values(
            "Hola {{1}} y {{2}}", {"1": "A"}
        )

        self.assertEqual(values, [])
        self.assertIn("{{2}}", error)

    def test_repeated_parameter_is_emitted_once(self):
        values, error = MetaAdapter._parameter_values(
            "{{1}} y otra vez {{1}}", {"1": "A"}
        )

        self.assertEqual(values, [{"type": "text", "text": "A"}])
        self.assertEqual(error, "")

    def test_without_parameters_returns_empty_list(self):
        values, error = MetaAdapter._parameter_values("Hola", {})

        self.assertEqual(values, [])
        self.assertEqual(error, "")

    def test_none_body_text_returns_empty_list(self):
        values, error = MetaAdapter._parameter_values(None, {})

        self.assertEqual(values, [])
        self.assertEqual(error, "")


@override_settings(**_META_OK)
class MetaAdapterPayloadTests(SimpleTestCase):
    def setUp(self):
        self.adapter = MetaAdapter()

    def test_builds_template_payload_with_body_parameters(self):
        template = TemplateRef(name="recordatorio", body_text="Hola {{1}}")

        payload, error = self.adapter._payload(
            "+57 300 111 2233", template, {"1": "Ana"}
        )

        self.assertEqual(error, "")
        self.assertEqual(
            payload,
            {
                "messaging_product": "whatsapp",
                "to": "573001112233",
                "type": "template",
                "template": {
                    "name": "recordatorio",
                    "language": {"code": "es_CO"},
                    "components": [
                        {
                            "type": "body",
                            "parameters": [{"type": "text", "text": "Ana"}],
                        }
                    ],
                },
            },
        )

    def test_omits_components_when_template_has_no_parameters(self):
        template = TemplateRef(name="sin_variables", body_text="Hola")

        payload, error = self.adapter._payload("+573001112233", template, {})

        self.assertEqual(error, "")
        self.assertNotIn("components", payload["template"])

    def test_orders_body_parameters_numerically(self):
        template = TemplateRef(name="orden", body_text="{{2}} luego {{1}}")

        payload, _ = self.adapter._payload(
            "+573001112233", template, {"2": "B", "1": "A"}
        )

        parameters = payload["template"]["components"][0]["parameters"]
        self.assertEqual(
            parameters,
            [{"type": "text", "text": "A"}, {"type": "text", "text": "B"}],
        )

    def test_rejects_empty_phone(self):
        template = TemplateRef(name="recordatorio", body_text="Hola")

        payload, error = self.adapter._payload("", template, {})

        self.assertIsNone(payload)
        self.assertEqual(error, "Número de teléfono vacío.")

    def test_rejects_template_without_name(self):
        template = TemplateRef(name="", body_text="Hola")

        payload, error = self.adapter._payload("+573001112233", template, {})

        self.assertIsNone(payload)
        self.assertEqual(
            error, "La plantilla no tiene un nombre válido en Meta."
        )

    def test_rejects_missing_body_parameter(self):
        template = TemplateRef(name="recordatorio", body_text="Hola {{1}}")

        payload, error = self.adapter._payload("+573001112233", template, {})

        self.assertIsNone(payload)
        self.assertIn("{{1}}", error)

    def test_rejects_text_header_without_text(self):
        template = TemplateRef(
            name="recordatorio", body_text="Hola", header_type="text"
        )

        payload, error = self.adapter._payload("+573001112233", template, {})

        self.assertIsNone(payload)
        self.assertEqual(
            error,
            "La plantilla tiene encabezado de texto, pero no contiene el texto requerido.",
        )

    def test_rejects_text_header_with_dynamic_variables(self):
        template = TemplateRef(
            name="recordatorio",
            body_text="Hola",
            header_type="text",
            header_text="Hola {{1}}",
        )

        payload, error = self.adapter._payload(
            "+573001112233", template, {"1": "Ana"}
        )

        self.assertIsNone(payload)
        self.assertEqual(
            error, "El encabezado de texto no admite variables dinámicas."
        )

    def test_builds_text_header_component(self):
        template = TemplateRef(
            name="recordatorio",
            body_text="Hola",
            header_type="text",
            header_text="Aviso importante",
        )

        payload, error = self.adapter._payload("+573001112233", template, {})

        self.assertEqual(error, "")
        self.assertEqual(
            payload["template"]["components"],
            [
                {
                    "type": "header",
                    "parameters": [{"type": "text", "text": "Aviso importante"}],
                }
            ],
        )

    def test_rejects_media_header_without_url(self):
        template = TemplateRef(
            name="recordatorio", body_text="Hola", header_type="image"
        )

        payload, error = self.adapter._payload("+573001112233", template, {})

        self.assertIsNone(payload)
        self.assertEqual(
            error,
            "La plantilla tiene encabezado multimedia pero no una URL configurada.",
        )

    def test_builds_image_header_component(self):
        template = TemplateRef(
            name="recordatorio",
            body_text="Hola",
            header_type="image",
            header_media_url="https://example.com/foto.jpg",
        )

        payload, error = self.adapter._payload("+573001112233", template, {})

        self.assertEqual(error, "")
        self.assertEqual(
            payload["template"]["components"],
            [
                {
                    "type": "header",
                    "parameters": [
                        {
                            "type": "image",
                            "image": {"link": "https://example.com/foto.jpg"},
                        }
                    ],
                }
            ],
        )

    def test_builds_video_header_component(self):
        template = TemplateRef(
            name="recordatorio",
            body_text="Hola",
            header_type="video",
            header_media_url="https://example.com/video.mp4",
        )

        payload, error = self.adapter._payload("+573001112233", template, {})

        self.assertEqual(error, "")
        self.assertEqual(
            payload["template"]["components"][0]["parameters"][0]["type"],
            "video",
        )

    def test_builds_document_header_component(self):
        template = TemplateRef(
            name="recordatorio",
            body_text="Hola",
            header_type="document",
            header_media_url="https://example.com/doc.pdf",
        )

        payload, error = self.adapter._payload("+573001112233", template, {})

        self.assertEqual(error, "")
        self.assertEqual(
            payload["template"]["components"][0]["parameters"][0]["type"],
            "document",
        )

    def test_rejects_unsupported_header_type(self):
        template = TemplateRef(
            name="recordatorio", body_text="Hola", header_type="audio"
        )

        payload, error = self.adapter._payload("+573001112233", template, {})

        self.assertIsNone(payload)
        self.assertEqual(error, "Tipo de encabezado no soportado: audio.")

    def test_uses_es_co_when_language_is_empty(self):
        template = TemplateRef(
            name="recordatorio", language="", body_text="Hola"
        )

        payload, _ = self.adapter._payload("+573001112233", template, {})

        self.assertEqual(
            payload["template"]["language"], {"code": "es_CO"}
        )

    def test_normalizes_phone_number(self):
        template = TemplateRef(name="recordatorio", body_text="Hola")

        payload, _ = self.adapter._payload("(57) 300-111-2233", template, {})

        self.assertEqual(payload["to"], "573001112233")


@override_settings(**_META_OK)
class MetaAdapterSendTemplateTests(SimpleTestCase):
    def setUp(self):
        self.adapter = MetaAdapter()

    @patch("communications.adapters.meta_adapter._post_message")
    def test_delegates_payload_to_post_message(self, post_message):
        post_message.return_value = SendResult(
            success=True, provider_message_id="wamid.template.1"
        )
        template = TemplateRef(name="recordatorio", body_text="Hola {{1}}")

        result = self.adapter.send_template_message(
            "+573001112233", template, {"1": "Ana"}
        )

        self.assertTrue(result.success)
        self.assertEqual(result.provider_message_id, "wamid.template.1")
        payload = post_message.call_args.args[0]
        self.assertEqual(payload["template"]["name"], "recordatorio")
        self.assertEqual(
            payload["template"]["components"],
            [{"type": "body", "parameters": [{"type": "text", "text": "Ana"}]}],
        )

    @patch("communications.adapters.meta_adapter._post_message")
    def test_propagates_validation_error_without_posting(self, post_message):
        template = TemplateRef(name="", body_text="Hola")

        result = self.adapter.send_template_message(
            "+573001112233", template, {}
        )

        self.assertFalse(result.success)
        self.assertEqual(
            result.error, "La plantilla no tiene un nombre válido en Meta."
        )
        post_message.assert_not_called()

    @patch(_POST_PATH)
    def test_sends_template_with_image_header_end_to_end(self, post):
        post.return_value = _ok_response({"messages": [{"id": "wamid.template.1"}]})
        template = TemplateRef(
            name="encabezado_imagen",
            language="es_CO",
            body_text="Hola {{1}}",
            header_type="image",
            header_media_url="https://example.com/foto.jpg",
        )

        result = self.adapter.send_template_message(
            "+57 300 111 2233", template, {"1": "Ana"}
        )

        self.assertTrue(result.success)
        self.assertEqual(result.provider_message_id, "wamid.template.1")
        payload = post.call_args.kwargs["json"]
        self.assertEqual(payload["to"], "573001112233")
        self.assertEqual(
            payload["template"]["components"],
            [
                {"type": "body", "parameters": [{"type": "text", "text": "Ana"}]},
                {
                    "type": "header",
                    "parameters": [
                        {
                            "type": "image",
                            "image": {"link": "https://example.com/foto.jpg"},
                        }
                    ],
                },
            ],
        )
