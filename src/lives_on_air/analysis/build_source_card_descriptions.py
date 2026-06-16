from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from html import unescape
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd
from lxml import html

from lives_on_air.config import PROJECT_ROOT


INPUT = PROJECT_ROOT / "data" / "processed" / "analysis_tables" / "core_semantic_enriched.csv"
EXCLUSIONS = PROJECT_ROOT / "data" / "curation" / "life_writing_exclusions.csv"
OUTPUT = PROJECT_ROOT / "data" / "curation" / "source_card_descriptions.csv"
CURL_CONFIG = PROJECT_ROOT / "data" / "interim" / "source_card_pages.curl"
HTML_CACHE = PROJECT_ROOT / "data" / "interim" / "source_card_pages"


SOURCE_LABELS = {
    "hoerspiele.dra.de": "DRA",
    "www.hoerspielundfeature.de": "DLF/DLF Kultur",
    "hoerspielundfeature.de": "DLF/DLF Kultur",
    "wirklichkeitimradio.de": "Wirklichkeit",
    "www.wirklichkeitimradio.de": "Wirklichkeit",
}


def load_excluded_urls() -> set[str]:
    if not EXCLUSIONS.exists():
        return set()
    df = pd.read_csv(EXCLUSIONS)
    if "source_url" not in df.columns:
        return set()
    return {str(url).strip() for url in df["source_url"].dropna() if str(url).strip()}


def displayed_records() -> pd.DataFrame:
    df = pd.read_csv(INPUT).fillna("")
    excluded = load_excluded_urls()
    if excluded:
        df = df[~df["source_url"].astype(str).str.strip().isin(excluded)].copy()
    return df


def cache_path(url: str) -> Path:
    parsed = urlparse(url)
    stem = Path(parsed.path).name or "index"
    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:10]
    safe_stem = re.sub(r"[^A-Za-z0-9._-]+", "_", stem)[:90]
    return HTML_CACHE / parsed.netloc / f"{safe_stem}-{digest}.html"


def write_curl_config(urls: list[str]) -> None:
    CURL_CONFIG.parent.mkdir(parents=True, exist_ok=True)
    HTML_CACHE.mkdir(parents=True, exist_ok=True)
    lines = [
        "location",
        "fail",
        "silent",
        "show-error",
        "retry = 2",
        "connect-timeout = 20",
        "max-time = 60",
        'user-agent = "Mozilla/5.0 radio-life-writing-data-curation"',
    ]
    for url in urls:
        path = cache_path(url)
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and path.stat().st_size > 0:
            continue
        lines.extend([f'url = "{url}"', f'output = "{path}"'])
    CURL_CONFIG.write_text("\n".join(lines) + "\n", encoding="utf-8")


def clean_text(value: object) -> str:
    text = unescape(str(value or ""))
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\s+([.,;:!?])", r"\1", text)
    return text


def split_sentences(text: str) -> list[str]:
    protected = clean_text(text)
    protected = re.sub(r"\b(\d{1,2})\.", r"\1<dot>", protected)
    abbreviations = {
        "v.": "v<dot>",
        "bzw.": "bzw<dot>",
        "ca.": "ca<dot>",
        "Dr.": "Dr<dot>",
        "Prof.": "Prof<dot>",
        "u.a.": "u<dot>a<dot>",
        "z.B.": "z<dot>B<dot>",
    }
    for abbreviation, replacement in abbreviations.items():
        protected = protected.replace(abbreviation, replacement)
    sentences = []
    for part in re.split(r"(?<=[.!?])\s+", protected):
        for abbreviation, replacement in abbreviations.items():
            part = part.replace(replacement, abbreviation)
        part = re.sub(r"\b(\d{1,2})<dot>", r"\1.", part)
        part = clean_text(part)
        if part:
            sentences.append(part)
    return sentences


def is_credit_line(text: str) -> bool:
    return bool(
        re.search(
            r"^(Autor/Autorin|Regie|Regieassistenz|Technische Realisierung|"
            r"Bearbeitung|Übersetzung|Dargeboten von|Sprecher|Mitwirkende|"
            r"Komposition|Musik|Produktion):?",
            text,
            flags=re.IGNORECASE,
        )
    )


def title_based_description(row: object) -> str:
    title = clean_text(getattr(row, "title", ""))
    genre = clean_text(getattr(row, "genre", ""))
    form = clean_text(getattr(row, "form_family", ""))
    if re.search(r"\bportr[aä]it\b", title, flags=re.IGNORECASE):
        return compressed(title, max_chars=240)
    if re.search(r"\berinnerungen?\b|\btagebuch\b|\bbriefe?\b|\bmemoiren\b", title, flags=re.IGNORECASE):
        return compressed(title, max_chars=240)
    parts = [title]
    if genre and genre.lower() not in title.lower():
        parts.append(genre)
    elif form and form.lower() not in title.lower():
        parts.append(form)
    return compressed(". ".join(part for part in parts if part), max_chars=240)


def compressed(text: str, max_chars: int = 360) -> str:
    text = clean_text(text)
    text = re.sub(r"^(Feature|Hörspiel|Porträt|Essay|Archiv)\s*[·:–-]\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^\s*•\s*", "", text)
    text = re.sub(r"\s+Aus dem Podcast.*$", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+Erstsendung vom\b.*$", "", text, flags=re.IGNORECASE)
    sentences = [
        sentence
        for sentence in split_sentences(text)
        if len(sentence) >= 35
        and not re.search(
            r"\b(Link kopieren|Audio herunterladen|Produktion|Regie|Autor/Autorin|"
            r"Technische Realisierung|Produktions- und Sendedaten|Infos zum Hörangebot)\b",
            sentence,
            flags=re.IGNORECASE,
        )
    ]
    if not sentences:
        sentences = split_sentences(text)
    summary = ""
    for sentence in sentences:
        candidate = f"{summary} {sentence}".strip()
        if len(candidate) > max_chars and summary:
            break
        summary = candidate
        if len(summary) >= 170:
            break
    if not summary:
        summary = text[:max_chars].rstrip(" ,;:-")
    if len(summary) > max_chars:
        summary = summary[: max_chars - 1].rsplit(" ", 1)[0].rstrip(" ,;:-") + "…"
    return summary


def parse_html_file(path: Path) -> html.HtmlElement | None:
    if not path.exists() or path.stat().st_size == 0:
        return None
    try:
        return html.fromstring(path.read_bytes())
    except (OSError, ValueError):
        return None


def dra_description(doc: html.HtmlElement) -> str:
    h1 = doc.xpath("//h1")
    after_title = False if h1 else True
    candidates: list[str] = []
    subtitles: list[str] = []
    for node in doc.xpath("//h1|//p"):
        if h1 and node is h1[0]:
            after_title = True
            continue
        if not after_title:
            continue
        paragraph = clean_text(node.text_content())
        if re.search(r"^Produktions- und Sendedaten\b", paragraph, flags=re.IGNORECASE):
            break
        if is_credit_line(paragraph) or re.search(
            r"^(Produktions- und Sendedaten|Infos zum Hörangebot|Bildnachweise)",
            paragraph,
            flags=re.IGNORECASE,
        ):
            continue
        if len(paragraph) < 80:
            if 5 <= len(paragraph) <= 120 and not is_credit_line(paragraph) and not re.search(
                r"^(Kommentar|Originalhörspiel|Hörspielbearbeitung|Hörspiel|Feature|Porträt)$",
                paragraph,
                flags=re.IGNORECASE,
            ):
                subtitles.append(paragraph)
            continue
        candidates.append(paragraph)
    if candidates:
        return compressed(max(candidates, key=len))
    if subtitles:
        return compressed(" ".join(subtitles), max_chars=240)
    return ""


def dlf_payloads(doc: html.HtmlElement) -> list[dict[str, object]]:
    payloads = []
    for script in doc.xpath("//script[contains(@class, 'js-client-queries')][@data-json]"):
        raw = script.get("data-json") or ""
        try:
            payload = json.loads(unescape(raw)).get("value", {})
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            payloads.append(payload)
    return payloads


def dlf_description(doc: html.HtmlElement, url: str, title: str) -> str:
    payloads = dlf_payloads(doc)
    matching: list[dict[str, object]] = []
    for payload in payloads:
        paths = {
            clean_text(payload.get("path")),
            clean_text(payload.get("pathSameOrigin")),
        }
        payload_title = clean_text(payload.get("title"))
        if url in paths or (payload.get("__typename") == "Teaser" and payload_title == title):
            matching.append(payload)
    for payload in matching + payloads:
        if payload.get("__typename") not in {"Teaser", "Audio"}:
            continue
        for field in ["teasertext", "description", "seoTeaserText", "audioLeader"]:
            value = clean_text(payload.get(field))
            if len(value) >= 35:
                return compressed(value)
    meta = doc.xpath("//meta[@name='description']/@content | //meta[@property='og:description']/@content")
    for value in meta:
        value = clean_text(value)
        if len(value) >= 35:
            return compressed(value)
    return ""


def wirklichkeit_description(doc: html.HtmlElement) -> str:
    selectors = [
        "//article//p",
        "//*[contains(@class, 'entry-content')]//p",
        "//*[contains(@class, 'post-content')]//p",
        "//main//p",
    ]
    candidates: list[str] = []
    for selector in selectors:
        for node in doc.xpath(selector):
            text = clean_text(node.text_content())
            if len(text) < 70:
                continue
            if re.search(r"^(Regie|Autor|Mitwirkende|Sprecher|Produktion|Länge):", text, flags=re.IGNORECASE):
                continue
            candidates.append(text)
        if candidates:
            break
    if candidates:
        return compressed(" ".join(candidates[:2]))
    meta = doc.xpath("//meta[@name='description']/@content | //meta[@property='og:description']/@content")
    for value in meta:
        value = clean_text(value)
        if len(value) >= 35:
            return compressed(value)
    return ""


def fallback_description(row: object) -> str:
    for field in ["description", "seo_description", "long_description", "raw_text_sample"]:
        value = clean_text(getattr(row, field, ""))
        if len(value) >= 35:
            if field == "raw_text_sample":
                value = re.sub(r"^ARD Hörspieldatenbank:\s*", "", value)
                value = re.sub(r"\bdra\.de Suche Kollektionen.*?Detailansicht\s+", "", value)
                value = re.split(
                    r"\s+Produktions- und Sendedaten\b|\s+Infos zum Hörangebot\b",
                    value,
                    maxsplit=1,
                )[0]
            return compressed(value)
    return title_based_description(row)


def source_from_url(url: str, row_source: str) -> str:
    host = urlparse(url).netloc
    return SOURCE_LABELS.get(host, row_source)


def extract_description(row: object) -> tuple[str, str]:
    url = clean_text(getattr(row, "source_url", ""))
    title = clean_text(getattr(row, "title", ""))
    source = source_from_url(url, clean_text(getattr(row, "source_label", "")))
    doc = parse_html_file(cache_path(url))
    description = ""
    method = "fallback"
    if doc is not None:
        if source == "DRA":
            description = dra_description(doc)
            method = "html:dra"
        elif source == "DLF/DLF Kultur":
            description = dlf_description(doc, url, title)
            method = "html:dlf"
        elif source == "Wirklichkeit":
            description = wirklichkeit_description(doc)
            method = "html:wirklichkeit"
    if not description:
        description = fallback_description(row)
        method = f"{method}:row"
    if (
        not description
        or is_credit_line(description)
        or re.search(r"Um den vollen Funktionsumfang|ARD Hörspieldatenbank|dra\.de Suche", description)
    ):
        description = title_based_description(row)
        method = f"{method}:title"
    return description, method


def build_descriptions() -> pd.DataFrame:
    df = displayed_records()
    rows = []
    for row in df.itertuples():
        url = clean_text(getattr(row, "source_url", ""))
        description, method = extract_description(row)
        rows.append(
            {
                "source_url": url,
                "title": clean_text(getattr(row, "title", "")),
                "source": clean_text(getattr(row, "source_label", "")),
                "short_description": description,
                "extraction_method": method,
            }
        )
    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write-curl-config", action="store_true")
    parser.add_argument("--extract", action="store_true")
    args = parser.parse_args()

    df = displayed_records()
    urls = [clean_text(url) for url in df["source_url"] if clean_text(url)]

    if args.write_curl_config:
        write_curl_config(urls)
        print(f"Wrote curl config for {len(urls)} URLs to {CURL_CONFIG}")

    if args.extract:
        descriptions = build_descriptions()
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        descriptions.to_csv(OUTPUT, index=False, quoting=csv.QUOTE_MINIMAL)
        present = descriptions["short_description"].astype(str).str.len().gt(0).sum()
        print(f"Wrote {len(descriptions)} descriptions ({present} non-empty) to {OUTPUT}")

    if not args.write_curl_config and not args.extract:
        parser.error("Choose --write-curl-config, --extract, or both.")


if __name__ == "__main__":
    main()
