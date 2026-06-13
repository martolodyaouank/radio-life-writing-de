from __future__ import annotations

import re

from bs4 import BeautifulSoup


WHITESPACE_RE = re.compile(r"\s+")


def clean_text(value: str | None) -> str:
    if not value:
        return ""
    return WHITESPACE_RE.sub(" ", value).strip()


def soup_from_html(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "lxml")
