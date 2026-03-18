"""
Plate Renderer — Renders license plate images with customizable text.
Primary: cairosvg (SVG→PNG). Fallback: pure Pillow drawing (no system deps).
SVG templates in /assets/plates/ are still loaded for cairosvg when available.
"""

import io
import os
from PIL import Image, ImageDraw, ImageFont, ImageFilter

PLATES_DIR = os.path.join(os.path.dirname(__file__), '..', 'assets', 'plates')
RENDER_WIDTH = 880
RENDER_HEIGHT = 440

# Try to import cairosvg — may fail on Windows without GTK runtime
_HAS_CAIROSVG = False
try:
    import cairosvg
    # Test that it actually works (cairocffi can import but fail on DLL load)
    cairosvg.svg2png(bytestring=b'<svg xmlns="http://www.w3.org/2000/svg" width="1" height="1"/>')
    _HAS_CAIROSVG = True
except Exception:
    pass


class PlateRenderer:
    def __init__(self):
        self._svg_cache: dict[str, str] = {}
        self._render_cache: dict[tuple[str, str], Image.Image] = {}
        self._pillow_renderers: dict[str, '_PillowPlateRenderer'] = {
            'texas': _TexasPlateRenderer(),
        }
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
        """Render a plate with the given text, returning a PIL Image."""
        key = (state.lower(), plate_text)
        if key in self._render_cache:
            return self._render_cache[key].copy()

        image = None

        # Try cairosvg first (best quality, full SVG support)
        if _HAS_CAIROSVG:
            svg_template = self._svg_cache.get(state.lower())
            if svg_template:
                try:
                    svg_data = svg_template.replace('{{PLATE_TEXT}}', plate_text)
                    png_bytes = cairosvg.svg2png(
                        bytestring=svg_data.encode('utf-8'),
                        output_width=RENDER_WIDTH,
                        output_height=RENDER_HEIGHT,
                    )
                    image = Image.open(io.BytesIO(png_bytes)).convert('RGBA')
                except Exception:
                    image = None

        # Fallback: Pillow-based rendering
        if image is None:
            renderer = self._pillow_renderers.get(state.lower())
            if renderer:
                image = renderer.render(plate_text)
            else:
                # Generic fallback for unknown states
                image = _GenericPlateRenderer(state).render(plate_text)

        self._render_cache[key] = image
        return image.copy()

    def available_states(self) -> list[str]:
        """Return sorted list of available state plate names."""
        states = set(self._svg_cache.keys()) | set(self._pillow_renderers.keys())
        return sorted(states)

    def clear_cache(self):
        """Clear the render cache to free memory."""
        self._render_cache.clear()


# ── Pillow-based plate renderers (no external deps) ──────────────


def _try_font(names: list[str], size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Try loading fonts by name, fall back to default."""
    for name in names:
        try:
            return ImageFont.truetype(name, size)
        except (OSError, IOError):
            continue
    return ImageFont.load_default()


class _TexasPlateRenderer:
    """Draws a Texas license plate using Pillow — no SVG/Cairo needed."""

    def render(self, plate_text: str) -> Image.Image:
        W, H = RENDER_WIDTH, RENDER_HEIGHT
        img = Image.new('RGBA', (W, H), (255, 255, 255, 255))
        draw = ImageDraw.Draw(img)

        navy = (27, 42, 74)
        gold = (201, 168, 76)
        white = (255, 255, 255)
        gray_bolt = (224, 224, 224)
        gray_bolt_inner = (136, 136, 136)
        bolt_outline = (170, 170, 170)

        # Outer border
        draw.rounded_rectangle([8, 8, W - 9, H - 9], radius=8,
                               outline=navy, width=4)
        # Inner border
        draw.rounded_rectangle([16, 16, W - 17, H - 17], radius=6,
                               outline=navy, width=2)

        # Header bar
        draw.rectangle([16, 16, W - 17, 88], fill=navy)

        # Lone Star (5-point star in header)
        import math
        cx, cy = W // 2, 52
        outer_r, inner_r = 28, 12
        star_pts = []
        for i in range(10):
            angle = math.radians(-90 + i * 36)
            r = outer_r if i % 2 == 0 else inner_r
            star_pts.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))
        draw.polygon(star_pts, fill=gold, outline=gold)

        # TEXAS text — split around star
        header_font = _try_font(['arialbd.ttf', 'Arial Bold.ttf', 'DejaVuSans-Bold.ttf'], 38)

        # "TEX" left of star
        draw.text((170, 36), "TEX", fill=gold, font=header_font, anchor='lm')
        # "AS" right of star
        draw.text((W - 170, 36), "AS", fill=gold, font=header_font, anchor='rm')

        # Main plate text
        plate_font = _try_font(['arialbd.ttf', 'Arial Bold.ttf', 'DejaVuSans-Bold.ttf'], 110)
        # Center the plate text
        draw.text((W // 2, 240), plate_text, fill=navy, font=plate_font, anchor='mm')

        # Bottom tagline
        tagline_font = _try_font(['arial.ttf', 'Arial.ttf', 'DejaVuSans.ttf'], 22)
        draw.text((W // 2, 380), "The Lone Star State", fill=navy,
                  font=tagline_font, anchor='mm')

        # Bolt holes
        for bx in [140, W - 140]:
            draw.ellipse([bx - 12, 388, bx + 12, 412], fill=gray_bolt,
                         outline=bolt_outline, width=2)
            draw.ellipse([bx - 4, 396, bx + 4, 404], fill=gray_bolt_inner)

        # Subtle emboss effect
        embossed = img.filter(ImageFilter.SMOOTH)
        img = Image.blend(img, embossed, 0.15)

        return img.convert('RGBA')


class _GenericPlateRenderer:
    """Generic fallback for states without a dedicated Pillow renderer."""

    def __init__(self, state: str):
        self.state = state

    def render(self, plate_text: str) -> Image.Image:
        W, H = RENDER_WIDTH, RENDER_HEIGHT
        img = Image.new('RGBA', (W, H), (255, 255, 255, 255))
        draw = ImageDraw.Draw(img)

        blue = (30, 60, 120)

        # Simple border
        draw.rounded_rectangle([8, 8, W - 9, H - 9], radius=8,
                               outline=blue, width=4)

        # State name header
        header_font = _try_font(['arialbd.ttf', 'Arial Bold.ttf', 'DejaVuSans-Bold.ttf'], 36)
        draw.text((W // 2, 50), self.state.upper(), fill=blue,
                  font=header_font, anchor='mm')

        # Plate text
        plate_font = _try_font(['arialbd.ttf', 'Arial Bold.ttf', 'DejaVuSans-Bold.ttf'], 110)
        draw.text((W // 2, 230), plate_text, fill=blue,
                  font=plate_font, anchor='mm')

        return img.convert('RGBA')
