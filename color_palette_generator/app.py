from flask import Blueprint, Flask, current_app, render_template, request, jsonify

import color_palette_generator as cpg

bp = Blueprint(
    "color_palette_generator",
    __name__,
    template_folder="templates",
    static_folder="static",
)

DEFAULTS = {
    "base_hue": 210,
    "harmony": cpg.DEFAULT_HARMONY,
    "style": cpg.DEFAULT_STYLE,
    "count": cpg.DEFAULT_COUNT,
}


@bp.route("/")
def index():
    return render_template(
        "color_palette_generator/index.html",
        defaults=DEFAULTS,
        harmonies=cpg.HARMONIES,
        styles=cpg.STYLES,
        min_colors=cpg.MIN_COLORS,
        max_colors=cpg.MAX_COLORS,
        hub_tools=current_app.config.get("HUB_TOOLS"),
        hub_active="color_palette_generator",
    )


@bp.route("/generate", methods=["POST"])
def generate():
    data = request.get_json(silent=True) or {}
    try:
        base_hue = float(data.get("base_hue", DEFAULTS["base_hue"]))
        harmony = str(data.get("harmony", DEFAULTS["harmony"]))
        style = str(data.get("style", DEFAULTS["style"]))
        count = int(data.get("count", DEFAULTS["count"]))
        palette_request = cpg.PaletteRequest(
            base_hue=base_hue, harmony=harmony, style=style, count=count
        )
        result = cpg.generate_palette(palette_request)
    except (ValueError, TypeError) as exc:
        return jsonify({"error": str(exc)}), 400

    return jsonify(
        {
            "base_hue": base_hue,
            "harmony": harmony,
            "style": style,
            "count": count,
            "swatches": [
                {
                    "hex": s.hex,
                    "hue": s.hue,
                    "saturation": s.saturation,
                    "lightness": s.lightness,
                    "contrast_on_white": s.contrast_on_white,
                    "contrast_on_black": s.contrast_on_black,
                    "aa_on_white": s.aa_on_white,
                    "aa_on_black": s.aa_on_black,
                }
                for s in result.swatches
            ],
        }
    )


def create_app() -> Flask:
    """Build a standalone Flask app around this tool's blueprint, so it
    can still be run on its own (`python3 app.py`). The hub instead
    imports `bp` directly and mounts it alongside the other tools."""
    app = Flask(__name__)
    app.register_blueprint(bp)
    return app


if __name__ == "__main__":
    create_app().run(debug=True)
