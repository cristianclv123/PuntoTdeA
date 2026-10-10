# Módulo Dashboard (`dashboard/`)

Home interno tras el login. No tiene modelos propios.

UI: `/dashboard/`.

## Árbol

```
dashboard/
  views.py       # métricas WhatsApp + campañas
  urls.py
  tests.py       # plantilla por defecto (casi vacío)
  apps.py
```

Template: `templates/dashboard.html` (proyecto raíz), layout `base.html` + sidebar.

## Qué muestra (`views.index`)

Solo conversaciones `channel=whatsapp`:

| Tarjeta | Definición |
| --- | --- |
| Casos abiertos | No `CERRADO` |
| Pendientes | `status=pendiente` |
| Sin asesor | abiertos sin `assigned_to` |
| Escalados | `status=escalado` |
| Cerrados hoy | `closed_at` del día (fallback `updated_at`) |

Además: carga de asesores (`_advisor_workload`) y bloque de campañas vía `communications.services.dashboard_service` (envíos / estados, no métricas inventadas de otros canales).

Auth: `login_required`.

## Qué no hace

No gestiona tickets (eso es `/bandeja/`). No dispara WhatsApp. Es lectura agregada.
