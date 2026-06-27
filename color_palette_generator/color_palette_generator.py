"""
Color Palette Generator
========================

Generates a coordinated set of colors from a single base color, using
classic color-harmony rules, and reports how readable each color is as
text on a white or black background (WCAG contrast ratio).

Inputs:
    - Base color (a hue, 0-360 degrees)
    - Harmony: how the other colors relate to the base hue
        - monochromatic  -- all colors share the base hue; only lightness varies
        - analogous      -- hues spread evenly across a narrow band next to the base hue
        - complementary  -- the base hue plus its opposite (180 degrees away)
        - triadic        -- the base hue plus two hues 120 degrees apart
    - Style: the overall saturation/lightness "mood" of the palette
        - pastel   -- light, softly saturated
        - vibrant  -- bold, highly saturated
        - muted    -- desaturated, mid-toned
        - dark     -- deep, low-lightness
    - Count: how many colors to generate (3-12)

For complementary/triadic/monochromatic, the requested count is split as
evenly as possible across the harmony's anchor hues, and within each
anchor a ladder of lightness values is generated (lightest to darkest)
while saturation stays fixed at the style's midpoint -- this keeps the
whole palette feeling cohesive rather than a random hue/lightness/
saturation scramble. For analogous, each of the N hues gets exactly one
tone at the style's midpoint, which is the same algorithm applied to a
harmony with N anchors instead of 1-3.

This tool has no dependency on any other tool in this repository and can
be copied and used entirely on its own. The core calculation has no
external dependencies (uses the standard library `colorsys` module).
"""

from __future__ import annotations

import colorsys
import random
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

HARMONIES = ("monochromatic", "analogous", "complementary", "triadic")
STYLES = ("pastel", "vibrant", "muted", "dark")

MIN_COLORS = 3
MAX_COLORS = 12
DEFAULT_COUNT = 6
DEFAULT_HARMONY = "analogous"
DEFAULT_STYLE = "pastel"

# How wide a band (in degrees) the analogous hues are spread across.
ANALOGOUS_BAND_DEGREES = 60.0

# (saturation_min, saturation_max), (lightness_min, lightness_max) per style,
# all as percentages (0-100). Lightness is what varies within an anchor's
# ladder of tones; saturation is fixed at the midpoint for every swatch.
STYLE_RANGES: dict[str, tuple[tuple[float, float], tuple[float, float]]] = {
    "pastel":  ((35.0, 55.0), (78.0, 90.0)),
    "vibrant": ((65.0, 90.0), (45.0, 60.0)),
    "muted":   ((20.0, 40.0), (55.0, 70.0)),
    "dark":    ((45.0, 70.0), (18.0, 32.0)),
}

# WCAG AA contrast threshold for normal-sized text.
WCAG_AA_THRESHOLD = 4.5


@dataclass
class PaletteRequest:
    """All user-provided inputs for a palette generation request."""

    base_hue: float          # 0-360 degrees
    harmony: str = DEFAULT_HARMONY
    style: str = DEFAULT_STYLE
    count: int = DEFAULT_COUNT


@dataclass
class ColorSwatch:
    """A single generated color, with its WCAG contrast info."""

    hex: str
    hue: float
    saturation: float
    lightness: float
    contrast_on_white: float
    contrast_on_black: float
    aa_on_white: bool
    aa_on_black: bool


@dataclass
class PaletteResult:
    """Output of a palette generation request."""

    request: PaletteRequest
    swatches: list[ColorSwatch] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Core calculation (kept free of any input()/print() so it can be reused
# from the web app, tests, or other tools in this repo).
# ---------------------------------------------------------------------------

def generate_palette(request: PaletteRequest) -> PaletteResult:
    """Generate a coordinated color palette from a `PaletteRequest`.

    Raises:
        ValueError: if harmony/style aren't recognized, or count is out
            of the supported 3-12 range.
    """
    if request.harmony not in HARMONIES:
        raise ValueError(f"Unknown harmony '{request.harmony}'. Choose from: {HARMONIES}")
    if request.style not in STYLES:
        raise ValueError(f"Unknown style '{request.style}'. Choose from: {STYLES}")
    if not (MIN_COLORS <= request.count <= MAX_COLORS):
        raise ValueError(f"count must be between {MIN_COLORS} and {MAX_COLORS}.")

    base_hue = request.base_hue % 360
    anchor_hues = _anchor_hues(base_hue, request.harmony, request.count)
    tones_per_anchor = _distribute(request.count, len(anchor_hues))

    (sat_min, sat_max), (light_min, light_max) = STYLE_RANGES[request.style]
    mid_saturation = (sat_min + sat_max) / 2

    swatches: list[ColorSwatch] = []
    for hue, n_tones in zip(anchor_hues, tones_per_anchor):
        if n_tones == 0:
            continue
        lightness_ladder = _linspace(light_max, light_min, n_tones)
        for lightness in lightness_ladder:
            swatches.append(_make_swatch(hue, mid_saturation, lightness))

    return PaletteResult(request=request, swatches=swatches)


def _anchor_hues(base_hue: float, harmony: str, count: int) -> list[float]:
    """The 'anchor' hues for a given harmony. For analogous, there are as
    many anchors as requested colors (each gets exactly one tone); for the
    others, the anchor count is fixed by the harmony's definition."""
    if harmony == "monochromatic":
        return [base_hue]
    if harmony == "complementary":
        return [base_hue, (base_hue + 180) % 360]
    if harmony == "triadic":
        return [base_hue, (base_hue + 120) % 360, (base_hue + 240) % 360]
    if harmony == "analogous":
        half_band = ANALOGOUS_BAND_DEGREES / 2
        if count == 1:
            return [base_hue]
        step = ANALOGOUS_BAND_DEGREES / (count - 1)
        return [(base_hue - half_band + i * step) % 360 for i in range(count)]
    raise ValueError(f"Unknown harmony '{harmony}'.")  # pragma: no cover


def _distribute(total: int, n_groups: int) -> list[int]:
    """Split `total` as evenly as possible across `n_groups` buckets, with
    any remainder going to the first buckets. E.g. distribute(7, 3) -> [3, 2, 2]."""
    base, remainder = divmod(total, n_groups)
    return [base + 1 if i < remainder else base for i in range(n_groups)]


def _linspace(start: float, stop: float, n: int) -> list[float]:
    """`n` evenly spaced values from `start` to `stop` (inclusive). For
    n == 1, returns the midpoint -- a single representative tone."""
    if n == 1:
        return [(start + stop) / 2]
    step = (stop - start) / (n - 1)
    return [start + i * step for i in range(n)]


def _make_swatch(hue: float, saturation: float, lightness: float) -> ColorSwatch:
    """Build a ColorSwatch (hex + WCAG contrast info) from HSL values."""
    hex_code = _hsl_to_hex(hue, saturation, lightness)
    rgb = _hex_to_rgb_unit(hex_code)
    contrast_white = _contrast_ratio(rgb, (1.0, 1.0, 1.0))
    contrast_black = _contrast_ratio(rgb, (0.0, 0.0, 0.0))
    return ColorSwatch(
        hex=hex_code,
        hue=round(hue, 1),
        saturation=round(saturation, 1),
        lightness=round(lightness, 1),
        contrast_on_white=round(contrast_white, 2),
        contrast_on_black=round(contrast_black, 2),
        aa_on_white=contrast_white >= WCAG_AA_THRESHOLD,
        aa_on_black=contrast_black >= WCAG_AA_THRESHOLD,
    )


# ---------------------------------------------------------------------------
# Color math (HSL <-> hex, WCAG contrast)
# ---------------------------------------------------------------------------

def _hsl_to_hex(hue: float, saturation: float, lightness: float) -> str:
    """Convert HSL (hue in degrees 0-360, saturation/lightness in
    percent 0-100) to a '#rrggbb' hex string."""
    h = (hue % 360) / 360
    s = max(0.0, min(100.0, saturation)) / 100
    l = max(0.0, min(100.0, lightness)) / 100
    # NOTE: colorsys uses HLS (hue, lightness, saturation) parameter order.
    r, g, b = colorsys.hls_to_rgb(h, l, s)
    return "#{:02x}{:02x}{:02x}".format(round(r * 255), round(g * 255), round(b * 255))


def _hex_to_rgb_unit(hex_code: str) -> tuple[float, float, float]:
    """Convert a '#rrggbb' hex string to (r, g, b) in the 0-1 range."""
    hex_code = hex_code.lstrip("#")
    r = int(hex_code[0:2], 16) / 255
    g = int(hex_code[2:4], 16) / 255
    b = int(hex_code[4:6], 16) / 255
    return (r, g, b)


def _relative_luminance(rgb: tuple[float, float, float]) -> float:
    """WCAG relative luminance of an sRGB color (components in 0-1)."""
    def linearize(c: float) -> float:
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (linearize(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _contrast_ratio(rgb_a: tuple[float, float, float], rgb_b: tuple[float, float, float]) -> float:
    """WCAG contrast ratio between two sRGB colors (1.0 to 21.0)."""
    lum_a = _relative_luminance(rgb_a)
    lum_b = _relative_luminance(rgb_b)
    lighter, darker = max(lum_a, lum_b), min(lum_a, lum_b)
    return (lighter + 0.05) / (darker + 0.05)


def random_hue() -> float:
    """A random hue in [0, 360) -- used for 'random base color' / 'shuffle'."""
    return random.uniform(0, 360)


# ---------------------------------------------------------------------------
# Simple interactive command-line interface
# ---------------------------------------------------------------------------

def _prompt_choice(label: str, choices: tuple[str, ...], default: str) -> str:
    options = "/".join(choices)
    while True:
        raw = input(f"{label} ({options}) [default: {default}]: ").strip().lower()
        if raw == "":
            return default
        if raw in choices:
            return raw
        print(f"  Please enter one of: {options}")


def _prompt_int(label: str, default: int, min_value: int, max_value: int) -> int:
    while True:
        raw = input(f"{label} [{min_value}-{max_value}, default: {default}]: ").strip()
        if raw == "":
            return default
        try:
            value = int(raw)
        except ValueError:
            print("  Please enter a whole number.")
            continue
        if not (min_value <= value <= max_value):
            print(f"  Value must be between {min_value} and {max_value}.")
            continue
        return value


def run_cli() -> None:
    print("=" * 60)
    print("Color Palette Generator")
    print("=" * 60)

    raw_hue = input(
        "Base color as a hue in degrees, 0-360 (press Enter for a random color): "
    ).strip()
    base_hue = random_hue() if raw_hue == "" else float(raw_hue) % 360

    harmony = _prompt_choice("Harmony", HARMONIES, DEFAULT_HARMONY)
    style = _prompt_choice("Style", STYLES, DEFAULT_STYLE)
    count = _prompt_int("Number of colors", DEFAULT_COUNT, MIN_COLORS, MAX_COLORS)

    request = PaletteRequest(base_hue=base_hue, harmony=harmony, style=style, count=count)

    try:
        result = generate_palette(request)
    except ValueError as exc:
        print(f"\nError: {exc}")
        return

    print(f"\nBase hue: {base_hue:.0f} deg | Harmony: {harmony} | Style: {style}\n")
    print(f"{'Hex':<9}{'H':>5}{'S':>6}{'L':>6}   {'On white':>10}   {'On black':>10}")
    for swatch in result.swatches:
        white_mark = "AA" if swatch.aa_on_white else "--"
        black_mark = "AA" if swatch.aa_on_black else "--"
        print(
            f"{swatch.hex:<9}{swatch.hue:>5.0f}{swatch.saturation:>6.0f}{swatch.lightness:>6.0f}"
            f"   {swatch.contrast_on_white:>6.2f}:1 {white_mark:>3}"
            f"   {swatch.contrast_on_black:>6.2f}:1 {black_mark:>3}"
        )
    print()


if __name__ == "__main__":
    run_cli()
