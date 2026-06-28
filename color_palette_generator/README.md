# Color Palette Generator

Generates a coordinated set of colors from a single base color, using
classic color-harmony rules, and reports how readable each color is as
text on a white or black background (WCAG contrast ratio).

This tool is primarily a web app. The core color math also has a small
CLI for quick terminal use, and has no dependency on any other tool in
this repository.

## Usage

### Web app (primary interface)

```bash
pip install -r requirements.txt
python3 app.py
```

Open the URL it prints (usually `http://127.0.0.1:5000`). Pick a base
color, a harmony, a style, and a color count; the palette updates
automatically, or use **Generate**. **Shuffle** keeps the same harmony,
style, and count, but picks a new random base color.

### Command line

```bash
python3 color_palette_generator.py
```

Prompts for a base hue (or press Enter for a random one), harmony, style,
and color count, then prints each color's hex code, HSL values, and WCAG
contrast ratio against white and black.

## Inputs

| Input | Description |
|---|---|
| Base color | A hue (0-360 degrees), via a color picker on the web, or in degrees on the CLI |
| Harmony | `varied` (default), `monochromatic`, `analogous`, `complementary`, or `triadic` — how the other colors relate to the base hue |
| Style | `pastel`, `vibrant`, `muted`, or `dark` — the overall saturation/lightness mood |
| Count | How many colors to generate (3-12) |

## How the harmonies work

- **Varied** (default): hues spread evenly across the full color wheel (360 / count degrees apart), so every color is visually distinct — useful when you just want N good-looking, easily-told-apart colors in a given style, rather than tints of one or two hues.
- **Monochromatic**: all colors share the base hue; only lightness varies (a tint-to-shade ladder).
- **Analogous**: hues spread evenly across a 60-degree band centered on the base hue; lightness and saturation stay constant.
- **Complementary**: the base hue plus its opposite (180 degrees away); the requested count is split evenly between the two, each as its own tint-to-shade ladder.
- **Triadic**: the base hue plus two hues 120 degrees apart; the count is split evenly across the three.

Saturation is fixed at the chosen style's midpoint for every color in the
palette, so the result feels cohesive rather than a random scramble of
hue, saturation, and lightness.

## Output

For each generated color:
- Hex code
- Hue / saturation / lightness
- WCAG contrast ratio as text on a white background, and on a black background
- Whether each of those passes the WCAG AA threshold for normal text (4.5:1)

## Requirements

Python 3.10+. The core calculation has no external dependencies (uses
the standard library `colorsys` module). The web app requires Flask (see
`requirements.txt`).
