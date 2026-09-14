"""Invariants for the published report.

This site is the first thing most people see of this project, and it is served from a domain
rather than from a repository, so a mistake here is public in a way a broken model is not.
Every check below is a bug that actually happened while these pages were being written.
"""

from __future__ import annotations

import re

import yaml

from refarch.config import DBT_DIR, EVIDENCE_DIR

PAGES = EVIDENCE_DIR / "pages"
STATIC = EVIDENCE_DIR / "static"

# A markdown link, excluding image/asset references, which start with `!`.
PAGE_LINK = re.compile(r"(?<!!)\[[^\]]*\]\((/[^)]*)\)")
ASSET_LINK = re.compile(r"!\[[^\]]*\]\((/[^)]*)\)")
# An inline <Value /> followed straight by punctuation, which renders with a space before it.
VALUE_THEN_PUNCTUATION = re.compile(r"<Value[^>]*/>\s*[.,;:!?)]")


def _markdown_pages() -> list:
    pages = sorted(PAGES.glob("*.md"))
    assert pages, f"no Evidence pages found in {PAGES}"
    return pages


def test_every_internal_link_resolves() -> None:
    """A root-relative link has to name a page that exists.

    Renaming a page is a two-line change and silently orphans every link into it -- on a site
    whose landing page exists to send readers to the other five.
    """
    routes = {"/"} | {f"/{p.stem}" for p in _markdown_pages() if p.stem != "index"}

    for page in _markdown_pages():
        for link in PAGE_LINK.findall(page.read_text()):
            assert link in routes, (
                f"{page.name} links to {link}, which is not a page. Available: {sorted(routes)}"
            )


def test_every_asset_reference_exists() -> None:
    """An asset a page points at has to be in static/, or it 404s once published.

    Evidence serves `evidence/static/x` at `/x`, and a missing one fails silently: the page
    renders with a broken image and the build reports nothing.
    """
    for page in _markdown_pages():
        for asset in ASSET_LINK.findall(page.read_text()):
            assert (STATIC / asset.lstrip("/")).exists(), (
                f"{page.name} references {asset}, which is not in {STATIC}"
            )


def test_no_value_component_starts_a_line() -> None:
    """A `<Value>` used mid-sentence must stay mid-line.

    Markdown treats a component at the start of a line as its own block, so rewrapping a
    paragraph so a line begins with `<Value ... />` splits that paragraph into three around it.
    It renders as a stray fragment, and nothing errors.
    """
    for page in _markdown_pages():
        for number, line in enumerate(page.read_text().splitlines(), start=1):
            assert not line.lstrip().startswith("<Value"), (
                f"{page.name}:{number} starts a line with <Value>, which splits the paragraph. "
                "Rewrap so it sits mid-line."
            )


def test_no_value_component_is_followed_by_punctuation() -> None:
    """An inline `<Value />` must be followed by a word, never by a comma or full stop.

    Evidence's component puts the formatted number on its own line inside its `<span>`, so the
    markup collapses to a trailing space *inside* the span. Follow it with punctuation and the
    page reads "was EUR 346,644 , so" -- with the gap before the comma. There is no prop for
    it and CSS cannot strip a text node's trailing space, so the sentence has to be worded so
    a word comes next.
    """
    for page in _markdown_pages():
        for number, line in enumerate(page.read_text().splitlines(), start=1):
            match = VALUE_THEN_PUNCTUATION.search(line)
            assert match is None, (
                f"{page.name}:{number} follows a <Value> with {match.group()[-1]!r}, which "
                "renders a space before it. Reword so a word follows the value."
            )


def _frontmatter(page) -> dict:
    """The page's YAML frontmatter. Evidence reads the same block for its head tags."""
    text = page.read_text()
    assert text.startswith("---\n"), f"{page.name} has no frontmatter"
    return yaml.safe_load(text.split("---", 2)[1])


def test_every_page_has_a_description() -> None:
    """Without one, a share of the page renders as a title over an empty grey box.

    Evidence only emits `description`, `og:description` and `twitter:description` when the
    frontmatter carries a description -- and it emits nothing at all, rather than warning, when
    it does not. This site exists to be linked to, so a page without one is a broken share.
    """
    for page in _markdown_pages():
        description = _frontmatter(page).get("description", "")
        assert description.strip(), (
            f"{page.name} has no frontmatter `description`; sharing it renders an empty card."
        )


def test_every_og_image_exists() -> None:
    """The social card is an asset like any other, and 404s just as silently."""
    for page in _markdown_pages():
        image = (_frontmatter(page).get("og") or {}).get("image")
        assert image, f"{page.name} has no og.image, so a share of it carries no card image"
        assert (STATIC / image.lstrip("/")).exists(), (
            f"{page.name} points og.image at {image}, which is not in {STATIC}"
        )


def test_no_page_charts_a_raw_enum_column() -> None:
    """A chart axis or table column must name a mart's label column, not its raw key.

    The marts are the semantic layer, and what a value is *called* is part of its definition --
    so `dim_products` carries `roast_label` beside `roast_level` and the page selects the label.
    Point a chart at the raw column and the site shows `mobile_app` to a business reader while
    claiming on /architecture that it does no such thing.

    The protected set is not listed here. Each raw enum in the marts schema declares the label
    column that stands in for it (`meta.display_label`), so adding an enum protects it on the
    same line that documents it, and a pairing that names a column which does not exist fails
    too -- a typo there would otherwise switch the check off silently for that column.
    """
    schema = yaml.safe_load((DBT_DIR / "models" / "marts" / "_marts__models.yml").read_text())
    protected, defined = {}, set()
    for model in schema["models"]:
        for column in model.get("columns", []):
            defined.add(column["name"])
            label = (column.get("meta") or {}).get("display_label")
            if label:
                protected[column["name"]] = label
    assert protected, "no meta.display_label pairings found; the marts schema changed shape"
    missing = {raw: label for raw, label in protected.items() if label not in defined}
    assert not missing, f"display_label names a column that no mart defines: {missing}"

    for page in _markdown_pages():
        for number, line in enumerate(page.read_text().splitlines(), start=1):
            for column in re.findall(r"\b(?:x|id)=(\w+)", line):
                assert column not in protected, (
                    f"{page.name}:{number} renders the raw enum {column!r}. Chart "
                    f"{protected[column]!r} instead -- see docs/architecture/README.md."
                )
