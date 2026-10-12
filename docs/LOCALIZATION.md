# English and Simplified Chinese

The official DCC-MCP website uses English at its root and Simplified Chinese
under `zh/`. Showcase follows the same convention:

- `/showcase/` and `/showcase/cases/<slug>/`: English
- `/showcase/zh/` and `/showcase/zh/cases/<slug>/`: Simplified Chinese
- The brand gallery and all ten published brand detail pages have both routes.
- Existing case URLs still address the same case. Slugs and fragment IDs remain
  stable; content is not redirected based on browser language or stored state.

Language links point to the equivalent page. With JavaScript, they also preserve
query filters and the current fragment. They work as ordinary page links when
JavaScript is unavailable. Filters retain stable original identifiers across
languages; searches also include bilingual search aliases as well as the localized visible card copy. Unsupported
language hints normalize to English; explicit page URLs always take precedence.

## Source and translation boundaries

`collection.json`, producer manifests, native projects, source archives,
artwork, embedded artistic text, original prompts and evidence files remain
unchanged. `locales/en/` contains English presentation translations keyed by
exact original Chinese strings. Software names, API names, versions, hashes,
paths and filter identifiers are not translated.

The English prompt section links directly to its original Chinese counterpart.
Its note makes clear that downloadable evidence, source instructions and native
artwork retain their original language. Rights statements and evidence limits
are translated without granting additional permissions or claiming additional
verification. In particular, unknown model attribution, incomplete listening
review, unmerged adapter dependencies and historical/non-rerun evidence remain
explicit in both languages.

The optional Godot Web shell separately declares its supported languages and
original artwork language in `play/manifest.json`. Its bilingual controls and
notes enter the same presentation layer; shared engine/media paths are never
copied into a locale directory.

## Maintaining translations

The builder first validates and renders the original data, then transforms only
presentation text, selected accessibility/SEO attributes, structured-data values
and known page URLs. It emits fully translated static HTML, including `lang`,
Open Graph locale, canonical URL, reciprocal `hreflang` entries, JSON-LD and a
bilingual sitemap. Media and source resources are shared once.

New or changed Chinese presentation text without a matching English entry
blocks publication **before** replacing the previous output directory. There is
no partial-word substitution or silent mixed-language fallback. A small set of
registered UI compositions (case/image label prefixes, counts and review dates)
is assembled from complete translated values. Case SEO titles are composed from
the same translated title/subtitle; descriptions use the translated summary.

To add or update content:

1. Edit its authoritative source and preserve its evidence/rights boundaries.
2. Add the exact new source string and complete English translation to the
   corresponding `locales/en/cases/<slug>.json`, `brands.json` or `ui.json`.
3. Run the build. It reports every missing string with the affected page.
4. Review both languages, especially long prompts, accessibility descriptions,
   unknown/unverified qualifiers and small-screen wrapping.

`locales/config.json` defines the supported routes. The source-language renderer
supports explicit `localize=False` only for minimal isolated unit-test fixtures.
Normal builds require and validate the config; a missing config fails closed.

## Verification

```sh
python scripts/test_localization.py
python scripts/test_playable.py
python scripts/build_site.py
python scripts/localization_browser_smoke.py --site _site --output /tmp/showcase-localization
```

The browser workflow runs against the exact PR head and the real `/showcase/`
mount. It renders all 24 content pages in both languages at desktop and mobile
widths (96 page/viewport checks), decodes actual images, checks local links and
fragment targets, checks localized accessibility and SEO, and exercises search,
filters, empty states, keyboard language changes, query/hash preservation,
Back, clipboard success/fallback and brand themes. A no-JavaScript pass checks
content and navigation. The original-language media/evidence browser suite is
retained under `/zh/`, alongside the existing Sonic Loom and Prism Tide checks.

CI screenshots and its JSON report are review evidence. Schema/build success
alone is not visual acceptance or new validation of the underlying artwork.
