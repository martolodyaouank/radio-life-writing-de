from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd
from bs4 import BeautifulSoup

from lives_on_air.classification.biographical import biographical_label, biographical_score
from lives_on_air.config import PROJECT_ROOT
from lives_on_air.scrapers.http import fetch_text


SITEMAP_URL = "https://wirklichkeitimradio.de/wp-sitemap-posts-stueck-1.xml"
SOURCE = "wirklichkeit_im_radio"


@dataclass(frozen=True)
class WirklichkeitUrl:
    url: str
    lastmod: str = ""


def _clean(text: str | None) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _node_text(node, name: str) -> str:
    child = node.find(name)
    return _clean(child.get_text(" ", strip=True) if child else "")


def _cache_path(url: str) -> Path:
    slug = urlparse(url).path.strip("/").replace("/", "__") or "index"
    return PROJECT_ROOT / "data" / "raw" / SOURCE / f"{slug}.html"


def sitemap_urls() -> list[WirklichkeitUrl]:
    xml = fetch_text(SITEMAP_URL, delay_seconds=0.2)
    soup = BeautifulSoup(xml, "xml")
    urls: list[WirklichkeitUrl] = []
    for node in soup.find_all("url"):
        loc = _node_text(node, "loc")
        if not loc:
            continue
        urls.append(WirklichkeitUrl(url=loc, lastmod=_node_text(node, "lastmod")))
    return urls


def _parse_stueckdaten(text: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in [part.strip() for part in text.splitlines() if part.strip()]:
        if ":" in line:
            key, value = line.split(":", 1)
            normalised = (
                key.strip()
                .lower()
                .replace("ä", "ae")
                .replace("ö", "oe")
                .replace("ü", "ue")
                .replace(" ", "_")
            )
            fields[f"wir_{normalised}"] = _clean(value)
        elif "produktion" not in fields:
            fields["wir_production_note"] = _clean(line)
    return fields


def parse_detail(html: str, url: str, lastmod: str = "") -> dict[str, object]:
    soup = BeautifulSoup(html, "lxml")
    article = soup.select_one("article.detail") or soup.find("main")
    h1 = article.find("h1") if article else soup.find("h1")
    title = _clean(h1.get_text(" ", strip=True) if h1 else "")

    header_text = ""
    if h1 and h1.next_sibling:
        parts = []
        for sibling in h1.next_siblings:
            name = getattr(sibling, "name", None)
            if name == "hr":
                break
            if isinstance(sibling, str):
                parts.append(sibling)
            else:
                parts.append(sibling.get_text(" ", strip=True))
        header_text = _clean(" ".join(parts))
    creator = re.sub(r"^von\s+", "", header_text, flags=re.IGNORECASE).strip()

    data_node = article.select_one(".stueckdaten") if article else None
    data_text = data_node.get_text("\n", strip=True) if data_node else ""
    parsed_fields = _parse_stueckdaten(data_text)

    lede = ""
    for strong in article.select("p strong") if article else []:
        lede = _clean(strong.get_text(" ", strip=True))
        if lede:
            break

    content = article.select_one(".thecontent") if article else None
    headings = [_clean(node.get_text(" ", strip=True)) for node in content.find_all(["h2", "h3"])] if content else []
    paragraphs = [_clean(node.get_text(" ", strip=True)) for node in content.find_all(["p", "blockquote"])] if content else []
    content_text = "\n".join(part for part in paragraphs if part)

    scharnier_links = []
    keyword_links = []
    if content:
        for link in content.find_all("a", href=True):
            href = link["href"]
            label = _clean(link.get_text(" ", strip=True))
            if "/scharnier/" in href and label:
                scharnier_links.append(label)
            elif label:
                keyword_links.append(label)

    audio_urls = []
    if article:
        for source in article.select("audio source[src]"):
            audio_urls.append(source["src"].split("?")[0])
        for link in article.select("audio a[href]"):
            audio_urls.append(link["href"].split("?")[0])
    audio_urls = sorted(set(audio_urls))

    image_urls = []
    if article:
        for image in article.select("img[src]"):
            image_urls.append(image["src"])

    searchable = " ".join([title, creator, data_text, lede, content_text, " ".join(scharnier_links)])
    record: dict[str, object] = {
        "source_archive": SOURCE,
        "country_context": "Germany",
        "source_url": url,
        "title": title,
        "display_title": title,
        "creator": creator,
        "author": creator,
        "last_modified": lastmod,
        "genre": "Feature / documentary radio work",
        "description": lede,
        "long_description": content_text,
        "section_headings": " | ".join([heading for heading in headings if heading]),
        "matched_terms": " | ".join(scharnier_links),
        "keyword_links": " | ".join(keyword_links),
        "audio_urls": " | ".join(audio_urls),
        "audio_count": len(audio_urls),
        "image_urls": " | ".join(sorted(set(image_urls))),
        "raw_text_sample": searchable[:4000],
        "biographical_score": biographical_score(searchable),
        "biographical_label": biographical_label(searchable),
    }
    record.update(parsed_fields)
    record["year"] = _extract_year(record)
    record["duration"] = record.get("wir_laenge") or record.get("wir_sendeversion") or ""
    return record


def _extract_year(record: dict[str, object]) -> str:
    haystack = " ".join(str(record.get(key, "")) for key in ["wir_produktion", "wir_production_note", "long_description"])
    match = re.search(r"\b(19[4-9]\d|20[0-2]\d)\b", haystack)
    return match.group(0) if match else ""


def collect(limit: int | None = None) -> pd.DataFrame:
    entries = sitemap_urls()
    if limit:
        entries = entries[:limit]
    records = []
    for index, entry in enumerate(entries, start=1):
        print(f"Wirklichkeit im Radio {index}/{len(entries)}: {entry.url}", flush=True)
        html = fetch_text(entry.url, cache_path=_cache_path(entry.url), delay_seconds=0.25)
        records.append(parse_detail(html, entry.url, entry.lastmod))
    return pd.DataFrame(records)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    df = collect(limit=args.limit)
    output = PROJECT_ROOT / "data" / "interim" / "wirklichkeit_im_radio_stuecke.csv"
    summary = PROJECT_ROOT / "data" / "interim" / "wirklichkeit_im_radio_summary.json"
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
