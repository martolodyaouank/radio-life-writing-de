# Lives on Air

German-first dataset and article prototype for studying biographical radio drama, documentary feature, and sound-based life writing through public archive and programme metadata.

Website: https://martolodyaouank.github.io/radio-lifewritingde/

The repository demonstrates a reproducible workflow:

- fetch public metadata from ARD/DRA Hoerspieldatenbank, Wirklichkeit im Radio, and Hoerspiel und Feature;
- parse archive-specific pages into a common schema;
- identify likely biographical or autobiographical radio plays;
- analyse the resulting dataset in Python;
- publish a short article with findings and limitations.

## Current Scope

The active scope is German-first. Earlier non-German source adapters are kept in the repository as inactive experiments, but the current research dataset excludes them.

The current pipeline:

1. Fetch DRA search/detail pages for biography-oriented terms, 1945-2026.
2. Fetch all `wirklichkeitimradio.de/stueck/` pages from the WordPress sitemap.
3. Fetch `hoerspielundfeature.de` sitemap entries and biography-oriented search results.
4. Preserve source-specific descriptive text, sonic/material keywords, production fields, audio links, dates, and duration metadata where available.
5. Merge only German rows into `data/processed/german_radio_biographical_candidates.csv`.

No audio files are downloaded. Raw archive text is cached locally only for analysis and parser testing.

## Project Layout

```text
article/                         Public-facing write-up
data/raw/                        Cached source HTML/JSON
data/interim/                    Archive-specific normalized tables
data/processed/                  Final merged datasets
notebooks/                       Analysis notebooks
src/lives_on_air/                Python package
tests/                           Parser and classifier tests
```

## Setup

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pip install -e .
```

## Feasibility Helpers

```bash
.venv/bin/python -m lives_on_air.scrapers.feasibility
.venv/bin/python -m lives_on_air.scrapers.dra
```

The script writes cached HTML into `data/raw/` and prints a short field-availability summary.

## Current German Batch Scrape

```bash
.venv/bin/python -m lives_on_air.scrapers.german_batch --dra-limit-per-term 80 --dra-max-pages 8 --dra-detail-workers 8
.venv/bin/python -m lives_on_air.analysis.combine_outputs
.venv/bin/python -m lives_on_air.analysis.deep_analysis
.venv/bin/python -m lives_on_air.analysis.export_3d_map
```

Current local outputs:

- `data/interim/dra_biography_term_batch.csv`
- `data/interim/wirklichkeit_im_radio_stuecke.csv`
- `data/interim/hoerspielundfeature_candidates.csv`
- `data/processed/german_radio_biographical_candidates.csv`
- `data/processed/german_scrape_summary.json`
- `data/processed/analysis_tables/core_semantic_enriched.csv`
- `data/processed/analysis_tables/semantic_cluster_terms.csv`
- `data/processed/analysis_tables/semantic_cluster_exemplars.csv`
- `article/figures/*.png`

The current batch uses biography-oriented DRA search terms, Wirklichkeit im Radio's WordPress sitemap, and Hoerspiel und Feature's sitemaps plus search pages. DRA detail pages are discovered through paginated search results with first-broadcast filters for 1945-2026.

## Source Notes

- `hoerspiele.dra.de` search is a TYPO3 POST form. The DRA scraper first loads `/suche`, preserves hidden trusted form fields, then submits archive queries and follows `/detailansicht/{id}` links.
