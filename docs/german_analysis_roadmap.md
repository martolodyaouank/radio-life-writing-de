# German Analysis Roadmap

This project is now a German-first corpus project. The postdoc proposal remains separate; this repository is the technical pet project demonstrating scraping, corpus construction, and computational exploration for radio studies.

## Current Corpus

- DRA/ARD Hoerspieldatenbank: historical backbone for 1945-2026.
- Wirklichkeit im Radio: curated documentary-feature pages with strong sonic and material commentary.
- Hoerspiel und Feature: DLF/DLF Kultur programme pages, sitemaps, and search-discovered biography/memory candidates.

The active merged dataset is:

```text
data/processed/german_radio_biographical_candidates.csv
```

## Near-Term Analytics

1. Source and confidence profile
   - Which sources supply high, medium, and review-level candidates?
   - Which sources are discovery layers versus structured archive layers?

2. Postwar visibility timeline
   - Candidate rows by decade and source.
   - Treat this as archive visibility, not production volume.

3. Form families
   - Track biography across portrait, feature, original radio play, adaptation, original sound, and sound art.
   - Compare whether life writing clusters around documentary forms or crosses into experimental forms.

4. Life-writing signals
   - Biography, autobiography, portrait, diary, letters, memoir/memory, testimony, and life-language.
   - Use these as interpretable labels before moving to embeddings.

5. Acoustic-memory vocabulary
   - Voice/speech: Stimme, Sprechen, Monolog.
   - Sound/material: O-Ton, Tonband, Kassette, Mitschnitt, Aufnahme, Klang.
   - Archive/document: Archiv, Akte, Briefe, Tagebuch, Dokument, Nachlass.
   - Memory/testimony: Erinnerung, Gedaechtnis, Zeitzeuge, Zeugnis, Vergangenheit.

6. Institutional geography
   - Broadcasters and site names visible in high/medium candidates.
   - Useful for connecting memory forms to commissioning and cataloguing institutions.

## Representation Learning Direction

The richest text fields are `description`, `long_description`, `raw_text_sample`, `matched_terms`, `section_headings`, `topics`, and DRA metadata text. A strong next step is to build German sentence embeddings over these fields and then:

- cluster candidate works by semantic memory mode rather than keyword label;
- map nearest neighbors for known anchor works such as `Bananen-Heinz`, `Die Callas`, Klemperer diary pieces, and archive/tape-based works;
- compare keyword classes with embedding clusters to find false negatives and unexpected families;
- project embeddings with UMAP or t-SNE for an exploratory “memory map” of German radio life writing;
- use topic models only as a secondary, interpretable layer after embedding clusters are inspected.

Recommended first embedding model family: a multilingual or German sentence-transformer. Keep embeddings local in `data/processed/embeddings/` and store only vectors plus row IDs, not scraped full text exports beyond the existing local research dataset.
