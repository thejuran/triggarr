"""Phase 63 header favicon (HDR-06) tests.

Verifies SVG primary <link>, raster fallback bundle existence and sizing,
and header icon <img> presence + structural invariants. Closes Phase 60 D-05.
"""

from __future__ import annotations

import re

import pytest

from triggarr.web.routes import STATIC_DIR

TEMPLATES_DIR = STATIC_DIR.parent / "templates"

FAVICON_BUNDLE = (
    "favicon.svg",
    "favicon.ico",
    "favicon-16x16.png",
    "favicon-32x32.png",
    "apple-touch-icon.png",
    "android-chrome-192x192.png",
    "android-chrome-512x512.png",
)

_IMG_TAG_RE = re.compile(r"<img\b[^>]*>", re.DOTALL)


@pytest.fixture(scope="module")
def base_html() -> str:
    return (TEMPLATES_DIR / "base.html").read_text(encoding="utf-8")


def _favicon_img_matches(base_html: str) -> list[re.Match[str]]:
    """Return every <img> tag in base.html whose src references favicon.svg."""
    return [m for m in _IMG_TAG_RE.finditer(base_html) if "favicon.svg" in m.group()]


def test_favicon_bundle_exists():
    """HDR-06: Full favicon bundle (SVG master + raster fallbacks) present in static dir."""
    for name in FAVICON_BUNDLE:
        assert (STATIC_DIR / name).exists(), f"missing favicon asset: {name}"


def test_favicon_files_non_empty():
    """HDR-06: Every favicon bundle file is non-empty (catches zero-byte drops)."""
    for name in FAVICON_BUNDLE:
        path = STATIC_DIR / name
        assert path.stat().st_size > 0, f"favicon asset is empty: {name}"


def test_favicon_svg_linked_as_primary_in_base_html(base_html: str):
    """HDR-06: SVG <link> is declared and precedes the .ico fallback."""
    assert 'type="image/svg+xml"' in base_html
    assert "favicon.svg" in base_html
    svg_idx = base_html.index("favicon.svg")
    ico_idx = base_html.index("favicon.ico")
    assert svg_idx < ico_idx, "SVG favicon link must precede .ico fallback"


def test_header_icon_img_present_in_base_html(base_html: str):
    """HDR-06: Header has an <img> referencing favicon.svg at w-6 h-6 with decorative alt."""
    favicon_imgs = _favicon_img_matches(base_html)
    assert favicon_imgs, "no <img> referencing favicon.svg found in base.html"
    matching = [m for m in favicon_imgs if "w-6 h-6" in m.group() and 'alt=""' in m.group()]
    assert matching, (
        "favicon <img> must use w-6 h-6 sizing (D-07) and decorative alt=\"\" (D-06). "
        f"favicon <img> tags found: {[m.group() for m in favicon_imgs]}"
    )


def test_header_icon_subflex_uses_gap_2(base_html: str):
    """HDR-06 / D-08, D-09: icon+text live in an inner flex gap-2 wrapper; icon precedes text."""
    favicon_imgs = _favicon_img_matches(base_html)
    assert favicon_imgs, "no <img> referencing favicon.svg found"
    img_idx = favicon_imgs[0].start()
    logo_idx = base_html.index(">Triggarr<")
    assert img_idx < logo_idx, "favicon <img> must precede the Triggarr logo span"
    # Scope to the wrapper <div> so nav link <a class="... gap-2 ..."> can't trivially satisfy this.
    wrapper = '<div class="flex items-center gap-2">'
    wrapper_idx = base_html.rfind(wrapper, 0, img_idx)
    assert wrapper_idx != -1, f"favicon <img> must sit inside a {wrapper!r} sub-flex"


def test_outer_left_zone_preserves_gap_3(base_html: str):
    """D-08 invariant: outer left-zone flex keeps gap-3 + w-64 shrink-0 (version-badge spacing)."""
    assert "flex items-center gap-3 w-64 shrink-0" in base_html
