"""
Effects Engine — Applies lighting adjustments, weather effects, zoom crops,
and film grain to composite images. All functions are stateless.
"""

import numpy as np
from PIL import Image, ImageEnhance, ImageFilter

# Lighting presets: (brightness_factor, color_temp_shift_rgb, extra_processing)
LIGHTING_PRESETS = {
    'day_sun':   {'brightness': 1.0,  'temp': (0, 0, 0)},
    'overcast':  {'brightness': 0.92, 'temp': (-5, -3, 5)},
    'dusk':      {'brightness': 0.78, 'temp': (15, 5, -15)},
    'night':     {'brightness': 0.65, 'temp': (10, 5, -10)},
    'night_ir':  {'brightness': 1.0,  'temp': (0, 0, 0)},  # handled specially
    'rain':      {'brightness': 0.88, 'temp': (-3, -2, 5)},
    'snow':      {'brightness': 0.95, 'temp': (3, 3, 8)},
    'fog':       {'brightness': 0.80, 'temp': (5, 5, 8)},
}


def apply_lighting(image: Image.Image, tag: str) -> Image.Image:
    """Apply lighting adjustment based on condition tag."""
    tag = tag.lower() if tag else 'day_sun'
    preset = LIGHTING_PRESETS.get(tag, LIGHTING_PRESETS['day_sun'])

    if tag == 'night_ir':
        return _apply_ir(image)

    # Brightness adjustment
    img = image.copy()
    if preset['brightness'] != 1.0:
        enhancer = ImageEnhance.Brightness(img)
        img = enhancer.enhance(preset['brightness'])

    # Color temperature shift
    temp = preset['temp']
    if any(t != 0 for t in temp):
        img = _shift_color_temp(img, temp)

    # Night: add warm plate-light glow in center
    if tag == 'night':
        img = _add_plate_glow(img)

    return img


def apply_weather(image: Image.Image, tag: str) -> Image.Image:
    """Apply weather effect overlay."""
    if not tag or tag.lower() == 'none':
        return image

    tag = tag.lower()
    if tag == 'rain':
        return _apply_rain(image)
    elif tag == 'snow':
        return _apply_snow(image)
    elif tag == 'fog':
        return _apply_fog(image)
    elif tag == 'ir':
        return _apply_ir(image)
    return image


def apply_zoom(image: Image.Image, factor: float) -> Image.Image:
    """Center-crop by zoom factor, then resize back to original dimensions."""
    if factor <= 1.0:
        return image

    w, h = image.size
    crop_w = int(w / factor)
    crop_h = int(h / factor)
    left = (w - crop_w) // 2
    top = (h - crop_h) // 2

    cropped = image.crop((left, top, left + crop_w, top + crop_h))
    return cropped.resize((w, h), Image.LANCZOS)


def apply_grain(image: Image.Image, intensity: float = 0.1) -> Image.Image:
    """Add gaussian noise grain to image."""
    if intensity <= 0:
        return image

    arr = np.array(image, dtype=np.float32)
    noise = np.random.normal(0, intensity * 255, arr.shape[:2])

    # Apply noise to RGB channels only
    for c in range(min(3, arr.shape[2])):
        arr[:, :, c] = np.clip(arr[:, :, c] + noise, 0, 255)

    return Image.fromarray(arr.astype(np.uint8), image.mode)


# --- Internal helpers ---

def _shift_color_temp(image: Image.Image, temp: tuple[int, int, int]) -> Image.Image:
    """Shift RGB channels by fixed amounts for color temperature."""
    arr = np.array(image, dtype=np.int16)
    arr[:, :, 0] = np.clip(arr[:, :, 0] + temp[0], 0, 255)  # R
    arr[:, :, 1] = np.clip(arr[:, :, 1] + temp[1], 0, 255)  # G
    arr[:, :, 2] = np.clip(arr[:, :, 2] + temp[2], 0, 255)  # B
    return Image.fromarray(arr.astype(np.uint8), image.mode)


def _add_plate_glow(image: Image.Image) -> Image.Image:
    """Add a warm yellowish glow in the center (simulates plate illumination at night)."""
    w, h = image.size
    arr = np.array(image, dtype=np.float32)

    # Create radial gradient centered slightly below middle
    y_center = int(h * 0.55)
    x_center = w // 2
    Y, X = np.ogrid[:h, :w]
    dist = np.sqrt(((X - x_center) / (w * 0.3)) ** 2 + ((Y - y_center) / (h * 0.25)) ** 2)
    glow = np.clip(1.0 - dist, 0, 1) * 0.15

    arr[:, :, 0] = np.clip(arr[:, :, 0] + glow * 60, 0, 255)   # warm R
    arr[:, :, 1] = np.clip(arr[:, :, 1] + glow * 40, 0, 255)   # warm G
    arr[:, :, 2] = np.clip(arr[:, :, 2] + glow * 10, 0, 255)   # slight B

    return Image.fromarray(arr.astype(np.uint8), image.mode)


def _apply_ir(image: Image.Image) -> Image.Image:
    """Night IR effect: desaturate, boost contrast, heavy grain, overexpose plate region."""
    # Desaturate
    img = image.convert('L').convert(image.mode)

    # Boost contrast
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(1.8)

    # Overexpose center plate region (blow out)
    arr = np.array(img, dtype=np.float32)
    w, h = img.size
    cy, cx = int(h * 0.55), w // 2
    Y, X = np.ogrid[:h, :w]
    dist = np.sqrt(((X - cx) / (w * 0.2)) ** 2 + ((Y - cy) / (h * 0.15)) ** 2)
    blow = np.clip(1.0 - dist, 0, 1) * 120
    for c in range(min(3, arr.shape[2])):
        arr[:, :, c] = np.clip(arr[:, :, c] + blow, 0, 255)
    img = Image.fromarray(arr.astype(np.uint8), image.mode)

    # Heavy grain
    img = apply_grain(img, 0.25)

    return img


def _apply_rain(image: Image.Image) -> Image.Image:
    """Rain effect: diagonal motion blur streaks and slight darkening."""
    w, h = image.size

    # Slight darkening for wet conditions
    enhancer = ImageEnhance.Brightness(image)
    img = enhancer.enhance(0.92)

    # Create rain streak layer
    rain = np.zeros((h, w), dtype=np.uint8)
    num_streaks = int(w * h / 800)
    for _ in range(num_streaks):
        x = np.random.randint(0, w)
        y = np.random.randint(0, h)
        length = np.random.randint(8, 25)
        for step in range(length):
            rx = x + step
            ry = y + step * 2
            if 0 <= rx < w and 0 <= ry < h:
                rain[ry, rx] = np.random.randint(100, 200)

    rain_layer = Image.fromarray(rain, 'L')
    rain_rgba = Image.merge('RGBA', (
        rain_layer, rain_layer, rain_layer,
        Image.fromarray((rain * 0.3).astype(np.uint8), 'L'),
    ))

    result = img.convert('RGBA')
    result = Image.alpha_composite(result, rain_rgba)
    return result


def _apply_snow(image: Image.Image) -> Image.Image:
    """Snow effect: white particle noise and slight blur."""
    w, h = image.size

    # Slight blur
    img = image.filter(ImageFilter.GaussianBlur(radius=0.5))

    # White particle noise
    snow = np.zeros((h, w, 4), dtype=np.uint8)
    num_flakes = int(w * h / 400)
    xs = np.random.randint(0, w, num_flakes)
    ys = np.random.randint(0, h, num_flakes)
    brightness = np.random.randint(180, 255, num_flakes).astype(np.uint8)
    alpha = np.random.randint(80, 180, num_flakes).astype(np.uint8)
    snow[ys, xs, 0] = brightness
    snow[ys, xs, 1] = brightness
    snow[ys, xs, 2] = brightness
    snow[ys, xs, 3] = alpha

    snow_layer = Image.fromarray(snow, 'RGBA')
    result = img.convert('RGBA')
    result = Image.alpha_composite(result, snow_layer)
    return result


def _apply_fog(image: Image.Image) -> Image.Image:
    """Fog effect: gaussian blur and semi-transparent white overlay."""
    # Gaussian blur
    img = image.filter(ImageFilter.GaussianBlur(radius=2.0))

    # White overlay at ~25% opacity
    w, h = img.size
    fog_layer = Image.new('RGBA', (w, h), (220, 220, 225, 64))
    result = img.convert('RGBA')
    result = Image.alpha_composite(result, fog_layer)
    return result
