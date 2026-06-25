from __future__ import annotations

import csv
import json
import math
import re

from lives_on_air.config import PROJECT_ROOT


INPUT = PROJECT_ROOT / "data" / "latent_semantic_map_all_602_sorted.csv"
ORIGINAL_LAYOUT_INPUT = PROJECT_ROOT / "data" / "processed" / "analysis_tables" / "core_semantic_enriched.csv"
OUTPUT = PROJECT_ROOT / "article" / "semantic-map-3d-data.js"
DURATION_OUTPUT = PROJECT_ROOT / "article" / "duration-scale-data.js"

CLUSTER_COLORS = {
    "Autobiographical lives": "#c29a45",
    "Diaries and self-records": "#a8734f",
    "Portrait catalogue": "#3e7883",
    "Letters and correspondence": "#8173a4",
    "Curated documentary close readings": "#78838c",
    "Social documentary lives": "#9b6675",
    "Biography": "#4f8f77",
    "Sound art and listening": "#6a7f67",
    "Based on diaries": "#b56d8f",
    "Based on letters": "#6f8fc9",
    "Biofiction": "#d07a56",
    "Sound art": "#5d9bb5",
}


def clean(value: object) -> str:
    return str(value or "").strip()


def safe_year(value: str) -> int | None:
    try:
        return int(float(clean(value)))
    except ValueError:
        return None


def safe_float(value: object, fallback: float = 0.0) -> float:
    try:
        parsed = float(clean(value))
    except ValueError:
        return fallback
    if not math.isfinite(parsed):
        return fallback
    return parsed


def duration_minutes_from_row(row: dict[str, str]) -> float | None:
    minutes = safe_float(row.get("duration_minutes"), math.nan)
    if math.isfinite(minutes) and minutes > 0:
        return minutes

    seconds = safe_float(row.get("duration_seconds"), math.nan)
    if math.isfinite(seconds) and seconds > 0:
        return seconds / 60

    duration = clean(row.get("duration"))
    if not duration:
        return None

    numeric_duration = safe_float(duration, math.nan)
    if math.isfinite(numeric_duration) and numeric_duration > 0:
        return numeric_duration / 60 if numeric_duration > 240 else numeric_duration

    return parse_legacy_duration(duration)


def parse_legacy_duration(value: str) -> float | None:
    text = clean(value)
    if not text:
        return None

    match = re.match(r"^(\d+)'(\d{1,2})$", text)
    if match:
        return int(match.group(1)) + int(match.group(2)) / 60

    match = re.match(r"^(\d+):(\d{1,2})(?::(\d{1,2}))?$", text)
    if match:
        first = int(match.group(1))
        second = int(match.group(2))
        third = int(match.group(3) or 0)
        if match.group(3):
            return first * 60 + second + third / 60
        return first + second / 60

    return None


def split_roles(value: str) -> list[str]:
    return [part.strip() for part in clean(value).split(";") if part.strip()]


def load_existing_descriptions() -> dict[str, str]:
    if not OUTPUT.exists():
        return {}
    text = OUTPUT.read_text(encoding="utf-8").strip()
    prefix = "window.semanticMap3D = "
    if not text.startswith(prefix):
        return {}
    payload = json.loads(text[len(prefix) :].rstrip(";"))
    return {
        clean(record.get("url")): clean(record.get("description"))
        for record in payload.get("records", [])
        if clean(record.get("url")) and clean(record.get("description"))
    }


def load_original_positions() -> dict[str, tuple[float, float]]:
    if not ORIGINAL_LAYOUT_INPUT.exists():
        return {}
    with ORIGINAL_LAYOUT_INPUT.open(newline="", encoding="utf-8") as handle:
        rows = csv.DictReader(handle)
        return {
            clean(row.get("source_url")): (
                safe_float(row.get("map_x")),
                safe_float(row.get("map_y")),
            )
            for row in rows
            if clean(row.get("source_url"))
        }


def load_duration_lookup() -> dict[str, float]:
    if not ORIGINAL_LAYOUT_INPUT.exists():
        return {}
    with ORIGINAL_LAYOUT_INPUT.open(newline="", encoding="utf-8") as handle:
        rows = csv.DictReader(handle)
        return {
            clean(row.get("source_url")): duration
            for row in rows
            if clean(row.get("source_url"))
            if (duration := duration_minutes_from_row(row)) is not None
        }


def main() -> None:
    with INPUT.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    years = [year for year in (safe_year(row["year"]) for row in rows) if year is not None]
    year_min = min(years)
    year_max = max(years)
    year_span = max(1, year_max - year_min)

    cluster_order = []
    for row in rows:
        cluster = clean(row["cluster"]) or "Unclustered"
        if cluster not in cluster_order:
            cluster_order.append(cluster)

    original_positions = load_original_positions()
    duration_lookup = load_duration_lookup()
    existing_descriptions = load_existing_descriptions()

    records = []
    duration_records = []
    for row in rows:
        cluster = clean(row["cluster"]) or "Unclustered"

        year = safe_year(row["year"])
        z = (((year or year_min) - year_min) / year_span - 0.5) * 46
        roles = split_roles(row["protagonist_role"])
        url = clean(row["url"])
        description = existing_descriptions.get(url) or clean(row["description"])
        x, y = original_positions.get(url, (0.0, 0.0))

        records.append(
            {
                "title": clean(row["title"]) or "Untitled",
                "year": year,
                "firstBroadcastDate": clean(row["first_broadcast_date"]),
                "date": clean(row["first_broadcast_date"]),
                "source": clean(row["source"]),
                "cluster": cluster,
                "form": clean(row["genre"]),
                "genre": clean(row["genre"]),
                "broadcaster": clean(row["broadcasting_station"]),
                "broadcastingStation": clean(row["broadcasting_station"]),
                "signals": [],
                "whoAbout": roles,
                "whoPrimary": roles[0] if roles else "",
                "protagonist": clean(row["protagonist_verified"]),
                "protagonistRole": clean(row["protagonist_role"]),
                "author": clean(row["author"]),
                "director": clean(row["director"]),
                "description": description,
                "subjectDescription": description,
                "url": url,
                "x": round(float(x), 4),
                "y": round(float(y), 4),
                "z": round(z, 4),
                "color": CLUSTER_COLORS.get(cluster, "#65717d"),
            }
        )
        duration = duration_lookup.get(url)
        if duration is not None:
            duration_records.append(
                {
                    "title": clean(row["title"]) or "Untitled",
                    "cluster": cluster,
                    "source": clean(row["source"]),
                    "year": year,
                    "duration": round(duration, 2),
                }
            )

    payload = {
        "records": records,
        "yearMin": year_min,
        "yearMax": year_max,
        "clusterColors": {cluster: CLUSTER_COLORS.get(cluster, "#65717d") for cluster in cluster_order},
        "forms": sorted({record["genre"] for record in records if record["genre"]}),
        "sources": sorted({record["source"] for record in records if record["source"]}),
        "signals": [],
        "whoAbout": sorted({role for record in records for role in record["whoAbout"]}),
    }

    OUTPUT.write_text(
        "window.semanticMap3D = "
        + json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        + ";\n",
        encoding="utf-8",
    )
    print(f"Wrote {len(records)} records to {OUTPUT}")

    duration_payload = {
        "records": duration_records,
        "matched": len(duration_records),
        "mapRecords": len(records),
        "unit": "minutes",
    }
    DURATION_OUTPUT.write_text(
        "window.durationScaleData = "
        + json.dumps(duration_payload, ensure_ascii=False, separators=(",", ":"))
        + ";\n",
        encoding="utf-8",
    )
    print(f"Wrote {len(duration_records)} duration records to {DURATION_OUTPUT}")


if __name__ == "__main__":
    main()
