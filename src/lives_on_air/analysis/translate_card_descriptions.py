from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from html import unescape
from pathlib import Path
from urllib.parse import quote_plus

import pandas as pd

from lives_on_air.config import PROJECT_ROOT


INPUT = PROJECT_ROOT / "data" / "curation" / "source_card_descriptions.csv"
TRANSLATION_CACHE = PROJECT_ROOT / "data" / "interim" / "source_card_translations"
CURL_CONFIG = PROJECT_ROOT / "data" / "interim" / "source_card_translations.curl"


def clean_text(value: object) -> str:
    text = unescape(str(value or ""))
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\s+([.,;:!?])", r"\1", text)
    return text


def cache_path(source_url: str, text: str) -> Path:
    digest = hashlib.sha1(f"{source_url}\n{text}".encode("utf-8")).hexdigest()
    return TRANSLATION_CACHE / f"{digest}.json"


def write_curl_config() -> None:
    df = pd.read_csv(INPUT).fillna("")
    TRANSLATION_CACHE.mkdir(parents=True, exist_ok=True)
    lines = [
        "location",
        "fail",
        "silent",
        "show-error",
        "retry = 2",
        "connect-timeout = 20",
        "max-time = 60",
        'user-agent = "Mozilla/5.0 radio-life-writing-translation-curation"',
    ]
    pending = 0
    for row in df.itertuples():
        text = clean_text(getattr(row, "short_description", ""))
        source_url = clean_text(getattr(row, "source_url", ""))
        path = cache_path(source_url, text)
        if not text or path.exists():
            continue
        url = (
            "https://translate.googleapis.com/translate_a/single"
            f"?client=gtx&sl=auto&tl=en&dt=t&q={quote_plus(text)}"
        )
        lines.extend([f'url = "{url}"', f'output = "{path}"'])
        pending += 1
    CURL_CONFIG.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote curl config with {pending} pending translations to {CURL_CONFIG}")


def read_translation(path: Path) -> str:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ""
    if not isinstance(payload, list) or not payload:
        return ""
    chunks = payload[0]
    if not isinstance(chunks, list):
        return ""
    translated = "".join(
        str(chunk[0])
        for chunk in chunks
        if isinstance(chunk, list) and chunk and chunk[0]
    )
    return polish_english(translated)


def polish_english(text: str) -> str:
    text = clean_text(text)
    replacements = {
        "radio play": "radio work",
        "radio drama": "radio work",
        "radio game": "radio work",
        "radio workmaker": "radio-work maker",
        "Hörspiel": "radio work",
        "Feature": "feature",
        "Original radio work": "Original radio work",
        "Original hearing game": "Original radio work",
        "editing (word)": "text adaptation",
        "Template:": "Based on:",
        "Direction:": "Direction:",
        "Technical realization:": "Technical production:",
        "black slaves": "enslaved Africans",
        "they dragged out gold": "they extracted gold",
        "G.M. Gilbert access": "G.M. Gilbert had access",
        "doctor of biotechnologist": "biotechnologist",
        "the “Ritterspelunke”": "the “Ritterspelunke” venue",
    }
    for source, target in replacements.items():
        text = re.sub(re.escape(source), target, text, flags=re.IGNORECASE)
    credit_summary = source_credit_summary(text)
    if credit_summary:
        return credit_summary
    text = re.sub(r"^Further information\s+", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\btext adaptation:", "Text adaptation:", text)
    text = re.sub(r"\bcomposition:", "Composition:", text)
    text = re.sub(r"\bassistant director:", "Assistant director:", text)
    text = re.sub(r"\s+-\s+", " - ", text)
    text = re.sub(r"\s+([.,;:!?])", r"\1", text)
    text = text.replace(" ,", ",")
    if text and text[-1] not in ".!?…":
        text += "."
    if text:
        text = text[0].upper() + text[1:]
    return text


def source_credit_summary(text: str) -> str:
    if not re.match(r"^(Original|Based on):\s+", text):
        return ""
    work = re.sub(r"^(Original|Based on):\s+", "", text)
    work = re.split(
        r"\s+(Translation|Text adaptation|Composition|Dramaturgy|Technical production|Assistant director):\s+",
        work,
        maxsplit=1,
    )[0]
    work = clean_text(work).rstrip(".")
    if not work:
        return ""
    return f"A radio work based on {work}."


def apply_translations() -> None:
    df = pd.read_csv(INPUT).fillna("")
    english: list[str] = []
    missing = 0
    for row in df.itertuples():
        text = clean_text(getattr(row, "short_description", ""))
        source_url = clean_text(getattr(row, "source_url", ""))
        translated = read_translation(cache_path(source_url, text))
        if not translated:
            translated = polish_english(text)
            missing += 1
        english.append(translated)
    df["english_description"] = english
    df.to_csv(INPUT, index=False, quoting=csv.QUOTE_MINIMAL)
    print(f"Updated {INPUT} with {len(df)} English descriptions ({missing} uncached fallbacks)")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write-curl-config", action="store_true")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    if args.write_curl_config:
        write_curl_config()
    if args.apply:
        apply_translations()
    if not args.write_curl_config and not args.apply:
        parser.error("Choose --write-curl-config, --apply, or both.")


if __name__ == "__main__":
    main()
