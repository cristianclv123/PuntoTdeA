from django import template
from django.utils.html import escape
from django.utils.safestring import mark_safe

from cases.services.message_links import first_http_url, iter_http_urls, link_host

register = template.Library()


@register.filter(name="linkify")
def linkify(value):
    text = str(value or "")
    pieces = []
    cursor = 0
    for start, end, url, tail in iter_http_urls(text):
        pieces.append(escape(text[cursor:start]))
        pieces.append(
            '<a class="bubble-link" href="{href}" target="_blank" rel="noopener noreferrer">{label}</a>'.format(
                href=escape(url),
                label=escape(url),
            )
        )
        pieces.append(escape(tail))
        cursor = end
    pieces.append(escape(text[cursor:]))
    return mark_safe("".join(pieces))


@register.filter(name="link_preview")
def link_preview(value):
    url = first_http_url(str(value or ""))
    if not url:
        return ""
    host = link_host(url)
    html = (
        '<a class="link-preview" href="{href}" target="_blank" rel="noopener noreferrer">'
        '<span class="link-preview-kicker">Enlace</span>'
        '<span class="link-preview-host">{host}</span>'
        '<span class="link-preview-url">{url}</span>'
        "</a>"
    ).format(href=escape(url), host=escape(host), url=escape(url))
    return mark_safe(html)
