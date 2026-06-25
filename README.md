# Lives on Air

German-first corpus and public article for exploring biographical radio drama,
documentary feature, and sound-based life writing through archive and programme
metadata.

Live site: https://martolodyaouank.github.io/radio-life-writing-de/

The repository currently contains both the research pipeline and the prebuilt
GitHub Pages article. The Pages workflow does not rebuild the analysis; it
uploads the checked-in `article/` directory.

## Current State

- `article/` is the published site, including the interactive dashboards, 3D
  semantic map, duration chart data, static figures, styles, and vendored
  Three.js.
- `article/semantic-map-3d-data.js` contains 566 curated visible map records.
- The visible map records come from
  `data/latent_semantic_map_all_602_sorted.csv`.
- The map x/y positions are restored from the original t-SNE layout in
  `data/processed/analysis_tables/core_semantic_enriched.csv`; the z-axis is
  mapped from broadcast year.
- Manual curation lives in `data/curation/`, including exclusions, life-subject
  overrides, year overrides, source-card descriptions, and protagonist audit
  files.
- The active dataset is German-first: DRA / ARD Hoerspieldatenbank,
  Hoerspiel und Feature / DLF Kultur, and Wirklichkeit im Radio. Older BBC and
  other source adapters remain as inactive experiments.

No audio files are downloaded by the pipeline.

## Repository Layout

```text
article/                         Published GitHub Pages article
article/figures/                 Static analysis figures
article/semantic-map-3d*.js      3D map data and renderer
article/semantic-dashboard.js    Front-end charts and dashboard panels
data/curation/                   Manual review and correction tables
data/interim/                    Cached summaries and curation helper output
data/latent_semantic_map_*.csv   Curated semantic-map spreadsheet exports
data/processed/                  Merged and modeled analysis tables
docs/                            Project notes and roadmap
src/lives_on_air/                Scrapers, parsers, classifiers, analysis code
tests/                           Focused parser/export/classifier tests
```

## Setup

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pip install -e .
```

The package requires Python 3.11 or newer. The main analysis stack is pandas,
scikit-learn, matplotlib, and seaborn.

## Data Pipeline

The broad scrape and analysis path is:

```bash
.venv/bin/python -m lives_on_air.scrapers.german_batch --dra-limit-per-term 80 --dra-max-pages 8 --dra-detail-workers 8
.venv/bin/python -m lives_on_air.analysis.combine_outputs
.venv/bin/python -m lives_on_air.analysis.deep_analysis
```

Important generated analysis outputs include:

- `data/processed/german_radio_biographical_candidates.csv`
- `data/processed/german_scrape_summary.json`
- `data/processed/analysis_tables/core_semantic_enriched.csv`
- `data/processed/analysis_tables/semantic_cluster_terms.csv`
- `data/processed/analysis_tables/semantic_cluster_exemplars.csv`
- `article/figures/*.png`

The current checked-in scrape summary contains 1,764 merged German rows:
1,386 DRA rows, 333 Hoerspiel und Feature rows, and 45 Wirklichkeit im Radio
rows. The modeled core table contains 806 high- and medium-confidence records
before the later visible-map curation layer.

## Map And Article Exports

There are two map exporters:

```bash
.venv/bin/python -m lives_on_air.analysis.export_3d_map
.venv/bin/python -m lives_on_air.analysis.export_spreadsheet_semantic_map
```

`export_3d_map` exports directly from
`data/processed/analysis_tables/core_semantic_enriched.csv`.

`export_spreadsheet_semantic_map` is the current article-facing exporter. It
keeps the curated 566-record spreadsheet set from
`data/latent_semantic_map_all_602_sorted.csv`, uses source-card descriptions
where available, and looks up each record's original t-SNE x/y coordinates by
URL from `core_semantic_enriched.csv`.

After changing curation tables or source-card descriptions, rerun:

```bash
.venv/bin/python -m lives_on_air.analysis.export_spreadsheet_semantic_map
```

Then commit the regenerated `article/semantic-map-3d-data.js`.

## Source Card Descriptions

The map cards use curated/derived short descriptions from:

```text
data/curation/source_card_descriptions.csv
```

Helper scripts:

```bash
.venv/bin/python -m lives_on_air.analysis.build_source_card_descriptions
.venv/bin/python -m lives_on_air.analysis.translate_card_descriptions --write-curl-config
.venv/bin/python -m lives_on_air.analysis.translate_card_descriptions --apply
```

The translation helper writes curl configs and cached JSON responses under
`data/interim/`; review generated text before treating it as final curation.

## Publishing

The GitHub Pages workflow is `.github/workflows/pages.yml`. On pushes to
`main`, it uploads the checked-in `article/` directory and deploys it to Pages.
It does not install dependencies or run the analysis scripts.

## Tests

```bash
.venv/bin/python -m pytest
```

Current tests cover the biographical classifier and subject/protagonist export
behavior for the 3D map pipeline.

## Source Notes

- `hoerspiele.dra.de` search is a TYPO3 POST form. The DRA scraper loads
  `/suche`, preserves hidden trusted form fields, submits archive queries, and
  follows `/detailansicht/{id}` links.
- Hoerspiel und Feature data comes from sitemap entries plus
  biography-oriented search results.
- Wirklichkeit im Radio data comes from WordPress sitemap pages under
  `/stueck/`.
