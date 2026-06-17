from __future__ import annotations

import json
import math
import re
from html import escape

import pandas as pd

from lives_on_air.config import PROJECT_ROOT


INPUT = PROJECT_ROOT / "data" / "processed" / "analysis_tables" / "core_semantic_enriched.csv"
OUTPUT = PROJECT_ROOT / "article" / "semantic-map-3d-data.js"
EXCLUSIONS = PROJECT_ROOT / "data" / "curation" / "life_writing_exclusions.csv"
SUBJECT_OVERRIDES = PROJECT_ROOT / "data" / "curation" / "life_subject_overrides.csv"
SOURCE_DESCRIPTIONS = PROJECT_ROOT / "data" / "curation" / "source_card_descriptions.csv"
PROTAGONIST_AUDIT = PROJECT_ROOT / "data" / "curation" / "semantic_map_protagonist_audit.csv"
PROTAGONIST_AUDIT_HTML = PROJECT_ROOT / "article" / "protagonist-audit.html"


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
    if any(fragment in text.casefold() for fragment in [" archiv", " hörspiel", " krimi", " doku", " feature", " podcast", "?", " idee"]):
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
    "ends up|portrays|portrayed|enters|comes|faces|reflects|keeps|retreats|"
    "appears|explains|reports"
)

PERSON_NAME = r"[A-ZÄÖÜ][\wÄÖÜäöüßéÉèÈáÁàÀíÍóÓúÚçÇ.-]+(?:\s+(?:v\.|von|van|de|del|der|den|du|da|di|la|le|[A-ZÄÖÜ][\wÄÖÜäöüßéÉèÈáÁàÀíÍóÓúÚçÇ.-]+)){1,4}"
PERSON_OR_SURNAME = rf"(?:{PERSON_NAME}|[A-ZÄÖÜ][\wÄÖÜäöüßéÉèÈáÁàÀíÍóÓúÚçÇ.-]{{3,}})"
ROLE_WORDS = (
    "author|writer|poet|playwright|critic|composer|musician|singer|painter|"
    "pianist|conductor|director|performer|artist|president|filmmaker|"
    "actor|actress|philosopher|scholar|student|emigrant|"
    "Autor|Autorin|Schriftsteller|Schriftstellerin|Dichter|Dichterin|"
    "Komponist|Komponistin|Musiker|Musikerin|Sänger|Sängerin|Maler|Malerin|"
    "Künstler|Künstlerin|Schauspieler|Schauspielerin|Regisseur|Regisseurin|"
    "Philosoph|Philosophin|Student|Studentin|Emigrant|Emigrantin|Dramatiker|"
    "Dramatikerin|Kritiker|Kritikerin|Präsident|Präsidentin|Filmemacher|"
    "Filmemacherin"
)
ROLE_CHAIN = rf"(?:{ROLE_WORDS})(?:(?:,\s*|\s+and\s+|\s+und\s+)(?:{ROLE_WORDS}))*"
ROLE_PHRASE = rf"(?:(?:[A-Za-zÄÖÜäöüß-]+\s+){{0,4}}{ROLE_CHAIN}\s+)?"
ROLE_PHRASE_REQUIRED = rf"(?:[A-Za-zÄÖÜäöüß-]+\s+){{0,4}}{ROLE_CHAIN}\s+"


def clean_subject_candidate(value: str) -> str:
    candidate = re.sub(
        rf"\s+(?:{SUBJECT_VERBS_DE}|{SUBJECT_VERBS_EN})\b.*$",
        "",
        value,
        flags=re.IGNORECASE,
    )
    candidate = re.sub(r"\s+who\b.*$", "", candidate, flags=re.IGNORECASE)
    if not re.match(r"^(Ein|Eine|Einen|Einem|Einer|A|An|The)\b", candidate):
        candidate = re.sub(r"\s+(?:die|der|das)\b.*$", "", candidate, flags=re.IGNORECASE)
    candidate = re.sub(r"\s+(?:up to|bis zu|until|bis)\b.*$", "", candidate, flags=re.IGNORECASE)
    if (
        not re.match(r"^(Ein|Eine|Einen|Einem|Einer|A|An|The)\b", candidate)
        and (re.match(PERSON_NAME + r"$", candidate.split(" from ", 1)[0]) or re.match(PERSON_NAME + r"$", candidate.split(" aus ", 1)[0]))
    ):
        candidate = re.split(r"\s+(?:from|aus)\b", candidate, maxsplit=1, flags=re.IGNORECASE)[0]
    candidate = re.sub(r"\s*\([^)]*\).*$", "", candidate)
    return re.sub(r"\s+", " ", candidate).strip()


def description_subject(value: str) -> str:
    decision = description_subject_decision(value)
    return decision["protagonist"]


def description_subject_decision(value: str) -> dict[str, str]:
    text = clean_summary_text(value)
    if not text:
        return {"protagonist": "", "evidence": "", "method": "", "confidence": ""}
    first_sentence = re.split(r"(?<=[.!?])\s+", text, maxsplit=1)[0].strip()
    patterns = [
        (rf"\b(?:letters?|Briefe?)\b[^.;:!?]{{0,180}}\b(?:that|die|der)\s+(?:the\s+|der\s+|die\s+)?{ROLE_PHRASE}({PERSON_NAME})\b[^.;:!?]{{0,160}}\b(?:wrote|written|geschrieben|verfasst)", re.IGNORECASE, "letters written by named subject", "high"),
        (r"^(?:Die|The)\s+Geschichte\s+von\s+([^.;:!?]{3,90})", re.IGNORECASE, "story-of phrase", "high"),
        (rf"^(?:Als|When)\s+({PERSON_NAME})\b", 0, "opening when-clause names subject", "high"),
        (rf"^({PERSON_NAME}),\s+(?:alias|geb\.|geboren|born|once|who|die|der)\b", 0, "opening biographical apposition", "high"),
        (rf"^({PERSON_NAME})\s+(?:war|was|ist|is|has|hat|prägt|praegt|taucht|shapes|shaped)\b", 0, "opening named biographical sentence", "high"),
        (rf"^(?:The|the|Der|der|Die|die|Das|das)\s+{ROLE_CHAIN}\s+({PERSON_NAME})\b", 0, "role phrase names subject", "high"),
        (r"^(?:The life of|Das Leben des|Das Leben der)\s+([^.;:!?]{3,90})", re.IGNORECASE, "life-of phrase", "high"),
        (rf"\b(?:Porträt|porträt|Portrait|portrait)\s+(?:des|der|of)\s+(?:the\s+)?(?:{ROLE_PHRASE})?({PERSON_NAME}|[^.;:!?]{{3,90}})", 0, "portrait phrase", "high"),
        (r"\b(?:über|ueber|about)\s+([^.;:!?]{3,90})", re.IGNORECASE, "about phrase", "medium"),
        (r"\b(?:focuses on|follows|porträtiert|portraitiert)\s+([^.;:!?]{3,90})", re.IGNORECASE, "focus/follows phrase", "medium"),
        (rf"\b{ROLE_PHRASE_REQUIRED}({PERSON_NAME})\b", 0, "role/name phrase in description", "medium"),
        (rf"\b(?:text|texts|fragment|novel|letters|poems|diaries|writings|Briefen|Briefe|Tagebücher|Gedichte|Texte|Roman)\s+(?:by|from|von|nach|of)\s+({PERSON_NAME})\b", re.IGNORECASE, "source-material by named subject", "medium"),
        (rf"^((?:Ein|Eine|Einen|Einem|Einer)\s+[^.;:!?]{{3,90}}?)\s+(?:{SUBJECT_VERBS_DE})\b", re.IGNORECASE, "generic protagonist phrase", "medium"),
        (rf"^((?:A|An)\s+[^.;:!?]{{3,90}}?)\s+(?:{SUBJECT_VERBS_EN})\b", re.IGNORECASE, "generic protagonist phrase", "medium"),
    ]
    for pattern, flags, method, confidence in patterns:
        match = re.search(pattern, first_sentence, flags=flags)
        if not match:
            continue
        candidate = clean_subject_candidate(match.group(1))
        subject = plausible_subject(candidate, allow_article=True)
        if subject:
            return {
                "protagonist": subject,
                "evidence": first_sentence,
                "method": method,
                "confidence": confidence,
            }
    return {"protagonist": "", "evidence": "", "method": "", "confidence": ""}


def compact_title_subject(value: str) -> str:
    title = re.sub(r"\([^)]*\)", "", str(value or ""))
    title = re.sub(r"\s*[-–:]\s*(?:Ein|Eine|A|An|The|Der|Die|Das)\s+", " - ", title, flags=re.IGNORECASE)
    title = re.sub(r"\s+", " ", title).strip(" \"'.,;:-–")
    return title[:70].strip() if title else ""


def first_named_person(value: str, allow_surname: bool = False) -> str:
    pattern = PERSON_OR_SURNAME if allow_surname else PERSON_NAME
    blocked = {
        "Art Review",
        "East Berlin",
        "New York",
        "West Berlin",
        "Radio Bremen",
        "German Film",
        "Czech President",
    }
    blocked_leads = {
        "A",
        "An",
        "As",
        "At",
        "Der",
        "Die",
        "Das",
        "For",
        "From",
        "In",
        "On",
        "The",
        "When",
    }
    blocked_genres = {"Feature", "Hörspiel", "Radio", "Podcast"}
    for match in re.finditer(pattern, value):
        candidate = clean_subject_candidate(match.group(0))
        candidate = re.sub(r"^(The|Der|Die|Das)\s+", "", candidate, flags=re.IGNORECASE)
        parts = candidate.split()
        if parts and (parts[0] in blocked_leads or parts[0] in blocked_genres):
            continue
        if parts and parts[-1].casefold() in {"de", "der", "des", "of", "the", "von", "v"}:
            continue
        if candidate in blocked:
            continue
        if plausible_subject(candidate):
            return candidate
    return ""


def curated_description_subject(row: object, source_description: str = "") -> dict[str, str]:
    title = str(getattr(row, "title", "") or "")
    description_sources = [
        source_description,
        first_value(row, ["description"]),
        first_value(row, ["seo_description"]),
        first_value(row, ["long_description"]),
    ]
    description = clean_summary_text(next((source for source in description_sources if source), ""))
    first_sentence = re.split(r"(?<=[.!?])\s+", description, maxsplit=1)[0].strip()
    text = description or " ".join(source for source in description_sources if source)
    author_credit = clean_person_list(first_value(row, ["authors", "creator", "author"]))

    normalized_title = title.casefold()
    title_overrides = {
        "das porträt": "A man visiting Alberto Giacometti",
        "das schlechteste hörspiel der welt oder eine biographie über niemand": "Nobody",
        "die policey": "The police",
        "seine rolle finden": "David Hirsch / David Hurst",
        "der todestrieb": "Jacques Mesrine",
        "tagebuch einer liebe oder jetzt erzählen wir uns eine geschichte, in der jetzt immerzu jetzt bleibt": "Veronika and Jens",
        "eingraviert": "Christin and the tattoo studio clients",
        "feature": "Feature authors and documentary makers",
        "ausgrabung einer utopie": "The Free Republic of Wendland",
    }
    if normalized_title in title_overrides:
        return {
            "protagonist": title_overrides[normalized_title],
            "evidence": first_sentence or title,
            "method": "curated title override",
            "confidence": "medium",
        }

    curated_patterns = [
        (r"\bDiary of\s+([^.;:!?]{3,80})", "diary-of phrase"),
        (r"\bmain character[^.]{0,120}\b(?:called|named)\s+([^.;:!?]{3,80})", "main-character naming"),
        (r"\bworker\s+(" + PERSON_OR_SURNAME + r")\b", "worker/name phrase"),
        (r"\b(?:letters?|Briefe?)\b[^.;:!?]{0,180}\b(?:artist|poet|writer|composer|painter|author|filmmaker|playwright|critic|director)\s+(" + PERSON_OR_SURNAME + r")\b[^.;:!?]{0,160}\bwrote\b", "letter writer"),
        (r"\b(?:artist|poet|writer|composer|painter|author|filmmaker|playwright|critic|director)\s+(" + PERSON_OR_SURNAME + r")\b", "role/name phrase"),
        (r"\bIt is well known that\s+(" + PERSON_OR_SURNAME + r")\b", "known-that phrase"),
        (r"\b(?:anniversary of|anniversary of .*?death of|Todestag des Hörspielautors)\s+(" + PERSON_NAME + r")\b", "anniversary phrase"),
        (r"\b(" + PERSON_OR_SURNAME + r")\s+(?:faces|comes|reflects|keeps|retreats|appears|explains|reports|is|was|has|had|wrote|writes)\b", "named subject action"),
    ]
    for pattern, method in curated_patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if not match:
            continue
        candidate = clean_subject_candidate(match.group(1))
        if candidate == "Johann Wolfgang v":
            candidate = "Johann Wolfgang v. Goethe"
        subject = plausible_subject(candidate, allow_article=True)
        if subject:
            return {
                "protagonist": subject,
                "evidence": first_sentence or text[:220],
                "method": method,
                "confidence": "medium",
            }

    generic_patterns = [
        (rf"^((?:A|An|The)\s+[^.;:!?]{{3,90}}?)\s+(?:{SUBJECT_VERBS_EN})\b", "opening role phrase"),
        (rf"^((?:Ein|Eine|Einen|Einem|Einer|Der|Die|Das)\s+[^.;:!?]{{3,90}}?)\s+(?:{SUBJECT_VERBS_DE})\b", "opening role phrase"),
        (r"\babout\s+((?:a|an|the)\s+[^.;:!?]{3,80})", "about role phrase"),
    ]
    for pattern, method in generic_patterns:
        match = re.search(pattern, first_sentence, flags=re.IGNORECASE)
        if not match:
            continue
        candidate = clean_subject_candidate(match.group(1))
        subject = plausible_subject(candidate, allow_article=True)
        if subject:
            return {
                "protagonist": subject,
                "evidence": first_sentence,
                "method": method,
                "confidence": "medium",
            }

    if first_sentence:
        named = first_named_person(first_sentence, allow_surname=True)
        if named:
            return {
                "protagonist": named,
                "evidence": first_sentence,
                "method": "first named figure in description",
                "confidence": "medium",
            }

    if author_credit and re.search(
        r"\b(the|der|die|das)\s+(?:czech\s+)?(?:poet|president|author|writer|composer|artist|painter|filmmaker|director|playwright|critic)\b",
        text,
        flags=re.IGNORECASE,
    ):
        subject = author_credit.split(";")[0].strip()
        if plausible_subject(subject):
            return {
                "protagonist": subject,
                "evidence": first_sentence or text[:220],
                "method": "role description confirms author subject",
                "confidence": "medium",
            }

    title_subject_guess = title_subject(title) or first_named_person(title, allow_surname=True) or compact_title_subject(title)
    if title_subject_guess:
        return {
            "protagonist": title_subject_guess,
            "evidence": first_sentence or title,
            "method": "curated title fallback",
            "confidence": "low",
        }

    return {
        "protagonist": "The central figure of the radio play",
        "evidence": first_sentence or text[:220],
        "method": "generic curated fallback",
        "confidence": "low",
    }


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


def subject_decision(row: object, source_description: str = "") -> dict[str, str]:
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
                return {
                    "protagonist": subject,
                    "evidence": source,
                    "method": "title/caption portrait phrase",
                    "confidence": "high",
                }
    title_match = title_subject(title)
    if title_match:
        return {
            "protagonist": title_match,
            "evidence": title,
            "method": "title names subject",
            "confidence": "high",
        }
    for source in [
        source_description,
        first_value(row, ["description"]),
        first_value(row, ["seo_description"]),
        first_value(row, ["long_description"]),
    ]:
        decision = description_subject_decision(source)
        if decision["protagonist"]:
            return decision
    hebammen_match = re.search(
        r"Hebammen\s+([A-ZÄÖÜ][\wÄÖÜäöüßéÉèÈáÁàÀíÍóÓúÚçÇ.-]+)\s+und\s+([A-ZÄÖÜ][\wÄÖÜäöüßéÉèÈáÁàÀíÍóÓúÚçÇ.-]+)\s+und\s+deren\s+Schwester\s+([A-ZÄÖÜ][\wÄÖÜäöüßéÉèÈáÁàÀíÍóÓúÚçÇ.-]+)",
        caption,
    )
    if hebammen_match:
        return {
            "protagonist": "; ".join(hebammen_match.groups()),
            "evidence": caption,
            "method": "caption family-name pattern",
            "confidence": "high",
        }
    leading_name = re.match(
        r"^([A-ZÄÖÜ][\wÄÖÜäöüßéÉèÈáÁàÀíÍóÓúÚçÇ.-]+"
        r"(?:\s+[A-ZÄÖÜ][\wÄÖÜäöüßéÉèÈáÁàÀíÍóÓúÚçÇ.-]+){1,3})\s+[-–]\s+.*porträt",
        title,
        flags=re.IGNORECASE,
    )
    if leading_name:
        subject = plausible_subject(leading_name.group(1))
        if subject:
            return {
                "protagonist": subject,
                "evidence": title,
                "method": "leading name in title",
                "confidence": "high",
            }
    if (
        str(getattr(row, "life_signal", "") or "") == "portrait"
        and re.match(r"^[A-ZÄÖÜ][\wÄÖÜäöüßéÉèÈáÁàÀíÍóÓúÚçÇ.-]+(?:\s+[A-ZÄÖÜ][\wÄÖÜäöüßéÉèÈáÁàÀíÍóÓúÚçÇ.-]+){0,3}$", title)
    ):
        return {
            "protagonist": title,
            "evidence": title,
            "method": "portrait title is name",
            "confidence": "high",
        }
    patterns = [
        r"porträt des autors ([A-ZÄÖÜ][^.,;:]+)",
        r"porträt der autorin ([A-ZÄÖÜ][^.,;:]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, f"{title} {text}", flags=re.IGNORECASE)
        if match:
            subject = plausible_subject(match.group(1))
            if subject:
                return {
                    "protagonist": subject,
                    "evidence": f"{title} {text}",
                    "method": "portrait-of-author phrase",
                    "confidence": "high",
                }
    memory_match = re.search(r"([A-ZÄÖÜ][^.;:]+?)\s+erinnert sich", title)
    if memory_match:
        subject = plausible_subject(memory_match.group(1))
        if subject:
            return {
                "protagonist": subject,
                "evidence": title,
                "method": "memory title pattern",
                "confidence": "medium",
            }
    if "lessing" in text:
        return {
            "protagonist": "Gotthold Ephraim Lessing",
            "evidence": text,
            "method": "explicit Lessing keyword fallback",
            "confidence": "medium",
        }
    return curated_description_subject(row, source_description)


def subject_name(row: object, source_description: str = "") -> str:
    return subject_decision(row, source_description)["protagonist"]


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


def write_protagonist_audit(rows: list[dict[str, object]]) -> None:
    audit = pd.DataFrame(rows)
    PROTAGONIST_AUDIT.parent.mkdir(parents=True, exist_ok=True)
    audit.to_csv(PROTAGONIST_AUDIT, index=False)

    high = int((audit["confidence"] == "high").sum())
    medium = int((audit["confidence"] == "medium").sum())
    low = int((audit["confidence"] == "low").sum())
    table_rows = []
    for row in audit.itertuples():
        confidence = escape(str(row.confidence))
        url = escape(str(row.source_url))
        source_link = f'<a href="{url}" target="_blank" rel="noopener noreferrer">source</a>' if url.startswith("http") else ""
        table_rows.append(
            "<tr>"
            f'<td class="num">{row.Index + 1}</td>'
            f"<td>{escape(str(row.title))}</td>"
            f"<td>{escape(str(row.year))}</td>"
            f"<td>{escape(str(row.source))}</td>"
            f"<td><strong>{escape(str(row.protagonist))}</strong></td>"
            f"<td>{escape(str(row.author))}</td>"
            f'<td><span class="badge {confidence}">{confidence}</span></td>'
            f"<td>{escape(str(row.method))}</td>"
            f"<td>{escape(str(row.evidence))}</td>"
            f"<td>{source_link}</td>"
            "</tr>"
        )
    html = f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Protagonist Audit | Lives on Air</title>
    <style>
      body {{ margin: 0; font: 14px/1.45 system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; color: #20252b; background: #f6f7f8; }}
      header {{ position: sticky; top: 0; z-index: 2; padding: 18px 22px; background: #fff; border-bottom: 1px solid #d8dee4; }}
      h1 {{ margin: 0 0 6px; font-size: 22px; }}
      p {{ margin: 0; max-width: 980px; color: #59636e; }}
      main {{ padding: 18px 22px 40px; }}
      .summary {{ display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 14px; }}
      .summary span {{ background: #fff; border: 1px solid #d8dee4; padding: 7px 10px; border-radius: 6px; }}
      table {{ width: 100%; border-collapse: collapse; background: #fff; box-shadow: 0 1px 2px rgba(0,0,0,.05); }}
      th, td {{ border-bottom: 1px solid #e5e9ef; padding: 8px 9px; vertical-align: top; text-align: left; }}
      th {{ position: sticky; top: 84px; z-index: 1; background: #eef2f5; font-size: 12px; text-transform: uppercase; letter-spacing: .02em; }}
      td:nth-child(2) {{ min-width: 220px; }}
      td:nth-child(5) {{ min-width: 160px; }}
      td:nth-child(9) {{ min-width: 360px; max-width: 620px; }}
      .num {{ color: #6b737c; text-align: right; }}
      .badge {{ display: inline-block; min-width: 54px; padding: 2px 7px; border-radius: 999px; text-align: center; font-size: 12px; }}
      .high {{ background: #daf5df; color: #175c28; }}
      .medium {{ background: #fff0bf; color: #714d00; }}
      .low {{ background: #ffd8d2; color: #8a1f11; }}
      a {{ color: #1f6feb; }}
    </style>
  </head>
  <body>
    <header>
      <h1>Semantic Map Protagonist Audit</h1>
      <p>Each row shows the protagonist displayed in the map, the evidence sentence used to derive it, and the extraction method/confidence. Low-confidence rows should be manually reviewed rather than trusted as settled.</p>
    </header>
    <main>
      <div class="summary">
        <span><strong>{len(audit)}</strong> entries</span>
        <span><strong>{high}</strong> high confidence</span>
        <span><strong>{medium}</strong> medium confidence</span>
        <span><strong>{low}</strong> needs review</span>
      </div>
      <table>
        <thead>
          <tr><th>#</th><th>Title</th><th>Year</th><th>Source</th><th>Protagonist</th><th>Author/Credit</th><th>Confidence</th><th>Method</th><th>Evidence</th><th>Link</th></tr>
        </thead>
        <tbody>
          {''.join(table_rows)}
        </tbody>
      </table>
    </main>
  </body>
</html>
"""
    PROTAGONIST_AUDIT_HTML.write_text(html, encoding="utf-8")


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
    audit_rows = []
    for row in df.itertuples():
        year = safe_float(getattr(row, "analysis_year", None), median_year)
        z = ((year - year_min) / year_span - 0.5) * 46
        cluster = str(getattr(row, "cluster_label", "unknown"))
        signals = [
            label
            for label, column in SIGNAL_COLUMNS.items()
            if safe_float(getattr(row, column, 0), 0) > 0
        ]
        override = subject_overrides.get(str(getattr(row, "source_url", "") or "").strip(), {})
        source_url = str(getattr(row, "source_url", "") or "").strip()
        source_description = source_descriptions.get(source_url, "")
        who_about = subject_tags(row)
        protagonist = subject_decision(row, source_description)
        who_name = protagonist["protagonist"]
        if override.get("dedicated_to") and override["dedicated_to"] != "Subject not identified":
            who_name = override["dedicated_to"]
            protagonist = {
                "protagonist": who_name,
                "evidence": override.get("short_description") or source_description,
                "method": "manual override",
                "confidence": "high",
            }
        if override.get("life_focus"):
            who_about = [tag.strip() for tag in override["life_focus"].split(";") if tag.strip()]
        card_description = source_description or override.get("short_description") or subject_description(row, who_name, who_about)
        author_credit = production_credit(row, ["authors", "creator", "author"])
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
                "protagonist": who_name,
                "author": author_credit,
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
        audit_rows.append(
            {
                "source_url": source_url,
                "title": str(getattr(row, "title", "") or "Untitled"),
                "year": int(year) if math.isfinite(year) else "",
                "source": str(getattr(row, "source_label", "") or ""),
                "protagonist": who_name,
                "author": author_credit,
                "confidence": protagonist["confidence"],
                "method": protagonist["method"],
                "evidence": protagonist["evidence"],
                "description": card_description,
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
    write_protagonist_audit(audit_rows)
    print(f"Wrote {len(records)} records to {OUTPUT}")
    print(f"Wrote protagonist audit to {PROTAGONIST_AUDIT}")
    print(f"Wrote protagonist audit HTML to {PROTAGONIST_AUDIT_HTML}")


if __name__ == "__main__":
    main()
