from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from lives_on_air.config import PROJECT_ROOT


INPUTS = [
    PROJECT_ROOT / "data" / "interim" / "dra_biography_term_batch.csv",
    PROJECT_ROOT / "data" / "interim" / "wirklichkeit_im_radio_stuecke.csv",
    PROJECT_ROOT / "data" / "interim" / "hoerspielundfeature_candidates.csv",
]


def source_confidence(row: pd.Series) -> str:
    source = row.get("source_archive", "")
    label = row.get("biographical_label", "")
    if source in {"dra", "wirklichkeit_im_radio", "hoerspielundfeature"} and label == "high_confidence_biographical":
        return "high"
    if source in {"dra", "wirklichkeit_im_radio", "hoerspielundfeature"} and label == "possible_biographical":
        return "medium"
    return "review"


def combine() -> pd.DataFrame:
    frames = []
    for path in INPUTS:
        if path.exists():
            frames.append(pd.read_csv(path))
    if not frames:
        raise RuntimeError("No input CSV files found")

    df = pd.concat(frames, ignore_index=True, sort=False)
    if "source_url" in df.columns:
        subset = [col for col in ["source_archive", "source_url", "title", "raw_text_sample"] if col in df.columns]
        df = df.drop_duplicates(subset=subset)
    df["candidate_confidence"] = df.apply(source_confidence, axis=1)

    df["country_context"] = "Germany"
    output_path = PROJECT_ROOT / "data" / "processed" / "german_radio_biographical_candidates.csv"
    summary_path = PROJECT_ROOT / "data" / "processed" / "german_scrape_summary.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)

    summary = {
        "rows": int(len(df)),
        "columns": int(len(df.columns)),
        "output": str(output_path),
        "sources": df["source_archive"].value_counts(dropna=False).to_dict(),
        "biographical_labels": df.get("biographical_label", pd.Series(dtype=str))
        .value_counts(dropna=False)
        .to_dict(),
        "candidate_confidence": df["candidate_confidence"].value_counts(dropna=False).to_dict(),
    }
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return df


if __name__ == "__main__":
    combine()
