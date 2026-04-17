"""Phase 63 header favicon (HDR-06) tests.

Verifies SVG primary <link>, raster fallback bundle existence and sizing,
and header icon <img> presence + structural invariants. Closes Phase 60 D-05.
"""

from __future__ import annotations

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


def test_favicon_bundle_exists():
    """HDR-06: Full favicon bundle (SVG master + raster fallbacks) present in static dir."""
    for name in FAVICON_BUNDLE:
        assert (STATIC_DIR / name).exists(), f"missing favicon asset: {name}"


def test_favicon_files_non_empty():
    """HDR-06: Every favicon bundle file is non-empty (catches zero-byte drops)."""
    for name in FAVICON_BUNDLE:
        path = STATIC_DIR / name
        assert path.stat().st_size > 0, f"favicon asset is empty: {name}"


def test_favicon_svg_linked_as_primary_in_base_html():
    """HDR-06: SVG <link> is declared and precedes the .ico fallback."""
    base_html = (TEMPLATES_DIR / "base.html").read_text()
    assert 'type="image/svg+xml"' in base_html
    assert "favicon.svg" in base_html
    svg_idx = base_html.index("favicon.svg")
    ico_idx = base_html.index("favicon.ico")
    assert svg_idx < ico_idx, "SVG favicon link must precede .ico fallback"


def test_header_icon_img_present_in_base_html():
    """HDR-06: Header contains an <img> referencing favicon.svg at w-6 h-6 sizing."""
    base_html = (TEMPLATES_DIR / "base.html").read_text()
    assert "<img" in base_html
    # Quoting can be ' or " depending on Jinja output; accept either.
    assert "path='favicon.svg'" in base_html or 'path="favicon.svg"' in base_html
    assert "w-6 h-6" in base_html


def test_header_icon_subflex_uses_gap_2():
    """HDR-06 / D-08, D-09: icon+text live in an inner flex gap-2 and icon precedes text."""
    base_html = (TEMPLATES_DIR / "base.html").read_text()
    assert "flex items-center gap-2" in base_html
    # The new <img> must appear before the Triggarr logo span in file order.
    img_idx = base_html.index("<img")
    logo_idx = base_html.index(">Triggarr<")
    assert img_idx < logo_idx, "favicon <img> must precede the Triggarr logo span"


def test_outer_left_zone_preserves_gap_3():
    """D-08 invariant: outer left-zone flex keeps gap-3 + w-64 shrink-0 (version-badge spacing)."""
    base_html = (TEMPLATES_DIR / "base.html").read_text()
    assert "flex items-center gap-3 w-64 shrink-0" in base_html
