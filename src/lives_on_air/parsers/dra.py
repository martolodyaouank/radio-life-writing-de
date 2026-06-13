from __future__ import annotations

import re

from lives_on_air.parsers.common import clean_text, soup_from_html


DETAIL_LABELS = {
    "Autor/Autorin:": "authors",
    "Vorlage:": "template",
    "Übersetzung:": "translation",
    "Komposition:": "composition",
    "Redaktion:": "editorial",
    "Technische Realisierung:": "technical_realisation",
    "Regieassistenz:": "assistant_director",
    "Regie:": "directors",
    "Bearbeitung (Wort):": "text_adaptation",
    "Dramaturgie:": "dramaturgy",
    "Musik:": "music",
    "Ton:": "sound",
}


def parse_dra_page(html: str, url: str) -> dict[str, str]:
    soup = soup_from_html(html)
    title = ""
    heading = soup.find(["h1", "h2"])
    if heading:
        title = clean_text(heading.get_text(" "))

    labels = [
        "Titel",
        "Autor",
        "Autorin",
        "Regie",
        "Produzent",
        "Erstsendung",
        "Gattung",
        "Dauer",
        "Preise",
    ]
    page_text = clean_text(soup.get_text(" "))

    present_labels = [label for label in labels if label.lower() in page_text.lower()]

    return {
        "source_archive": "dra",
        "source_url": url,
        "title": title,
        "page_title": clean_text(soup.title.get_text(" ") if soup.title else ""),
        "field_label_signals": "; ".join(present_labels),
        "raw_text_sample": page_text[:1200],
    }


def _values_after_prefix(soup, label: str) -> str:
    prefix = soup.find("span", class_="prefix", string=lambda value: value and label in value)
    if not prefix:
        return ""

    parent = prefix.find_parent()
    if not parent:
        return ""

    values = []
    for anchor in parent.find_all("a"):
        value = clean_text(anchor.get_text(" "))
        if value:
            values.append(value)

    if values:
        return "; ".join(values)

    sibling_text = []
    for sibling in prefix.next_siblings:
        if getattr(sibling, "name", None) == "br":
            break
        sibling_text.append(clean_text(sibling.get_text(" ") if hasattr(sibling, "get_text") else str(sibling)))
    value = clean_text(" ".join(part for part in sibling_text if part))
    if value:
        return value

    text = clean_text(parent.get_text(" "))
    return clean_text(text.replace(label, "", 1).strip(" :"))


def _sidebar_items(soup) -> list[str]:
    sidebar = soup.select_one(".column.is-one-third .frame-blue") or soup.select_one(".frame-blue")
    if not sidebar:
        return []
    return [clean_text(item.get_text(" ")) for item in sidebar.find_all("li")]


def _cast_rows(soup) -> str:
    rows = []
    for row in soup.select("table.resultSubTable tr"):
        cells = [clean_text(cell.get_text(" ")) for cell in row.find_all("td")]
        if len(cells) < 3:
            continue
        speaker = cells[0]
        role = cells[2]
        if speaker and role:
            rows.append(f"{speaker} as {role}")
        elif speaker:
            rows.append(speaker)
    return " | ".join(rows)


def _all_detail_labels(soup) -> dict[str, str]:
    return {field: _values_after_prefix(soup, label) for label, field in DETAIL_LABELS.items()}


def parse_dra_detail_page(html: str, url: str) -> dict[str, str]:
    soup = soup_from_html(html)
    page_text = clean_text(soup.get_text(" "))

    title_tag = soup.find("h1", class_="ti") or soup.find("h1")
    title = clean_text(title_tag.get_text(" ")) if title_tag else ""

    genre = ""
    genre_icon = soup.select_one("img.icon-gat")
    if genre_icon:
        genre = clean_text(genre_icon.get("title") or "")
    if not genre:
        first_column = soup.select_one(".single-view .column p")
        genre = clean_text(first_column.get_text(" ")) if first_column else ""

    items = _sidebar_items(soup)
    production_line = items[0] if items else ""
    broadcast_line = next((item for item in items if item.startswith("Erstsendung:")), "")
    reviews = " | ".join(item for item in items[1:] if not item.startswith("Erstsendung:"))

    production_year = ""
    year_match = re.search(r"\b(19|20)\d{2}\b", production_line)
    if year_match:
        production_year = year_match.group(0)

    first_broadcast_date = ""
    broadcaster = ""
    start_time = ""
    duration = ""
    if broadcast_line:
        parts = [clean_text(part) for part in broadcast_line.replace("Erstsendung:", "").split("|")]
        if len(parts) > 0:
            first_broadcast_date = parts[0]
        for part in parts[1:]:
            if not part:
                continue
            if re.search(r"\b\d{1,2}:\d{2}\s*Uhr\b", part):
                start_time = part
            elif re.search(r"\b\d{1,3}'\d{0,2}\b", part):
                duration = part
            elif not broadcaster:
                broadcaster = part

    labelled_fields = _all_detail_labels(soup)
    record = {
        "source_archive": "dra",
        "source_url": url,
        "title": title,
        "page_title": clean_text(soup.title.get_text(" ") if soup.title else ""),
        "genre": genre,
        "production_line": production_line,
        "production_year": production_year,
        "first_broadcast_date": first_broadcast_date,
        "broadcaster": broadcaster,
        "start_time": start_time,
        "duration": duration,
        "reviews": reviews,
        "cast": _cast_rows(soup),
        "detail_labels_present": "; ".join(
            clean_text(prefix.get_text(" ")) for prefix in soup.select("span.prefix")
        ),
        "raw_text_sample": page_text[:1200],
    }
    record.update(labelled_fields)
    return record
