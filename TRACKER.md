# LPRTestBench — Project Tracker

**Repo:** https://github.com/daltonloomis0818/LPRTestBench
**Purpose:** Professional-grade LPR camera testing and showcase tool for trade shows, sales demos, and engineering validation scenarios. Built to demonstrate and stress-test LPR systems like PatriotLPR.

---

## Current Phase: Fully Operational — Runtime Tested

**Status:** All code written, dependencies installed, full pipeline verified end-to-end

---

## Completed Phases

| Phase | Description | Status | Notes |
|-------|-------------|--------|-------|
| 0a | GitHub repo created | Done | Public repo, MIT license, Python .gitignore |
| 0b | Architecture plan | Done | Full module-by-module design reviewed and approved |
| 0c | README + TRACKER | Done | Setup instructions, project overview |
| 1 | Core Engine | Done | plate_renderer, plate_generator, compositor, effects, cache_engine |
| 2 | Assets Mode | Done | Onboarding wizard, asset browser, detail view, metadata edit, corner redo, file import |
| 3 | Templates Mode | Done | Template builder with live preview, browser with sort/filter/delete |
| 4 | Libraries Mode | Done | Library builder with template picker/reorder, browser with launch/edit/duplicate/delete |
| 5 | Demo Mode | Done | Cache-driven display, auto-cycle, prev/next, fullscreen, export, session log, vault |
| 5a | Texas plate (Pillow) | Done | Pillow-based renderer with cairosvg fallback. Header, Lone Star, bolt holes, emboss |
| 5b | Plate list seed data | Done | 10 sample plates in data/plate_list.txt |
| 6a | Dependency install | Done | Pillow, opencv-python, numpy all working on Python 3.13 |
| 6b | Cairo workaround | Done | Pillow fallback renderer — no Cairo DLL needed on Windows |
| 6c | Engine pipeline test | Done | Renderer → Compositor → Effects → Cache Engine all verified |
| 6d | Full UI test | Done | All 4 modes load and switch cleanly with registered data |

---

## In-Progress Tasks

- None — ready for real-world use

---

## Next Steps Queue (Priority Order)

1. **Real vehicle photos** — Drop actual vehicle PNGs into assets/vehicles/ and onboard them via the wizard
2. **Additional state plates** — Add more SVG templates to assets/plates/ (or they'll use the generic Pillow renderer)
3. **Polish** — Filmstrip preview in library builder, window resize refinement, additional keyboard shortcuts

---

## Open Questions / Blockers

- None

---

## Dependencies (Verified Working)

| Package | Installed Version | Purpose |
|---------|-------------------|---------|
| Python | 3.13.12 | Runtime |
| Pillow | 12.1.1 | Image processing, plate rendering fallback, compositing |
| opencv-python | 4.13.0.92 | Perspective warp (getPerspectiveTransform, warpPerspective) |
| numpy | 2.4.2 | Effects math, noise generation |
| cairosvg | 2.9.0 | SVG rendering (optional — only works on Linux/Mac with Cairo installed) |
| tkinter | stdlib | Desktop UI framework |
| sqlite3 | stdlib | Asset registry |
| threading/queue | stdlib | Cache engine background processing |

---

## Architecture Decisions

- **Normalized corners (0.0–1.0)** — Plate corner coordinates stored as ratios, not pixels. Compositor denormalizes at render time.
- **Dual renderer** — cairosvg attempted first (full SVG support), falls back to Pillow drawing (works everywhere, no system deps).
- **Library reorder via Up/Down buttons** — Simpler than drag-and-drop, no external Tkinter DnD dependencies.
- **Debounced live preview** — Template builder re-renders 500ms after last parameter change.
- **Daemon cache thread** — Dies automatically when app closes. threading.Event for graceful stop.
- **Catppuccin Mocha color scheme** — Dark theme throughout.

---

## Deviations from Spec

| Item | Spec | Actual | Reason |
|------|------|--------|--------|
| SVG rendering | cairosvg only | Pillow primary + cairosvg fallback | Cairo DLL not available on Windows without GTK runtime |
| Drop zone | Drag-and-drop zone | File picker button | Tkinter DnD requires tkdnd extension |
| Filmstrip preview | Thumbnail strip in library builder | Deferred | Rendering all templates is expensive for builder UX |
| cairosvg requirement | Required | Optional (Linux/Mac only) | Windows uses Pillow-based plate rendering |

---

## File Map

```
main.py                     — App shell, nav, mode router, startup init, DB setup
modes/assets_mode.py        — Asset browser, onboarding wizard, detail view, metadata edit
modes/templates_mode.py     — Template builder (live preview), browser, edit
modes/libraries_mode.py     — Library builder (template picker), browser, launch
modes/demo_mode.py          — Demo runner, cache display, controls, export, session log
engine/plate_renderer.py    — Dual renderer: cairosvg (optional) + Pillow fallback
engine/plate_generator.py   — Random/list/mixed plate gen, hard mode, repeat tracking
engine/compositor.py        — OpenCV perspective warp, plate-onto-vehicle compositing
engine/effects.py           — Lighting, weather, zoom, grain effects (all stateless)
engine/cache_engine.py      — Background thread, queue pool, vault check, prewarm
assets/plates/texas.svg     — Texas standard plate SVG template (used when cairosvg available)
data/plate_list.txt         — Sample plate list for list/mixed mode
data/asset_registry.db      — SQLite (auto-created on first run)
data/templates.json         — Template configurations
data/libraries.json         — Library configurations
```

---

**Last Updated:** 2026-03-18 — Full pipeline verified, all 4 UI modes tested, ready for use
