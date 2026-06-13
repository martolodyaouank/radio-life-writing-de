from __future__ import annotations

import time
from dataclasses import dataclass
from urllib.parse import urljoin

import pandas as pd
import requests

from lives_on_air.classification.biographical import biographical_label, biographical_score
from lives_on_air.config import DRA_RAW_DIR, PROJECT_ROOT, REQUEST_HEADERS, REQUEST_TIMEOUT_SECONDS
from lives_on_air.parsers.common import clean_text, soup_from_html
from lives_on_air.parsers.dra import parse_dra_detail_page


DRA_BASE_URL = "https://hoerspiele.dra.de"
DRA_SEARCH_URL = f"{DRA_BASE_URL}/suche"


@dataclass(frozen=True)
class DraSearchResult:
    title: str
    detail_url: str


def _cache_name(url: str) -> str:
    return (
        url.replace("https://", "")
        .replace("http://", "")
        .replace("/", "_")
        .replace("?", "_")
        .replace("&", "_")
        .strip("_")
        + ".html"
    )


def _form_payload(
    search_html: str,
    field: str,
    term: str,
    showhits: int = 10,
    first_broadcast_from: str | None = None,
    first_broadcast_to: str | None = None,
) -> dict[str, str]:
    soup = soup_from_html(search_html)
    form = soup.find("form", id="searchform") or soup.find("form")
    if not form:
        raise RuntimeError("DRA search form not found")

    data: dict[str, str] = {}
    for element in form.find_all(["input", "select", "textarea"]):
        name = element.get("name")
        if not name:
            continue

        field_type = element.get("type", "")
        if element.name == "select":
            option = element.find("option", selected=True) or element.find("option")
            data[name] = option.get("value", "") if option else ""
        elif field_type in {"checkbox", "radio"}:
            if element.has_attr("checked"):
                data[name] = element.get("value", "")
        else:
            data[name] = element.get("value", "")

    data[f"tx_drahsdbsearch_hsdbsearch[search][{field}]"] = term
    data["tx_drahsdbsearch_hsdbsearch[search][showhits]"] = str(showhits)
    if first_broadcast_from:
        data["tx_drahsdbsearch_hsdbsearch[search][erstsendungvon]"] = first_broadcast_from
    if first_broadcast_to:
        data["tx_drahsdbsearch_hsdbsearch[search][erstsendungbis]"] = first_broadcast_to
    return data


def _results_from_html(html: str) -> list[DraSearchResult]:
    soup = soup_from_html(html)
    records: list[DraSearchResult] = []
    seen: set[str] = set()
    for anchor in soup.find_all("a", href=True):
        href = anchor["href"]
        if "/detailansicht/" not in href:
            continue
        detail_url = urljoin(DRA_BASE_URL, href)
        if detail_url in seen:
            continue
        seen.add(detail_url)
        records.append(DraSearchResult(title=clean_text(anchor.get_text(" ")), detail_url=detail_url))
    return records


def _pager_payload(result_html: str, page_index: int) -> dict[str, str] | None:
    soup = soup_from_html(result_html)
    for form in soup.find_all("form"):
        if not form.find("input", {"name": "tx_drahsdbsearch_hsdbsearch[search][pager]"}):
            continue
        payload: dict[str, str] = {}
        for element in form.find_all("input"):
            name = element.get("name")
            if name:
                payload[name] = element.get("value", "")
        payload["tx_drahsdbsearch_hsdbsearch[search][seite]"] = str(page_index)
        return payload
    return None


def search_dra(
    term: str,
    field: str = "ueberall",
    showhits: int = 10,
    first_broadcast_from: str | None = "1945",
    first_broadcast_to: str | None = "2026",
    max_pages: int = 1,
) -> list[DraSearchResult]:
    session = requests.Session()
    response = session.get(
        DRA_SEARCH_URL,
        headers=REQUEST_HEADERS,
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()

    payload = _form_payload(
        response.text,
        field=field,
        term=term,
        showhits=showhits,
        first_broadcast_from=first_broadcast_from,
        first_broadcast_to=first_broadcast_to,
    )
    result = session.post(
        DRA_SEARCH_URL,
        headers=REQUEST_HEADERS,
        data=payload,
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    result.raise_for_status()

    cache_path = DRA_RAW_DIR / f"search_{field}_{term.replace(' ', '_')}.html"
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(result.text, encoding="utf-8")

    records = _results_from_html(result.text)
    seen = {record.detail_url for record in records}
    page_html = result.text
    for page_index in range(1, max_pages):
        pager_payload = _pager_payload(page_html, page_index)
        if not pager_payload:
            break
        page_response = session.post(
            DRA_SEARCH_URL,
            headers=REQUEST_HEADERS,
            data=pager_payload,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        page_response.raise_for_status()
        page_html = page_response.text
        page_cache_path = DRA_RAW_DIR / f"search_{field}_{term.replace(' ', '_')}_page_{page_index + 1}.html"
        page_cache_path.write_text(page_html, encoding="utf-8")
        page_records = _results_from_html(page_html)
        new_records = [record for record in page_records if record.detail_url not in seen]
        if not new_records:
            break
        for record in new_records:
            seen.add(record.detail_url)
            records.append(record)
    return records


def fetch_dra_detail(detail_url: str, delay_seconds: float = 1.0) -> str:
    cache_path = DRA_RAW_DIR / _cache_name(detail_url)
    if cache_path.exists():
        return cache_path.read_text(encoding="utf-8")

    time.sleep(delay_seconds)
    response = requests.get(
        detail_url,
        headers=REQUEST_HEADERS,
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(response.text, encoding="utf-8")
    return response.text


def collect_dra_sample(term: str = "Dylan Thomas", field: str = "ueberall", limit: int = 5) -> pd.DataFrame:
    results = search_dra(term=term, field=field, showhits=max(limit, 10))
    records = []
    for result in results[:limit]:
        html = fetch_dra_detail(result.detail_url)
        record = parse_dra_detail_page(html, result.detail_url)
        searchable_text = " ".join(
            [
                record.get("title", ""),
                record.get("genre", ""),
                record.get("description", ""),
                record.get("reviews", ""),
                record.get("raw_text_sample", ""),
            ]
        )
        record["search_term"] = term
        record["search_field"] = field
        record["biographical_score"] = biographical_score(searchable_text)
        record["biographical_label"] = biographical_label(searchable_text)
        records.append(record)

    df = pd.DataFrame(records)
    output_path = PROJECT_ROOT / "data" / "interim" / f"dra_sample_{field}_{term.replace(' ', '_')}.csv"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)
    return df


if __name__ == "__main__":
    sample = collect_dra_sample()
    columns = [
        "title",
        "genre",
        "authors",
        "directors",
        "production_year",
        "first_broadcast_date",
        "broadcaster",
        "duration",
        "biographical_label",
        "source_url",
    ]
    print(sample[[column for column in columns if column in sample.columns]].to_string(index=False))
