"""What the built report's `<head>` has to carry before the site is worth linking to.

These run against a fixture rather than a real build: `uv run poe check` has to pass on a fresh
clone with no `node_modules` and no `evidence/build`. The fixture reproduces the head Evidence
actually emits -- including the `twitter:site` default that is the reason this step exists -- so
a change in Evidence's output shows up here as a failing assertion rather than as a live site
quietly losing a tag.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from refarch import seo

# Trimmed from a real evidence build. The relative og:image and the @evidence_dev attribution
# are both verbatim.
EVIDENCE_HEAD = """<!doctype html>
<html lang="en">
\t<head>
\t\t<meta charset="utf-8" />
\t\t<title>{title}</title>
\t\t<meta property="og:title" content="{title}">
\t\t<meta name="twitter:card" content="summary_large_image">
\t\t<meta name="twitter:site" content="@evidence_dev">
\t\t<meta name="description" content="Something true and short.">
\t\t<meta property="og:image" content="/og.png"><meta name="twitter:image" content="/og.png">
\t</head>
\t<body><h1 class="title">{title}</h1></body>
</html>
"""


@pytest.fixture
def build(tmp_path: Path) -> Path:
    for route, title in {
        ".": "A data platform you can read, trust and build on",
        "customers": "Customers",
        "architecture": "Architecture",
    }.items():
        page = tmp_path / route / "index.html"
        page.parent.mkdir(parents=True, exist_ok=True)
        page.write_text(EVIDENCE_HEAD.format(title=title), encoding="utf-8")
    return tmp_path


def _head(build: Path, route: str) -> str:
    page = build / "index.html" if route == "/" else build / route.strip("/") / "index.html"
    return page.read_text(encoding="utf-8").split("</head>")[0]


def test_every_route_is_finalised(build: Path) -> None:
    assert sorted(seo.finalise(build)) == ["/", "/architecture/", "/customers/"]


def test_evidences_twitter_attribution_is_removed(build: Path) -> None:
    """Evidence hardcodes `@evidence_dev`, and JB Analytica has no X account to put there.

    Left alone, every share of this site credits the framework's account. jbanalytica.com sets
    the other twitter tags and deliberately omits this one, so the tag goes rather than changes.
    """
    seo.finalise(build)
    for route in ("/", "/customers/"):
        assert "twitter:site" not in _head(build, route)


def _tag_value(head: str, tag: str) -> str | None:
    """The content of one named head tag.

    Matched by name rather than by substring: `og:image` and `og:image:secure_url` carry the
    same URL, so a looser check passed happily while og:image itself was still relative.
    """
    if tag == "canonical":
        match = re.search(r'<link rel="canonical" href="([^"]*)">', head)
    else:
        match = re.search(rf'<meta (?:property|name)="{re.escape(tag)}" content="([^"]*)">', head)
    return match.group(1) if match else None


def test_social_and_canonical_urls_are_absolute(build: Path) -> None:
    """A scraper cannot resolve a root-relative URL, and nothing in the build knows the host."""
    seo.finalise(build, site_url="https://example.test")
    head = _head(build, "/customers/")
    assert _tag_value(head, "canonical") == "https://example.test/customers/"
    assert _tag_value(head, "og:url") == "https://example.test/customers/"
    assert _tag_value(head, "og:image") == "https://example.test/og.png"
    assert _tag_value(head, "twitter:image") == "https://example.test/og.png"


def test_the_site_wide_tags_are_present(build: Path) -> None:
    """Constants, so they live here rather than in six frontmatter blocks."""
    seo.finalise(build)
    head = _head(build, "/architecture/")
    assert _tag_value(head, "og:site_name") == seo.SITE_NAME
    assert _tag_value(head, "og:type") == "website"
    assert _tag_value(head, "og:locale") == seo.LOCALE
    assert _tag_value(head, "og:image:alt") == seo.OG_IMAGE_ALT
    assert _tag_value(head, "twitter:image:alt") == seo.OG_IMAGE_ALT


def test_a_base_path_is_included_in_every_url(build: Path) -> None:
    """On a project site the report sits under /<repo>, and the canonical has to say so."""
    seo.finalise(build, site_url="https://example.test", base_path="/reference-architecture")
    head = _head(build, "/customers/")
    assert _tag_value(head, "canonical") == "https://example.test/reference-architecture/customers/"
    assert _tag_value(head, "og:image") == "https://example.test/reference-architecture/og.png"


def test_titles_are_suffixed_except_on_the_home_page(build: Path) -> None:
    """`Customers` is not a search result anyone can place; the home page already reads as one."""
    seo.finalise(build)
    assert f"<title>Customers · {seo.TITLE_SUFFIX}</title>" in _head(build, "/customers/")
    assert "<title>A data platform you can read, trust and build on</title>" in _head(build, "/")


def test_the_page_title_is_not_suffixed_in_the_body(build: Path) -> None:
    """The title is also the `<h1>`. The suffix belongs in the tab, not on the page."""
    seo.finalise(build)
    body = (build / "customers" / "index.html").read_text().split("</head>")[1]
    assert '<h1 class="title">Customers</h1>' in body


def test_robots_and_sitemap_list_every_page(build: Path) -> None:
    """Both returned 404 on the live site until this step existed."""
    routes = seo.finalise(build, site_url="https://example.test")
    robots = (build / "robots.txt").read_text()
    assert "https://example.test/sitemap.xml" in robots

    sitemap = (build / "sitemap.xml").read_text()
    locations = re.findall(r"<loc>(.*?)</loc>", sitemap)
    assert locations == [f"https://example.test{route}" for route in routes]


def test_an_empty_build_is_an_error_not_a_silent_pass(tmp_path: Path) -> None:
    """Finalising nothing would publish a site with no canonical and no sitemap, quietly."""
    with pytest.raises(FileNotFoundError):
        seo.finalise(tmp_path)
