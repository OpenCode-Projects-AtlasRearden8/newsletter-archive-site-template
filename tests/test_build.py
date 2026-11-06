import csv
import importlib.util
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session")
def build_module():
    spec = importlib.util.spec_from_file_location("build", REPO / "build.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def built(tmp_path, build_module):
    """Build the sample issues into a tmp dir; return the site Path."""
    out = tmp_path / "site"
    build_module.build(REPO / "issues", out,
                       site_title="The Plain English AI Letter",
                       tagline="A friendly AI newsletter, archived.",
                       base_url="https://example.org/newsletter/")
    return out


def csv_titles():
    with (REPO / "issues" / "index.csv").open(newline="", encoding="utf-8") as fh:
        return [row["title"] for row in csv.DictReader(fh) if row.get("file")]


def csv_rows():
    with (REPO / "issues" / "index.csv").open(newline="", encoding="utf-8") as fh:
        return [row for row in csv.DictReader(fh) if row.get("file")]


# --------------------------------------------------------------------------
# Unit tests: helpers and the small Markdown converter
# --------------------------------------------------------------------------

def test_markdown_headings_and_emphasis(build_module):
    html_out = build_module.markdown_to_html(
        "# Title\n\nSome **bold** and *soft* text.\n\n## Sub"
    )
    assert "<h1>Title</h1>" in html_out
    assert "<strong>bold</strong>" in html_out
    assert "<em>soft</em>" in html_out
    assert "<h2>Sub</h2>" in html_out


def test_markdown_lists_and_code_fence(build_module):
    html_out = build_module.markdown_to_html(
        "- one\n- two\n\n```python\nprint(1)\n```\n\n1. first\n2. second\n"
    )
    assert "<ul>" in html_out and "<li>one</li>" in html_out and "<li>two</li>" in html_out
    assert "<pre><code>print(1)" in html_out
    assert "<ol>" in html_out and "<li>first</li>" in html_out and "<li>second</li>" in html_out


def test_markdown_link_and_inline_code(build_module):
    html_out = build_module.markdown_to_html(
        "See [the docs](https://example.org) and run `pip list`.\n"
    )
    assert '<a href="https://example.org">the docs</a>' in html_out
    assert "<code>pip list</code>" in html_out


def test_markdown_escapes_html_in_md_source(build_module):
    html_out = build_module.markdown_to_html("Tell <script>alert(1)</script> a cousin?\n")
    assert "<script>" not in html_out
    assert "&lt;script&gt;" in html_out


def test_markdown_blockquote(build_module):
    html_out = build_module.markdown_to_html("> quoted text here\n")
    assert html_out == "<blockquote>quoted text here</blockquote>"


def test_slugify(build_module):
    assert build_module.slugify("Hello, World! (v2)") == "hello-world-v2"
    assert build_module.slugify("///") == "issue"


def test_duplicate_titles_get_unique_slugs(built: Path):
    pages = {p.name for p in (built / "issues").glob("*.html")}
    assert len(pages) == len(csv_rows())


# --------------------------------------------------------------------------
# End-to-end: full build of the sample folder
# --------------------------------------------------------------------------

def test_build_creates_expected_files(built: Path):
    index = built / "index.html"
    feed = built / "feed.xml"
    assert index.is_file()
    assert feed.is_file()
    assert (built / "assets" / "style.css").is_file()
    assert (built / "assets" / "search.js").is_file()


def test_index_has_one_card_per_issue(built: Path):
    text = (built / "index.html").read_text(encoding="utf-8")
    n = len(csv_rows())
    assert text.count('<article class="card">') == n
    assert text.count('<h2><a href="issues/') == n


def test_index_has_search_box_and_count(built: Path):
    text = (built / "index.html").read_text(encoding="utf-8")
    assert 'id="archive-search"' in text
    assert 'id="search-count"' in text
    assert '<script src="assets/search.js"></script>' in text
    assert (built / "assets" / "search.js").read_text(encoding="utf-8").startswith("(function")


def test_index_has_subscribe_placeholder(built: Path):
    text = (built / "index.html").read_text(encoding="utf-8")
    assert "subscribe" in text.lower()
    assert 'type="email"' in text
    assert "placeholder-note" in text


def test_index_links_feed_and_stylesheet(built: Path):
    text = (built / "index.html").read_text(encoding="utf-8")
    assert '<a href="feed.xml">RSS feed</a>' in text
    assert 'href="assets/style.css"' in text


def test_index_cards_show_dates_and_topics(built: Path):
    text = (built / "index.html").read_text(encoding="utf-8")
    for row in csv_rows():
        assert row["title"] in text
        assert 'datetime="%s"' % row["date"] in text
        for topic in row["topics"].split(";"):
            assert topic.strip() in text


def test_index_cards_newest_first(built: Path):
    text = (built / "index.html").read_text(encoding="utf-8")
    positions = [text.index(t) for t in csv_titles()]
    assert positions == sorted(positions, reverse=True), (
        "cards are not ordered newest first"
    )


def test_issue_pages_exist_with_slugs(built: Path, build_module):
    expected = {it["slug"] + ".html" for it in build_module.load_issues(REPO / "issues")}
    actual = {p.name for p in (built / "issues").glob("*.html")}
    assert actual == expected


def test_issue_page_renders_markdown_issue(built: Path):
    page = (built / "issues" / "ai-coding-tools-you-can-use-free-right-now.html").read_text(encoding="utf-8")
    assert "<h1>AI Coding Tools You Can Use Free Right Now</h1>" in page
    assert "<pre><code>" in page and "print(add(2, 3))" in page
    assert "<ol>" in page and "<li>" in page
    assert "<time datetime=\"2026-02-02\">" in page


def test_issue_page_passes_html_issue_through(built: Path):
    page = (built / "issues" / "running-ai-on-your-own-computer.html").read_text(encoding="utf-8")
    assert "<blockquote>Suggested first prompt" in page
    assert "nothing leaves your" in page
    assert "&lt;" not in page.split("nothing")[0]


def test_issue_page_is_print_clean_and_styled(built: Path):
    page = (built / "issues" / "welcome-to-the-plain-english-ai-letter.html").read_text(encoding="utf-8")
    assert 'href="assets/style.css"' in page
    assert "@media print" in (built / "assets" / "style.css").read_text(encoding="utf-8")
    assert 'href="index.html"' in page           # back link works from subfolder
    assert "{prefix}" not in page               # all template placeholders filled


def test_every_template_placeholder_is_fulfilled(built: Path):
    for page in built.rglob("*.html"):
        text = page.read_text(encoding="utf-8")
        assert "{" not in text.replace("&#123;", ""), "unfilled placeholder in %s" % page
        assert "None" not in text


def test_feed_is_well_formed_rss(built: Path):
    root = ET.fromstring((built / "feed.xml").read_text(encoding="utf-8"))
    assert root.tag == "rss"
    assert root.get("version") == "2.0"
    channel = root.find("channel")
    titles = [item.findtext("title") for item in channel.findall("item")]
    assert titles == list(reversed(csv_titles()))
    assert len(titles) == len(csv_rows())
    for item in channel.findall("item"):
        link = item.findtext("link")
        assert link.startswith("https://example.org/newsletter/issues/")
        assert item.findtext("pubDate")
        assert item.findtext("description")


# --------------------------------------------------------------------------
# Error handling: bad CSVs fail loudly
# --------------------------------------------------------------------------

@pytest.mark.parametrize("bad_csv,fixture_files,match", [
    ("file,date\nonly.md\n", [], "missing column"),
    ("file,date,title\nmissing.md,2026-01-01,T\n", [], "missing file"),
    ("file,date,title\na.md,not-a-date,T\n", ["a.md"], "bad date"),
])
def test_load_issues_rejects_bad_index(build_module, tmp_path, bad_csv, fixture_files, match):
    issues_dir = tmp_path / "issues"
    issues_dir.mkdir()
    (issues_dir / "index.csv").write_text(bad_csv, encoding="utf-8")
    for name in fixture_files:
        (issues_dir / name).write_text("# x\n", encoding="utf-8")
    with pytest.raises(SystemExit) as excinfo:
        build_module.load_issues(issues_dir)
    assert match in str(excinfo.value)


def test_load_issues_requires_index_csv(build_module, tmp_path):
    empty = tmp_path / "issues"
    empty.mkdir()
    with pytest.raises(SystemExit) as excinfo:
        build_module.load_issues(empty)
    assert "not found" in str(excinfo.value)
