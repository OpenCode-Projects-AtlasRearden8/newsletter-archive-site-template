#!/usr/bin/env python3
"""Build a browsable static archive site from a folder of newsletter issues.

Input:  an ``issues/`` folder containing HTML or Markdown issue files, plus an
``index.csv`` (CSV index) with metadata: file, date, title, topics, summary.

Output: a static ``site/`` folder with:
  - index.html    archive listing (issue cards, client-side search, subscribe)
  - issues/*.html one readable, print-clean page per issue
  - feed.xml      RSS 2.0 feed pointing at the issue pages
  - assets/       style.css and search.js (no external dependencies)

Usage:
    python3 build.py [--issues issues] [--out site]
                     [--title "..."] [--base-url https://example.org/path/]

No third-party dependencies; standard library only. MIT licensed.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import html
import re
import shutil
import sys
from pathlib import Path


def escape(text: str) -> str:
    return html.escape(text, quote=False)


def attr(text: str) -> str:
    return html.escape(text, quote=True)


def slugify(text: str) -> str:
    text = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return text or "issue"


def human_date(d: dt.date) -> str:
    return d.strftime("%B %d, %Y").replace(" 0", " ")


# --------------------------------------------------------------------------- #
# Tiny Markdown -> HTML converter (standard library only).
# Supports: headings, paragraphs, bold/italic/inline code, links,
# unordered/ordered lists, code fences, blockquotes, horizontal rules.
# --------------------------------------------------------------------------- #

INLINE_STRONG = re.compile(r"\*\*(.+?)\*\*")
INLINE_TRACK_RE = re.compile(r"^(#{1,4}\s|[-*]\s|\d+[.)]\s|>\s?|```)")


def inline_md(text: str) -> str:
    text = html.escape(text, quote=False)
    text = INLINE_STRONG.sub(r"<strong>\1</strong>", text)
    text = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", text)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    text = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", r'<a href="\2">\1</a>', text)
    return text


def markdown_to_html(md: str) -> str:
    out: list[str] = []
    lines = md.replace("\r\n", "\n").split("\n")
    i = 0
    n = len(lines)
    open_list: str | None = None

    def close_list() -> None:
        nonlocal open_list
        if open_list:
            out.append("</%s>" % open_list)
            open_list = None

    while i < n:
        raw = lines[i]
        stripped = raw.strip()

        # Code fence
        if stripped.startswith("```"):
            close_list()
            code: list[str] = []
            i += 1
            while i < n and not lines[i].strip().startswith("```"):
                code.append(lines[i])
                i += 1
            i += 1  # past closing fence (or EOF)
            out.append("<pre><code>%s</code></pre>" % html.escape("\n".join(code)))
            continue

        # Heading
        m = re.match(r"^(#{1,4})\s+(.*)$", stripped)
        if m:
            close_list()
            level = len(m.group(1))
            out.append("<h%d>%s</h%d>" % (level, inline_md(m.group(2)), level))
            i += 1
            continue

        # Blockquote (runs until a non-quote line)
        if stripped.startswith(">"):
            close_list()
            quote: list[str] = []
            while i < n and lines[i].strip().startswith(">"):
                quote.append(re.sub(r"^\s*>\s?", "", lines[i]))
                i += 1
            out.append("<blockquote>%s</blockquote>" % inline_md(" ".join(q.strip() for q in quote)))
            continue

        # Horizontal rule
        if re.fullmatch(r"(-{3,}|\*{3,}|_{3,})", stripped):
            close_list()
            out.append("<hr>")
            i += 1
            continue

        # List items
        bullet = re.match(r"^[-*]\s+(.*)$", stripped)
        ordered = re.match(r"^\d+[.)]\s+(.*)$", stripped)
        if bullet or ordered:
            wanted = "ul" if bullet else "ol"
            if open_list != wanted:
                close_list()
                out.append("<%s>" % wanted)
                open_list = wanted
            out.append("<li>%s</li>" % inline_md((bullet or ordered).group(1)))
            i += 1
            continue

        # Blank line closes the current list but starts nothing new
        if not stripped:
            close_list()
            i += 1
            continue

        # Everything else: one paragraph per line
        close_list()
        out.append("<p>%s</p>" % inline_md(stripped))
        i += 1

    close_list()
    return "\n".join(out)


# --------------------------------------------------------------------------- #
# Loading issues from the CSV index
# --------------------------------------------------------------------------- #

def load_issues(issues_dir: Path) -> list[dict]:
    index_csv = issues_dir / "index.csv"
    if not index_csv.is_file():
        sys.exit("error: %s not found (CSV index is required)" % index_csv)
    issues: list[dict] = []
    required = {"file", "date", "title"}
    with index_csv.open(newline="", encoding="utf-8") as fh:
        for row_num, row in enumerate(csv.DictReader(fh), start=2):
            row = {(k or "").strip(): (v or "").strip() for k, v in row.items()}
            if not row.get("file"):
                continue
            missing = required - row.keys()
            if missing:
                sys.exit("error: %s row %d missing column(s): %s"
                         % (index_csv.name, row_num, ", ".join(sorted(missing))))
            src = issues_dir / row["file"]
            if not src.is_file():
                sys.exit("error: %s row %d points to missing file: %s"
                         % (index_csv.name, row_num, row["file"]))
            try:
                date_obj = dt.date.fromisoformat(row["date"])
            except ValueError:
                sys.exit("error: %s row %d has bad date %r (use YYYY-MM-DD)"
                         % (index_csv.name, row_num, row["date"]))
            if src.suffix.lower() not in (".md", ".markdown", ".html", ".htm"):
                sys.exit("error: %s row %d: unsupported issue type %s (use .md or .html)"
                         % (index_csv.name, row_num, src.suffix))
            issues.append({
                "file": row["file"],
                "src": src,
                "date": date_obj,
                "title": row["title"],
                "topics": [t for t in (s.strip() for s in row.get("topics", "").split(";")) if t],
                "summary": row.get("summary", ""),
            })
    if not issues:
        sys.exit("error: no issues listed in %s" % index_csv)

    issues.sort(key=lambda it: (it["date"], slugify(it["title"])), reverse=True)
    used: set[str] = set()
    for it in issues:
        base = slugify(it["title"])
        cand, k = base, 2
        while cand in used:
            cand = "%s-%d" % (base, k)
            k += 1
        used.add(cand)
        it["slug"] = cand
        it["date_iso"] = it["date"].isoformat()
    return issues


# --------------------------------------------------------------------------- #
# Templates
# --------------------------------------------------------------------------- #

STYLESHEET = """
:root {
  --ink: #1f2933;
  --muted: #52606d;
  --paper: #faf8f4;
  --card: #ffffff;
  --accent: #0b6e5f;
  --accent-soft: #e3f1ee;
  --border: #e2ddd3;
  --chip: #eef2f7;
}
* { box-sizing: border-box; }
html { font-size: 17px; }
body {
  margin: 0;
  background: var(--paper);
  color: var(--ink);
  font-family: Georgia, "Iowan Old Style", "Times New Roman", serif;
  line-height: 1.65;
}
header.site-head, main, footer.site-foot {
  max-width: 46rem;
  margin: 0 auto;
  padding-left: 1.25rem;
  padding-right: 1.25rem;
}
header.site-head { padding-top: 2.5rem; padding-bottom: 2rem; }
header.site-head h1 { margin: 0 0 0.4rem; font-size: 2rem; line-height: 1.2; }
header.site-head h1 a { color: inherit; text-decoration: none; }
header.site-head p.tagline { margin: 0 0 0.5rem; color: var(--muted); }
header.site-head p.feedline { margin: 0; font-size: 0.9rem; }
header.site-head a { color: var(--accent); }

.search-wrap { margin: 1rem 0 1.5rem; }
#archive-search {
  width: 100%;
  padding: 0.7rem 0.9rem;
  font: inherit;
  color: var(--ink);
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 8px;
}
#archive-search:focus { outline: 2px solid var(--accent); outline-offset: 1px; }
#search-count { margin: 0.4rem 0 0; font-size: 0.85rem; color: var(--muted); }

.card {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 1.1rem 1.3rem;
  margin: 0 0 1.1rem;
}
.card h2 { margin: 0 0 0.35rem; font-size: 1.3rem; line-height: 1.25; }
.card h2 a { color: var(--ink); text-decoration: none; }
.card h2 a:hover { text-decoration: underline; }
.card .meta { margin: 0 0 0.5rem; color: var(--muted); font-size: 0.9rem; }
.card time { color: var(--accent); font-weight: bold; }
.card p.summary { margin: 0.5rem 0 0; }
.card .topics { margin: 0.6rem 0 0; padding: 0; list-style: none; }
.card .topics li {
  display: inline-block;
  background: var(--chip);
  border-radius: 999px;
  padding: 0.1rem 0.7rem;
  font-size: 0.8rem;
  margin: 0.25rem 0.35rem 0.25rem 0;
}

.subscribe {
  margin: 2rem 0;
  padding: 1.2rem 1.3rem;
  background: var(--accent-soft);
  border: 1px solid var(--border);
  border-radius: 10px;
}
.subscribe h2 { margin: 0 0 0.4rem; font-size: 1.2rem; }
.subscribe p { margin: 0 0 0.8rem; }
.subscribe form { display: flex; gap: 0.5rem; flex-wrap: wrap; }
.subscribe input[type="email"] {
  flex: 1 1 14rem;
  padding: 0.55rem 0.7rem;
  font: inherit;
  border: 1px solid var(--border);
  border-radius: 7px;
}
.subscribe button {
  padding: 0.55rem 1.1rem;
  font: inherit;
  color: #fff;
  background: var(--accent);
  border: 0;
  border-radius: 7px;
  cursor: pointer;
}
.subscribe .placeholder-note { margin: 0.5rem 0 0; font-size: 0.85rem; color: var(--muted); }

a.backlink { display: inline-block; color: var(--accent); margin-bottom: 1rem; }
article.issue h1 { font-size: 1.9rem; line-height: 1.25; margin: 0 0 0.3rem; }
article.issue .meta { color: var(--muted); font-size: 0.95rem; }
article.issue time { color: var(--accent); font-weight: bold; }
article.issue hr { border: 0; border-top: 1px solid var(--border); margin: 1.2rem 0; }
article.issue h2 { margin: 1.8rem 0 0.5rem; font-size: 1.4rem; }
article.issue h3 { margin: 1.4rem 0 0.4rem; font-size: 1.15rem; }
article.issue blockquote {
  margin: 1rem 0;
  padding: 0.2rem 1rem;
  border-left: 3px solid var(--accent);
  color: var(--muted);
}
article.issue pre {
  background: #f2f0ea;
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 0.8rem 1rem;
  overflow-x: auto;
}
article.issue code,
.subscribe code {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 0.85em;
}
article.issue img { max-width: 100%; height: auto; }
footer.site-foot {
  margin-top: 2.5rem;
  padding-top: 1rem;
  padding-bottom: 2.5rem;
  color: var(--muted);
  font-size: 0.85rem;
}
footer.site-foot p { margin: 0.3rem 0; }

@media print {
  :root { --paper: #fff; --card: #fff; --bg: #fff; }
  header.site-head, .search-wrap, .subscribe, footer.site-foot { display: none; }
  body { background: #fff; color: #000; font-size: 12pt; }
  header.site-head, main, footer.site-foot { max-width: none; padding: 0; }
  a.backlink { display: none; }
  .card { border: 0; padding: 0; margin: 0 0 0.8rem; break-inside: avoid; }
  .card a, article.issue a { text-decoration: none; color: #000; }
  article.issue pre { border: 1px solid #999; background: #fff; }
  .card .topics li { background: none; padding-left: 0; }
}
""".strip()

SEARCH_JS = """(function () {
  var input = document.getElementById("archive-search");
  var count = document.getElementById("search-count");
  if (!input) { return; }
  var cards = Array.prototype.slice.call(document.querySelectorAll("main > .card"));
  var initial = count && count.textContent ? count.textContent : "";
  var topicText = function (card) {
    var chips = card.querySelectorAll(".topics li");
    var out = [];
    for (var i = 0; i < chips.length; i++) { out.push(chips[i].textContent); }
    return " " + out.join(" ") + " ";
  };
  var apply = function () {
    var q = input.value.trim().toLowerCase();
    var shown = 0;
    for (var i = 0; i < cards.length; i++) {
      var hit = q === "" || (cards[i].textContent + " " + topicText(cards[i]))
        .toLowerCase().indexOf(q) !== -1;
      cards[i].hidden = !hit;
      if (hit) { shown++; }
    }
    if (count) {
      count.textContent = q === ""
        ? initial
        : shown + " issue" + (shown === 1 ? "" : "s") + ' matching: "' + q + '"';
    }
  };
  input.addEventListener("input", apply);
})();
""".strip()

INDEX = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<meta name="description" content="{desc}">
<link rel="stylesheet" href="assets/style.css">
<link rel="alternate" type="application/rss+xml" title="{title} RSS" href="feed.xml">
</head>
<body>
<header class="site-head">
  <h1>{title}</h1>
  <p class="tagline">{tagline}</p>
  <p class="feedline"><a href="feed.xml">RSS feed</a></p>
</header>
<main>
<section class="search-wrap" aria-label="Search the archive">
  <input id="archive-search" type="search" placeholder="Search issues by word or topic..."
         aria-label="Search issues">
  <p id="search-count">{n_issues} issues in the archive</p>
</section>
{cards}
<section class="subscribe">
  <h2>Get the newsletter</h2>
  <p>Get a note when new issues go out. This form is a placeholder &mdash; point it at your
     email provider&rsquo;s sign-up endpoint, or swap it for their embed code.</p>
  <form action="#" method="get">
    <input type="email" name="email" placeholder="name@example.com" aria-label="Email address">
    <button type="submit">Subscribe</button>
  </form>
  <p class="placeholder-note">Intentionally inert until you wire it up; no data leaves this page.</p>
</section>
</main>
<footer class="site-foot">
<p>Built from a folder of newsletter issues with <a href="https://github.com/AsdaleDynamics/newsletter-archive-site-template">newsletter-archive-site-template</a>.</p>
<p>RSS-friendly: every issue also appears in <a href="feed.xml">feed.xml</a>.</p>
</footer>
<script src="assets/search.js"></script>
</body>
</html>
"""

CARD = """<article class="card">
<h2><a href="issues/{slug}.html">{title}</a></h2>
<p class="meta"><time datetime="{date_iso}">{date_human}</time></p>
{topics_html}{summary_html}
</article>
"""

PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{page_title}</title>
<meta name="description" content="{desc}">
<link rel="stylesheet" href="{prefix}assets/style.css">
<link rel="alternate" type="application/rss+xml" title="{site_title} RSS" href="{prefix}feed.xml">
</head>
<body>
<header class="site-head">
  <h1><a href="{prefix}">{site_title}</a></h1>
  <p class="tagline">Issue archive</p>
  <p class="feedline"><a href="{prefix}feed.xml">RSS feed</a> &middot; <a href="{prefix}index.html">All issues</a></p>
</header>
<main>
<a class="backlink" href="{prefix}index.html">&larr; All issues</a>
<article class="issue">
<h1>{title}</h1>
<p class="meta"><time datetime="{date_iso}">{date_human}</time> &middot; <a href="{prefix}feed.xml">subscribe via RSS</a></p>
{topics_html}
<hr>
{body}
</article>
</main>
<footer class="site-foot">
<p>Printing? This page is styled to print clean &mdash; just use your reader&rsquo;s print menu.</p>
<p>Built with <a href="https://github.com/AsdaleDynamics/newsletter-archive-site-template">newsletter-archive-site-template</a>.</p>
</footer>
</body>
</html>
"""


def topics_html(topics: list[str]) -> str:
    if not topics:
        return ""
    lis = "".join("<li>%s</li>" % escape(t) for t in topics)
    return '<ul class="topics">%s</ul>' % lis


def issue_body(it: dict) -> str:
    text = it["src"].read_text(encoding="utf-8")
    if it["src"].suffix.lower() in (".md", ".markdown"):
        return markdown_to_html(text)
    return text


# --------------------------------------------------------------------------- #
# Build
# --------------------------------------------------------------------------- #

def rss_date(d: dt.date) -> str:
    return d.strftime("%a, %d %b %Y 12:00:00 GMT")


def build(issues_dir: Path, out_dir: Path, site_title: str, tagline: str,
          base_url: str) -> None:
    issues = load_issues(issues_dir)

    if out_dir.exists():
        shutil.rmtree(out_dir)
    (out_dir / "issues").mkdir(parents=True)
    assets = out_dir / "assets"
    assets.mkdir(parents=True)
    (assets / "style.css").write_text(STYLESHEET + "\n", encoding="utf-8")
    (assets / "search.js").write_text(SEARCH_JS + "\n", encoding="utf-8")

    # index.html — issue cards (newest first), search box, subscribe placeholder
    cards = []
    for it in issues:
        cards.append(CARD.format(
            slug=attr(it["slug"]),
            title=escape(it["title"]),
            date_iso=attr(it["date_iso"]),
            date_human=escape(human_date(it["date"])),
            topics_html=topics_html(it["topics"]),
            summary_html=('<p class="summary">%s</p>' % escape(it["summary"])) if it["summary"] else "",
        ))
    (out_dir / "index.html").write_text(INDEX.format(
        title=escape(site_title),
        desc=attr(tagline),
        tagline=escape(tagline),
        n_issues=len(issues),
        cards="\n".join(cards),
    ), encoding="utf-8")

    # One print-clean page per issue
    for it in issues:
        it["body"] = issue_body(it)
        (out_dir / "issues" / (it["slug"] + ".html")).write_text(PAGE.format(
            page_title=escape("%s: %s" % (site_title, it["title"])),
            desc=attr(it["summary"] or it["title"]),
            prefix="",
            site_title=escape(site_title),
            title=escape(it["title"]),
            date_iso=attr(it["date_iso"]),
            date_human=escape(human_date(it["date"])),
            topics_html=topics_html(it["topics"]),
            body=it["body"],
        ), encoding="utf-8")

    # RSS 2.0 feed (RSS entry links need an absolute base URL)
    feed_base = base_url.rstrip("/") + "/"
    items = []
    for it in issues:
        link = feed_base + "issues/" + it["slug"] + ".html"
        excerpt = re.sub(r"<[^>]+>", " ", it["body"])
        excerpt = re.sub(r"\s+", " ", excerpt).strip()
        items.append(
            "<item><title>%s</title><link>%s</link><guid isPermaLink=\"true\">%s</guid>"
            "<pubDate>%s</pubDate><description>%s</description></item>" % (
                escape(it["title"]),
                attr(link),
                attr(link),
                escape(rss_date(it["date"])),
                escape((it["summary"] or excerpt)[:500]),
            )
        )
    now = dt.datetime.now(dt.timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")
    feed = ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<rss version="2.0"><channel><title>%s</title><link>%s</link>'
            '<description>%s</description><lastBuildDate>%s</lastBuildDate>'
            '%s</channel></rss>' % (
                escape(site_title), attr(feed_base), attr(tagline), escape(now), "".join(items)))
    (out_dir / "feed.xml").write_text(feed + "\n", encoding="utf-8")

    print("Built %d issue page(s) + index.html + feed.xml into %s" % (len(issues), out_dir))


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a static newsletter archive site.",
                                     epilog="See README.md for the expected folder layout.")
    parser.add_argument("--issues", default="issues", help="folder with issue files + index.csv")
    parser.add_argument("--out", default="site", help="output folder for the static site")
    parser.add_argument("--title", default="The Newsletter Archive", help="site title")
    parser.add_argument("--tagline", default="Plain-English notes from the archive.",
                        help="short tagline shown on the index page")
    parser.add_argument("--base-url", default="https://example.org/newsletter/",
                        help="site root URL used for RSS links (set to your GitHub Pages URL)")
    args = parser.parse_args()
    build(Path(args.issues), Path(args.out), args.title, args.tagline, args.base_url)


if __name__ == "__main__":
    main()
