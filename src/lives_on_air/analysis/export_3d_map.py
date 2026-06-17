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
SOURCE_DESCRIPTIONS = PROJECT_ROOT / "data" / "curation" / "source_card_descriptions.csv"


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


def load_source_descriptions() -> dict[str, str]:
    if not SOURCE_DESCRIPTIONS.exists():
        return {}
    descriptions = pd.read_csv(SOURCE_DESCRIPTIONS).fillna("")
    if "source_url" not in descriptions.columns:
        return {}
    description_column = "english_description" if "english_description" in descriptions.columns else "short_description"
    if description_column not in descriptions.columns:
        return {}
    return {
        str(row.source_url).strip(): str(getattr(row, description_column, "")).strip()
        for row in descriptions.itertuples()
        if str(row.source_url).strip() and str(getattr(row, description_column, "")).strip()
    }


def row_text(row: object) -> str:
    fields = [
        "title",
        "display_title",
        "genre",
        "life_signal",
        "cluster_label",
        "description",
        "seo_description",
        "image_caption",
        "image_alt",
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


def clean_summary_text(value: str) -> str:
    text = re.sub(r"\s+", " ", value).strip()
    text = re.sub(r"^(Feature|Hörspiel|Archiv|Essay)\s+", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+Aus dem Podcast.*$", "", text, flags=re.IGNORECASE)
    return text.strip()


def source_summary(row: object) -> str:
    for field in ["description", "seo_description"]:
        value = first_value(row, [field])
        if value:
            return clean_summary_text(value)
    long_description = first_value(row, ["long_description"])
    if long_description:
        sentences = re.split(r"(?<=[.!?])\s+", clean_summary_text(long_description))
        useful = [
            sentence
            for sentence in sentences
            if 35 <= len(sentence) <= 260
            and not re.search(r"\b(link kopieren|audio herunterladen|produktion|länge|minuten)\b", sentence, flags=re.IGNORECASE)
        ]
        if useful:
            return " ".join(useful[:2])
    return ""


def first_value(row: object, fields: list[str]) -> str:
    for field in fields:
        value = getattr(row, field, "")
        if not pd.isna(value):
            text = str(value).strip()
            if text:
                return text
    return ""


def clean_person_list(value: str) -> str:
    names = [
        re.sub(r"^(von|Von|nach|Nach|by|By)\s+", "", name.strip())
        for name in re.split(r";|\s+/\s+", value)
        if name.strip()
    ]
    return "; ".join(dict.fromkeys(names[:4]))


def production_credit(row: object, fields: list[str]) -> str:
    value = first_value(row, fields)
    if value:
        return clean_person_list(value)
    text = first_value(row, ["long_description", "raw_text_sample"])
    for label in fields:
        if "director" in label or "regie" in label or "realisation" in label:
            match = re.search(
                r"\bRegie:\s*(.+?)(?=\s+(?:Mit:|Ton(?:\s+und\s+Technik)?:|Produktion:|Länge:)|[.;\n|]|$)",
                text,
            )
            if match:
                return clean_person_list(match.group(1))
    return ""


def plausible_subject(value: str, allow_article: bool = False) -> str:
    text = re.sub(r"\s+", " ", value).strip(" -–.,;:")
    if not text or len(text) > 72:
        return ""
    blocked_leads = "von|nach|mit|aus|über|ueber"
    if not allow_article:
        blocked_leads = f"der|die|das|den|dem|ein|eine|einen|einem|einer|a|an|the|{blocked_leads}"
    if re.match(rf"^({blocked_leads})\b", text, flags=re.IGNORECASE):
        return ""
    if any(fragment in text.casefold() for fragment in [" archiv", " hörspiel", " krimi", " doku", "?", " idee"]):
        return ""
    if not re.match(r"^[A-ZÄÖÜ]", text):
        return ""
    return text


SUBJECT_VERBS_DE = (
    "beginnt|erzählt|erzaehlt|berichtet|erinnert|schreibt|lebt|wohnt|kehrt|"
    "sucht|findet|arbeitet|kämpft|kaempft|steht|wird|ist|hat|macht|reist|"
    "versucht|nimmt"
)
SUBJECT_VERBS_EN = (
    "begins|tells|reports|remembers|writes|lives|returns|searches|finds|"
    "works|fights|stands|becomes|is|has|makes|travels|tries|takes|looks|"
    "ends up|portrays|portrayed"
)

PERSON_NAME = r"[A-ZÄÖÜ][\wÄÖÜäöüßéÉèÈáÁàÀíÍóÓúÚçÇ.-]+(?:\s+(?:v\.|von|van|de|del|der|den|du|da|di|la|le|[A-ZÄÖÜ][\wÄÖÜäöüßéÉèÈáÁàÀíÍóÓúÚçÇ.-]+)){1,4}"
ROLE_WORDS = (
    "author|writer|poet|playwright|critic|composer|musician|singer|painter|"
    "artist|actor|actress|director|philosopher|scholar|student|emigrant|"
    "Autor|Autorin|Schriftsteller|Schriftstellerin|Dichter|Dichterin|"
    "Komponist|Komponistin|Musiker|Musikerin|Sänger|Sängerin|Maler|Malerin|"
    "Künstler|Künstlerin|Schauspieler|Schauspielerin|Regisseur|Regisseurin|"
    "Philosoph|Philosophin|Student|Studentin|Emigrant|Emigrantin|Dramatiker|"
    "Dramatikerin|Kritiker|Kritikerin"
)
ROLE_CHAIN = rf"(?:{ROLE_WORDS})(?:(?:,\s*|\s+and\s+|\s+und\s+)(?:{ROLE_WORDS}))*"


def description_subject(value: str) -> str:
    text = clean_summary_text(value)
    if not text:
        return ""
    first_sentence = re.split(r"(?<=[.!?])\s+", text, maxsplit=1)[0].strip()
    patterns = [
        (rf"^(?:Als|When)\s+({PERSON_NAME})\b", 0),
        (rf"^({PERSON_NAME}),\s+(?:alias|geb\.|geboren|born|once|who|die|der)\b", 0),
        (rf"^({PERSON_NAME})\s+(?:war|was|ist|is)\b", 0),
        (rf"^(?:The|the|Der|der|Die|die|Das|das)\s+{ROLE_CHAIN}\s+({PERSON_NAME})\b", 0),
        (r"^(?:The life of|Das Leben des|Das Leben der)\s+([^.;:!?]{3,90})", re.IGNORECASE),
        (rf"^((?:Ein|Eine|Einen|Einem|Einer)\s+[^.;:!?]{{3,90}}?)\s+(?:{SUBJECT_VERBS_DE})\b", re.IGNORECASE),
        (rf"^((?:A|An|The)\s+[^.;:!?]{{3,90}}?)\s+(?:{SUBJECT_VERBS_EN})\b", re.IGNORECASE),
        (rf"\b(?:Porträt|porträt|Portrait|portrait)\s+(?:des|der|of)\s+(?:the\s+)?(?:{ROLE_CHAIN}\s+)?({PERSON_NAME}|[^.;:!?]{{3,90}})", 0),
        (r"\b(?:über|ueber|about)\s+([^.;:!?]{3,90})", re.IGNORECASE),
        (r"\b(?:focuses on|follows|porträtiert|portraitiert)\s+([^.;:!?]{3,90})", re.IGNORECASE),
    ]
    for pattern, flags in patterns:
        match = re.search(pattern, first_sentence, flags=flags)
        if not match:
            continue
        candidate = re.sub(
            rf"\s+(?:{SUBJECT_VERBS_DE}|{SUBJECT_VERBS_EN})\b.*$",
            "",
            match.group(1),
            flags=re.IGNORECASE,
        )
        candidate = re.sub(r"\s+(?:up to|bis zu|until|bis)\b.*$", "", candidate, flags=re.IGNORECASE)
        subject = plausible_subject(candidate, allow_article=True)
        if subject:
            return subject
    return ""


def title_subject(value: str) -> str:
    title = str(value or "").strip()
    case_sensitive_patterns = [
        r"^([A-ZÄÖÜ][\wÄÖÜäöüßéÉèÈáÁàÀíÍóÓúÚçÇ.-]+(?:\s+[A-ZÄÖÜ][\wÄÖÜäöüßéÉèÈáÁàÀíÍóÓúÚçÇ.-]+){1,3})\s+[-–]",
    ]
    case_insensitive_patterns = [
        r"\bDas Leben des\s+([A-ZÄÖÜ][^()/:;,]+)",
        r"\bDas Leben der\s+([A-ZÄÖÜ][^()/:;,]+)",
        r"\bThe life of\s+([A-Z][^()/:;,]+)",
    ]
    for pattern in case_sensitive_patterns:
        match = re.search(pattern, title)
        if match:
            subject = plausible_subject(match.group(1))
            if subject:
                return subject
    for pattern in case_insensitive_patterns:
        match = re.search(pattern, title, flags=re.IGNORECASE)
        if match:
            subject = plausible_subject(match.group(1))
            if subject:
                return subject
    return ""


def credit_subject_if_in_text(row: object, source_description: str = "") -> str:
    credit = plausible_subject(clean_person_list(first_value(row, ["authors", "creator", "author"])))
    if not credit:
        return ""
    haystack = " ".join(
        source
        for source in [
            str(getattr(row, "title", "") or ""),
            str(getattr(row, "display_title", "") or ""),
            source_description,
            first_value(row, ["description"]),
            first_value(row, ["seo_description"]),
            first_value(row, ["long_description"]),
        ]
        if source
    ).casefold()
    credit_parts = [part.strip() for part in credit.split(";") if part.strip()]
    mentioned_parts = [part for part in credit_parts if part.casefold() in haystack]
    if mentioned_parts:
        return "; ".join(mentioned_parts)
    return ""


def subject_name(row: object, source_description: str = "") -> str:
    title = str(getattr(row, "title", "") or "")
    text = row_text(row)
    display_title = str(getattr(row, "display_title", "") or "")
    caption = " ".join(
        first_value(row, [field])
        for field in ["image_caption", "image_alt"]
        if first_value(row, [field])
    )
    for source in [display_title, title, caption]:
        portrait_match = re.search(
            r"portr[aä]it\s+de[rs]\s+(?:[A-Za-zÄÖÜäöüß-]+\s+){0,4}([A-ZÄÖÜ][\wÄÖÜäöüßéÉèÈáÁàÀíÍóÓúÚçÇ.-]+(?:\s+[A-ZÄÖÜ][\wÄÖÜäöüßéÉèÈáÁàÀíÍóÓúÚçÇ.-]+){1,3})",
            source,
            flags=re.IGNORECASE,
        )
        if portrait_match:
            subject = plausible_subject(portrait_match.group(1))
            if subject:
                return subject
    title_match = title_subject(title)
    if title_match:
        return title_match
    for source in [
        source_description,
        first_value(row, ["description"]),
        first_value(row, ["seo_description"]),
        first_value(row, ["long_description"]),
    ]:
        subject = description_subject(source)
        if subject:
            return subject
    hebammen_match = re.search(
        r"Hebammen\s+([A-ZÄÖÜ][\wÄÖÜäöüßéÉèÈáÁàÀíÍóÓúÚçÇ.-]+)\s+und\s+([A-ZÄÖÜ][\wÄÖÜäöüßéÉèÈáÁàÀíÍóÓúÚçÇ.-]+)\s+und\s+deren\s+Schwester\s+([A-ZÄÖÜ][\wÄÖÜäöüßéÉèÈáÁàÀíÍóÓúÚçÇ.-]+)",
        caption,
    )
    if hebammen_match:
        return "; ".join(hebammen_match.groups())
    leading_name = re.match(
        r"^([A-ZÄÖÜ][\wÄÖÜäöüßéÉèÈáÁàÀíÍóÓúÚçÇ.-]+"
        r"(?:\s+[A-ZÄÖÜ][\wÄÖÜäöüßéÉèÈáÁàÀíÍóÓúÚçÇ.-]+){1,3})\s+[-–]\s+.*porträt",
        title,
        flags=re.IGNORECASE,
    )
    if leading_name:
        return plausible_subject(leading_name.group(1)) or "Subject not identified"
    if (
        str(getattr(row, "life_signal", "") or "") == "portrait"
        and re.match(r"^[A-ZÄÖÜ][\wÄÖÜäöüßéÉèÈáÁàÀíÍóÓúÚçÇ.-]+(?:\s+[A-ZÄÖÜ][\wÄÖÜäöüßéÉèÈáÁàÀíÍóÓúÚçÇ.-]+){0,3}$", title)
    ):
        return title
    patterns = [
        r"porträt des autors ([A-ZÄÖÜ][^.,;:]+)",
        r"porträt der autorin ([A-ZÄÖÜ][^.,;:]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, f"{title} {text}", flags=re.IGNORECASE)
        if match:
            subject = plausible_subject(match.group(1))
            if subject:
                return subject
    memory_match = re.search(r"([A-ZÄÖÜ][^.;:]+?)\s+erinnert sich", title)
    if memory_match:
        subject = plausible_subject(memory_match.group(1))
        if subject:
            return subject
    credit_subject = credit_subject_if_in_text(row, source_description)
    if credit_subject:
        return credit_subject
    if "lessing" in text:
        return "Gotthold Ephraim Lessing"
    return "Subject not identified"


def subject_role(row: object) -> str:
    text = row_text(row)
    role_patterns = [
        ("composer and radio-play maker", r"komponist[^.]{0,80}hörspielmacher|hörspielmacher[^.]{0,80}komponist"),
        ("composer", r"\bkomponist|komponistin|composer\b"),
        ("writer", r"\bautor|autorin|schriftsteller|schriftstellerin|dichter|dichterin|writer\b"),
        ("singer or musician", r"\bsänger|sängerin|musiker|musikerin|jazz|blues\b"),
        ("actor or performer", r"\bschauspieler|schauspielerin|darsteller|darstellerin|performer\b"),
        ("artist", r"\bkünstler|künstlerin|maler|malerin|bildhauer|bildhauerin|artist\b"),
        ("scholar or intellectual", r"\bphilosoph|philosophin|wissenschaftler|wissenschaftlerin|kritiker|kritikerin\b"),
    ]
    for role, pattern in role_patterns:
        if re.search(pattern, text, flags=re.IGNORECASE):
            return role
    return ""


def subject_description(row: object, subject: str, tags: list[str]) -> str:
    summary = source_summary(row)
    if summary:
        return summary
    description = first_value(row, ["description", "seo_description", "long_description"])
    life_signal = str(getattr(row, "life_signal", "") or "")
    role = subject_role(row)
    if subject and subject != "Subject not identified":
        if "diary/letters" in life_signal:
            base = f"This record is based on letters, diaries, writings, or other self-records connected to {subject}."
        elif "autobiography" in life_signal:
            base = f"This record adapts autobiographical material by or about {subject}."
        elif "biography" in life_signal:
            base = f"This record presents biographical material about {subject}."
        elif "portrait" in life_signal:
            base = f"This record is a radio portrait of {subject}."
        else:
            base = f"This record appears to focus on {subject}."
        if role:
            return f"{base} The metadata identifies the subject as a {role}."
        return base
    if "diary/letters" in life_signal:
        return "This record is included because the source metadata points to diary, letter, or self-record material, but the subject still needs manual identification."
    if description:
        return "The source description indicates a life-writing or portrait record, but the subject still needs manual identification."
    return "The source metadata is too sparse to identify the subject reliably; this record needs manual review."


def main() -> None:
    df = pd.read_csv(INPUT)
    excluded_urls = load_excluded_urls()
    if excluded_urls:
        df = df[~df["source_url"].astype(str).str.strip().isin(excluded_urls)].copy()
    subject_overrides = load_subject_overrides()
    source_descriptions = load_source_descriptions()

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
        override = subject_overrides.get(str(getattr(row, "source_url", "") or "").strip(), {})
        source_url = str(getattr(row, "source_url", "") or "").strip()
        source_description = source_descriptions.get(source_url, "")
        who_name = subject_name(row, source_description)
        if override.get("dedicated_to"):
            who_name = override["dedicated_to"]
        if override.get("life_focus"):
            who_about = [tag.strip() for tag in override["life_focus"].split(";") if tag.strip()]
        card_description = source_description or override.get("short_description") or subject_description(row, who_name, who_about)
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
                "author": production_credit(row, ["authors", "creator", "author"]),
                "director": production_credit(
                    row,
                    [
                        "directors",
                        "wir_regie",
                        "wir_realisation",
                        "wir_autor_und_regie",
                        "wir_funkeinrichtung_und_regie",
                    ],
                ),
                "description": card_description,
                "subjectDescription": card_description,
                "url": source_url,
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
