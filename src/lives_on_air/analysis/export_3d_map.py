from __future__ import annotations

import json
import math

import pandas as pd

from lives_on_air.config import PROJECT_ROOT


INPUT = PROJECT_ROOT / "data" / "processed" / "analysis_tables" / "core_semantic_enriched.csv"
OUTPUT = PROJECT_ROOT / "article" / "semantic-map-3d-data.js"


CLUSTER_COLORS = {
    "Autobiographical lives": "#c29a45",
    "Social documentary lives": "#9b6675",
    "Curated documentary close readings": "#78838c",
    "Sound art and listening": "#6a7f67",
    "Letters and correspondence": "#8173a4",
    "Portrait catalogue": "#3e7883",
    "Diaries and self-records": "#a8734f",
}

SIGNAL_COLUMNS = {
    "voice": "flag_voice",
    "sound": "flag_sound",
    "archive": "flag_archive",
    "memory": "flag_memory",
    "trauma/history": "flag_trauma_history",
    "artist/author": "flag_artist_author",
    "family/self": "flag_family_self",
    "letters/diaries": "flag_letters_diaries",
}


def safe_float(value: object, fallback: float = 0.0) -> float:
    if pd.isna(value):
        return fallback
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return fallback
    if not math.isfinite(parsed):
        return fallback
    return parsed


def clean_label(value: object, fallback: str = "Unknown") -> str:
    if pd.isna(value):
        return fallback
    text = str(value).strip()
    return text if text else fallback


def main() -> None:
    df = pd.read_csv(INPUT)
    years = pd.to_numeric(df["analysis_year"], errors="coerce")
    median_year = float(years.median())
    year_min = float(years.min())
    year_max = float(years.max())
    year_span = max(1.0, year_max - year_min)

    records = []
    for row in df.itertuples():
        year = safe_float(getattr(row, "analysis_year", None), median_year)
        z = ((year - year_min) / year_span - 0.5) * 46
        cluster = str(getattr(row, "cluster_label", "unknown"))
        signals = [
            label
            for label, column in SIGNAL_COLUMNS.items()
            if safe_float(getattr(row, column, 0), 0) > 0
        ]
        records.append(
            {
                "title": str(getattr(row, "title", "") or "Untitled"),
                "year": int(year) if math.isfinite(year) else None,
                "source": str(getattr(row, "source_label", "") or ""),
                "cluster": cluster,
                "form": clean_label(getattr(row, "form_family", None), "Unknown form"),
                "genre": clean_label(getattr(row, "genre", None), "Unknown genre"),
                "broadcaster": clean_label(getattr(row, "broadcaster", None), ""),
                "duration": round(safe_float(getattr(row, "duration_minutes", 0.0)), 1),
                "signals": signals,
                "url": str(getattr(row, "source_url", "") or ""),
                "x": round(safe_float(getattr(row, "map_x", 0.0)), 4),
                "y": round(safe_float(getattr(row, "map_y", 0.0)), 4),
                "z": round(z, 4),
                "color": CLUSTER_COLORS.get(cluster, "#65717d"),
            }
        )

    payload = {
        "records": records,
        "yearMin": int(year_min),
        "yearMax": int(year_max),
        "clusterColors": CLUSTER_COLORS,
        "forms": sorted({record["form"] for record in records}),
        "sources": sorted({record["source"] for record in records}),
        "signals": list(SIGNAL_COLUMNS),
    }
    OUTPUT.write_text(
        "window.semanticMap3D = "
        + json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        + ";\n",
        encoding="utf-8",
    )
    print(f"Wrote {len(records)} records to {OUTPUT}")


if __name__ == "__main__":
    main()
