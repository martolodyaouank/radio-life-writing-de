from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from lives_on_air.classification.biographical import biographical_label, biographical_score
from lives_on_air.config import BBC_RAW_DIR, DRA_RAW_DIR, PROJECT_ROOT
from lives_on_air.parsers.bbc_genome import parse_bbc_programme_page
from lives_on_air.parsers.dra import parse_dra_page
from lives_on_air.scrapers.http import FetchError, fetch_text


BBC_TEST_URLS = [
    "https://genome.ch.bbc.co.uk/",
    "https://genome.ch.bbc.co.uk/b01qhqgf",
]

DRA_TEST_URLS = [
    "https://hoerspiele.dra.de/",
    "https://hoerspiele.dra.de/suche",
]


def cache_name(url: str) -> str:
    return (
        url.replace("https://", "")
        .replace("http://", "")
        .replace("/", "_")
        .replace("?", "_")
        .strip("_")
        + ".html"
    )


def run() -> pd.DataFrame:
    records: list[dict[str, str | int]] = []

    for url in BBC_TEST_URLS:
        try:
            html = fetch_text(url, BBC_RAW_DIR / cache_name(url))
            record = parse_bbc_programme_page(html, url)
            record["fetch_status"] = "ok"
        except FetchError as error:
            record = {
                "source_archive": "bbc_genome",
                "source_url": url,
                "title": "",
                "page_title": "",
                "raw_text_sample": str(error),
                "fetch_status": "failed",
            }
        searchable_text = " ".join(
            [record.get("title", ""), record.get("page_title", ""), record.get("raw_text_sample", "")]
        )
        record["biographical_score"] = biographical_score(searchable_text)
        record["biographical_label"] = biographical_label(searchable_text)
        records.append(record)

    for url in DRA_TEST_URLS:
        try:
            html = fetch_text(url, DRA_RAW_DIR / cache_name(url))
            record = parse_dra_page(html, url)
            record["fetch_status"] = "ok"
        except FetchError as error:
            record = {
                "source_archive": "dra",
                "source_url": url,
                "title": "",
                "page_title": "",
                "field_label_signals": "",
                "raw_text_sample": str(error),
                "fetch_status": "failed",
            }
        searchable_text = " ".join(
            [record.get("title", ""), record.get("page_title", ""), record.get("raw_text_sample", "")]
        )
        record["biographical_score"] = biographical_score(searchable_text)
        record["biographical_label"] = biographical_label(searchable_text)
        records.append(record)

    df = pd.DataFrame(records)
    output_dir = PROJECT_ROOT / "data" / "interim"
    output_dir.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_dir / "feasibility_records.csv", index=False)

    summary = {
        "records": len(df),
        "archives": sorted(df["source_archive"].unique().tolist()),
        "output": str(output_dir / "feasibility_records.csv"),
    }
    Path(output_dir / "feasibility_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    return df


if __name__ == "__main__":
    result = run()
    print(
        result[
            [
                "source_archive",
                "fetch_status",
                "source_url",
                "title",
                "page_title",
                "biographical_label",
            ]
        ]
    )
