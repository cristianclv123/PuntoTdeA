from django.shortcuts import render

from .mock_data import CASE_MESSAGES, CASE_NOTES, CHANNEL_META, CONVERSATIONS, get_conversation


def _with_channel_meta(conversation):
    icon_name, css_class, label = CHANNEL_META[conversation["channel"]]
    return {**conversation, "channel_icon": icon_name, "channel_class": css_class, "channel_label": label}


def bandeja(request):
    conversations = [_with_channel_meta(c) for c in CONVERSATIONS]
    context = {
        "active_nav": "bandeja",
        "conversations": conversations,
        "result_count": len(conversations),
    }
    return render(request, "cases/bandeja.html", context)


def caso_detail(request, case_id):
    conversation = _with_channel_meta(get_conversation(case_id))
    context = {
        "active_nav": "bandeja",
        "conversation": conversation,
        "messages": CASE_MESSAGES,
        "notes": CASE_NOTES,
    }
    return render(request, "cases/caso_detail.html", context)
