# LPRTestBench — Project Tracker

**Repo:** https://github.com/daltonloomis0818/LPRTestBench
**Purpose:** Professional-grade LPR camera testing and showcase tool for trade shows, sales demos, and engineering validation scenarios. Built to demonstrate and stress-test LPR systems like PatriotLPR.

---

## Current Phase: Full Implementation Complete — Needs Runtime Testing

**Status:** All code written, syntax-verified, ready for first launch

---

## Completed Phases

| Phase | Description | Status | Notes |
|-------|-------------|--------|-------|
| 0a | GitHub repo created | Done | Public repo, MIT license, Python .gitignore |
| 0b | Architecture plan | Done | Full module-by-module design reviewed and approved |
| 0c | README + TRACKER | Done | Setup instructions, project overview |
| 1 | Core Engine | Done | plate_renderer, plate_generator, compositor, effects, cache_engine |
| 2 | Assets Mode | Done | Onboarding wizard (4-corner mapping + preview), asset browser with filters, detail view, metadata edit, corner redo, file import |
| 3 | Templates Mode | Done | Template builder with live preview, browser with sort/filter/delete, edit existing templates |
| 4 | Libraries Mode | Done | Library builder with template picker/reorder, browser with launch/edit/duplicate/delete |
| 5 | Demo Mode | Done | Cache-driven display, auto-cycle with speed control, prev/next, fullscreen, export current/batch, session logging, vault write-back, keyboard shortcuts |
| 5a | Texas SVG Plate | Done | Full Texas standard plate with header, Lone Star, emboss filter, bolt holes, {{PLATE_TEXT}} variable |
| 5b | Plate list seed data | Done | 10 sample plates in data/plate_list.txt |

---

## In-Progress Tasks

- [ ] Install dependencies and first runtime test
- [ ] Drop a test vehicle PNG and run full onboarding flow
- [ ] Verify composite rendering pipeline end-to-end

---

## Next Steps Queue (Priority Order)

1. **Runtime Test** — `pip install -r requirements.txt` → `python main.py` → verify all 4 modes load
2. **End-to-End Test** — Drop a vehicle PNG, onboard it, create template, create library, run demo
3. **Bug Fixes** — Address any runtime issues found during testing
4. **Polish** — Error handling edge cases, window resize behavior, drag-and-drop file import refinement

---

## Open Questions / Blockers

- **cairosvg** requires Cairo system library — may need `pip install cairocffi` or system-level Cairo install on Windows
- Need at least one vehicle PNG to test the full pipeline

---

## Dependencies

| Package | Min Version | Purpose |
|---------|-------------|---------|
| Python | 3.12 | Runtime |
| Pillow | >=10.4.0 | Image processing, compositing |
| opencv-python | >=4.10.0 | Perspective warp (getPerspectiveTransform, warpPerspective) |
| cairosvg | >=2.7.1 | SVG plate rendering to PNG |
| numpy | >=1.26.0 | Effects math, noise generation |
| tkinter | stdlib | Desktop UI framework |
| sqlite3 | stdlib | Asset registry |
| threading/queue | stdlib | Cache engine background processing |

---

## Architecture Decisions

- **Normalized corners (0.0–1.0)** — Plate corner coordinates stored as ratios, not pixels. Compositor denormalizes at render time using actual image dimensions. Decouples from display resolution.
- **Library reorder via Up/Down buttons** — Not drag-and-drop. Simpler, no external Tkinter DnD dependencies, reliable.
- **Debounced live preview** — Template builder re-renders 500ms after last parameter change to avoid waste during slider drags.
- **Daemon cache thread** — Dies automatically when app closes. `threading.Event` for graceful stop on demo exit.
- **Catppuccin Mocha color scheme** — Dark theme using #1e1e2e background, #cdd6f4 text, accent colors from the palette.

---

## Deviations from Spec

- **Drop zone**: Implemented as "Import Vehicle" file picker button rather than drag-and-drop zone. Tkinter native DnD requires `tkdnd` extension which isn't reliably available. File picker achieves the same result.
- **Filmstrip preview in Library Builder**: Deferred to polish phase. Template list with names is functional; thumbnail filmstrip requires rendering all templates which is expensive for the builder.

---

## File Map

```
main.py                     — App shell, nav, mode router, startup init, DB setup
modes/assets_mode.py        — Asset browser, onboarding wizard, detail view, metadata edit
modes/templates_mode.py     — Template builder (live preview), browser, edit
modes/libraries_mode.py     — Library builder (template picker), browser, launch
modes/demo_mode.py          — Demo runner, cache display, controls, export, session log
engine/plate_renderer.py    — SVG load, {{PLATE_TEXT}} replace, cairosvg render, in-memory cache
engine/plate_generator.py   — Random/list/mixed plate gen, hard mode, repeat tracking
engine/compositor.py        — OpenCV perspective warp, plate-onto-vehicle compositing
engine/effects.py           — Lighting, weather, zoom, grain effects (all stateless)
engine/cache_engine.py      — Background thread, queue pool, vault check, prewarm
assets/plates/texas.svg     — Texas standard plate SVG template
data/plate_list.txt         — Sample plate list for list/mixed mode
```

---

**Last Updated:** 2026-03-18 — Full implementation complete, pending runtime testing
