"""
Plate Renderer — Renders license plate images with customizable text.
Primary: cairosvg (SVG→PNG). Fallback: pure Pillow drawing (no system deps).
SVG templates in /assets/plates/ are still loaded for cairosvg when available.
"""

import io
import os
import sys
from PIL import Image, ImageDraw, ImageFont, ImageFilter

if getattr(sys, 'frozen', False):
    _BASE_DIR = os.path.dirname(sys.executable)
else:
    _BASE_DIR = os.path.join(os.path.dirname(__file__), '..')

PLATES_DIR = os.path.join(_BASE_DIR, 'assets', 'plates')
RENDER_WIDTH = 2968
RENDER_HEIGHT = 1440

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


FONTS_DIR = os.path.join(_BASE_DIR, 'assets', 'fonts')


def _plate_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Load the license plate font, fall back to system fonts."""
    candidates = [
        os.path.join(FONTS_DIR, 'LICENSE PLATE USA.ttf'),
        os.path.join(FONTS_DIR, 'Mandatory.otf'),
        'impact.ttf',
        'arialbd.ttf',
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except (OSError, IOError):
            continue
    return ImageFont.load_default()


def _try_font(names: list[str], size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Try loading fonts by name, fall back to default."""
    for name in names:
        try:
            return ImageFont.truetype(name, size)
        except (OSError, IOError):
            continue
    return ImageFont.load_default()


class _TexasPlateRenderer:
    """Texas Classic plate — uses the real blank plate image, stamps text only."""

    _blank: Image.Image | None = None

    def _get_blank(self) -> Image.Image:
        """Load the blank Texas plate template image (cached)."""
        if _TexasPlateRenderer._blank is None:
            blank_path = os.path.join(_BASE_DIR, 'assets', 'plates', 'texas_blank.png')
            if os.path.isfile(blank_path):
                _TexasPlateRenderer._blank = Image.open(blank_path).convert('RGBA')
            else:
                # Fallback: solid background if image missing
                _TexasPlateRenderer._blank = Image.new('RGBA',
                    (RENDER_WIDTH, RENDER_HEIGHT), (210, 218, 228, 255))
        return _TexasPlateRenderer._blank

    def render(self, plate_text: str) -> Image.Image:
        import math

        img = self._get_blank().copy()
        W, H = img.size
        draw = ImageDraw.Draw(img)
        black = (10, 10, 10)

        # Split plate text: "ABC-1234" → "ABC" ★ "1234"
        if '-' in plate_text:
            left_text, right_text = plate_text.split('-', 1)
        else:
            left_text = plate_text[:3]
            right_text = plate_text[3:]

        # Font sized to fill ~72% of plate width (matches real TX plates)
        font_size = int(H * 0.42)
        plate_font = _plate_font(font_size)

        # Plate number sits at roughly 52% down from top
        center_y = int(H * 0.57)

        # Measure text to center around star separator
        left_bbox = draw.textbbox((0, 0), left_text, font=plate_font)
        right_bbox = draw.textbbox((0, 0), right_text, font=plate_font)
        left_w = left_bbox[2] - left_bbox[0]
        right_w = right_bbox[2] - right_bbox[0]

        star_gap = int(W * 0.045)
        total_w = left_w + star_gap + right_w
        start_x = (W - total_w) // 2

        # Left letters
        draw.text((start_x + left_w // 2, center_y), left_text,
                  fill=black, font=plate_font, anchor='mm')

        # Star separator with Texas shape
        sep_cx = start_x + left_w + star_gap // 2
        sep_cy = center_y
        sep_r = int(H * 0.028)
        sep_ir = int(sep_r * 0.4)
        sep_pts = []
        for i in range(10):
            angle = math.radians(-90 + i * 36)
            r = sep_r if i % 2 == 0 else sep_ir
            sep_pts.append((sep_cx + r * math.cos(angle),
                            sep_cy + r * math.sin(angle)))
        draw.polygon(sep_pts, fill=None, outline=black, width=max(3, int(H * 0.003)))

        # Texas shape inside
        tx_scale = sep_r * 0.012
        tx_raw = [
            (-30, -28), (-30, 2), (-18, 2), (-18, 18), (-8, 28),
            (4, 28), (10, 18), (18, 18), (26, 8), (30, 2),
            (30, -6), (22, -6), (16, -16), (10, -16), (4, -26),
            (-6, -30), (-16, -30), (-22, -28),
        ]
        tx_pts = [(sep_cx + p[0] * tx_scale, sep_cy + p[1] * tx_scale) for p in tx_raw]
        draw.polygon(tx_pts, fill=black)

        # Right numbers
        draw.text((start_x + left_w + star_gap + right_w // 2, center_y),
                  right_text, fill=black, font=plate_font, anchor='mm')

        return img


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
