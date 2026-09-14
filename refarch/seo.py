"""Finish the built report's `<head>`, and write robots.txt and sitemap.xml.

Evidence generates most of a page's head from the page's own frontmatter -- `title`,
`description` and `og.image` all land correctly without help. Three things it will not do, and
this module does after `evidence build` has run:

* **Absolute URLs.** `og:image`, `og:url` and `<link rel="canonical">` have to carry a scheme
  and a host or a scraper cannot resolve them, and nothing inside the build knows what host it
  will be served from. Evidence emits `og:image` as the root-relative path from the frontmatter.
* **Site-wide constants.** `og:site_name`, `og:type`, `og:locale` and the image alt text are the
  same on all six pages, so they do not belong in six frontmatter blocks.
* **`twitter:site`.** Evidence hardcodes `@evidence_dev` in its preprocessor, with no config for
  it, so every share of this site was attributed to the framework's account. JB Analytica has no
  X account -- jbanalytica.com deliberately sets the other twitter tags and omits this one -- so
  the tag is removed rather than replaced.

Rewriting built HTML is not free of cost: it runs after the framework and has to be kept in step
with it. It is done here rather than by patching `@evidence-dev/preprocess` in node_modules,
because node_modules is not committed and `npm ci` would silently drop the patch on the next
clean run -- the report would keep building and quietly go back to being wrong.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

SITE_URL = "https://reference.jbanalytica.com"
SITE_NAME = "JB Analytica"
LOCALE = "en_GB"

# Appended to every page title except the home page, whose own title is already a full sentence.
TITLE_SUFFIX = "JB Analytica Reference Architecture"

OG_IMAGE_ALT = (
    "One year of orders, two defensible revenue figures: 346,644 euro booked against "
    "329,441 euro realised. JB Analytica reference architecture."
)

_TITLE = re.compile(r"<title>(.*?)</title>", re.S)
_TWITTER_SITE = re.compile(r'\s*<meta name="twitter:site"[^>]*>')
_IMAGE_META = re.compile(
    r'(<meta (?:property="og:image"|name="twitter:image") content=")(/[^"]*)(")'
)


def _route(page: Path, build_dir: Path) -> str:
    """The URL path a built file is served at, with the trailing slash GitHub Pages redirects to.

    Evidence's static adapter writes `<page>/index.html`, and Pages 301s `/performance` to
    `/performance/`. The canonical URL has to be the destination of that redirect, not its
    source, or every page advertises a URL that does not serve it.
    """
    relative = page.relative_to(build_dir).parent.as_posix()
    return "/" if relative == "." else f"/{relative}/"


def _head_additions(url: str, image_url: str) -> str:
    return "".join(
        f"\n\t\t{tag}"
        for tag in (
            f'<link rel="canonical" href="{url}">',
            f'<meta property="og:url" content="{url}">',
            f'<meta property="og:site_name" content="{SITE_NAME}">',
            '<meta property="og:type" content="website">',
            f'<meta property="og:locale" content="{LOCALE}">',
            f'<meta property="og:image:secure_url" content="{image_url}">',
            '<meta property="og:image:width" content="1200">',
            '<meta property="og:image:height" content="630">',
            f'<meta property="og:image:alt" content="{OG_IMAGE_ALT}">',
            f'<meta name="twitter:image:alt" content="{OG_IMAGE_ALT}">',
        )
    )


def finalise(build_dir: Path, site_url: str = SITE_URL, base_path: str | None = None) -> list[str]:
    """Rewrite every built page's head, then write robots.txt and sitemap.xml.

    Returns the routes found, so a caller (and the tests) can assert on what was published.
    """
    origin = site_url.rstrip("/") + (base_path or "").rstrip("/")
    pages = sorted(build_dir.rglob("index.html"))
    if not pages:
        raise FileNotFoundError(f"No built pages under {build_dir}. Run `refarch report` first.")

    routes = []
    for page in pages:
        route = _route(page, build_dir)
        routes.append(route)
        url = f"{origin}{route}"
        html = page.read_text(encoding="utf-8")

        # Everything below edits the head only. The page title is also rendered as the <h1> in
        # the body, and the suffix belongs in the browser tab and the search result, not on the
        # page itself.
        head, sep, body = html.partition("</head>")
        if not sep:
            raise ValueError(f"{page} has no </head>; the Evidence build output changed shape.")

        head = _TWITTER_SITE.sub("", head)
        head = _IMAGE_META.sub(lambda m: f"{m.group(1)}{origin}{m.group(2)}{m.group(3)}", head)
        if route != "/":
            head = _TITLE.sub(
                lambda m: f"<title>{m.group(1).strip()} · {TITLE_SUFFIX}</title>", head, count=1
            )

        image_url = f"{origin}/og.png"
        page.write_text(f"{head}{_head_additions(url, image_url)}\n\t{sep}{body}", encoding="utf-8")

    (build_dir / "robots.txt").write_text(
        f"User-agent: *\nAllow: /\n\nSitemap: {origin}/sitemap.xml\n", encoding="utf-8"
    )
    today = date.today().isoformat()
    urls = "\n".join(
        f"  <url>\n    <loc>{origin}{route}</loc>\n    <lastmod>{today}</lastmod>\n  </url>"
        for route in routes
    )
    (build_dir / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{urls}\n"
        "</urlset>\n",
        encoding="utf-8",
    )
    return routes
