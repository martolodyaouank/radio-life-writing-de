from __future__ import annotations

import json
from collections import deque

import pandas as pd
import requests

from lives_on_air.classification.biographical import biographical_label, biographical_score
from lives_on_air.config import BBC_RAW_DIR, PROJECT_ROOT, REQUEST_HEADERS, REQUEST_TIMEOUT_SECONDS
from lives_on_air.parsers.bbc_programmes import parse_bbc_programmes_json


BBC_PROGRAMMES_URL = "https://www.bbc.co.uk/programmes/{pid}.json"
BBC_EPISODES_FILTERS_URL = "https://www.bbc.co.uk/programmes/{pid}/episodes.json"
BBC_EPISODES_MONTH_URL = "https://www.bbc.co.uk/programmes/{pid}/episodes/{year}/{month}.json"


def fetch_bbc_programme_json(pid: str) -> dict:
    url = BBC_PROGRAMMES_URL.format(pid=pid)
    cache_path = BBC_RAW_DIR / f"bbc_programmes_{pid}.json"
    if cache_path.exists():
        return json.loads(cache_path.read_text(encoding="utf-8"))

    response = requests.get(url, headers=REQUEST_HEADERS, timeout=REQUEST_TIMEOUT_SECONDS)
    response.raise_for_status()
    payload = response.json()
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def _fetch_json_url(url: str, cache_name: str) -> dict:
    cache_path = BBC_RAW_DIR / cache_name
    if cache_path.exists():
        return json.loads(cache_path.read_text(encoding="utf-8"))

    response = requests.get(url, headers=REQUEST_HEADERS, timeout=REQUEST_TIMEOUT_SECONDS)
    response.raise_for_status()
    if not response.headers.get("content-type", "").startswith("application/json"):
        raise RuntimeError(f"Expected JSON from {url}, got {response.headers.get('content-type')}")
    payload = response.json()
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def episode_pids_for_container(pid: str) -> list[str]:
    filters = _fetch_json_url(
        BBC_EPISODES_FILTERS_URL.format(pid=pid),
        f"bbc_programmes_{pid}_episodes_filters.json",
    )
    pids: list[str] = []
    seen: set[str] = set()
    for year in filters.get("filters", {}).get("years", []):
        year_id = year.get("id")
        for month in year.get("months", []):
            month_id = month.get("id")
            url = BBC_EPISODES_MONTH_URL.format(pid=pid, year=year_id, month=str(month_id).zfill(2))
            payload = _fetch_json_url(
                url,
                f"bbc_programmes_{pid}_episodes_{year_id}_{str(month_id).zfill(2)}.json",
            )
            for broadcast in payload.get("broadcasts", []):
                programme = broadcast.get("programme") or {}
                episode_pid = programme.get("pid")
                if episode_pid and episode_pid not in seen:
                    seen.add(episode_pid)
                    pids.append(episode_pid)
    return pids


def expand_seed_pids(seed_pids: list[str]) -> list[str]:
    discovered: set[str] = set(seed_pids)
    queue = deque(seed_pids)
    while queue:
        pid = queue.popleft()
        try:
            payload = fetch_bbc_programme_json(pid)
        except Exception:
            continue

        programme = payload.get("programme", {})
        for peer_key in ["previous", "next"]:
            peer = (programme.get("peers") or {}).get(peer_key) or {}
            peer_pid = peer.get("pid")
            if peer_pid and peer_pid not in discovered:
                discovered.add(peer_pid)
                queue.append(peer_pid)

        for parentish in [
            (programme.get("parent") or {}).get("programme") or {},
            ((programme.get("parent") or {}).get("programme") or {}).get("parent", {}).get("programme") or {},
        ]:
            parent_pid = parentish.get("pid")
            if parent_pid:
                try:
                    for episode_pid in episode_pids_for_container(parent_pid):
                        if episode_pid not in discovered:
                            discovered.add(episode_pid)
                            queue.append(episode_pid)
                except Exception:
                    pass
    return sorted(discovered)


def collect_bbc_programmes_sample(pids: list[str] | None = None, expand: bool = True) -> pd.DataFrame:
    if pids is None:
        pids = ["b01qhqgf", "b007ncns"]
    if expand:
        pids = expand_seed_pids(pids)

    records = []
    for pid in pids:
        url = BBC_PROGRAMMES_URL.format(pid=pid)
        record = parse_bbc_programmes_json(fetch_bbc_programme_json(pid), url)
        searchable_text = " ".join(
            [
                record.get("display_title", ""),
                record.get("category_titles", ""),
                record.get("short_synopsis", ""),
                record.get("medium_synopsis", ""),
                record.get("long_synopsis", ""),
            ]
        )
        record["biographical_score"] = biographical_score(searchable_text)
        record["biographical_label"] = biographical_label(searchable_text)
        records.append(record)

    df = pd.DataFrame(records)
    output_path = PROJECT_ROOT / "data" / "interim" / "bbc_programmes_sample.csv"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)
    return df


if __name__ == "__main__":
    sample = collect_bbc_programmes_sample()
    columns = [
        "pid",
        "display_title",
        "first_broadcast_date",
        "broadcaster",
        "category_titles",
        "biographical_label",
        "source_url",
    ]
    print(sample[[column for column in columns if column in sample.columns]].to_string(index=False))
