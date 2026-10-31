"""Detección de URLs http(s) en el texto de un mensaje de caso."""

import re
from urllib.parse import urlparse

_URL_RE = re.compile(r"https?://[^\s<>'\"]+", re.IGNORECASE)
_TRAILING = ".,);:]"


def clean_url(raw: str) -> str:
    return (raw or "").rstrip(_TRAILING)


def iter_http_urls(text: str):
    for match in _URL_RE.finditer(text or ""):
        url = clean_url(match.group(0))
        if url:
            yield match.start(), match.end(), url, match.group(0)[len(url) :]


def first_http_url(text: str) -> str:
    for _start, _end, url, _tail in iter_http_urls(text):
        return url
    return ""


def link_host(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    if host.startswith("www."):
        return host[4:]
    return host or url
