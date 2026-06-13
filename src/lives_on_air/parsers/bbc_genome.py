from __future__ import annotations

from lives_on_air.parsers.common import clean_text, soup_from_html


def parse_bbc_programme_page(html: str, url: str) -> dict[str, str]:
    soup = soup_from_html(html)

    title = ""
    heading = soup.find(["h1", "h2"])
    if heading:
        title = clean_text(heading.get_text(" "))

    page_text = clean_text(soup.get_text(" "))

    return {
        "source_archive": "bbc_genome",
        "source_url": url,
        "title": title,
        "page_title": clean_text(soup.title.get_text(" ") if soup.title else ""),
        "raw_text_sample": page_text[:1200],
    }
