"""Embed the JB Analytica brand faces into a board dbt Charts has already rendered.

dbt Charts vendors its own families in a closed registry (`dbt_charts/core/fonts.py`:
"adding a font means adding a row") and offers no hook for a `@font-face`. So a board
that asks for `Poppins` renders `font-family: Poppins` with nothing behind it and falls
back to whatever the viewer happens to have. This puts the real bytes behind the name.

It rewrites generated output, which is why it is a separate step rather than something
hidden inside `dct render`: the rendered file stays exactly what dbt Charts produced,
plus one `<style>` block appended to `<head>`.

Known limit -- dbt Charts measures text with the metrics of the family it thinks it is
painting (Inter), then the browser paints these. Poppins is the wider face, so a long
title or axis label can sit wider than the box that was measured for it. Fine for the
headings and prose here; check any dense chart before trusting it.

    python embed_brand_fonts.py renders/webshop.html
"""

from __future__ import annotations

import base64
import sys
from pathlib import Path

# Weights the board actually uses. The site ships 400-800; pulling in all ten files
# would add ~200 KB of woff2 to a self-contained page for faces nothing asks for.
WEIGHTS = (400, 500, 600, 700)

# Lifted from evidence/app.css, which lifted them from the website's assets/css/style.css.
UNICODE_RANGES = {
    "latin": (
        "U+0000-00FF, U+0131, U+0152-0153, U+02BB-02BC, U+02C6, U+02DA, U+02DC, U+0304, "
        "U+0308, U+0329, U+2000-206F, U+20AC, U+2122, U+2191, U+2193, U+2212, U+2215, "
        "U+FEFF, U+FFFD"
    ),
    "latin-ext": (
        "U+0100-02BA, U+02BD-02C5, U+02C7-02CC, U+02CE-02D7, U+02DD-02FF, U+0304, U+0308, "
        "U+0329, U+1D00-1DBF, U+1E00-1E9F, U+1EF2-1EFF, U+2020, U+20A0-20AB, U+20AD-20C0, "
        "U+2113, U+2C60-2C7F, U+A720-A7FF"
    ),
}

FONT_DIR = Path(__file__).resolve().parent.parent / "evidence" / "static" / "fonts"
MARKER = "<!-- jba-brand-fonts -->"


def font_face_css() -> str:
    """One @font-face per weight per subset, with the woff2 inlined as a data URI.

    Inlined rather than linked so the page stays the single self-contained file that
    makes it hostable from any web root -- or none.
    """
    rules = []
    for weight in WEIGHTS:
        for subset, unicode_range in UNICODE_RANGES.items():
            path = FONT_DIR / f"poppins-{weight}-{subset}.woff2"
            if not path.exists():
                raise SystemExit(f"missing brand face: {path}")
            encoded = base64.b64encode(path.read_bytes()).decode("ascii")
            rules.append(
                "@font-face{font-family:'Poppins';font-style:normal;"
                f"font-weight:{weight};font-display:swap;"
                f"src:url(data:font/woff2;base64,{encoded}) format('woff2');"
                f"unicode-range:{unicode_range}}}"
            )
    return "\n".join(rules)


def embed(html_path: Path) -> None:
    html = html_path.read_text(encoding="utf-8")

    if MARKER in html:
        print(f"{html_path}: already embedded, nothing to do")
        return
    if "</head>" not in html:
        raise SystemExit(f"{html_path}: no </head> to append to -- is this a dct HTML render?")

    block = f"{MARKER}\n<style>\n{font_face_css()}\n</style>\n</head>"
    html_path.write_text(html.replace("</head>", block, 1), encoding="utf-8")

    size_mb = html_path.stat().st_size / 1_000_000
    print(f"{html_path}: embedded Poppins {WEIGHTS} -- now {size_mb:.1f} MB")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    embed(Path(sys.argv[1]))
