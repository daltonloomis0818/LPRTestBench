"""
Plate Renderer — Loads state SVG templates, replaces {{PLATE_TEXT}},
renders to PIL Image via cairosvg. Caches rendered results in memory.
"""

import io
import os
from PIL import Image
import cairosvg

PLATES_DIR = os.path.join(os.path.dirname(__file__), '..', 'assets', 'plates')
RENDER_WIDTH = 880
RENDER_HEIGHT = 440


class PlateRenderer:
    def __init__(self):
        self._svg_cache: dict[str, str] = {}
        self._render_cache: dict[tuple[str, str], Image.Image] = {}
        self._load_templates()

    def _load_templates(self):
        plates_dir = os.path.normpath(PLATES_DIR)
        if not os.path.isdir(plates_dir):
            return
        for fname in os.listdir(plates_dir):
            if fname.lower().endswith('.svg'):
                state = os.path.splitext(fname)[0].lower()
                path = os.path.join(plates_dir, fname)
                with open(path, 'r', encoding='utf-8') as f:
                    self._svg_cache[state] = f.read()

    def reload_templates(self):
        """Re-scan plates directory for new SVGs added at runtime."""
        self._svg_cache.clear()
        self._load_templates()

    def render(self, state: str, plate_text: str) -> Image.Image:
        """Render a plate SVG with the given text, returning a PIL Image."""
        key = (state.lower(), plate_text)
        if key in self._render_cache:
            return self._render_cache[key].copy()

        svg_template = self._svg_cache.get(state.lower())
        if svg_template is None:
            raise ValueError(f"No SVG template found for state: {state}")

        svg_data = svg_template.replace('{{PLATE_TEXT}}', plate_text)
        png_bytes = cairosvg.svg2png(
            bytestring=svg_data.encode('utf-8'),
            output_width=RENDER_WIDTH,
            output_height=RENDER_HEIGHT,
        )
        image = Image.open(io.BytesIO(png_bytes)).convert('RGBA')
        self._render_cache[key] = image
        return image.copy()

    def available_states(self) -> list[str]:
        """Return sorted list of available state plate names."""
        return sorted(self._svg_cache.keys())

    def clear_cache(self):
        """Clear the render cache to free memory."""
        self._render_cache.clear()
