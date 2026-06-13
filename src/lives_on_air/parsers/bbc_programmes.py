from __future__ import annotations

from lives_on_air.parsers.common import clean_text


def parse_bbc_programmes_json(payload: dict, url: str) -> dict[str, str]:
    programme = payload.get("programme", {})
    display_title = programme.get("display_title") or {}
    ownership = programme.get("ownership") or {}
    service = ownership.get("service") or {}
    categories = programme.get("categories") or []
    parent = (programme.get("parent") or {}).get("programme") or {}
    grandparent = (parent.get("parent") or {}).get("programme") or {}
    versions = programme.get("versions") or []
    links = programme.get("links") or []

    category_titles = []
    category_keys = []
    for category in categories:
        title = clean_text(category.get("title"))
        key = clean_text(category.get("key"))
        if title:
            category_titles.append(title)
        if key:
            category_keys.append(key)

    title_parts = [
        clean_text(display_title.get("title")),
        clean_text(display_title.get("subtitle")),
    ]
    display = ": ".join(part for part in title_parts if part)

    return {
        "source_archive": "bbc_programmes",
        "source_url": url,
        "pid": clean_text(programme.get("pid")),
        "title": clean_text(programme.get("title")),
        "display_title": display,
        "programme_type": clean_text(programme.get("type")),
        "media_type": clean_text(programme.get("media_type")),
        "first_broadcast_date": clean_text(programme.get("first_broadcast_date")),
        "broadcaster": clean_text(service.get("title")),
        "short_synopsis": clean_text(programme.get("short_synopsis")),
        "medium_synopsis": clean_text(programme.get("medium_synopsis")),
        "long_synopsis": clean_text(programme.get("long_synopsis")),
        "category_titles": "; ".join(category_titles),
        "category_keys": "; ".join(category_keys),
        "parent_pid": clean_text(parent.get("pid")),
        "parent_type": clean_text(parent.get("type")),
        "parent_title": clean_text(parent.get("title")),
        "grandparent_pid": clean_text(grandparent.get("pid")),
        "grandparent_type": clean_text(grandparent.get("type")),
        "grandparent_title": clean_text(grandparent.get("title")),
        "version_pids": "; ".join(clean_text(version.get("pid")) for version in versions if version.get("pid")),
        "version_durations": "; ".join(
            str(version.get("duration")) for version in versions if version.get("duration") is not None
        ),
        "related_links": " | ".join(
            f"{clean_text(link.get('title'))}: {clean_text(link.get('url'))}"
            for link in links
            if link.get("url")
        ),
    }
