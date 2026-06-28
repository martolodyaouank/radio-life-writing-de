# German Analysis Roadmap

This project is now a German-first corpus and public static article for radio
life writing. The deployed website at
`https://martolodyaouank.github.io/radio-life-writing-de/` is built from the
checked-in `article/` directory; the GitHub Pages workflow publishes those files
directly and does not rerun the scrape or analysis pipeline.

## Current Website

The live article currently contains:

- a hero with corpus metrics for 566 programmes, broadcast years 1949-2026, and
  six working clusters;
- an introductory methods note linking to `notebooks/selection_method.ipynb`;
- a corpus triage panel summarising the visible 566-entry curated map layer;
- an interactive 3D latent semantic map with year, genre, source, life-focus,
  and cluster filters;
- a "Who are these lives about?" section with top life-focus tags and a decade
  heatmap;
- a cluster explorer with source split, year range, genre count, life-focus
  bars, and exemplar cards;
- source mix, genre mix, cluster profile, and genre-by-year overview panels;
- a running-time chart backed by the duration export.

The visible map layer is not the full scraped corpus. It is the curated,
article-facing selection exported from
`data/latent_semantic_map_all_602_sorted.csv` into
`article/semantic-map-3d-data.js`.

## Current Corpus State

The active sources are:

- DRA / ARD Hoerspieldatenbank;
- Hoerspiel und Feature / DLF and DLF Kultur;
- Wirklichkeit im Radio.

The checked-in scrape summary contains 1,764 merged German records:

- DRA: 1,386 rows;
- Hoerspiel und Feature / DLF and DLF Kultur: 333 rows;
- Wirklichkeit im Radio: 45 rows.

The modeled core analysis table contains 806 high- and medium-confidence
records. The deployed semantic map displays a curated subset of 566 records:

- DRA: 459 visible records;
- DLF/DLF Kultur: 92 visible records;
- Wirklichkeit: 15 visible records.

The live map exposes six article-facing clusters:

- Biography: 155 records;
- Biofiction: 114 records;
- Based on diaries: 100 records;
- Autobiographical lives: 79 records;
- Based on letters: 69 records;
- Sound art: 49 records.

The 566 visible records span 1949-2026 and expose 72 genre/form filter values
and 119 life-focus or protagonist-role tags. The duration chart has 544 matched
records from the visible map layer.

## Current Data Files

The important checked-in data artifacts are:

- `data/processed/analysis_tables/german_candidates_enriched_all.csv`: the
  1,764-row enriched German candidate table used as the main inspected corpus
  artifact;
- `data/processed/analysis_tables/core_high_medium_candidates.csv`: the
  806-row high/medium confidence subset;
- `data/processed/analysis_tables/core_semantic_enriched.csv`: the 806-row
  semantic model table with the original t-SNE map coordinates;
- `data/latent_semantic_map_all_602_sorted.csv`: the curated 566-row
  article-facing map spreadsheet, despite the historical `602` in the filename;
- `article/semantic-map-3d-data.js`: the live 3D map payload;
- `article/duration-scale-data.js`: the live running-time payload;
- `data/curation/source_card_descriptions.csv`: curated and derived card
  descriptions used by the map export process;
- `data/curation/semantic_map_protagonist_audit.csv` and
  `data/curation/life_subject_audit.csv`: review tables for protagonist and
  life-focus metadata.

## Current Pipeline

The broad regeneration path remains:

```bash
.venv/bin/python -m lives_on_air.scrapers.german_batch --dra-limit-per-term 80 --dra-max-pages 8 --dra-detail-workers 8
.venv/bin/python -m lives_on_air.analysis.combine_outputs
.venv/bin/python -m lives_on_air.analysis.deep_analysis
.venv/bin/python -m lives_on_air.analysis.export_spreadsheet_semantic_map
```

`combine_outputs` writes `data/processed/german_radio_biographical_candidates.csv`.
That file is a generated pipeline input for `deep_analysis`; it is not currently
the checked-in article-facing enriched table. The checked-in enriched table is
`data/processed/analysis_tables/german_candidates_enriched_all.csv`.

`export_spreadsheet_semantic_map` is the current live-site exporter. It reads the
curated spreadsheet, restores x/y coordinates from
`core_semantic_enriched.csv`, preserves existing card descriptions from
`article/semantic-map-3d-data.js` when available, and writes both
`article/semantic-map-3d-data.js` and `article/duration-scale-data.js`.

## Remaining Technical Work

1. Make the generated pipeline path and checked-in enriched table path less
   confusing. Either check in `data/processed/german_radio_biographical_candidates.csv`
   when it is part of the supported workflow, or update `deep_analysis` to read
   the checked-in enriched table directly.

2. Add a lightweight verification script for the website payloads. It should
   assert the visible map count, year range, source counts, cluster counts,
   duration-match count, and presence of the expected section mounts in
   `article/index.html`.

3. Keep curation review focused on the deployed surfaces: protagonist labels,
   life-focus tags, card descriptions, duration availability, and records whose
   cluster labels differ from the older seven-cluster model labels.

4. Treat the semantic map as an exploratory t-SNE layout over TF-IDF/SVD-derived
   features, not as a stable distance-preserving atlas. If new embeddings are
   added later, store vectors under `data/processed/embeddings/` and regenerate
   the article payloads rather than manually editing the JavaScript data files.

5. Preserve the German-first scope. Older BBC and other experimental adapters may
   remain in `src/`, but they are not represented in the deployed website.
