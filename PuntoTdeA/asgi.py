"""
ASGI config for PuntoTdeA project.
"""

import os

from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "PuntoTdeA.settings")

django_asgi_app = get_asgi_application()

from cases.routing import websocket_urlpatterns as cases_ws  # noqa: E402
from notifications.routing import websocket_urlpatterns as notifications_ws  # noqa: E402

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": AllowedHostsOriginValidator(
            AuthMiddlewareStack(URLRouter(cases_ws + notifications_ws))
        ),
    }
)
