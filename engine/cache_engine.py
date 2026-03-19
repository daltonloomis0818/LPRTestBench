"""
Cache Engine — Background-threaded image generation pipeline.
Maintains a queue of pre-rendered composites for zero-lag demo display.
Checks vault for cached renders before generating fresh.
"""

import os
import queue
import sys
import threading
import time
import uuid
from PIL import Image

from engine.plate_renderer import PlateRenderer
from engine.compositor import Compositor
from engine.plate_generator import PlateGenerator
from engine import effects

if getattr(sys, 'frozen', False):
    _BASE_DIR = os.path.dirname(sys.executable)
else:
    _BASE_DIR = os.path.join(os.path.dirname(__file__), '..')

VAULT_DIR = os.path.join(_BASE_DIR, 'vault')
ASSETS_DIR = os.path.join(_BASE_DIR, 'assets', 'vehicles')
TARGET_POOL_SIZE = 20
REFILL_THRESHOLD = 5


class CacheEngine:
    def __init__(self, templates: list[dict], asset_lookup: dict[int, dict],
                 cycle_mode: str = "sequential",
                 plate_renderer: PlateRenderer | None = None,
                 compositor: Compositor | None = None,
                 plate_generator: PlateGenerator | None = None):
        """
        Args:
            templates: List of template dicts from the loaded library.
            asset_lookup: Dict mapping asset ID → asset record dict (from DB).
            cycle_mode: 'sequential' or 'random'.
            plate_renderer: PlateRenderer instance (created if None).
            compositor: Compositor instance (created if None).
            plate_generator: PlateGenerator instance (created if None).
        """
        self._templates = [t for t in templates if t.get('enabled', True)]
        self._asset_lookup = asset_lookup
        self._cycle_mode = cycle_mode
        self._cycle_index = 0

        self._plate_renderer = plate_renderer or PlateRenderer()
        self._compositor = compositor or Compositor()
        self._plate_generator = plate_generator or PlateGenerator()

        self._queue: queue.Queue[tuple[Image.Image, dict]] = queue.Queue(maxsize=30)
        self._running = threading.Event()
        self._thread: threading.Thread | None = None

        self._history: list[tuple[Image.Image, dict]] = []
        self._history_index: int = -1

    def start(self):
        """Start the background generator thread."""
        if self._thread and self._thread.is_alive():
            return
        self._running.set()
        self._thread = threading.Thread(target=self._generator_loop, daemon=True)
        self._thread.start()

    def stop(self):
        """Stop the background generator thread."""
        self._running.clear()
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None

    def prewarm(self, count: int = 20):
        """Synchronously generate images to fill the queue before display starts."""
        for _ in range(min(count, len(self._templates) * 5 if self._templates else 0)):
            item = self._generate_one()
            if item:
                self._queue.put(item)
            if self._queue.qsize() >= count:
                break

    def get_next(self) -> tuple[Image.Image, dict] | None:
        """Pull next image from the queue. Returns None if empty."""
        try:
            item = self._queue.get(timeout=0.1)
            self._history.append(item)
            self._history_index = len(self._history) - 1
            return item
        except queue.Empty:
            return None

    def get_prev(self) -> tuple[Image.Image, dict] | None:
        """Get previous image from history."""
        if self._history_index > 0:
            self._history_index -= 1
            return self._history[self._history_index]
        return None

    def queue_depth(self) -> int:
        """Current number of images ready in the queue."""
        return self._queue.qsize()

    def _generator_loop(self):
        """Background thread: continuously generate and enqueue images."""
        while self._running.is_set():
            if self._queue.qsize() < TARGET_POOL_SIZE:
                item = self._generate_one()
                if item:
                    try:
                        self._queue.put(item, timeout=1.0)
                    except queue.Full:
                        pass
            else:
                time.sleep(0.05)

    def _generate_one(self) -> tuple[Image.Image, dict] | None:
        """Generate a single composite image from the next template."""
        if not self._templates:
            return None

        template = self._next_template()
        vehicle_id = template.get('vehicle_id')
        asset = self._asset_lookup.get(vehicle_id)
        if not asset:
            return None

        state = template.get('state', 'texas')
        plate_source = template.get('plate_source', 'random')
        mix_ratio = template.get('mix_ratio', 0.3)
        locked_plate = template.get('locked_plate')

        plate_text = self._plate_generator.next(plate_source, mix_ratio, locked_plate)

        # Check vault cache
        vault_image = self._check_vault(template['id'], plate_text)
        if vault_image:
            metadata = self._build_metadata(template, asset, plate_text, state)
            return (vault_image, metadata)

        # Generate fresh
        try:
            vehicle_path = os.path.join(os.path.normpath(ASSETS_DIR), asset['filename'])
            vehicle_img = Image.open(vehicle_path).convert('RGBA')

            plate_img = self._plate_renderer.render(state, plate_text)

            import json
            corners = asset['corners']
            if isinstance(corners, str):
                corners = json.loads(corners)

            composite = self._compositor.composite(vehicle_img, plate_img, corners)

            # Apply lighting
            lighting = template.get('lighting_override') or asset.get('lighting', 'day_sun')
            composite = effects.apply_lighting(composite, lighting)

            # Apply weather
            weather = template.get('weather_override')
            if weather and weather.lower() != 'none':
                composite = effects.apply_weather(composite, weather)

            # Apply zoom
            zoom = template.get('zoom', 1.0)
            if zoom > 1.0:
                composite = effects.apply_zoom(composite, zoom)

            metadata = self._build_metadata(template, asset, plate_text, state)
            return (composite, metadata)

        except Exception as e:
            print(f"[CacheEngine] Error generating image: {e}")
            return None

    def _next_template(self) -> dict:
        """Pick the next template based on cycle mode."""
        if self._cycle_mode == 'random':
            import random
            return random.choice(self._templates)
        else:
            template = self._templates[self._cycle_index % len(self._templates)]
            self._cycle_index += 1
            return template

    def _check_vault(self, template_id: str, plate_text: str) -> Image.Image | None:
        """Check if a cached render exists in the vault."""
        vault_dir = os.path.normpath(VAULT_DIR)
        safe_plate = plate_text.replace('/', '_').replace('\\', '_')
        path = os.path.join(vault_dir, str(template_id), f"{safe_plate}.png")
        if os.path.isfile(path):
            try:
                return Image.open(path).convert('RGBA')
            except Exception:
                return None
        return None

    def _build_metadata(self, template: dict, asset: dict, plate_text: str,
                        state: str) -> dict:
        """Build metadata dict for a rendered image."""
        return {
            'template_id': template['id'],
            'template_name': template.get('name', ''),
            'vehicle_id': template.get('vehicle_id'),
            'vehicle_info': f"{asset.get('make', '')} {asset.get('model', '')}".strip(),
            'plate_text': plate_text,
            'state': state,
        }


def write_to_vault(template_id: str, plate_text: str, image: Image.Image):
    """Save a rendered image to the vault for future reuse."""
    vault_dir = os.path.normpath(VAULT_DIR)
    template_dir = os.path.join(vault_dir, str(template_id))
    os.makedirs(template_dir, exist_ok=True)
    safe_plate = plate_text.replace('/', '_').replace('\\', '_')
    path = os.path.join(template_dir, f"{safe_plate}.png")
    image.save(path, 'PNG')
