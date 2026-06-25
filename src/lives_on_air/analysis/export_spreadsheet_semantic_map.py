from __future__ import annotations

import csv
import json
import math
import re
from collections import Counter

import numpy as np

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

TEXT_FIELDS = [
    "title",
    "description",
    "genre",
    "protagonist_verified",
    "protagonist_role",
    "author",
    "director",
    "broadcasting_station",
    "source",
]

STOPWORDS = {
    "aber",
    "alle",
    "als",
    "auch",
    "auf",
    "aus",
    "bei",
    "das",
    "dem",
    "den",
    "der",
    "des",
    "die",
    "ein",
    "eine",
    "einem",
    "einen",
    "einer",
    "eines",
    "feature",
    "für",
    "hat",
    "hörspiel",
    "im",
    "in",
    "ist",
    "mit",
    "nach",
    "nicht",
    "oder",
    "sich",
    "und",
    "von",
    "war",
    "wird",
    "zu",
    "zum",
    "zur",
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


def row_text(row: dict[str, str]) -> str:
    return " ".join(clean(row.get(field)) for field in TEXT_FIELDS if clean(row.get(field)))


def tokenize(text: str) -> list[str]:
    return [
        token
        for token in re.findall(r"[a-zA-ZäöüÄÖÜß][a-zA-ZäöüÄÖÜß-]{2,}", text.casefold())
        if token not in STOPWORDS
    ]


def tfidf_matrix(texts: list[str], max_features: int = 5000) -> np.ndarray:
    tokenized = [tokenize(text) for text in texts]
    document_frequency = Counter(token for tokens in tokenized for token in set(tokens))
    min_df = 2 if len(texts) < 120 else 3
    terms = [
        term
        for term, _ in document_frequency.most_common(max_features)
        if document_frequency[term] >= min_df and document_frequency[term] <= len(texts) * 0.85
    ]
    if len(terms) < 2:
        return np.empty((len(texts), 0))

    term_index = {term: index for index, term in enumerate(terms)}
    matrix = np.zeros((len(texts), len(terms)), dtype=float)
    for row_index, tokens in enumerate(tokenized):
        counts = Counter(token for token in tokens if token in term_index)
        for token, count in counts.items():
            matrix[row_index, term_index[token]] = 1.0 + math.log(count)

    idf = np.log((1 + len(texts)) / (1 + np.array([document_frequency[term] for term in terms]))) + 1.0
    matrix *= idf
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    np.divide(matrix, norms, out=matrix, where=norms > 0)
    return matrix


def scale_coordinates(coords: np.ndarray, target_radius: float = 32.0) -> np.ndarray:
    if coords.size == 0:
        return coords
    centered = coords - coords.mean(axis=0, keepdims=True)
    spread = float(np.percentile(np.abs(centered), 98))
    if spread <= 0:
        spread = float(np.max(np.abs(centered)))
    if spread <= 0:
        return centered
    return centered * (target_radius / spread)


def pca_positions(matrix: np.ndarray) -> np.ndarray:
    if matrix.shape[0] == 0:
        return np.empty((0, 2))
    if matrix.shape[0] == 1:
        return np.zeros((1, 2))
    centered = matrix - matrix.mean(axis=0, keepdims=True)
    if centered.shape[1] == 0 or not np.any(centered):
        return np.zeros((matrix.shape[0], 2))
    _, _, vh = np.linalg.svd(centered, full_matrices=False)
    n_components = min(2, vh.shape[0])
    coords = centered @ vh[:n_components].T
    if n_components < 2:
        coords = np.column_stack([coords[:, 0], np.zeros(matrix.shape[0])])
    return coords


def reduced_positions(rows: list[dict[str, str]]) -> np.ndarray:
    texts = [row_text(row) for row in rows]
    if len(texts) < 2 or not any(texts):
        return np.zeros((len(texts), 2))

    matrix = tfidf_matrix(texts)
    if matrix.shape[1] < 2:
        coords = np.column_stack([np.arange(len(texts), dtype=float), np.zeros(len(texts))])
        return scale_coordinates(coords)
    return scale_coordinates(pca_positions(matrix))


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

    positions = reduced_positions(rows)
    existing_descriptions = load_existing_descriptions()

    records = []
    for index, row in enumerate(rows):
        cluster = clean(row["cluster"]) or "Unclustered"

        year = safe_year(row["year"])
        z = (((year or year_min) - year_min) / year_span - 0.5) * 46
        roles = split_roles(row["protagonist_role"])
        url = clean(row["url"])
        description = existing_descriptions.get(url) or clean(row["description"])
        x, y = positions[index]

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
