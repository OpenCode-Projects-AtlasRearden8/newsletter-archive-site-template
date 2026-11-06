# newsletter-archive-site-template

A copy-ready static template that turns a folder of newsletter issues into a
browsable archive site.

Drop your issues (HTML or Markdown) plus a small CSV index in `issues/`, run
**one Python build script**, and you get a GitHub Pages-ready site with issue
cards, a search box, a subscribe placeholder, a working RSS feed, and
print-clean reading CSS. No dependencies, no JavaScript framework, no
secrets: everything is standard-library Python and generated HTML/CSS/JS.

Built and maintained by **Asdale Dynamics, LLC** (Dylan Asdale's plain-English
AI education shop).

## What the built site includes

- **Issue cards** on `index.html`, newest first, each showing the issue
  title, human-readable date, and topic chips from the CSV.
- **Search box** that filters cards client-side as you type (plain
  `assets/search.js`, no tracking, no network calls).
- **Subscribe placeholder** section wired to nothing, ready to point at your
  email provider when you choose one.
- **RSS-friendly structure**: every issue gets its own page, and
  `feed.xml` is a standard RSS 2.0 feed linked from every page.
- **Print-clean reading CSS**: issue pages hide site chrome and print as a
  tidy, ink-friendly article (`@media print` rules in `assets/style.css`).
- Mobile-friendly by default; works from a plain folder served statically.

## Folder layout

```
.
├── build.py                 # the one build script (Python 3.9+, stdlib only)
├── issues/
│   ├── index.csv            # the CSV index (authoritative metadata)
│   ├── 001-learning-style.md
│   ├── 002-free-ai-coding.md
│   └── 003-local-ai.html    # raw HTML issues get passed through
├── site/                    # build output (safe to delete/rebuild)
└── tests/                   # pytest tests validating the rendered archive
```

## Quick start

```bash
python3 build.py                    # reads ./issues, writes ./site
python3 -m http.server 8000 --directory site
# open http://localhost:8000
```

Everything is generated fresh on each run; `site/` is disposable.

## The CSV index

`issues/index.csv` drives the whole site. Columns:

| column    | required | notes                                                  |
|-----------|----------|--------------------------------------------------------|
| `file`    | yes      | file name inside `issues/`, `.md` or `.html`           |
| `date`    | yes      | `YYYY-MM-DD`                                           |
| `title`   | yes      | shown on cards, pages, and in RSS                      |
| `topics`  | no       | `;`-separated chips (e.g. `local-ai;privacy`)          |
| `summary` | no       | one-line description used in cards, meta, and RSS     |

```csv
file,date,title,topics,summary
001-learning-style.md,2026-01-05,Welcome to the Plain English AI Letter,getting-started;beginners,"Use commas freely; wrap summaries containing commas in quotes."
```

Order doesn't matter — the build sorts newest first automatically.

## Markdown support in issues

`build.py` includes a small built-in converter supporting: headings (`#`–`####`),
paragraphs, **bold**, *italic*, `` `inline code` ``, `[links](url)`,
`-`/`1.` lists, ``` fenced code blocks, `>` blockquotes, and `---` rules.
Escaping rules: content written in Markdown is HTML-escaped, so `<script>` in a
`.md` file is shown as text instead of executed (raw `.html` issues are
passed through as you wrote them — write those yourself, carefully).

Not enough? Edit `markdown_to_html()` in `build.py`, or pre-render to `.html`.

## CLI flags

```
--issues issues       folder with issue files + index.csv
--out site            output folder for the static site
--title "..."         site title
--tagline "..."       short tagline shown on the index page
--base-url URL        absolute root used for RSS links
```

## GitHub Pages

1. Set `--base-url` in CI to `https://<user>.github.io/<repo>/`.
2. Push and either commit `site/` or build in CI into a `gh-pages` branch.
3. In the repository, enable *Settings → Pages → Build with Actions* and serve
   the generated folder.

(`site/` is `.gitignore`d by default. Choose whichever workflow suits you —
GitHub's *Pages from action* pattern in `.github/workflows/` is the tested,
documented, zero-config option on github.com.)

## Tests

```bash
python3 -m pytest tests/
```

The suite builds the sample archive in a temp directory and validates the
result: card counts, search wiring, RSS well-formedness, slug uniqueness,
print CSS presence, and loud error exits for bad CSV input.

## Fetching changes from upstream

If this template was copied with cookiecutter-style caveats: the only two
files that ever matter are `build.py` and `issues/index.csv`; your own issue
files are safe to edit/delete. There's nothing else to sync up with.

## License & credits

MIT — see [LICENSE](LICENSE).

Template and maintenance by Dylan Asdale / **Asdale Dynamics, LLC**
([dylanasdale.github.io](https://dylanasdale.github.io/)) which explains AI
"like a friend would": plain English, step by step, never condescending.
Brief heresy: no paid tools are assumed anywhere in this template.
