"""
Plate Generator — Produces license plate text strings in Texas LLL-NNNN format.
Supports random, list, and mixed modes. Tracks used plates to avoid repeats.
Hard mode forces visually ambiguous characters for LPR stress testing.
"""

import os
import random
import sys

if getattr(sys, 'frozen', False):
    _BASE_DIR = os.path.dirname(sys.executable)
else:
    _BASE_DIR = os.path.join(os.path.dirname(__file__), '..')

DATA_DIR = os.path.join(_BASE_DIR, 'data')

NORMAL_LETTERS = "ABCDEFGHJKLMNPRSTUVWXYZ"  # excludes I, O, Q
HARD_LETTERS = "IOQDB"
NORMAL_DIGITS = "0123456789"
HARD_DIGITS = "0168"  # 0/O, 1/I, 6/G, 8/B confusion


class PlateGenerator:
    def __init__(self, hard_mode: bool = False):
        self.hard_mode = hard_mode
        self._used: set[str] = set()
        self._plate_list: list[str] = []
        self._list_index: int = 0
        self._last_list_plate: str | None = None
        self._load_plate_list()

    def _load_plate_list(self):
        path = os.path.join(DATA_DIR, 'plate_list.txt')
        if os.path.isfile(path):
            with open(path, 'r', encoding='utf-8') as f:
                self._plate_list = [
                    line.strip() for line in f if line.strip()
                ]
        self._list_index = 0

    def next(self, source: str = "random", ratio: float = 0.3,
             locked: str | None = None) -> str:
        """Get next plate text based on source mode."""
        if locked:
            return locked

        if source == "random":
            return self._random_plate()
        elif source == "list":
            return self._list_plate()
        elif source == "mixed":
            if random.random() < ratio:
                return self._list_plate()
            else:
                return self._random_plate()
        else:
            return self._random_plate()

    def _random_plate(self) -> str:
        """Generate a random Texas-format plate: LLL-NNNN."""
        letters = HARD_LETTERS if self.hard_mode else NORMAL_LETTERS
        digits = HARD_DIGITS if self.hard_mode else NORMAL_DIGITS

        max_attempts = 1000
        for _ in range(max_attempts):
            text = (
                ''.join(random.choice(letters) for _ in range(3))
                + '-'
                + ''.join(random.choice(digits) for _ in range(4))
            )
            if text not in self._used:
                self._used.add(text)
                return text

        # Pool exhausted — clear and start over
        self._used.clear()
        return self._random_plate()

    def _list_plate(self) -> str:
        """Get next plate from the user-supplied list."""
        if not self._plate_list:
            return self._random_plate()

        max_attempts = len(self._plate_list)
        for _ in range(max_attempts):
            plate = self._plate_list[self._list_index]
            self._list_index = (self._list_index + 1) % len(self._plate_list)
            if plate != self._last_list_plate:
                self._last_list_plate = plate
                return plate

        # All plates are the same single entry
        return self._plate_list[0]

    def reset(self):
        """Clear used plates and reset list position."""
        self._used.clear()
        self._list_index = 0
        self._last_list_plate = None

    def set_hard_mode(self, enabled: bool):
        """Toggle hard mode for ambiguous characters."""
        self.hard_mode = enabled
