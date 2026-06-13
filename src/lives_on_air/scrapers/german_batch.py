from __future__ import annotations

import argparse
import json

import pandas as pd

from lives_on_air.config import PROJECT_ROOT
from lives_on_air.scrapers.batch import DRA_QUERY_SPECS, collect_dra_batch
from lives_on_air.scrapers.hoerspielundfeature import collect as collect_huf
from lives_on_air.scrapers.wirklichkeit import collect as collect_wirklichkeit


def write_source(df: pd.DataFrame, filename: str) -> str:
    path = PROJECT_ROOT / "data" / "interim" / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    return str(path)


def candidate_confidence(row: pd.Series) -> str:
    source = row.get("source_archive", "")
    label = row.get("biographical_label", "")
    score = int(row.get("biographical_score") or 0)
    if source in {"wirklichkeit_im_radio", "hoerspielundfeature"} and label == "high_confidence_biographical":
        return "high"
    if source == "dra" and label == "high_confidence_biographical":
        return "high"
    if label == "possible_biographical" or score == 1:
        return "medium"
    return "review"


def combine_german(frames: list[pd.DataFrame]) -> pd.DataFrame:
    df = pd.concat([frame for frame in frames if not frame.empty], ignore_index=True, sort=False)
    if "source_url" in df.columns:
        subset = [col for col in ["source_archive", "source_url", "title"] if col in df.columns]
        df = df.drop_duplicates(subset=subset)
    df["country_context"] = "Germany"
    df["candidate_confidence"] = df.apply(candidate_confidence, axis=1)
    return df


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-dra", action="store_true")
    parser.add_argument("--skip-wirklichkeit", action="store_true")
    parser.add_argument("--skip-hoerspielundfeature", action="store_true")
    parser.add_argument("--dra-limit-per-term", type=int, default=80)
    parser.add_argument("--dra-max-pages", type=int, default=8)
    parser.add_argument("--dra-detail-workers", type=int, default=6)
    parser.add_argument("--wirklichkeit-limit", type=int, default=None)
    parser.add_argument("--huf-limit", type=int, default=None)
    parser.add_argument("--huf-no-search", action="store_true")
    args = parser.parse_args()

    outputs: dict[str, str] = {}
    frames: list[pd.DataFrame] = []

    if not args.skip_dra:
        dra = collect_dra_batch(DRA_QUERY_SPECS, args.dra_limit_per_term, args.dra_max_pages, args.dra_detail_workers)
        outputs["dra"] = write_source(dra, "dra_biography_term_batch.csv")
        frames.append(dra)

    if not args.skip_wirklichkeit:
        wirklichkeit = collect_wirklichkeit(limit=args.wirklichkeit_limit)
        outputs["wirklichkeit_im_radio"] = write_source(wirklichkeit, "wirklichkeit_im_radio_stuecke.csv")
        frames.append(wirklichkeit)

    if not args.skip_hoerspielundfeature:
        huf = collect_huf(limit=args.huf_limit, include_search=not args.huf_no_search)
        outputs["hoerspielundfeature"] = write_source(huf, "hoerspielundfeature_candidates.csv")
        frames.append(huf)

    combined = combine_german(frames)
    processed = PROJECT_ROOT / "data" / "processed"
    processed.mkdir(parents=True, exist_ok=True)
    merged_path = processed / "german_radio_biographical_candidates.csv"
    summary_path = processed / "german_scrape_summary.json"
    combined.to_csv(merged_path, index=False)

    summary = {
        "rows": int(len(combined)),
        "columns": int(len(combined.columns)),
        "output": str(merged_path),
        "source_outputs": outputs,
        "sources": combined["source_archive"].value_counts(dropna=False).to_dict(),
        "biographical_labels": combined.get("biographical_label", pd.Series(dtype=str))
        .value_counts(dropna=False)
        .to_dict(),
        "candidate_confidence": combined["candidate_confidence"].value_counts(dropna=False).to_dict(),
    }
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
