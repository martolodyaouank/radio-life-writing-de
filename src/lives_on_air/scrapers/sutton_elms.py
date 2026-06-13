from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup

from lives_on_air.classification.biographical import biographical_label, biographical_score
from lives_on_air.config import PROJECT_ROOT, RAW_DIR, REQUEST_HEADERS, REQUEST_TIMEOUT_SECONDS
from lives_on_air.parsers.common import clean_text


SUTTON_BASE_URL = "https://suttonelms.org.uk"
SUTTON_RAW_DIR = RAW_DIR / "sutton_elms"

BIO_TERMS = [
    "biographical",
    "biography",
    "autobiographical",
    "auto biographical",
    "semi-autobiographical",
    "semi autobiographical",
    "life of",
    "about the life",
    "based on the life",
    "memoir",
    "diary",
    "letters",
]

DATE_RE = re.compile(
    r"(?P<day>\b\d{1,2})(?:st|nd|rd|th)?[ ./-]*(?P<month>[A-Za-z]{3,9}|\d{1,2})[ ./-]*(?P<year>\d{2,4})?"
)


def candidate_urls(start_year: int = 1945, end_year: int = 2026) -> list[str]:
    urls: list[str] = []
    for year in range(start_year, end_year + 1):
        urls.append(f"{SUTTON_BASE_URL}/r4-plays-{year}.html")
        urls.append(f"{SUTTON_BASE_URL}/others{str(year)[-2:]}.html")
    urls.extend(
        [
            f"{SUTTON_BASE_URL}/jholloway.html",
            f"{SUTTON_BASE_URL}/julietace.html",
            f"{SUTTON_BASE_URL}/VP.HTML",
            f"{SUTTON_BASE_URL}/philip-palmer.html",
            f"{SUTTON_BASE_URL}/JFOLLETT.HTML",
            f"{SUTTON_BASE_URL}/david-wade.html",
            f"{SUTTON_BASE_URL}/rcscriven.html",
            f"{SUTTON_BASE_URL}/karen-rose.html",
            f"{SUTTON_BASE_URL}/miriam-margolyes.html",
        ]
    )
    return urls


def _cache_name(url: str) -> str:
    return (
        url.replace("https://", "")
        .replace("http://", "")
        .replace("/", "_")
        .strip("_")
        + ".html"
    )


def fetch_page(url: str) -> str | None:
    cache_path = SUTTON_RAW_DIR / _cache_name(url)
    if cache_path.exists():
        return cache_path.read_text(encoding="utf-8", errors="ignore")
    try:
        response = requests.get(url, headers=REQUEST_HEADERS, timeout=REQUEST_TIMEOUT_SECONDS)
    except requests.RequestException:
        return None
    if response.status_code == 404:
        return None
    response.raise_for_status()
    response.encoding = response.encoding or "utf-8"
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(response.text, encoding="utf-8", errors="ignore")
    return response.text


def _blocks_from_text(text: str) -> list[str]:
    text = text.replace("\r", "\n")
    rough_blocks = re.split(r"(?:~{5,}|\n\s*\n\s*\n)", text)
    blocks = []
    for block in rough_blocks:
        cleaned = clean_text(block)
        if len(cleaned) >= 80:
            blocks.append(cleaned)
    return blocks


def _year_from_url(url: str) -> str:
    match = re.search(r"(?:r4-plays-|others)(\d{2,4})", url)
    if not match:
        return ""
    value = match.group(1)
    if len(value) == 2:
        number = int(value)
        return str(2000 + number if number <= 26 else 1900 + number)
    return value


def _date_signal(block: str, fallback_year: str) -> str:
    match = DATE_RE.search(block)
    if not match:
        return fallback_year
    year = match.group("year") or fallback_year
    return clean_text(match.group(0) if year else "")


def parse_candidates(html: str, url: str) -> list[dict[str, str | int]]:
    soup = BeautifulSoup(html, "lxml")
    page_title = clean_text(soup.title.get_text(" ") if soup.title else "")
    text = soup.get_text("\n", strip=True)
    fallback_year = _year_from_url(url)
    records = []
    for block in _blocks_from_text(text):
        lower = block.lower()
        matched_terms = [term for term in BIO_TERMS if term in lower]
        if not matched_terms:
            continue
        title = ""
        for sentence in re.split(r"(?<=[.!?])\s+", block):
            if any(term in sentence.lower() for term in matched_terms):
                title = sentence[:180]
                break
        record = {
            "source_archive": "sutton_elms",
            "source_url": url,
            "page_title": page_title,
            "title": clean_text(title),
            "country": "United Kingdom",
            "language": "English",
            "year": fallback_year,
            "date_signal": _date_signal(block, fallback_year),
            "matched_terms": "; ".join(matched_terms),
            "raw_text_sample": block[:2000],
        }
        record["biographical_score"] = biographical_score(block)
        record["biographical_label"] = biographical_label(block)
        records.append(record)
    return records


def collect_sutton_elms(start_year: int = 1945, end_year: int = 2026) -> pd.DataFrame:
    records = []
    urls = candidate_urls(start_year=start_year, end_year=end_year)
    for index, url in enumerate(urls, start=1):
        print(f"Sutton Elms {index}/{len(urls)}: {url}", flush=True)
        html = fetch_page(url)
        if not html:
            continue
        records.extend(parse_candidates(html, url))
    df = pd.DataFrame(records).drop_duplicates(subset=["source_url", "raw_text_sample"])
    output_path = PROJECT_ROOT / "data" / "interim" / "sutton_elms_biography_candidates.csv"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)
    return df


if __name__ == "__main__":
    result = collect_sutton_elms()
    print(result[["year", "title", "matched_terms", "biographical_label", "source_url"]].head(50).to_string(index=False))
