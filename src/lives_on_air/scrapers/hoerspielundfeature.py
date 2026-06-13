from __future__ import annotations

import argparse
import html
import json
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote_plus, urlparse

import pandas as pd
from bs4 import BeautifulSoup

from lives_on_air.classification.biographical import biographical_label, biographical_score
from lives_on_air.config import PROJECT_ROOT
from lives_on_air.scrapers.http import fetch_text


SOURCE = "hoerspielundfeature"
BASE = "https://www.hoerspielundfeature.de"
STATION = "8b03297f-1f18-4708-9efa-38dd8e243cc2"
SITEMAPS = [
    "https://www.hoerspielundfeature.de/hf-feature-100.sitemap",
    "https://www.hoerspielundfeature.de/hf-hoerspiel-100.sitemap",
    "https://www.hoerspielundfeature.de/hf-klangkunst-100.sitemap",
    "https://www.hoerspielundfeature.de/hoerspiel-feature-alle-100.sitemap",
]
SEARCH_TERMS = [
    "Biografie",
    "Biographie",
    "autobiografisch",
    "Porträt",
    "Portrait",
    "Lebensgeschichte",
    "Erinnerungen",
    "Tagebuch",
    "Briefe",
    "Zeitzeuge",
    "Stimme",
    "O-Ton",
]


@dataclass(frozen=True)
class HufUrl:
    url: str
    source_hint: str = ""
    publication_date: str = ""
    title_hint: str = ""


def _clean(text: str | None) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _node_text(node, name: str) -> str:
    child = node.find(name)
    return _clean(child.get_text(" ", strip=True) if child else "")


def _cache_path(url: str) -> Path:
    slug = urlparse(url).path.strip("/").replace("/", "__") or "index"
    return PROJECT_ROOT / "data" / "raw" / SOURCE / f"{slug}.html"


def sitemap_urls() -> list[HufUrl]:
    found: dict[str, HufUrl] = {}
    for sitemap in SITEMAPS:
        xml = fetch_text(sitemap, delay_seconds=0.2)
        soup = BeautifulSoup(xml, "xml")
        for node in soup.find_all("url"):
            loc = _node_text(node, "loc")
            if not loc or not loc.endswith(".html"):
                continue
            title = _node_text(node, "news:title") or _node_text(node, "title")
            date = _node_text(node, "news:publication_date") or _node_text(node, "publication_date")
            found.setdefault(loc, HufUrl(loc, "sitemap", date, title))
    return list(found.values())


def search_urls(terms: list[str] | None = None) -> list[HufUrl]:
    terms = terms or SEARCH_TERMS
    found: dict[str, HufUrl] = {}
    pattern = re.compile(r"https://www\.hoerspielundfeature\.de/[a-z0-9\-]+-100\.html")
    for term in terms:
        url = f"{BASE}/suche?drsearch:searchText={quote_plus(term)}&drsearch:stations={STATION}"
        print(f"Hörspiel und Feature search: {term}", flush=True)
        html_text = fetch_text(url, delay_seconds=0.5)
        for match in pattern.findall(html.unescape(html_text)):
            if any(skip in match for skip in ["/suche-", "/datenschutz-", "/kontakt-"]):
                continue
            found.setdefault(match, HufUrl(match, f"search:{term}"))
    return list(found.values())


def _json_payloads(soup: BeautifulSoup) -> list[object]:
    payloads: list[object] = []
    for script in soup.select("script.js-client-queries[data-json]"):
        raw = html.unescape(script.get("data-json", ""))
        if not raw:
            continue
        try:
            wrapper = json.loads(raw)
        except json.JSONDecodeError:
            continue
        payloads.append(wrapper.get("value", wrapper))
    return payloads


def _first_payload(payloads: list[object], typename: str) -> dict:
    for payload in payloads:
        if isinstance(payload, dict) and payload.get("__typename") == typename:
            return payload
    return {}


def _payloads(payloads: list[object], typename: str) -> list[dict]:
    return [payload for payload in payloads if isinstance(payload, dict) and payload.get("__typename") == typename]


def _image_payload(payloads: list[object]) -> dict:
    for payload in payloads:
        if isinstance(payload, dict) and payload.get("__typename") == "Image" and payload.get("src"):
            return payload
    return {}


def _extract_article_body(soup: BeautifulSoup) -> str:
    selectors = [
        ".article-text",
        ".b-article-text",
        ".text",
        ".b-content",
        "main",
    ]
    for selector in selectors:
        node = soup.select_one(selector)
        if node:
            text = "\n".join(_clean(p.get_text(" ", strip=True)) for p in node.find_all(["p", "div"], recursive=True))
            text = "\n".join(part for part in text.splitlines() if part and len(part) > 20)
            if len(text) > 80:
                return text[:12000]
    return _clean(soup.get_text(" ", strip=True))[:12000]


def parse_detail(html_text: str, url: str, source_hint: str = "", sitemap_title: str = "", sitemap_date: str = "") -> dict[str, object]:
    soup = BeautifulSoup(html_text, "lxml")
    payloads = _json_payloads(soup)
    teaser = _first_payload(payloads, "Teaser")
    audios = _payloads(payloads, "Audio")
    audio = audios[0] if audios else {}
    image = _image_payload(payloads)

    title_node = soup.find("title")
    title = teaser.get("title") or audio.get("title") or sitemap_title or _clean(title_node.get_text(" ", strip=True) if title_node else "")
    headline = teaser.get("teaserHeadline") or audio.get("audioKicker") or ""
    description = teaser.get("teasertext") or teaser.get("seoTeaserText") or audio.get("audioLeader") or ""
    body = _extract_article_body(soup)
    topics = teaser.get("topics") or audio.get("topics") or []
    norm_tags = audio.get("normDbTags") or []
    if isinstance(norm_tags, list):
        norm_tags_text = " | ".join(_clean(str(tag)) for tag in norm_tags)
    else:
        norm_tags_text = _clean(str(norm_tags))

    searchable = " ".join(
        [
            str(title),
            str(headline),
            str(description),
            str(teaser.get("seoTitle") or ""),
            str(teaser.get("author") or ""),
            str(audio.get("authorText") or ""),
            str(audio.get("chapter2") or ""),
            " ".join(str(topic) for topic in topics),
            body,
        ]
    )
    broadcast = audio.get("broadcastDateTime") or teaser.get("date") or sitemap_date

    return {
        "source_archive": SOURCE,
        "country_context": "Germany",
        "source_url": url,
        "title": title,
        "display_title": " - ".join(part for part in [headline, title] if part),
        "creator": teaser.get("author") or audio.get("authorText") or "",
        "author": teaser.get("author") or audio.get("authorText") or "",
        "site_name": teaser.get("siteName") or audio.get("siteName") or "",
        "genre": audio.get("chapter2") or " | ".join(str(topic) for topic in topics) or "",
        "topics": " | ".join(str(topic) for topic in topics),
        "description": description,
        "long_description": body,
        "seo_title": teaser.get("seoTitle") or "",
        "seo_description": teaser.get("seoTeaserText") or "",
        "first_publication_date": teaser.get("firstPublicationDate") or "",
        "first_broadcast_date": broadcast,
        "year": str(broadcast)[:4] if broadcast else "",
        "duration_seconds": audio.get("duration") or "",
        "duration": audio.get("duration") or "",
        "audio_url": audio.get("audioUrl") or "",
        "download_url": audio.get("downloadUrl") or "",
        "file_size": audio.get("fileSize") or "",
        "image_url": image.get("src") or "",
        "image_caption": image.get("caption") or "",
        "image_alt": image.get("alt") or "",
        "norm_db_tags": norm_tags_text,
        "source_hint": source_hint,
        "raw_text_sample": searchable[:4000],
        "biographical_score": biographical_score(searchable),
        "biographical_label": biographical_label(searchable),
    }


def collect(limit: int | None = None, include_search: bool = True) -> pd.DataFrame:
    candidates: dict[str, HufUrl] = {entry.url: entry for entry in sitemap_urls()}
    if include_search:
        for entry in search_urls():
            candidates.setdefault(entry.url, entry)
    entries = list(candidates.values())
    if limit:
        entries = entries[:limit]
    records = []
    for index, entry in enumerate(entries, start=1):
        print(f"Hörspiel und Feature {index}/{len(entries)}: {entry.url}", flush=True)
        page = fetch_text(entry.url, cache_path=_cache_path(entry.url), delay_seconds=0.35)
        records.append(parse_detail(page, entry.url, entry.source_hint, entry.title_hint, entry.publication_date))
    return pd.DataFrame(records)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--no-search", action="store_true")
    args = parser.parse_args()

    df = collect(limit=args.limit, include_search=not args.no_search)
    output = PROJECT_ROOT / "data" / "interim" / "hoerspielundfeature_candidates.csv"
    summary = PROJECT_ROOT / "data" / "interim" / "hoerspielundfeature_summary.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output, index=False)
    summary.write_text(
        json.dumps(
            {
                "rows": int(len(df)),
                "output": str(output),
                "biographical_labels": df.get("biographical_label", pd.Series(dtype=str))
                .value_counts(dropna=False)
                .to_dict(),
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    print(summary.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
