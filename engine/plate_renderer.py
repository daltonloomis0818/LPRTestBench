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


FONTS_DIR = os.path.join(_BASE_DIR, 'assets', 'fonts')


def _plate_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Load the license plate font (Mandatory), fall back to system fonts."""
    candidates = [
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
    """Draws the current Texas Classic plate — matches real DMV design."""

    def render(self, plate_text: str) -> Image.Image:
        import math
        W, H = RENDER_WIDTH, RENDER_HEIGHT

        # Background: reflective light blue-gray with subtle noise
        bg = (210, 218, 228)
        img = Image.new('RGBA', (W, H), bg)

        # Add subtle noise texture to simulate reflective sheeting
        import numpy as np
        arr = np.array(img, dtype=np.float32)
        noise = np.random.normal(0, 3.5, (H, W))
        for c in range(3):
            arr[:, :, c] = np.clip(arr[:, :, c] + noise, 0, 255)
        img = Image.fromarray(arr.astype(np.uint8), 'RGBA')

        draw = ImageDraw.Draw(img)
        black = (15, 15, 15)
        white_bolt = (235, 240, 245)
        bolt_shadow = (170, 175, 180)

        # Plate border — thin dark outline with rounded corners
        draw.rounded_rectangle([3, 3, W - 4, H - 4], radius=12,
                               outline=(80, 80, 80), width=2)

        # ── Large 5-point star — top-left corner ──
        star_cx, star_cy = 100, 75
        star_r, star_ir = 48, 20
        star_pts = []
        for i in range(10):
            angle = math.radians(-90 + i * 36)
            r = star_r if i % 2 == 0 else star_ir
            star_pts.append((star_cx + r * math.cos(angle),
                             star_cy + r * math.sin(angle)))
        draw.polygon(star_pts, fill=black)

        # ── "TEXAS" — top area, right of the star ──
        texas_font = _plate_font(80)
        draw.text((490, 72), "TEXAS", fill=black, font=texas_font, anchor='mm')

        # ── Bolt holes — 4 corners ──
        bolt_positions = [(52, 42), (W - 52, 42), (52, H - 42), (W - 52, H - 42)]
        for bx, by in bolt_positions:
            # Outer ring
            draw.ellipse([bx - 14, by - 14, bx + 14, by + 14],
                         fill=white_bolt, outline=bolt_shadow, width=2)
            # Slot
            draw.rounded_rectangle([bx - 8, by - 3, bx + 8, by + 3],
                                   radius=2, fill=bolt_shadow)

        # ── Decorative wavy vertical lines (the DNA helix pattern) ──
        for base_x in [260, 620]:
            for y in range(20, H - 20, 3):
                offset = math.sin(y * 0.06) * 12
                c = (190, 195, 200, 100)
                draw.ellipse([base_x + offset - 1, y - 1,
                              base_x + offset + 1, y + 1], fill=c)

        # ── Main plate number — centered in plate body ──
        # Split: "ABC-1234" → "ABC" ★ "1234"
        if '-' in plate_text:
            left_text, right_text = plate_text.split('-', 1)
        else:
            left_text = plate_text[:3]
            right_text = plate_text[3:]

        plate_font = _plate_font(128)
        center_y = 240

        # Measure to position around small star separator
        left_bbox = draw.textbbox((0, 0), left_text, font=plate_font)
        right_bbox = draw.textbbox((0, 0), right_text, font=plate_font)
        left_w = left_bbox[2] - left_bbox[0]
        right_w = right_bbox[2] - right_bbox[0]
        star_gap = 62
        total_w = left_w + star_gap + right_w
        start_x = (W - total_w) // 2

        # Left letters
        draw.text((start_x + left_w // 2, center_y), left_text,
                  fill=black, font=plate_font, anchor='mm')

        # Small star separator with Texas outline inside
        sep_cx = start_x + left_w + star_gap // 2
        sep_cy = center_y
        sep_r, sep_ir = 18, 7
        sep_pts = []
        for i in range(10):
            angle = math.radians(-90 + i * 36)
            r = sep_r if i % 2 == 0 else sep_ir
            sep_pts.append((sep_cx + r * math.cos(angle),
                            sep_cy + r * math.sin(angle)))
        draw.polygon(sep_pts, fill=None, outline=black, width=2)

        # Texas state shape inside separator star
        tx_scale = 0.20
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

        # ── "The Lone Star State" — bottom left area ──
        tagline_font = _plate_font(30)
        draw.text((W // 2 - 60, H - 52), "The Lone Star State",
                  fill=black, font=tagline_font, anchor='mm')

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
