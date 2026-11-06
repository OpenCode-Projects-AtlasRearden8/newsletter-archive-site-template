# STATUS.md — newsletter-archive-site-template

Built 2026-11-06 by Asdale Dynamics, LLC.

## What was built

A copy-ready static template that turns a folder of newsletter issues into a
browsable archive site:

- `build.py` — one standard-library-only Python 3 build script. Reads
  `issues/` (`.md` or `.html` files plus a required `issues/index.csv` with
  columns `file,date,title,topics,summary`) and generates a fresh `site/`:
  - `index.html` — issue cards (newest first) with dates, topic chips, and
    summaries; client-side search box; inert subscribe placeholder.
  - `issues/<slug>.html` — one readable, print-clean page per issue
    (Markdown issues converted by a built-in mini-converter; HTML passed
    through; Markdown source is HTML-escaped so injected tags render as text).
  - `feed.xml` — RSS 2.0 feed with one `<item>` per issue, linked from every
    page (absolute links via `--base-url`).
  - `assets/style.css` (warm, readable, `@media print` rules so issue pages
    print clean) and `assets/search.js` (tracking-free client filtering).
- `issues/` — three realistic sample issues (two Markdown, one HTML) + CSV
  index, matching the "plain English AI letter" tone.
- `tests/test_build.py` — pytest suite (24 tests): Markdown converter units,
  full end-to-end build of the sample archive validating card counts, search
  wiring, subscribe placeholder, RSS well-formedness/link targets, slug
  uniqueness, newest-first ordering, print CSS presence, template
  completeness, and loud `SystemExit` errors for bad CSV indexes.
- `README.md` — usage, CSV schema, CLI flags, GitHub Pages notes, credits,
  MIT license pointer. `LICENSE` — MIT, `Copyright (c) 2026 Asdale Dynamics, LLC`.
- `.gitignore` — ignores `site/` build output, caches.

## How to run

```bash
python3 build.py                                  # issues/ -> site/
python3 -m http.server 8000 --directory site      # preview locally
python3 -m pytest tests/                          # run the test suite
python3 build.py --help                           # see all flags
```

For GitHub Pages, set `--base-url https://<user>.github.io/<repo>/` so RSS
links are absolute, then publish `site/`.

## Verification results (2026-11-06)

- `python3 build.py` — completed: "Built 3 issue page(s) + index.html +
  feed.xml into site". Inspected rendered `index.html` (cards, dates, chips,
  search box, subscribe section) and issue pages (headings, code fences,
  blockquotes, HTML passthrough) — all correct.
- `python3 -m pytest tests/ -q` — **24 passed**.
- Bad CSV indexes (missing column, missing file, bad date) verified to fail
  with clear `SystemExit` messages.
- No secrets, API keys, or personal data in any file. No network calls;
  everything is local-first.

## Known gaps

- The built-in Markdown converter is intentionally minimal (no tables,
  nested lists, or footnotes); for more, pre-render issues to `.html` or
  extend `markdown_to_html()` in `build.py`.
- The search box filters the assembled card text (title, date, topics,
  summary) client-side; it does not search inside issue bodies yet.
- The subscribe form is a placeholder by design — wire it to your email
  provider before real use.
- RSS links depend on `--base-url`; relative-only mode is not supported
  (RSS entry links need absolute URLs).
- No CI workflow file is included (kept template-minimal); tests are runnable
  anywhere with pytest installed.
