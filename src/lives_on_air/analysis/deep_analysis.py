from __future__ import annotations

import json
import re
import textwrap
from collections import Counter

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from sklearn.cluster import KMeans
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.manifold import TSNE
from sklearn.metrics import pairwise_distances
from sklearn.preprocessing import normalize

from lives_on_air.config import PROJECT_ROOT


INPUT = PROJECT_ROOT / "data" / "processed" / "german_radio_biographical_candidates.csv"
OUTPUT_DIR = PROJECT_ROOT / "article" / "figures"
TABLE_DIR = PROJECT_ROOT / "data" / "processed" / "analysis_tables"

SOURCE_LABELS = {
    "dra": "DRA",
    "hoerspielundfeature": "DLF/DLF Kultur",
    "wirklichkeit_im_radio": "Wirklichkeit",
}

PALETTE = {
    "ink": "#1f2328",
    "muted": "#687078",
    "line": "#d8dde3",
    "paper": "#ffffff",
    "bg": "#f7f7f4",
    "high": "#254f4a",
    "medium": "#7aa184",
    "review": "#c4c8ce",
    "accent1": "#2d6a75",
    "accent2": "#a15c38",
    "accent3": "#6f5b8f",
    "accent4": "#c29a45",
    "accent5": "#4f6f52",
    "accent6": "#8a4f63",
    "accent7": "#65717d",
}

CLUSTER_COLORS = [
    PALETTE["accent1"],
    PALETTE["accent2"],
    PALETTE["accent3"],
    PALETTE["accent4"],
    PALETTE["accent5"],
    PALETTE["accent6"],
    PALETTE["accent7"],
]

GERMAN_STOPWORDS = {
    "aber",
    "alle",
    "allem",
    "allen",
    "aller",
    "als",
    "also",
    "am",
    "an",
    "andere",
    "auch",
    "auf",
    "aus",
    "bei",
    "beim",
    "bin",
    "bis",
    "bist",
    "da",
    "damit",
    "dann",
    "das",
    "dass",
    "dem",
    "den",
    "der",
    "des",
    "deutschlandfunk",
    "die",
    "dies",
    "diese",
    "diesem",
    "diesen",
    "dieser",
    "doch",
    "durch",
    "ein",
    "eine",
    "einem",
    "einen",
    "einer",
    "eines",
    "er",
    "es",
    "feature",
    "fuer",
    "fur",
    "für",
    "hat",
    "heute",
    "hier",
    "hoerspiel",
    "hörspiel",
    "horspiel",
    "ich",
    "im",
    "in",
    "ist",
    "ja",
    "kann",
    "kein",
    "keine",
    "mit",
    "nach",
    "nicht",
    "noch",
    "oder",
    "sich",
    "sie",
    "sind",
    "so",
    "ueber",
    "uber",
    "über",
    "und",
    "uns",
    "von",
    "vom",
    "vor",
    "war",
    "was",
    "wenn",
    "wer",
    "wie",
    "wird",
    "wir",
    "zu",
    "zum",
    "zur",
    "anzeigen",
    "app",
    "apple",
    "assistenz",
    "bearbeitung",
    "bayerischer",
    "deutschlandradio",
    "dradio",
    "folge",
    "funktion",
    "gibt",
    "haben",
    "horspielbearbeitung",
    "ihre",
    "komposition",
    "kurzhorspiel",
    "man",
    "mehr",
    "minuten",
    "originalhorspiel",
    "originalhörspiel",
    "podcast",
    "podcasts",
    "realisation",
    "realisierung",
    "redaktion",
    "reihentitel",
    "rolle",
    "rss",
    "rundfunk",
    "sprecher",
    "sprecherin",
    "spotify",
    "technische",
    "teil",
    "titel",
    "ueberall",
    "ubersetzung",
    "vorlage",
    "wurde",
    "wort",
}


def set_style() -> None:
    sns.set_theme(style="whitegrid", context="notebook")
    plt.rcParams.update(
        {
            "figure.facecolor": PALETTE["paper"],
            "axes.facecolor": PALETTE["paper"],
            "axes.edgecolor": PALETTE["line"],
            "axes.labelcolor": PALETTE["ink"],
            "axes.titlecolor": PALETTE["ink"],
            "axes.titlesize": 15,
            "axes.titleweight": "bold",
            "axes.labelsize": 10,
            "xtick.color": PALETTE["muted"],
            "ytick.color": PALETTE["muted"],
            "font.family": "DejaVu Sans",
            "font.size": 10,
            "legend.frameon": False,
            "grid.color": PALETTE["line"],
            "grid.linewidth": 0.7,
            "savefig.facecolor": PALETTE["paper"],
        }
    )


def savefig(name: str) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / name, dpi=240, bbox_inches="tight")
    plt.close()


def strip_boilerplate(text: object) -> str:
    if pd.isna(text):
        return ""
    value = str(text)
    value = re.sub(r"ARD Hörspieldatenbank:?", " ", value)
    value = re.sub(r"dra\.de Suche Kollektionen.*?Detailansicht", " ", value, flags=re.IGNORECASE)
    value = re.sub(r"Um den vollen Funktionsumfang.*?einschalten \.", " ", value, flags=re.IGNORECASE)
    value = re.sub(r"Link kopieren/teilen.*?Audio herunterladen", " ", value, flags=re.IGNORECASE)
    value = re.sub(r"Der Link wurde in die Zwischenablage kopiert\.?", " ", value, flags=re.IGNORECASE)
    value = re.sub(r"Aus dem Podcast Feature", " ", value, flags=re.IGNORECASE)
    value = re.sub(r"\b(Autor/Autorin|Technische Realisierung|Sprecher/Sprecherin|Rolle/Funktion|Bearbeitung \(Wort\)|Regie|Vorlage):?", " ", value)
    value = re.sub(r"\b(Spotify|Apple Podcasts|RSS|App|Mehr anzeigen|Anzeigen)\b", " ", value, flags=re.IGNORECASE)
    value = re.sub(r"\s+", " ", value).strip()
    return dedupe_chunks(value)


def dedupe_chunks(text: str) -> str:
    chunks = re.split(r"(?<=[.!?])\s+|\n+", text)
    seen: set[str] = set()
    kept: list[str] = []
    for chunk in chunks:
        clean = re.sub(r"\s+", " ", chunk).strip()
        if len(clean) < 8:
            continue
        key = clean.lower()[:180]
        if key in seen:
            continue
        seen.add(key)
        kept.append(clean)
    return " ".join(kept)


def parse_year(row: pd.Series) -> int | None:
    for field in ["first_broadcast_date", "year", "production_year", "production_line"]:
        value = row.get(field)
        if pd.notna(value):
            match = re.search(r"(19[4-9]\d|20[0-2]\d)", str(value))
            if match:
                return int(match.group(0))
    return None


def minutes_from_duration(value: object) -> float | None:
    if pd.isna(value):
        return None
    text = str(value).strip()
    if text.isdigit():
        seconds = int(text)
        return seconds / 60 if seconds > 180 else float(seconds)
    match = re.search(r"(\d{1,3})['’](\d{0,2})", text)
    if match:
        return int(match.group(1)) + int(match.group(2) or 0) / 60
    match = re.search(r"(\d{1,3}):(\d{2})", text)
    if match:
        return int(match.group(1)) + int(match.group(2)) / 60
    return None


def form_family(value: object) -> str:
    text = str(value or "").lower()
    if "feature" in text or "dokumentar" in text or "originalton" in text:
        return "feature / documentary"
    if "portr" in text:
        return "portrait"
    if "ars acustica" in text or "klangkunst" in text:
        return "sound art"
    if "bearbeitung" in text:
        return "adaptation"
    if "original" in text:
        return "original radio play"
    if "essay" in text:
        return "essay"
    return "other"


def flags_for(text: str) -> dict[str, bool]:
    lowered = text.lower()
    return {
        "voice": any(word in lowered for word in ["stimme", "stimmen", "sprechen", "sprechweise", "monolog", "dialog", "erzählt", "erzaehlt"]),
        "sound": any(word in lowered for word in ["o-ton", "originalton", "tonband", "tonbänder", "kassette", "aufnahme", "mitschnitt", "geräusch", "geraeusch", "klang", "sound", "audio", "mikrofon"]),
        "archive": any(word in lowered for word in ["archiv", "akte", "akten", "dokument", "nachlass", "quelle", "material", "briefe", "briefwechsel", "tagebuch"]),
        "memory": any(word in lowered for word in ["erinner", "gedächtnis", "gedaechtnis", "vergangenheit", "gedenken", "zeitzeuge", "zeugnis", "überleben", "ueberleben"]),
        "trauma_history": any(word in lowered for word in ["krieg", "ns", "nazi", "auschwitz", "holocaust", "ddr", "mauer", "flucht", "gefangene", "gewalt", "exil"]),
        "artist_author": any(word in lowered for word in ["dichter", "schriftsteller", "autorin", "autor", "künstler", "kuenstler", "komponist", "maler", "poetin"]),
        "family_self": any(word in lowered for word in ["familie", "mutter", "vater", "schwester", "bruder", "kindheit", "jugend", "ich ", "mein ", "meine "]),
        "letters_diaries": any(word in lowered for word in ["tagebuch", "tagebücher", "tagebuecher", "brief", "briefe", "briefwechsel", "memoiren"]),
    }


def life_signal(text: str) -> str:
    lowered = text.lower()
    signals = []
    checks = [
        ("portrait", ["portrait", "porträt", "portraet"]),
        ("biography", ["biografie", "biographie", "biograph"]),
        ("autobiography", ["autobiograph"]),
        ("diary/letters", ["tagebuch", "tagebücher", "tagebuecher", "briefe", "briefwechsel"]),
        ("memory/testimony", ["erinner", "zeitzeuge", "zeugnis", "gedenken"]),
        ("life story", ["lebensgeschichte", "leben von", "aus seinem leben", "aus ihrem leben"]),
    ]
    for label, terms in checks:
        if any(term in lowered for term in terms):
            signals.append(label)
    return "; ".join(signals) if signals else "implicit"


def build_text(df: pd.DataFrame) -> pd.Series:
    rows: list[str] = []
    for _, row in df.iterrows():
        source = row.get("source_archive", "")
        if source == "hoerspielundfeature":
            fields = [
                "title",
                "display_title",
                "creator",
                "genre",
                "topics",
                "description",
                "seo_title",
                "seo_description",
            ]
        elif source == "wirklichkeit_im_radio":
            fields = [
                "title",
                "creator",
                "description",
                "long_description",
                "section_headings",
                "matched_terms",
                "keyword_links",
                "wir_produktion",
                "wir_regie",
            ]
        else:
            fields = [
                "title",
                "genre",
                "authors",
                "template",
                "reviews",
                "production_line",
                "search_terms",
                "raw_text_sample",
            ]
        parts = [str(row.get(field, "")) for field in fields if pd.notna(row.get(field, ""))]
        rows.append(strip_boilerplate(" ".join(parts))[:5000])
    return pd.Series(rows, index=df.index)


def prepare() -> pd.DataFrame:
    df = pd.read_csv(INPUT)
    df["source_label"] = df["source_archive"].map(SOURCE_LABELS).fillna(df["source_archive"])
    df["analysis_year"] = df.apply(parse_year, axis=1)
    df["decade"] = (df["analysis_year"] // 10 * 10).astype("Int64")
    df["include_core"] = df["candidate_confidence"].isin(["high", "medium"])
    df["analysis_text"] = build_text(df)
    df["text_length"] = df["analysis_text"].str.split().map(len)
    df["duration_minutes"] = df["duration"].map(minutes_from_duration)
    df["form_family"] = df["genre"].map(form_family)
    df["life_signal"] = df["analysis_text"].map(life_signal)
    flag_frame = df["analysis_text"].map(flags_for).apply(pd.Series)
    for column in flag_frame.columns:
        df[f"flag_{column}"] = flag_frame[column].astype(bool)
    return df


def fit_semantic_model(core: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    texts = core["analysis_text"].fillna("").tolist()
    vectorizer = TfidfVectorizer(
        lowercase=True,
        strip_accents="unicode",
        token_pattern=r"(?u)\b[a-zA-ZäöüÄÖÜß][a-zA-ZäöüÄÖÜß-]{2,}\b",
        ngram_range=(1, 2),
        min_df=3,
        max_df=0.55,
        max_features=5000,
        stop_words=list(GERMAN_STOPWORDS),
        sublinear_tf=True,
    )
    matrix = vectorizer.fit_transform(texts)
    svd_components = min(40, matrix.shape[1] - 1, matrix.shape[0] - 1)
    svd = TruncatedSVD(n_components=svd_components, random_state=42)
    embedding = normalize(svd.fit_transform(matrix))
    n_clusters = 7
    model = KMeans(n_clusters=n_clusters, n_init=25, random_state=42)
    cluster_id = model.fit_predict(embedding)

    perplexity = min(35, max(5, (len(core) - 1) // 4))
    tsne = TSNE(
        n_components=2,
        perplexity=perplexity,
        init="pca",
        learning_rate="auto",
        random_state=42,
        metric="cosine",
    )
    coords = tsne.fit_transform(embedding)

    terms = np.array(vectorizer.get_feature_names_out())
    cluster_rows = []
    exemplar_rows = []
    for cluster in range(n_clusters):
        mask = cluster_id == cluster
        mean_tfidf = np.asarray(matrix[mask].mean(axis=0)).ravel()
        top_terms = terms[mean_tfidf.argsort()[::-1][:10]].tolist()
        label = label_cluster(top_terms)
        source_mix = core.loc[mask, "source_archive"].value_counts(normalize=True).to_dict()
        if source_mix.get("wirklichkeit_im_radio", 0) > 0.25:
            label = "Curated documentary close readings"
        cluster_rows.append(
            {
                "cluster_id": cluster,
                "cluster_label": label,
                "top_terms": " | ".join(top_terms),
                "rows": int(mask.sum()),
                "dominant_source": max(source_mix, key=source_mix.get),
            }
        )

        distances = pairwise_distances(embedding[mask], model.cluster_centers_[[cluster]], metric="cosine").ravel()
        local = core.loc[mask].copy()
        local["distance_to_cluster"] = distances
        for _, row in local.sort_values("distance_to_cluster").head(5).iterrows():
            exemplar_rows.append(
                {
                    "cluster_id": cluster,
                    "cluster_label": label,
                    "source_archive": row["source_archive"],
                    "title": row["title"],
                    "year": row.get("analysis_year"),
                    "source_url": row.get("source_url"),
                    "distance_to_cluster": row["distance_to_cluster"],
                }
            )

    cluster_table = pd.DataFrame(cluster_rows)
    cluster_table["cluster_label"] = unique_cluster_labels(cluster_table)
    cluster_label_map = cluster_table.set_index("cluster_id")["cluster_label"].to_dict()
    enriched = core.copy()
    enriched["cluster_id"] = cluster_id
    enriched["cluster_label"] = enriched["cluster_id"].map(cluster_label_map)
    enriched["map_x"] = coords[:, 0]
    enriched["map_y"] = coords[:, 1]

    explained = {
        "rows": int(len(core)),
        "features": int(matrix.shape[1]),
        "svd_components": int(svd_components),
        "svd_explained_variance_ratio_sum": float(svd.explained_variance_ratio_.sum()),
        "clusters": int(n_clusters),
    }
    (TABLE_DIR / "semantic_model_summary.json").write_text(json.dumps(explained, indent=2), encoding="utf-8")
    return enriched, cluster_table, pd.DataFrame(exemplar_rows)


def label_cluster(top_terms: list[str]) -> str:
    top_terms = [term for term in top_terms if term not in GERMAN_STOPWORDS]
    term_set = set(top_terms)
    joined = " ".join(top_terms)
    rules = [
        ("Letters and correspondence", ["briefe", "brief", "briefwechsel"]),
        ("Diaries and self-records", ["tagebuch", "tagebucher", "tagebücher"]),
        ("Sound art and listening", ["ars", "acustica", "klang", "sound", "stimme", "aufnahme", "mikrofon"]),
        ("Portrait catalogue", ["portrat", "portrait", "porträt"]),
        ("Social documentary lives", ["menschen", "stadt", "arbeit", "gesellschaft", "frauen", "doku"]),
        ("Autobiographical lives", ["autobiographie", "biographie", "biografie", "leben"]),
        ("Memory and recollection", ["erinnerungen", "erinnerung", "gedachtnis", "gedächtnis"]),
        ("Political history and violence", ["krieg", "auschwitz", "holocaust", "ddr", "mauer", "gewalt", "gefangene", "exil"]),
        ("Family, self, and intimate life", ["mutter", "vater", "familie", "kindheit", "jugend", "liebe"]),
    ]
    for label, needles in rules:
        if any(needle in term_set or re.search(rf"\b{re.escape(needle)}\b", joined) for needle in needles):
            return label
    return ", ".join(top_terms[:3]).title()


def unique_cluster_labels(cluster_table: pd.DataFrame) -> list[str]:
    counts = Counter(cluster_table["cluster_label"])
    labels: list[str] = []
    for row in cluster_table.itertuples():
        label = row.cluster_label
        if counts[label] > 1:
            terms = [term for term in str(row.top_terms).split(" | ") if term not in GERMAN_STOPWORDS]
            label = f"{label}: {', '.join(terms[:2])}"
        labels.append(label)
    return labels


def finish(ax, grid_axis: str | None = "x") -> None:
    if grid_axis:
        ax.grid(axis=grid_axis, alpha=0.45)
    else:
        ax.grid(False)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)


def plot_corpus_triage(df: pd.DataFrame) -> None:
    order = ["DRA", "DLF/DLF Kultur", "Wirklichkeit"]
    table = (
        df.groupby(["source_label", "candidate_confidence"])
        .size()
        .unstack(fill_value=0)
        .reindex(index=order, fill_value=0)
        .reindex(columns=["high", "medium", "review"], fill_value=0)
    )
    ax = table.plot(
        kind="barh",
        stacked=True,
        figsize=(10.8, 4.6),
        color=[PALETTE["high"], PALETTE["medium"], PALETTE["review"]],
    )
    ax.set_title("A Working Corpus, Not a Finished Canon")
    ax.set_xlabel("Rows")
    ax.set_ylabel("")
    ax.legend(title="", loc="lower right")
    for container in ax.containers:
        labels = [f"{int(value.get_width())}" if value.get_width() > 25 else "" for value in container]
        ax.bar_label(container, labels=labels, label_type="center", color="white", fontsize=8)
    finish(ax)
    savefig("01_corpus_triage.png")


def plot_temporal_form_heatmap(core: pd.DataFrame) -> None:
    selected = core[core["analysis_year"].between(1945, 2026, inclusive="both")].copy()
    table = selected.groupby(["decade", "form_family"]).size().unstack(fill_value=0).sort_index()
    keep = table.sum().sort_values(ascending=False).head(7).index
    fig, ax = plt.subplots(figsize=(11.2, 5.8))
    sns.heatmap(table[keep].T, cmap="YlGnBu", linewidths=0.6, linecolor="#ffffff", annot=True, fmt=".0f", cbar_kws={"label": "candidate rows"}, ax=ax)
    ax.set_title("Where Biography Appears: Form Families Over Time")
    ax.set_xlabel("Decade")
    ax.set_ylabel("")
    savefig("02_temporal_form_heatmap.png")


def plot_acoustic_heatmap(core: pd.DataFrame) -> None:
    flags = ["voice", "sound", "archive", "memory", "trauma_history", "artist_author", "family_self", "letters_diaries"]
    labels = {
        "voice": "voice / speech",
        "sound": "sound material",
        "archive": "archive / document",
        "memory": "memory / testimony",
        "trauma_history": "political history",
        "artist_author": "artist / author",
        "family_self": "family / self",
        "letters_diaries": "letters / diaries",
    }
    table = core.groupby("source_label")[[f"flag_{flag}" for flag in flags]].mean() * 100
    table = table.rename(columns={f"flag_{flag}": labels[flag] for flag in flags})
    fig, ax = plt.subplots(figsize=(11.5, 4.8))
    sns.heatmap(table, cmap="crest", vmin=0, vmax=max(80, table.max().max()), annot=True, fmt=".0f", linewidths=0.7, linecolor="#ffffff", cbar_kws={"label": "% of high/medium rows"}, ax=ax)
    ax.set_title("Acoustic-Memory Signals Differ by Source")
    ax.set_xlabel("")
    ax.set_ylabel("")
    savefig("03_acoustic_memory_heatmap.png")


def plot_semantic_map(enriched: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(10.5, 7.2))
    sns.scatterplot(
        data=enriched,
        x="map_x",
        y="map_y",
        hue="cluster_label",
        style="source_label",
        palette=CLUSTER_COLORS,
        s=42,
        alpha=0.78,
        linewidth=0,
        ax=ax,
    )
    ax.set_title("Latent Semantic Map of German Radio Life Writing")
    ax.set_xlabel("t-SNE 1 over TF-IDF/SVD embeddings")
    ax.set_ylabel("t-SNE 2")
    ax.legend(bbox_to_anchor=(1.02, 1), loc="upper left", borderaxespad=0, fontsize=8)
    finish(ax, grid_axis=None)
    savefig("04_semantic_map.png")


def plot_cluster_profile(enriched: pd.DataFrame) -> None:
    flags = ["voice", "sound", "archive", "memory", "trauma_history", "artist_author", "family_self", "letters_diaries"]
    columns = [f"flag_{flag}" for flag in flags]
    table = enriched.groupby("cluster_label")[columns].mean() * 100
    table = table.rename(
        columns={
            "flag_voice": "voice",
            "flag_sound": "sound",
            "flag_archive": "archive",
            "flag_memory": "memory",
            "flag_trauma_history": "history",
            "flag_artist_author": "artist",
            "flag_family_self": "family/self",
            "flag_letters_diaries": "letters/diaries",
        }
    )
    order = enriched["cluster_label"].value_counts().index
    fig, ax = plt.subplots(figsize=(11.8, 6.2))
    sns.heatmap(table.loc[order], cmap="rocket_r", vmin=0, annot=True, fmt=".0f", linewidths=0.7, linecolor="#ffffff", cbar_kws={"label": "% of cluster rows"}, ax=ax)
    ax.set_title("What Each Semantic Cluster Is Made Of")
    ax.set_xlabel("")
    ax.set_ylabel("")
    savefig("05_cluster_profile.png")


def plot_cluster_sizes(cluster_table: pd.DataFrame) -> None:
    table = cluster_table.sort_values("rows")
    labels = [textwrap.fill(f"{row.cluster_label}\n{row.top_terms}", width=58) for row in table.itertuples()]
    fig, ax = plt.subplots(figsize=(11.5, 6.4))
    ax.barh(labels, table["rows"], color=CLUSTER_COLORS[: len(table)])
    ax.set_title("Semantic Clusters and Their Terms")
    ax.set_xlabel("High/medium candidate rows")
    ax.set_ylabel("")
    finish(ax)
    savefig("06_cluster_terms.png")


def plot_cluster_source_mix(enriched: pd.DataFrame) -> None:
    table = pd.crosstab(enriched["cluster_label"], enriched["source_label"], normalize="index") * 100
    counts = enriched["cluster_label"].value_counts()
    table = table.loc[counts.index]
    source_colors = {
        "DLF/DLF Kultur": PALETTE["accent1"],
        "DRA": PALETTE["accent2"],
        "Wirklichkeit": PALETTE["accent3"],
    }
    colors = [source_colors.get(source, PALETTE["muted"]) for source in table.columns]
    ax = table.plot(kind="barh", stacked=True, figsize=(11.2, 6.45), color=colors)
    ax.set_title("Which Sources Shape Each Semantic Cluster?", pad=34)
    ax.set_xlabel("Share of cluster rows (%)")
    ax.set_ylabel("")
    ax.legend(
        title="",
        loc="lower center",
        bbox_to_anchor=(0.5, 1.01),
        ncol=len(table.columns),
        frameon=False,
        columnspacing=1.5,
        handlelength=1.4,
    )
    finish(ax)
    savefig("07_cluster_source_mix.png")


def plot_duration_by_cluster(enriched: pd.DataFrame) -> None:
    data = enriched[enriched["duration_minutes"].between(5, 180, inclusive="both")].copy()
    order = data["cluster_label"].value_counts().index.tolist()
    fig, ax = plt.subplots(figsize=(11.4, 6.0))
    sns.boxplot(data=data, x="duration_minutes", y="cluster_label", order=order, color="#dfe8e3", fliersize=0, ax=ax)
    sns.stripplot(data=data, x="duration_minutes", y="cluster_label", order=order, color=PALETTE["accent1"], alpha=0.35, size=2.4, ax=ax)
    ax.set_title("Dramaturgical Scale by Semantic Cluster")
    ax.set_xlabel("Duration in minutes")
    ax.set_ylabel("")
    finish(ax)
    savefig("08_duration_by_cluster.png")


def write_tables(df: pd.DataFrame, enriched: pd.DataFrame, cluster_table: pd.DataFrame, exemplars: pd.DataFrame) -> None:
    TABLE_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(TABLE_DIR / "german_candidates_enriched_all.csv", index=False)
    enriched.to_csv(TABLE_DIR / "core_semantic_enriched.csv", index=False)
    cluster_table.to_csv(TABLE_DIR / "semantic_cluster_terms.csv", index=False)
    exemplars.to_csv(TABLE_DIR / "semantic_cluster_exemplars.csv", index=False)

    summary = {
        "rows": int(len(df)),
        "core_rows": int(len(enriched)),
        "sources": df["source_archive"].value_counts().to_dict(),
        "core_sources": enriched["source_archive"].value_counts().to_dict(),
        "clusters": cluster_table[["cluster_id", "cluster_label", "rows", "top_terms"]].to_dict(orient="records"),
        "flag_rates_core": {
            column.replace("flag_", ""): float(enriched[column].mean())
            for column in enriched.columns
            if column.startswith("flag_")
        },
    }
    (TABLE_DIR / "deep_analysis_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")


def main() -> None:
    set_style()
    df = prepare()
    core = df[df["include_core"]].copy()
    enriched, cluster_table, exemplars = fit_semantic_model(core)
    write_tables(df, enriched, cluster_table, exemplars)

    plot_corpus_triage(df)
    plot_temporal_form_heatmap(core)
    plot_acoustic_heatmap(core)
    plot_semantic_map(enriched)
    plot_cluster_profile(enriched)
    plot_cluster_sizes(cluster_table)
    plot_cluster_source_mix(enriched)
    plot_duration_by_cluster(enriched)

    print(f"Wrote deep figures to {OUTPUT_DIR}")
    print(f"Wrote deep analysis tables to {TABLE_DIR}")


if __name__ == "__main__":
    main()
