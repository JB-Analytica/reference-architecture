"""Invariants for the published report.

This site is the first thing most people see of this project, and it is served from a domain
rather than from a repository, so a mistake here is public in a way a broken model is not.
Every check below is a bug that actually happened while these pages were being written.
"""

from __future__ import annotations

import re

from refarch.config import EVIDENCE_DIR

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
