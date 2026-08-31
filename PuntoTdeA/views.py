from django.shortcuts import render

METRIC_CARDS = [
    {"label": "Casos pendientes", "value": "34", "sub": "requieren atención", "icon": "inbox", "bg": "var(--warning-bg)", "fg": "var(--warning-text)"},
    {"label": "Casos escalados", "value": "7", "sub": "a otras dependencias", "icon": "arrow-up-right", "bg": "var(--danger-bg)", "fg": "var(--danger-text)"},
    {"label": "Cerrados hoy", "value": "52", "sub": "resueltos en el día", "icon": "circle-check", "bg": "var(--success-bg)", "fg": "var(--success-text)"},
    {"label": "Tiempo prom. respuesta", "value": "6m 40s", "sub": "últimas 24 horas", "icon": "clock-4", "bg": "var(--blue-soft)", "fg": "var(--blue)"},
]

CHANNEL_BARS = [
    {"label": "WhatsApp", "value": 58, "icon": "message-circle", "color": "var(--green)"},
    {"label": "Facebook", "value": 34, "icon": "facebook", "color": "var(--facebook)"},
    {"label": "Instagram", "value": 22, "icon": "instagram", "color": "var(--instagram)"},
    {"label": "Web", "value": 14, "icon": "globe", "color": "var(--web)"},
]

ADVISOR_LOAD = [
    {"name": "Laura Gómez", "value": 42},
    {"name": "Karen Ruiz", "value": 36},
    {"name": "Julián Torres", "value": 29},
    {"name": "Sin asignar", "value": 15},
]

WORKLOAD_ROWS = [
    {"initials": "LG", "name": "Laura Gómez", "assigned": 42, "pending": 9, "closed_today": 14, "state": "Disponible", "state_class": "pill-success"},
    {"initials": "KR", "name": "Karen Ruiz", "assigned": 36, "pending": 12, "closed_today": 10, "state": "En llamada", "state_class": "pill-info"},
    {"initials": "JT", "name": "Julián Torres", "assigned": 29, "pending": 4, "closed_today": 18, "state": "Disponible", "state_class": "pill-success"},
    {"initials": "CO", "name": "Camila Ortiz", "assigned": 24, "pending": 7, "closed_today": 11, "state": "Ausente", "state_class": "pill-neutral"},
]


def login_view(request):
    return render(request, "login.html")


def dashboard(request):
    max_channel_value = max(bar["value"] for bar in CHANNEL_BARS)
    channel_bars = [
        {**bar, "height_pct": round(bar["value"] / max_channel_value * 100)}
        for bar in CHANNEL_BARS
    ]
    max_advisor_value = max(row["value"] for row in ADVISOR_LOAD)
    advisor_load = [
        {**row, "width_pct": round(row["value"] / max_advisor_value * 100)}
        for row in ADVISOR_LOAD
    ]
    context = {
        "active_nav": "dashboard",
        "metric_cards": METRIC_CARDS,
        "channel_bars": channel_bars,
        "advisor_load": advisor_load,
        "workload_rows": WORKLOAD_ROWS,
    }
    return render(request, "dashboard.html", context)
