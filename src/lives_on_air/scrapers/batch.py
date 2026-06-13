from __future__ import annotations

import argparse
import json
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd

from lives_on_air.config import PROJECT_ROOT
from lives_on_air.scrapers.bbc_programmes import collect_bbc_programmes_sample
from lives_on_air.scrapers.dra import fetch_dra_detail, parse_dra_detail_page, search_dra
from lives_on_air.classification.biographical import biographical_label, biographical_score


DRA_QUERY_SPECS = [
    ("ueberall", "Biographie"),
    ("ueberall", "biographisch"),
    ("ueberall", "Autobiographie"),
    ("ueberall", "autobiographisch"),
    ("ueberall", "Porträt"),
    ("ueberall", "Erinnerungen"),
    ("ueberall", "Memoiren"),
    ("ueberall", "Tagebuch"),
    ("ueberall", "Tagebücher"),
    ("ueberall", "Briefe"),
    ("ueberall", "Briefwechsel"),
    ("ueberall", "Nachlass"),
    ("titel", "Leben"),
    ("titel", "Lebensgeschichte"),
    ("titel", "Erinnerungen"),
    ("titel", "Tagebuch"),
    ("titel", "Briefe"),
    ("titel", "Porträt"),
    ("titel", "Biografie"),
    ("titel", "Biographie"),
    ("titel", "Autobiographie"),
    ("ueberall", "Dylan Thomas"),
    ("ueberall", "George Orwell"),
    ("ueberall", "Franz Kafka"),
    ("ueberall", "Bertolt Brecht"),
    ("ueberall", "Virginia Woolf"),
]

BBC_SEED_PIDS = [
    "b01qhqgf",  # The Real George Orwell: Biographical Dramas, Loving
    "b01qdtpw",  # peer episode
    "b01qlhjp",  # peer episode
    "b01q8l3k",  # peer episode
    "b01pyz0z",  # parent brand; expands via episodes filters
]


def classify_record(record: dict) -> dict:
    searchable_text = " ".join(
        str(record.get(field, ""))
        for field in [
            "title",
            "display_title",
            "genre",
            "category_titles",
            "short_synopsis",
            "medium_synopsis",
            "long_synopsis",
            "template",
            "reviews",
            "raw_text_sample",
        ]
    )
    record["biographical_score"] = biographical_score(searchable_text)
    record["biographical_label"] = biographical_label(searchable_text)
    return record


def _collect_one_dra_detail(index: int, total: int, detail_url: str, url_to_terms, title_by_url) -> dict | None:
    print(f"DRA detail {index}/{total}: {detail_url}", flush=True)
    try:
        html = fetch_dra_detail(detail_url, delay_seconds=0.2)
        record = parse_dra_detail_page(html, detail_url)
    except Exception as error:
        print(f"  failed: {error}", flush=True)
        return None
    record["search_terms"] = "; ".join(sorted(url_to_terms[detail_url]))
    record["search_result_title"] = title_by_url.get(detail_url, "")
    return classify_record(record)


def collect_dra_batch(
    query_specs: list[tuple[str, str]],
    limit_per_query: int,
    max_pages: int,
    detail_workers: int,
) -> pd.DataFrame:
    url_to_terms: dict[str, set[str]] = defaultdict(set)
    title_by_url: dict[str, str] = {}

    for field, term in query_specs:
        print(f"DRA search: {field}={term}", flush=True)
        try:
            results = search_dra(
                term=term,
                field=field,
                showhits=10,
                first_broadcast_from="1945",
                first_broadcast_to="2026",
                max_pages=max_pages,
            )
        except Exception as error:
            print(f"DRA search failed for {field}={term}: {error}", flush=True)
            continue
        print(f"  found {len(results)} visible result links", flush=True)
        for result in results[:limit_per_query]:
            url_to_terms[result.detail_url].add(f"{field}:{term}")
            title_by_url[result.detail_url] = result.title

    total = len(url_to_terms)
    records = []
    detail_urls = sorted(url_to_terms)
    with ThreadPoolExecutor(max_workers=detail_workers) as executor:
        futures = [
            executor.submit(_collect_one_dra_detail, index, total, detail_url, url_to_terms, title_by_url)
            for index, detail_url in enumerate(detail_urls, start=1)
        ]
        for future in as_completed(futures):
            record = future.result()
            if record:
                records.append(record)

    return pd.DataFrame(records)


def write_outputs(dra_df: pd.DataFrame, bbc_df: pd.DataFrame) -> None:
    interim_dir = PROJECT_ROOT / "data" / "interim"
    processed_dir = PROJECT_ROOT / "data" / "processed"
    interim_dir.mkdir(parents=True, exist_ok=True)
    processed_dir.mkdir(parents=True, exist_ok=True)

    dra_path = interim_dir / "dra_biography_term_batch.csv"
    bbc_path = interim_dir / "bbc_programmes_seed_batch.csv"
    merged_path = processed_dir / "radio_biographical_drama_candidates.csv"
    summary_path = processed_dir / "scrape_summary.json"

    dra_df.to_csv(dra_path, index=False)
    bbc_df.to_csv(bbc_path, index=False)
    pd.concat([dra_df, bbc_df], ignore_index=True, sort=False).to_csv(merged_path, index=False)

    summary = {
        "dra_rows": int(len(dra_df)),
        "bbc_rows": int(len(bbc_df)),
        "merged_rows": int(len(dra_df) + len(bbc_df)),
        "dra_output": str(dra_path),
        "bbc_output": str(bbc_path),
        "merged_output": str(merged_path),
        "biographical_labels": pd.concat([dra_df, bbc_df], ignore_index=True, sort=False)
        .get("biographical_label", pd.Series(dtype=str))
        .value_counts(dropna=False)
        .to_dict(),
    }
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dra-limit-per-term", type=int, default=80)
    parser.add_argument("--dra-max-pages", type=int, default=8)
    parser.add_argument("--dra-detail-workers", type=int, default=6)
    parser.add_argument("--skip-bbc", action="store_true")
    parser.add_argument("--skip-dra", action="store_true")
    args = parser.parse_args()

    dra_df = pd.DataFrame()
    bbc_df = pd.DataFrame()

    if not args.skip_dra:
        dra_df = collect_dra_batch(
            DRA_QUERY_SPECS,
            args.dra_limit_per_term,
            args.dra_max_pages,
            args.dra_detail_workers,
        )
    if not args.skip_bbc:
        bbc_df = collect_bbc_programmes_sample(BBC_SEED_PIDS)

    write_outputs(dra_df, bbc_df)


if __name__ == "__main__":
    main()
