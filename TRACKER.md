# LPRTestBench — Project Tracker

**Repo:** https://github.com/daltonloomis0818/LPRTestBench
**Purpose:** Professional-grade LPR camera testing and showcase tool for trade shows, sales demos, and engineering validation scenarios. Built to demonstrate and stress-test LPR systems like PatriotLPR.

---

## Current Phase: 0 — Project Setup & Architecture Planning

**Status:** In Progress

---

## Completed Phases

| Phase | Description | Status | Notes |
|-------|-------------|--------|-------|
| 0a | GitHub repo created | Done | Public repo, MIT license, Python .gitignore |

---

## In-Progress Tasks

- [ ] Produce full architectural plan for review
- [ ] Write README with setup/install/usage
- [ ] Create initial project scaffold (directories, empty modules)

---

## Next Steps Queue (Priority Order)

1. **Architecture Plan** — Full module-by-module design, data flow diagrams, dependency map
2. **Phase 1: Core Engine** — plate_renderer, plate_generator, effects, compositor, cache_engine
3. **Phase 2: Assets Mode** — SQLite registry, onboarding wizard, asset browser
4. **Phase 3: Templates Mode** — Template builder, browser, JSON persistence
5. **Phase 4: Libraries Mode** — Library builder, browser, template grouping
6. **Phase 5: Demo Mode** — Cache-driven display, session logging, export
7. **Phase 6: Polish** — Full-screen mode, keyboard shortcuts, error handling, edge cases

---

## Open Questions / Blockers

- None currently

---

## Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| Python | 3.12 | Runtime |
| Pillow | latest | Image processing, compositing |
| opencv-python | latest | Perspective warp (getPerspectiveTransform, warpPerspective) |
| cairosvg | latest | SVG plate rendering to PNG |
| numpy | latest | Effects math, noise generation |
| tkinter | stdlib | Desktop UI framework |
| sqlite3 | stdlib | Asset registry and session logs |
| threading/queue | stdlib | Cache engine background processing |

---

## Deviations from Spec

None yet.

---

**Last Updated:** 2026-03-18 — Initial project creation
