from __future__ import annotations

import csv
import json
import math
from collections import defaultdict

from lives_on_air.config import PROJECT_ROOT


INPUT = PROJECT_ROOT / "data" / "latent_semantic_map_all_602_sorted.csv"
OUTPUT = PROJECT_ROOT / "article" / "semantic-map-3d-data.js"

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


def cluster_centers(clusters: list[str]) -> dict[str, tuple[float, float]]:
    radius = 22
    return {
        cluster: (
            math.cos((2 * math.pi * index) / max(1, len(clusters))) * radius,
            math.sin((2 * math.pi * index) / max(1, len(clusters))) * radius,
        )
        for index, cluster in enumerate(clusters)
    }


def local_position(index: int, total: int) -> tuple[float, float]:
    if total <= 1:
        return (0.0, 0.0)
    angle = index * math.pi * (3 - math.sqrt(5))
    radius = 2.2 + 9.5 * math.sqrt(index / max(1, total - 1))
    return (math.cos(angle) * radius, math.sin(angle) * radius)


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

    centers = cluster_centers(cluster_order)
    cluster_counts = defaultdict(int)
    cluster_totals = defaultdict(int)
    existing_descriptions = load_existing_descriptions()
    for row in rows:
        cluster_totals[clean(row["cluster"]) or "Unclustered"] += 1

    records = []
    for row in rows:
        cluster = clean(row["cluster"]) or "Unclustered"
        cluster_index = cluster_counts[cluster]
        cluster_counts[cluster] += 1

        year = safe_year(row["year"])
        z = (((year or year_min) - year_min) / year_span - 0.5) * 46
        center_x, center_y = centers[cluster]
        offset_x, offset_y = local_position(cluster_index, cluster_totals[cluster])
        roles = split_roles(row["protagonist_role"])
        url = clean(row["url"])
        description = existing_descriptions.get(url) or clean(row["description"])

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
                "x": round(center_x + offset_x, 4),
                "y": round(center_y + offset_y, 4),
                "z": round(z, 4),
                "color": CLUSTER_COLORS.get(cluster, "#65717d"),
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


if __name__ == "__main__":
    main()
