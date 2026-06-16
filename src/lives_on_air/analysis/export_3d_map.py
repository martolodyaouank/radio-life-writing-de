from __future__ import annotations

import json
import math
import re

import pandas as pd

from lives_on_air.config import PROJECT_ROOT


INPUT = PROJECT_ROOT / "data" / "processed" / "analysis_tables" / "core_semantic_enriched.csv"
OUTPUT = PROJECT_ROOT / "article" / "semantic-map-3d-data.js"
EXCLUSIONS = PROJECT_ROOT / "data" / "curation" / "life_writing_exclusions.csv"
SUBJECT_OVERRIDES = PROJECT_ROOT / "data" / "curation" / "life_subject_overrides.csv"


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

SUBJECT_PATTERNS = [
    (
        "Women's life",
        re.compile(
            r"\b(frau|frauen|weiblich|mutter|tochter|schwester|mädchen|witwe|"
            r"autorin|schriftstellerin|dichterin|künstlerin|sängerin|"
            r"schauspielerin|regisseurin|komponistin|femin)"
        ),
    ),
    (
        "Author / literary figure",
        re.compile(
            r"\b(autor|autorin|schriftsteller|schriftstellerin|dichter|dichterin|"
            r"literat|literatur|poet|poetin|essayist|essayistin)"
        ),
    ),
    (
        "Musician / composer",
        re.compile(
            r"\b(musik|musiker|musikerin|komponist|komponistin|sänger|sängerin|"
            r"pianist|pianistin|geiger|geigerin|dirigent|dirigentin|jazz|oper)"
        ),
    ),
    (
        "Artist / visual artist",
        re.compile(
            r"\b(kunst|künstler|künstlerin|maler|malerin|bildhauer|bildhauerin|"
            r"fotograf|fotografin|architekt|architektin|performance)"
        ),
    ),
    (
        "Actor / performer",
        re.compile(
            r"\b(schauspiel|schauspieler|schauspielerin|darsteller|darstellerin|"
            r"theater|bühne|kabarett|regisseur|regisseurin)"
        ),
    ),
    (
        "Political / historical figure",
        re.compile(
            r"\b(politik|politiker|politikerin|krieg|ns-|nationalsozial|holocaust|"
            r"shoah|exil|widerstand|revolution|stasi|kolonial|prozess|verfolg)"
        ),
    ),
    (
        "Scholar / intellectual",
        re.compile(
            r"\b(philosoph|philosophin|wissenschaft|wissenschaftler|forscher|"
            r"forscherin|theolog|historiker|historikerin|kritiker|kritikerin)"
        ),
    ),
    (
        "Family / intimate life",
        re.compile(
            r"\b(familie|familien|vater|mutter|kindheit|kind|kinder|eltern|"
            r"tochter|sohn|schwester|bruder|ehe|liebe|privat)"
        ),
    ),
    (
        "Collective / community",
        re.compile(
            r"\b(generation|gruppe|kollektiv|gemeinde|dorf|stadt|arbeiter|"
            r"migration|migrant|community|chor|klasse)"
        ),
    ),
]


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


def load_excluded_urls() -> set[str]:
    if not EXCLUSIONS.exists():
        return set()
    exclusions = pd.read_csv(EXCLUSIONS)
    if "source_url" not in exclusions.columns:
        return set()
    return {
        str(url).strip()
        for url in exclusions["source_url"].dropna()
        if str(url).strip()
    }


def load_subject_overrides() -> dict[str, dict[str, str]]:
    if not SUBJECT_OVERRIDES.exists():
        return {}
    overrides = pd.read_csv(SUBJECT_OVERRIDES).fillna("")
    if "source_url" not in overrides.columns:
        return {}
    return {
        str(row.source_url).strip(): {
            "dedicated_to": str(getattr(row, "dedicated_to", "")).strip(),
            "life_focus": str(getattr(row, "life_focus", "")).strip(),
            "short_description": str(getattr(row, "short_description", "")).strip(),
        }
        for row in overrides.itertuples()
        if str(row.source_url).strip()
    }


def row_text(row: object) -> str:
    fields = [
        "title",
        "genre",
        "life_signal",
        "cluster_label",
        "creator",
        "author",
        "description",
        "long_description",
        "seo_description",
        "analysis_text",
    ]
    return " ".join(
        str(getattr(row, field, "") or "")
        for field in fields
        if not pd.isna(getattr(row, field, ""))
    ).casefold()


def subject_tags(row: object) -> list[str]:
    text = row_text(row)
    tags = [label for label, pattern in SUBJECT_PATTERNS if pattern.search(text)]
    if safe_float(getattr(row, "flag_artist_author", 0), 0) > 0 and not any(
        tag
        in {
            "Author / literary figure",
            "Musician / composer",
            "Artist / visual artist",
            "Actor / performer",
        }
        for tag in tags
    ):
        tags.append("Author / artist")
    if safe_float(getattr(row, "flag_family_self", 0), 0) > 0 and "Family / intimate life" not in tags:
        tags.append("Family / intimate life")
    if not tags and str(getattr(row, "life_signal", "") or "") == "implicit":
        tags.append("Unclear / needs review")
    if not tags:
        tags.append("Ordinary / private person")
    return tags


def first_value(row: object, fields: list[str]) -> str:
    for field in fields:
        value = getattr(row, field, "")
        if not pd.isna(value):
            text = str(value).strip()
            if text:
                return text
    return ""


def clean_person_list(value: str) -> str:
    names = [name.strip() for name in re.split(r";|\s+/\s+", value) if name.strip()]
    return "; ".join(dict.fromkeys(names[:4]))


def subject_name(row: object) -> str:
    title = str(getattr(row, "title", "") or "")
    text = row_text(row)
    patterns = [
        r"porträt des autors ([A-ZÄÖÜ][^.,;:]+)",
        r"porträt der autorin ([A-ZÄÖÜ][^.,;:]+)",
        r"porträt des ([A-ZÄÖÜ][^.,;:]+)",
        r"porträt der ([A-ZÄÖÜ][^.,;:]+)",
        r"über ([A-ZÄÖÜ][^.,;:]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, title, flags=re.IGNORECASE)
        if match:
            return match.group(1).strip()
    memory_match = re.search(r"([A-ZÄÖÜ][^.;:]+?)\s+erinnert sich", title)
    if memory_match:
        return memory_match.group(1).strip()
    authors = first_value(row, ["authors", "creator", "author"])
    life_signal = str(getattr(row, "life_signal", "") or "")
    if authors and any(signal in life_signal for signal in ["autobiography", "biography", "diary/letters", "portrait"]):
        return clean_person_list(authors)
    if "lessing" in text:
        return "Gotthold Ephraim Lessing"
    return "Subject not identified"


def subject_description(row: object) -> str:
    description = first_value(row, ["description", "seo_description", "long_description"])
    if description:
        return re.sub(r"\s+", " ", description)[:260]
    text = first_value(row, ["analysis_text", "raw_text_sample"])
    if not text:
        return "No short description available in the source metadata."
    document_match = re.search(
        r"((?:Briefe|Tagebuch|Schriften|Dokumente|Autobiographie)[^.]{20,220})",
        text,
        flags=re.IGNORECASE,
    )
    if document_match:
        return re.sub(r"\s+", " ", document_match.group(1)).strip()
    title = str(getattr(row, "title", "") or "")
    text = text.replace(title, "", 1)
    text = re.sub(
        r"\b(Technische Realisierung|Regieassistenz|Regie|Weitere Mitwirkende|"
        r"Sprecher/Sprecherin|Produktions- und Sendedaten)\b.*",
        "",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(r"\s+", " ", text).strip(" .")
    return text[:260] if text else "No short description available in the source metadata."


def main() -> None:
    df = pd.read_csv(INPUT)
    excluded_urls = load_excluded_urls()
    if excluded_urls:
        df = df[~df["source_url"].astype(str).str.strip().isin(excluded_urls)].copy()
    subject_overrides = load_subject_overrides()

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
        who_about = subject_tags(row)
        who_name = subject_name(row)
        override = subject_overrides.get(str(getattr(row, "source_url", "") or "").strip(), {})
        if override.get("dedicated_to"):
            who_name = override["dedicated_to"]
        if override.get("life_focus"):
            who_about = [tag.strip() for tag in override["life_focus"].split(";") if tag.strip()]
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
                "whoAbout": who_about,
                "whoPrimary": who_about[0],
                "dedicatedTo": who_name,
                "subjectDescription": override.get("short_description") or subject_description(row),
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
        "whoAbout": sorted({tag for record in records for tag in record["whoAbout"]}),
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
