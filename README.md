# LPRTestBench

Professional-grade LPR (License Plate Recognition) camera testing and showcase tool. Built for trade show demonstrations, sales demos, and engineering validation of LPR systems like PatriotLPR.

## What It Does

LPRTestBench composites realistic license plate images onto vehicle photos with configurable lighting, weather effects, and camera perspectives. It pre-renders a cache of images and cycles through them smoothly — producing a live feed of realistic LPR scenarios without needing a real camera or vehicles.

## Features

- **Assets Mode** — Import vehicle photos, map plate regions with 4-corner selection, tag metadata
- **Templates Mode** — Build composite configurations: vehicle + state plate + lighting + weather + zoom
- **Libraries Mode** — Group templates into ordered collections for specific demo scenarios
- **Demo Mode** — Smooth, zero-lag live cycling through pre-rendered composites with full-screen display
- **Cache Engine** — Background threading keeps 20+ images ready at all times, vault caching for reuse
- **Extensible** — Drop new state SVGs or vehicle PNGs into the assets folder and they're automatically detected

## Requirements

- Python 3.12+
- Windows / macOS / Linux (Tkinter must be available)

## Installation

```bash
git clone https://github.com/daltonloomis0818/LPRTestBench.git
cd LPRTestBench
pip install -r requirements.txt
```

## Usage

```bash
python main.py
```

## Project Structure

```
LPRTestBench/
├── main.py                  ← Entry point, top nav, mode router
├── modes/                   ← UI modes (Assets, Templates, Libraries, Demo)
├── engine/                  ← Core rendering and caching engine
├── assets/                  ← Vehicle images, plate SVGs, overlay PNGs
├── data/                    ← SQLite DB, JSON configs, plate lists
├── vault/                   ← Pre-rendered composite cache
└── output/                  ← Exported images
```

## License

MIT
